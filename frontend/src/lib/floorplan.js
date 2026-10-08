// Draws the schematic floor plan. Used by the on-screen canvas AND the PDF
// report, so both always show the same drawing.

export const INK = '#0e1b26'
export const FLAG = '#ff5a1f'
const RULE = '#dfe5ea'
const RULE_STRONG = '#b8c3cc'
const SHEET = '#fafbfb'
const GRAPHITE = '#4a5966'

// Symbols are drawn in a local box centred on (0,0): [width, height] in px.
const SIZE = {
  chair: [15, 15],
  couch: [38, 17],
  'dining table': [34, 22],
  bed: [32, 24],
  'potted plant': [16, 16],
  tv: [28, 7],
  sink: [20, 14],
  refrigerator: [18, 20],
  bench: [30, 9],
  microwave: [18, 12],
  oven: [20, 18],
  toilet: [12, 18],
  clock: [14, 14],
}

function rr(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, r)
}

export function drawSymbol(ctx, cls, cx, cy, { active = false } = {}) {
  const [w, h] = SIZE[cls] ?? [14, 14]
  ctx.save()
  ctx.translate(cx, cy)
  ctx.lineWidth = active ? 2.2 : 1.5
  ctx.strokeStyle = INK
  ctx.fillStyle = active ? '#ffe4d9' : SHEET
  const x = -w / 2
  const y = -h / 2

  switch (cls) {
    case 'chair':
      rr(ctx, x, y, w, h, 2); ctx.fill(); ctx.stroke()
      ctx.lineWidth = 3.4; ctx.beginPath(); ctx.moveTo(x + 1, y + 1); ctx.lineTo(x + w - 1, y + 1); ctx.stroke()
      break
    case 'couch':
      rr(ctx, x, y, w, h, 3); ctx.fill(); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(x + 5, y); ctx.lineTo(x + 5, y + h); ctx.moveTo(x + w - 5, y); ctx.lineTo(x + w - 5, y + h); ctx.stroke()
      break
    case 'dining table':
      rr(ctx, x, y, w, h, 3); ctx.fill(); ctx.stroke()
      ctx.lineWidth = 0.9; rr(ctx, x + 4, y + 4, w - 8, h - 8, 1.5); ctx.stroke()
      break
    case 'bed':
      rr(ctx, x, y, w, h, 2); ctx.fill(); ctx.stroke()
      rr(ctx, x + 3, y + 3, w - 6, 6, 1.5); ctx.stroke()
      break
    case 'potted plant':
      ctx.beginPath(); ctx.arc(0, 0, w / 2, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
      ctx.lineWidth = 1; ctx.beginPath()
      for (let i = 0; i < 4; i++) { const a = (i * Math.PI) / 2 + Math.PI / 4; ctx.moveTo(0, 0); ctx.lineTo(Math.cos(a) * 5.5, Math.sin(a) * 5.5) }
      ctx.stroke()
      break
    case 'tv':
      rr(ctx, x, y, w, h, 1.5); ctx.fillStyle = INK; ctx.fill(); ctx.stroke()
      break
    case 'clock':
      ctx.beginPath(); ctx.arc(0, 0, w / 2, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
      ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -4); ctx.moveTo(0, 0); ctx.lineTo(3, 1); ctx.stroke()
      break
    case 'sink':
      rr(ctx, x, y, w, h, 2); ctx.fill(); ctx.stroke()
      ctx.beginPath(); ctx.ellipse(0, 1, 5.5, 3.5, 0, 0, Math.PI * 2); ctx.stroke()
      break
    case 'refrigerator':
      rr(ctx, x, y, w, h, 2); ctx.fill(); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(x, y + h * 0.38); ctx.lineTo(x + w, y + h * 0.38); ctx.stroke()
      break
    default:
      rr(ctx, x, y, w, h, 2); ctx.fill(); ctx.stroke()
  }
  ctx.restore()
}

function tick(ctx, x1, y1, x2, y2) {
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
}

/** Dimension line with end ticks and a centred label. */
function dimension(ctx, x1, y1, x2, y2, label, { vertical = false } = {}) {
  ctx.save()
  ctx.strokeStyle = GRAPHITE
  ctx.fillStyle = GRAPHITE
  ctx.lineWidth = 1
  tick(ctx, x1, y1, x2, y2)
  const d = 5
  if (vertical) { tick(ctx, x1 - d, y1, x1 + d, y1); tick(ctx, x2 - d, y2, x2 + d, y2) }
  else { tick(ctx, x1, y1 - d, x1, y1 + d); tick(ctx, x2, y2 - d, x2, y2 + d) }
  ctx.font = '500 11px "IBM Plex Mono", monospace'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  const mx = (x1 + x2) / 2
  const my = (y1 + y2) / 2
  const tw = ctx.measureText(label).width + 10
  ctx.save()
  ctx.translate(mx, my)
  if (vertical) ctx.rotate(-Math.PI / 2)
  ctx.fillStyle = SHEET
  ctx.fillRect(-tw / 2, -8, tw, 16)
  ctx.fillStyle = INK
  ctx.fillText(label, 0, 0.5)
  ctx.restore()
  ctx.restore()
}

/**
 * @param layout  real-world layout from the backend (metres), or null for the
 *                legacy camera-view mode.
 * @returns hit targets [{x, y, r, cls, confidence}] in canvas px, for tooltips.
 */
export function drawFloorPlan(ctx, W, H, { detections = [], rooms = [], layout = null, calibration = null, showHeatmap = false, hover = null } = {}) {
  ctx.clearRect(0, 0, W, H)
  ctx.fillStyle = SHEET
  ctx.fillRect(0, 0, W, H)

  // drafting grid
  for (let x = 0; x <= W; x += 20) {
    ctx.strokeStyle = x % 100 === 0 ? RULE_STRONG : RULE
    ctx.lineWidth = x % 100 === 0 ? 0.8 : 0.5
    tick(ctx, x + 0.5, 0, x + 0.5, H)
  }
  for (let y = 0; y <= H; y += 20) {
    ctx.strokeStyle = y % 100 === 0 ? RULE_STRONG : RULE
    ctx.lineWidth = y % 100 === 0 ? 0.8 : 0.5
    tick(ctx, 0, y + 0.5, W, y + 0.5)
  }

  const k = layout ? layout.scale_factor ?? 1 : 1
  const points = []
  for (const d of detections) {
    ;(d.positions ?? []).forEach((p, idx) => points.push({ x: p.x * k, z: p.z * k, cls: d.class, confidence: p.confidence, idx }))
  }
  const polygon = layout?.polygon ?? []
  const path = layout?.camera_path ?? []

  if (points.length === 0 && polygon.length === 0) {
    ctx.fillStyle = GRAPHITE
    ctx.font = '500 13px "IBM Plex Mono", monospace'
    ctx.textAlign = 'center'
    ctx.fillText('NO OBJECTS TO PLOT', W / 2, H / 2)
    return []
  }

  const padL = 92, padR = 40, padT = 92, padB = 56
  const xs = [...points.map((p) => p.x), ...polygon.map((p) => p[0])]
  const zs = [...points.map((p) => p.z), ...polygon.map((p) => p[1])]
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minZ = Math.min(...zs), maxZ = Math.max(...zs)
  const spanX = Math.max(maxX - minX, 0.08)
  const spanZ = Math.max(maxZ - minZ, 0.08)
  // Uniform scale keeps the layout's proportions honest.
  const scale = Math.min((W - padL - padR) / spanX, (H - padT - padB) / spanZ)
  const drawW = spanX * scale
  const drawH = spanZ * scale
  const ox = padL + (W - padL - padR - drawW) / 2
  const oy = padT + (H - padT - padB - drawH) / 2
  const toCanvas = (x, z) => [ox + (x - minX) * scale, oy + (z - minZ) * scale]

  // room outline from the reconstructed floor footprint
  if (polygon.length > 2) {
    ctx.save()
    ctx.beginPath()
    polygon.forEach(([x, z], i) => {
      const [cx, cy] = toCanvas(x, z)
      if (i === 0) ctx.moveTo(cx, cy)
      else ctx.lineTo(cx, cy)
    })
    ctx.closePath()
    ctx.fillStyle = 'rgba(14,27,38,0.04)'
    ctx.fill()
    ctx.lineWidth = 2.2
    ctx.strokeStyle = INK
    ctx.lineJoin = 'round'
    ctx.stroke()
    ctx.restore()
  }

  // where the phone walked
  if (path.length > 1) {
    ctx.save()
    ctx.setLineDash([2, 5])
    ctx.lineWidth = 1.2
    ctx.globalAlpha = 0.55
    ctx.strokeStyle = FLAG
    ctx.beginPath()
    path.forEach(([x, z], i) => {
      const [cx, cy] = toCanvas(x, z)
      if (i === 0) ctx.moveTo(cx, cy)
      else ctx.lineTo(cx, cy)
    })
    ctx.stroke()
    ctx.restore()
    ctx.globalAlpha = 1
    const [sx, sy] = toCanvas(path[0][0], path[0][1])
    ctx.fillStyle = FLAG
    ctx.beginPath(); ctx.arc(sx, sy, 4.5, 0, Math.PI * 2); ctx.fill()
    ctx.strokeStyle = INK; ctx.lineWidth = 1.2; ctx.stroke()
  }

  // density heatmap (same transform as the symbols, so the two always line up)
  if (showHeatmap) {
    for (const p of points) {
      const [cx, cy] = toCanvas(p.x, p.z)
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, 64)
      g.addColorStop(0, 'rgba(255,90,31,0.30)')
      g.addColorStop(1, 'rgba(255,90,31,0)')
      ctx.fillStyle = g
      ctx.fillRect(cx - 64, cy - 64, 128, 128)
    }
  }

  // zones
  ctx.font = '500 11px "IBM Plex Mono", monospace'
  rooms.forEach((room, i) => {
    const [x1, z1, x2, z2] = room.bounds
    const [a, b] = toCanvas(x1, z1)
    const [c, d] = toCanvas(x2, z2)
    const pad = 20
    const rx = Math.min(a, c) - pad, ry = Math.min(b, d) - pad
    const rw = Math.abs(c - a) + pad * 2, rh = Math.abs(d - b) + pad * 2
    ctx.save()
    ctx.fillStyle = 'rgba(14,27,38,0.035)'
    ctx.fillRect(rx, ry, rw, rh)
    ctx.setLineDash([7, 4])
    ctx.lineWidth = 1.6
    ctx.strokeStyle = INK
    ctx.strokeRect(rx, ry, rw, rh)
    ctx.restore()
    const label = `Z${i + 1} · ${room.objects} obj`
    const tw = ctx.measureText(label).width + 12
    ctx.fillStyle = INK
    ctx.fillRect(rx, ry - 18, tw, 18)
    ctx.fillStyle = '#fafbfb'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillText(label, rx + 6, ry - 8.5)
  })

  // overall extent dimensions
  const [x0, y0] = toCanvas(minX, minZ)
  const [x1d, y1d] = toCanvas(maxX, maxZ)
  let widthLabel, heightLabel, note
  if (layout) {
    const est = layout.source !== 'user'
    widthLabel = `${est ? '~' : ''}${layout.width_m.toFixed(1)} m`
    heightLabel = `${est ? '~' : ''}${layout.depth_m.toFixed(1)} m`
    note = est ? 'SCALE ESTIMATED FROM CAMERA HEIGHT' : 'SCALE FROM YOUR MEASUREMENT'
  } else {
    widthLabel = calibration?.width_m ? `${calibration.width_m.toFixed(1)} m` : 'uncalibrated'
    heightLabel = calibration?.height_m ? `${calibration.height_m.toFixed(1)} m` : 'uncalibrated'
    note = calibration ? 'SCALE: USER-CALIBRATED WIDTH' : 'SCHEMATIC · NOT TO SCALE'
  }
  // 56px clear of the extents so zone labels (which sit above their boxes) never touch it
  dimension(ctx, x0, y0 - 56, x1d, y0 - 56, widthLabel)
  dimension(ctx, x0 - 56, y0, x0 - 56, y1d, heightLabel, { vertical: true })

  // symbols
  const hits = []
  for (const p of points) {
    const [cx, cy] = toCanvas(p.x, p.z)
    const active = hover && hover.cls === p.cls && Math.abs(hover.x - cx) < 1 && Math.abs(hover.y - cy) < 1
    drawSymbol(ctx, p.cls, cx, cy, { active })
    hits.push({ x: cx, y: cy, r: 16, cls: p.cls, confidence: p.confidence, idx: p.idx })
  }

  // real scale bar (only when positions are in metres)
  if (layout) {
    const bar = [0.5, 1, 2, 5].find((m) => m * scale >= 60) ?? 5
    const bx = 20, by = H - 26
    ctx.strokeStyle = INK; ctx.lineWidth = 2
    tick(ctx, bx, by, bx + bar * scale, by)
    tick(ctx, bx, by - 5, bx, by + 5)
    tick(ctx, bx + bar * scale, by - 5, bx + bar * scale, by + 5)
    ctx.fillStyle = INK
    ctx.font = '500 11px "IBM Plex Mono", monospace'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'alphabetic'
    ctx.fillText(`${bar} m`, bx, by - 9)
  }

  ctx.fillStyle = GRAPHITE
  ctx.font = '500 10px "IBM Plex Mono", monospace'
  ctx.textAlign = 'right'
  ctx.textBaseline = 'alphabetic'
  ctx.fillText(note, W - 14, H - 14)

  return hits
}
