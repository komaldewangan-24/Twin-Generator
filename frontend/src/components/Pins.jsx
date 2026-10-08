import { useEffect, useRef } from 'react'
import { Vector3 } from 'three'
import { project } from '../lib/camera'

/**
 * Labels floating on objects in the 3D scene. Positions are updated every frame
 * straight on the DOM nodes (no React re-render), so they follow the camera smoothly.
 * Note: pins are not hidden behind walls or furniture.
 */
export default function Pins({ viewerRef, pins, onPick, selectedId }) {
  const overlay = useRef(null)
  const nodes = useRef({})

  useEffect(() => {
    let raf = 0
    const tmp = new Vector3()
    const tick = () => {
      const viewer = viewerRef.current
      const box = overlay.current
      if (viewer?.camera && box) {
        const { clientWidth: w, clientHeight: h } = box
        for (const pin of pins) {
          const el = nodes.current[pin.id]
          if (!el) continue
          const p = project(viewer, pin.world, w, h, tmp)
          if (p) {
            el.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -100%)`
            el.style.opacity = '1'
            el.style.pointerEvents = 'auto'
          } else {
            el.style.opacity = '0'
            el.style.pointerEvents = 'none'
          }
        }
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [pins, viewerRef])

  return (
    <div ref={overlay} className="pointer-events-none absolute inset-0 z-10 overflow-hidden">
      {pins.map((pin) => (
        <button
          key={pin.id}
          ref={(el) => { nodes.current[pin.id] = el }}
          onClick={() => onPick?.(pin)}
          className={`absolute left-0 top-0 flex items-center gap-1.5 whitespace-nowrap rounded-[3px] border px-2 py-1 font-mono text-[11px] font-medium uppercase tracking-wider opacity-0 shadow-lg transition-colors ${
            selectedId === pin.id ? 'border-flag bg-flag text-ink' : 'border-ink bg-sheet text-ink hover:bg-flag-soft'
          }`}
          style={{ willChange: 'transform' }}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-flag ring-2 ring-ink" aria-hidden />
          {pin.label}
        </button>
      ))}
    </div>
  )
}
