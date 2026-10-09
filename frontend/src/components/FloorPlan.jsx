import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { DEFAULT_VIEW, drawFloorPlan } from '../lib/floorplan'
import { classLabel, classSingular } from '../lib/format'
import ObjectGlyph from './ObjectGlyph'

const MIN_ZOOM = 0.6
const MAX_ZOOM = 8

function Toggle({ on, onClick, children }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={on}
      className={`rounded-full border px-3 py-1.5 text-[13px] font-semibold shadow-sm transition ${
        on ? 'border-ink bg-ink text-paper' : 'border-rule-strong bg-white/90 text-ink hover:border-ink'
      }`}
    >
      {children}
    </button>
  )
}

function RoundButton({ label, onClick, children }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className="grid h-9 w-9 place-items-center rounded-full border border-rule-strong bg-white/95 text-lg font-semibold text-ink shadow-sm transition hover:border-ink"
    >
      {children}
    </button>
  )
}

export default function FloorPlan({ analytics, detections, onSelect }) {
  const wrap = useRef(null)
  const canvas = useRef(null)
  const hits = useRef([])
  const drag = useRef(null)
  const [width, setWidth] = useState(0)
  const [view, setView] = useState(DEFAULT_VIEW)
  const [hover, setHover] = useState(null)
  const [selected, setSelected] = useState(null)
  const [showPath, setShowPath] = useState(false)
  const [showHeat, setShowHeat] = useState(false)
  const [showLabels, setShowLabels] = useState(false)

  const layout = analytics?.layout ?? null
  const height = width < 560 ? Math.round(width * 1.05) : Math.max(500, Math.round(width * 0.72))

  useEffect(() => {
    const el = wrap.current
    if (!el) return undefined
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

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
      layout,
      calibration: analytics?.area?.calibration ?? null,
      showHeatmap: showHeat,
      showPath,
      showLabels,
      view,
      hover,
      selected,
    })
  }, [analytics, detections, layout, showHeat, showPath, showLabels, view, hover, selected, width, height])

  const zoomTo = useCallback((factor, cx = width / 2, cy = height / 2) => {
    setView((v) => {
      const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, v.k * factor))
      const r = k / v.k
      return { k, tx: cx - (cx - v.tx) * r, ty: cy - (cy - v.ty) * r }   // keep the point under the cursor fixed
    })
  }, [width, height])

  // Wheel needs a non-passive listener so the page does not scroll while zooming the plan.
  useEffect(() => {
    const c = canvas.current
    if (!c || !layout) return undefined
    const onWheel = (e) => {
      // Plain scrolling must still scroll the page; zoom needs Ctrl/Cmd (a trackpad pinch sends it too).
      if (!(e.ctrlKey || e.metaKey)) return
      e.preventDefault()
      const rect = c.getBoundingClientRect()
      zoomTo(Math.exp(-e.deltaY * 0.0015), e.clientX - rect.left, e.clientY - rect.top)
    }
    c.addEventListener('wheel', onWheel, { passive: false })
    return () => c.removeEventListener('wheel', onWheel)
  }, [zoomTo, layout])

  const pointer = (e) => {
    const rect = canvas.current.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }
  const hitAt = ({ x, y }) => hits.current.find((h) => Math.hypot(h.x - x, h.y - y) < h.r)

  const onPointerDown = (e) => {
    canvas.current.setPointerCapture(e.pointerId)
    const p = pointer(e)
    drag.current = { x: p.x, y: p.y, tx: view.tx, ty: view.ty, moved: false }
  }
  const onPointerMove = (e) => {
    const p = pointer(e)
    const d = drag.current
    if (d && layout) {
      const dx = p.x - d.x
      const dy = p.y - d.y
      if (Math.abs(dx) + Math.abs(dy) > 4) d.moved = true
      if (d.moved) setView((v) => ({ ...v, tx: d.tx + dx, ty: d.ty + dy }))
      return
    }
    const h = hitAt(p)
    setHover((prev) => (h ? (prev && prev.cls === h.cls && prev.idx === h.idx ? prev : { cls: h.cls, idx: h.idx }) : prev ? null : prev))
  }
  const onPointerUp = (e) => {
    const d = drag.current
    drag.current = null
    if (d && !d.moved) {
      const h = hitAt(pointer(e))
      setSelected(h ? { cls: h.cls, idx: h.idx } : null)
    }
  }

  const counts = useMemo(() => (detections ?? []).map((d) => ({ cls: d.class, count: d.count })), [detections])
  const chosen = useMemo(() => {
    if (!selected) return null
    const d = (detections ?? []).find((x) => x.class === selected.cls)
    const p = d?.positions?.[selected.idx]
    if (!p) return null
    const fac = layout?.scale_factor ?? 1
    return { cls: selected.cls, idx: selected.idx, confidence: p.confidence, votes: p.votes, x: p.x * fac, z: p.z * fac, total: d.count }
  }, [selected, detections, layout])

  return (
    <div>
      <div ref={wrap} className="relative overflow-hidden rounded-[3px] border border-ink bg-[#eef2f5]">
        <canvas
          ref={canvas}
          style={{ width: '100%', height, touchAction: 'none' }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={() => { setHover(null); drag.current = null }}
          onDoubleClick={() => setView(DEFAULT_VIEW)}
          role="img"
          aria-label="Floor plan of the scanned room with the detected furniture"
          className={`block ${layout ? (drag.current?.moved ? 'cursor-grabbing' : hover ? 'cursor-pointer' : 'cursor-grab') : hover ? 'cursor-pointer' : ''}`}
        />

        <div className="absolute left-3 top-3 flex flex-wrap gap-2">
          {layout?.camera_path?.length > 1 && <Toggle on={showPath} onClick={() => setShowPath((v) => !v)}>Camera path</Toggle>}
          <Toggle on={showHeat} onClick={() => setShowHeat((v) => !v)}>Density</Toggle>
          <Toggle on={showLabels} onClick={() => setShowLabels((v) => !v)}>Names</Toggle>
        </div>

        {layout && (
          <div className="absolute bottom-14 right-3 flex flex-col gap-2">
            <RoundButton label="Zoom in" onClick={() => zoomTo(1.4)}>+</RoundButton>
            <RoundButton label="Zoom out" onClick={() => zoomTo(1 / 1.4)}>−</RoundButton>
            <RoundButton label="Fit the room" onClick={() => setView(DEFAULT_VIEW)}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M2 6V2h4M14 6V2h-4M2 10v4h4M14 10v4h-4" /></svg>
            </RoundButton>
          </div>
        )}

        {chosen && (
          <div className="absolute right-3 top-3 w-60 rounded-[6px] border border-ink bg-white p-4 shadow-[0_12px_30px_-12px_rgba(14,27,38,0.45)]" role="dialog" aria-label="Selected object">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <span className="grid h-9 w-9 place-items-center rounded-[4px] border border-rule-strong bg-sheet"><ObjectGlyph cls={chosen.cls} size={24} /></span>
                <div>
                  <p className="font-display text-lg font-semibold leading-tight">{classSingular(chosen.cls)}</p>
                  {chosen.total > 1 && <p className="label !text-[10px]">{chosen.idx + 1} of {chosen.total}</p>}
                </div>
              </div>
              <button onClick={() => setSelected(null)} aria-label="Close" className="-mr-1 -mt-1 grid h-7 w-7 place-items-center rounded-full text-graphite hover:bg-sheet hover:text-ink">×</button>
            </div>
            <dl className="mt-3 space-y-1.5 text-sm">
              <div className="flex justify-between"><dt className="text-graphite">Confidence</dt><dd className="figure">{Math.round(chosen.confidence * 100)}%</dd></div>
              {chosen.votes != null && <div className="flex justify-between"><dt className="text-graphite">Seen in</dt><dd className="figure">{chosen.votes} frames</dd></div>}
              {layout && <div className="flex justify-between"><dt className="text-graphite">Position</dt><dd className="figure">{chosen.x.toFixed(1)}, {chosen.z.toFixed(1)} m</dd></div>}
            </dl>
            {onSelect && (
              <button onClick={() => onSelect(chosen.cls, chosen.idx)} className="btn btn-ink mt-3 w-full !py-2">Show in 3D</button>
            )}
          </div>
        )}
      </div>

      <ul className="mt-3 flex flex-wrap gap-2" aria-label="Legend">
        {counts.map(({ cls, count }) => (
          <li key={cls} className="flex items-center gap-1.5 rounded-full border border-rule-strong bg-white py-1 pl-1.5 pr-3 text-sm">
            <ObjectGlyph cls={cls} size={20} />
            <span className="font-semibold">{classLabel(cls)}</span>
            <span className="figure text-graphite">{count}</span>
          </li>
        ))}
        {layout && <li className="flex items-center px-1 text-sm text-graphite">Drag to move · Ctrl or ⌘ + scroll to zoom · double-click to fit</li>}
      </ul>
    </div>
  )
}
