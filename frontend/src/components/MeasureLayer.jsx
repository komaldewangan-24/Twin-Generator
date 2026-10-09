import { useEffect, useRef } from 'react'
import { Vector3 } from 'three'
import { dist, formatLength } from '../lib/measure'
import { project } from '../lib/camera'

const FLAG = '#ff5a1f'
const INK = '#0b141c'

function Dot({ nodeRef }) {
  return (
    <g ref={nodeRef} style={{ display: 'none' }}>
      <circle r="6.5" fill={FLAG} stroke={INK} strokeWidth="2" />
      <circle r="2" fill="#fff" />
    </g>
  )
}

/** One measurement. Its nodes are registered so the frame loop can move them without re-rendering. */
function Segment({ id, text, dim, registry }) {
  const refs = useRef({})
  useEffect(() => {
    registry.current[id] = refs.current
    return () => { delete registry.current[id] }
  }, [id, registry])
  const set = (key) => (el) => { refs.current[key] = el }
  return (
    <g ref={set('root')} style={{ display: 'none' }} opacity={dim ? 0.5 : 1}>
      <line ref={set('casing')} stroke={INK} strokeWidth="5" strokeLinecap="round" opacity="0.65" />
      <line ref={set('line')} stroke={FLAG} strokeWidth="2" strokeLinecap="round" />
      <Dot nodeRef={set('a')} />
      <Dot nodeRef={set('b')} />
      <g ref={set('label')}>
        <text textAnchor="middle" fontFamily="IBM Plex Mono, monospace" fontSize="13" fontWeight="600" fill="#fff" stroke={INK} strokeWidth="4" paintOrder="stroke">
          {text}
        </text>
      </g>
    </g>
  )
}

/**
 * Measurements drawn over the 3D view, plus the click handling that makes them.
 * `surface` is {camera, canvas, pick(clientX, clientY) -> [x, y, z] | null, pauseClicks?()} from
 * whichever viewer is showing. End points and lines follow the camera: they are moved straight on
 * the SVG nodes every frame (no React re-render), like the object labels.
 */
export default function MeasureLayer({ surface, active, items, pending, metersPerUnit, estimated, selectedId, onPick }) {
  const box = useRef(null)
  const registry = useRef({})
  const pendingNode = useRef(null)
  const pick = useRef(onPick)
  pick.current = onPick

  // Clicks. A drag is the user orbiting, so only a quick, still press counts as a point.
  useEffect(() => {
    const el = surface?.canvas
    if (!active || !el) return undefined
    const resume = surface.pauseClicks?.()
    el.style.cursor = 'crosshair'
    let down = null
    const onDown = (e) => {
      if (e.button === 0) down = { x: e.clientX, y: e.clientY, t: performance.now() }
    }
    const onUp = (e) => {
      const d = down
      down = null
      if (!d || Math.abs(e.clientX - d.x) + Math.abs(e.clientY - d.y) > 6 || performance.now() - d.t > 600) return
      const p = surface.pick(e.clientX, e.clientY)
      if (p) pick.current?.(p)
    }
    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointerup', onUp)
    return () => {
      el.removeEventListener('pointerdown', onDown)
      el.removeEventListener('pointerup', onUp)
      el.style.cursor = ''
      resume?.()
    }
  }, [active, surface])

  // Follow the camera.
  useEffect(() => {
    let raf = 0
    const tmp = new Vector3()
    const move = (node, p, dy = 0) => node?.setAttribute('transform', `translate(${p.x} ${p.y + dy})`)
    const tick = () => {
      const w = box.current?.clientWidth
      const h = box.current?.clientHeight
      if (surface?.camera && w) {
        const at = (world) => project(surface, world, w, h, tmp)
        for (const it of items) {
          const n = registry.current[it.id]
          if (!n?.root) continue
          const a = at(it.a)
          const b = a && at(it.b)
          n.root.style.display = a && b ? '' : 'none'
          if (!a || !b) continue
          for (const line of [n.casing, n.line]) {
            line.setAttribute('x1', a.x); line.setAttribute('y1', a.y)
            line.setAttribute('x2', b.x); line.setAttribute('y2', b.y)
          }
          for (const [node, p] of [[n.a, a], [n.b, b]]) {
            move(node, p)
            node.style.display = ''
          }
          move(n.label, { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, -12)
        }
        const node = pendingNode.current
        if (node) {
          const p = pending ? at(pending) : null
          if (p) { move(node, p); node.style.display = '' } else node.style.display = 'none'
        }
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [surface, items, pending])

  return (
    <svg ref={box} className="pointer-events-none absolute inset-0 z-10 h-full w-full overflow-visible" aria-hidden>
      {items.map((it) => (
        <Segment
          key={it.id}
          id={it.id}
          registry={registry}
          dim={!!selectedId && selectedId !== it.id}
          text={`${estimated ? '≈ ' : ''}${formatLength(dist(it.a, it.b) * metersPerUnit)}`}
        />
      ))}
      {pending && <Dot nodeRef={pendingNode} />}
    </svg>
  )
}
