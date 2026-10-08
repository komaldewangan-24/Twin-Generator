import { useEffect, useRef } from 'react'

const CLASS_COLORS = {
  chair: '#f87171',
  couch: '#60a5fa',
  'dining table': '#fbbf24',
  bed: '#a78bfa',
  'potted plant': '#4ade80',
  tv: '#f472b6',
  sink: '#38bdf8',
  refrigerator: '#94a3b8',
  bench: '#fb923c',
  clock: '#22d3ee',
}

function colorFor(cls) {
  return CLASS_COLORS[cls] ?? '#cbd5e1'
}

export default function FloorPlan({ analytics, detections, showHeatmap = false }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width
    const H = canvas.height
    const pad = 48
    ctx.clearRect(0, 0, W, H)

    const positions = []
    for (const d of detections || []) {
      for (const p of d.positions || []) {
        positions.push({ x: p.x, z: p.z, cls: d.class })
      }
    }
    const rooms = analytics?.rooms?.details || []
    const allXs = [...positions.map((p) => p.x), ...[].concat(...rooms.map((r) => [r.bounds[0], r.bounds[2]]))]
    const allZs = [...positions.map((p) => p.z), ...[].concat(...rooms.map((r) => [r.bounds[1], r.bounds[3]]))]
    if (allXs.length === 0) {
      ctx.fillStyle = '#475569'
      ctx.font = '16px sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('No objects detected to plot', W / 2, H / 2)
      return
    }

    const minX = Math.min(...allXs)
    const maxX = Math.max(...allXs)
    const minZ = Math.min(...allZs)
    const maxZ = Math.max(...allZs)
    const spanX = Math.max(maxX - minX, 0.01)
    const spanZ = Math.max(maxZ - minZ, 0.01)
    const scale = Math.min((W - pad * 2) / spanX, (H - pad * 2) / spanZ)
    const toCanvas = (x, z) => [
      pad + (x - minX) * scale,
      pad + (H - pad * 2) - (z - minZ) * scale,
    ]

    // grid
    ctx.strokeStyle = '#1e293b'
    ctx.lineWidth = 1
    for (let i = 0; i <= 10; i++) {
      const gx = pad + (i / 10) * (W - pad * 2)
      const gy = pad + (i / 10) * (H - pad * 2)
      ctx.beginPath()
      ctx.moveTo(gx, pad)
      ctx.lineTo(gx, H - pad)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(pad, gy)
      ctx.lineTo(W - pad, gy)
      ctx.stroke()
    }

    // room boundaries
    rooms.forEach((room, i) => {
      const [x1, z1, x2, z2] = room.bounds
      const [a, b] = toCanvas(x1, z1)
      const [c, d] = toCanvas(x2, z2)
      ctx.strokeStyle = '#34d399'
      ctx.lineWidth = 2
      ctx.setLineDash([6, 4])
      ctx.strokeRect(a, Math.min(b, d), Math.abs(c - a), Math.abs(b - d))
      ctx.setLineDash([])
      ctx.fillStyle = '#34d399'
      ctx.font = 'bold 12px sans-serif'
      ctx.fillText(`R${i + 1}`, a + 6, d - 6)
    })

    // heatmap: density by count in grid cells
    if (showHeatmap && positions.length > 0) {
      const cells = 12
      const grid = Array.from({ length: cells }, () => Array(cells).fill(0))
      for (const p of positions) {
        const gx = Math.min(cells - 1, Math.floor(((p.x - minX) / spanX) * cells))
        const gz = Math.min(cells - 1, Math.floor(((p.z - minZ) / spanZ) * cells))
        grid[gz][gx]++
      }
      const maxCount = Math.max(1, ...grid.flat())
      for (let gz = 0; gz < cells; gz++) {
        for (let gx = 0; gx < cells; gx++) {
          if (grid[gz][gx] === 0) continue
          const alpha = 0.15 + 0.5 * (grid[gz][gx] / maxCount)
          const cx = pad + (gx / cells) * (W - pad * 2)
          const cz = pad + (gz / cells) * (H - pad * 2)
          ctx.fillStyle = `rgba(248,113,113,${alpha})`
          ctx.fillRect(cx, cz, (W - pad * 2) / cells + 1, (H - pad * 2) / cells + 1)
        }
      }
    }

    // objects
    for (const p of positions) {
      const [cx, cy] = toCanvas(p.x, p.z)
      ctx.beginPath()
      ctx.arc(cx, cy, 7, 0, Math.PI * 2)
      ctx.fillStyle = colorFor(p.cls)
      ctx.fill()
      ctx.strokeStyle = 'rgba(15,23,42,0.8)'
      ctx.lineWidth = 1.5
      ctx.stroke()
    }

    // legend
    const legend = [...new Set(positions.map((p) => p.cls))]
    let lx = 8
    const ly = H - 14
    for (const cls of legend.slice(0, 12)) {
      ctx.fillStyle = colorFor(cls)
      ctx.beginPath()
      ctx.arc(lx + 4, ly, 4, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = '#94a3b8'
      ctx.font = '10px sans-serif'
      ctx.textAlign = 'left'
      ctx.fillText(cls, lx + 10, ly + 3)
      lx += 10 + ctx.measureText(cls).width + 12
    }
  }, [analytics, detections, showHeatmap])

  return <canvas ref={canvasRef} width={640} height={520} className="w-full rounded-xl bg-slate-950" />
}