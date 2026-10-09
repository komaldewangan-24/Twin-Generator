// Measuring in the 3D view: pick a point on the model, turn distances into metres.
import { Vector4 } from 'three'

/** Straight-line distance between two [x, y, z] points, in the model's own units. */
export const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])

export function formatLength(metres) {
  if (!Number.isFinite(metres)) return '–'
  if (metres < 1) return `${Math.round(metres * 100)} cm`
  return `${metres.toFixed(metres < 10 ? 2 : 1)} m`
}

const UNITS = { mm: 0.001, cm: 0.01, m: 1, in: 0.0254, '"': 0.0254, ft: 0.3048, "'": 0.3048 }

/** "2.1", "210 cm", "7 ft" -> metres; null when it is not a sensible length. */
export function parseLength(text) {
  const m = String(text ?? '').trim().toLowerCase().replace(',', '.').match(/^(\d*\.?\d+)\s*(mm|cm|m|in|ft|"|')?$/)
  if (!m) return null
  const metres = parseFloat(m[1]) * UNITS[m[2] ?? 'm']
  return metres > 0 && metres <= 100 ? metres : null
}

const color = new Vector4()

/**
 * The 3D point under a screen position in the Gaussian-splat viewer.
 *
 * A ray touches many translucent splats, nearest first, including faint floaters in front of the
 * real surface. Like the renderer does, walk them front to back and stop where they add up to
 * mostly opaque: that is the surface the person sees and means. The few hits right around that
 * depth are averaged so the point does not sit on one noisy splat.
 */
export function pickSplat(viewer, clientX, clientY) {
  const canvas = viewer?.renderer?.domElement
  const mesh = viewer?.getSplatMesh?.()
  if (!canvas || !mesh || !viewer.raycaster) return null
  const rect = canvas.getBoundingClientRect()
  const hits = []
  viewer.raycaster.setFromCameraAndScreenPosition(
    viewer.camera,
    { x: clientX - rect.left, y: clientY - rect.top },
    { x: rect.width, y: rect.height },
  )
  viewer.raycaster.intersectSplatMesh(mesh, hits)
  if (!hits.length) return null

  const alpha = hits.map((h) => {
    mesh.getSplatColor(h.splatIndex, color)
    return color.w / 255
  })
  let seen = 1
  let at = -1
  for (let i = 0; i < hits.length; i++) {
    seen *= 1 - alpha[i]
    if (seen <= 0.5) { at = i; break }
  }
  if (at < 0) {
    // a sparse patch that never adds up: take its most solid splat, unless even that is just haze
    at = alpha.indexOf(Math.max(...alpha))
    if (alpha[at] < 0.1) return null
  }
  const near = hits.filter((h) => Math.abs(h.distance - hits[at].distance) <= hits[at].distance * 0.02)
  const p = [0, 0, 0]
  for (const h of near) {
    p[0] += h.origin.x; p[1] += h.origin.y; p[2] += h.origin.z
  }
  return p.map((v) => v / near.length)
}
