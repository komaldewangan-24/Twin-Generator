import { useEffect, useRef, useState } from 'react'
import { drawFloorPlan } from '../lib/floorplan'
import { classSingular } from '../lib/format'
import ObjectGlyph from './ObjectGlyph'

export default function FloorPlan({ analytics, detections, showHeatmap = false, onSelect }) {
  const wrap = useRef(null)
  const canvas = useRef(null)
  const hits = useRef([])
  const [width, setWidth] = useState(0)
  const [hover, setHover] = useState(null)

  useEffect(() => {
    const el = wrap.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const height = width < 560 ? Math.round(width * 1.15) : Math.max(360, Math.round(width * 0.68))

  useEffect(() => {
    const c = canvas.current
    if (!c || !width) return
    const dpr = window.devicePixelRatio || 1
    c.width = width * dpr
    c.height = height * dpr
    const ctx = c.getContext('2d')
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    hits.current = drawFloorPlan(ctx, width, height, {
      detections,
      rooms: analytics?.rooms?.details ?? [],
      layout: analytics?.layout ?? null,
      calibration: analytics?.area?.calibration ?? null,
      showHeatmap,
      hover,
    })
  }, [analytics, detections, showHeatmap, width, height, hover])

  const onMove = (e) => {
    const rect = canvas.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const h = hits.current.find((p) => Math.hypot(p.x - x, p.y - y) < p.r)
    setHover((prev) => (h ? (prev && prev.x === h.x && prev.y === h.y ? prev : h) : prev ? null : prev))
  }

  const present = [...new Set((detections ?? []).map((d) => d.class))]

  return (
    <div>
      <div ref={wrap} className="relative overflow-hidden rounded-[3px] border border-ink">
        <canvas
          ref={canvas}
          style={{ width: '100%', height }}
          onMouseMove={onMove}
          onClick={() => hover && onSelect?.(hover.cls, hover.idx)}
          onMouseLeave={() => setHover(null)}
          role="img"
          aria-label="Schematic floor plan of the detected furniture"
          className={`block ${hover && onSelect ? 'cursor-pointer' : ''}`}
        />
        {hover && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-[3px] bg-ink px-2.5 py-1.5 text-paper shadow-lg"
            style={{ left: Math.min(Math.max(hover.x, 70), width - 70), top: hover.y - 14 }}
          >
            <p className="text-sm font-semibold">{classSingular(hover.cls)}</p>
            <p className="figure text-[11px] text-[#9db0be]">confidence {Math.round(hover.confidence * 100)}%</p>
            {onSelect && <p className="figure text-[11px] text-flag">click to show in 3D</p>}
          </div>
        )}
      </div>

      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2" aria-label="Legend">
        {present.map((c) => (
          <li key={c} className="flex items-center gap-1.5 text-sm text-graphite">
            <ObjectGlyph cls={c} size={20} /> {classSingular(c)}
          </li>
        ))}
        <li className="flex items-center gap-1.5 text-sm text-graphite">
          <svg width="22" height="10" aria-hidden><rect x="1" y="1" width="20" height="8" fill="none" stroke="#0e1b26" strokeWidth="1.5" strokeDasharray="4 3" /></svg>
          Zone
        </li>
        {analytics?.layout && (
          <li className="flex items-center gap-1.5 text-sm text-graphite">
            <svg width="22" height="10" aria-hidden><path d="M1 5h20" stroke="#ff5a1f" strokeWidth="1.6" strokeDasharray="2 4" /></svg>
            Camera path
          </li>
        )}
      </ul>
    </div>
  )
}
