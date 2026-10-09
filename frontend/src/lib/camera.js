// Camera moves for the 3D viewer: fly to an object, replay the filmed walk.
import { Vector3 } from 'three'

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)

/** Run `step(progress 0..1)` over `ms`. Returns a function that cancels it. */
function animate(ms, step, done) {
  let raf = 0
  let cancelled = false
  const start = performance.now()
  const tick = (now) => {
    if (cancelled) return
    const t = Math.min(1, (now - start) / ms)
    step(t)
    if (t < 1) raf = requestAnimationFrame(tick)
    else done?.()
  }
  raf = requestAnimationFrame(tick)
  return () => {
    cancelled = true
    cancelAnimationFrame(raf)
  }
}

/**
 * The viewer only re-sorts its splats after a big camera move (over ~8 degrees or 1 unit).
 * When we place the camera ourselves a small move leaves the old sort in use, and while the sorting
 * worker is still starting up a request can be dropped without any error, which leaves the first
 * frames blank (worst on slow GPUs and just after a page load). So ask again until a sort has
 * really finished since we placed the camera, then once more to be sure.
 */
export function refreshSort(viewer) {
  if (!viewer?.runSplatSort) return
  let finished = 0
  let tries = 0
  let waiting = false
  const attempt = () => {
    try {
      if (viewer.isDisposingOrDisposed?.() || tries++ > 40) return
      if (!viewer.sortRunning) {
        if (!waiting) {
          waiting = true
          viewer.runAfterNextSort?.push(() => { waiting = false; finished += 1 })
        }
        viewer.runSplatSort(true, true)
        viewer.forceRenderNextFrame?.()
      }
    } catch {
      return // viewer was disposed
    }
    if (finished < 2) setTimeout(attempt, finished ? 1200 : 400)
  }
  attempt()
}

function look(viewer, position, target) {
  viewer.camera.position.copy(position)
  viewer.controls.target.copy(target)
  viewer.camera.lookAt(target)
  viewer.controls.update()
}

/** Glide the camera to look at a 3D point from about 1.6 m away, from the side you are already on. */
export function flyToObject(viewer, world, up, unitsPerMeter, done) {
  if (!viewer?.controls) return () => {}
  const target = new Vector3(...world)
  const upV = new Vector3(...up).normalize()
  const away = viewer.camera.position.clone().sub(target)
  away.addScaledVector(upV, -away.dot(upV)) // keep it horizontal
  if (away.lengthSq() < 1e-9) away.set(1, 0, 0).addScaledVector(upV, -upV.x)
  away.normalize()
  const dist = 1.6 * unitsPerMeter
  const endPos = target.clone().addScaledVector(away, dist).addScaledVector(upV, 0.35 * unitsPerMeter)

  const fromPos = viewer.camera.position.clone()
  const fromTarget = viewer.controls.target.clone()
  const pos = new Vector3()
  const tgt = new Vector3()
  return animate(1000, (t) => {
    const e = ease(t)
    pos.lerpVectors(fromPos, endPos, e)
    tgt.lerpVectors(fromTarget, target, e)
    look(viewer, pos, tgt)
  }, () => { refreshSort(viewer); done?.() })
}

const SEGMENT_MS = 900

/** How long playTour takes for these poses, in milliseconds. */
export const tourDuration = (poses) => SEGMENT_MS * Math.max(0, (poses?.length ?? 0) - 1)

/** Replay the walk: glide through the real camera poses in the order they were filmed. */
export function playTour(viewer, poses, unitsPerMeter, onEnd) {
  if (!viewer?.controls || !poses?.length) return () => {}
  const smooth = poses.map((p, i) => {
    // light moving average removes hand shake
    const a = poses[Math.max(0, i - 1)], b = p, c = poses[Math.min(poses.length - 1, i + 1)]
    const pos = new Vector3(...a.position).add(new Vector3(...b.position).multiplyScalar(2)).add(new Vector3(...c.position)).multiplyScalar(0.25)
    const fwd = new Vector3(...a.forward).add(new Vector3(...b.forward).multiplyScalar(2)).add(new Vector3(...c.forward)).normalize()
    return { pos, fwd }
  })
  const lookAhead = 1.2 * unitsPerMeter
  const pos = new Vector3()
  const fwd = new Vector3()
  const tgt = new Vector3()
  return animate(SEGMENT_MS * (smooth.length - 1), (t) => {
    const f = t * (smooth.length - 1)
    const i = Math.min(smooth.length - 2, Math.floor(f))
    const k = f - i
    pos.lerpVectors(smooth[i].pos, smooth[i + 1].pos, k)
    fwd.lerpVectors(smooth[i].fwd, smooth[i + 1].fwd, k).normalize()
    tgt.copy(pos).addScaledVector(fwd, lookAhead)
    look(viewer, pos, tgt)
  }, () => { refreshSort(viewer); onEnd?.() })
}

/** Screen position of a 3D point, or null when it is behind the camera. */
export function project(viewer, world, width, height, out = new Vector3()) {
  out.set(world[0], world[1], world[2]).project(viewer.camera)
  if (out.z > 1 || out.z < -1 || Math.abs(out.x) > 1.2 || Math.abs(out.y) > 1.2) return null
  return { x: ((out.x + 1) / 2) * width, y: ((1 - out.y) / 2) * height }
}
