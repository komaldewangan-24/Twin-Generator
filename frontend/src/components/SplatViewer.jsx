import { useEffect, useRef, useState } from 'react'
import { Vector3 } from 'three'
import { refreshSort } from '../lib/camera'

/** Which axis points "up" differs between splat trainers, so the viewer lets the user pick. */
export const ORIENTATIONS = [
  { id: 'y-down', label: 'Y down', up: [0, -1, 0] },
  { id: 'y-up', label: 'Y up', up: [0, 1, 0] },
  { id: 'z-up', label: 'Z up', up: [0, 0, 1] },
]

const median = (a) => {
  const b = Float32Array.from(a).sort()
  return b[Math.floor(b.length / 2)]
}

/**
 * Robust bounds: real scans have floaters far outside the room, so the library's
 * own centre/radius (mean and max) are pulled way out. Use the median centre and
 * a percentile radius of a sample of splats instead.
 */
function sceneBounds(mesh) {
  const total = mesh.getSplatCount()
  const step = Math.max(1, Math.floor(total / 20000))
  const p = new Vector3()
  const xs = []; const ys = []; const zs = []
  for (let i = 0; i < total; i += step) {
    mesh.getSplatCenter(i, p)
    xs.push(p.x); ys.push(p.y); zs.push(p.z)
  }
  const center = new Vector3(median(xs), median(ys), median(zs))
  const d = xs.map((x, i) => Math.hypot(x - center.x, ys[i] - center.y, zs[i] - center.z)).sort((a, b) => a - b)
  return { center, radius: Math.max(d[Math.floor(d.length * 0.8)], 0.25) }
}

/** Put the camera at a pleasant 3/4 view that fits the room, whatever its size or position. */
export function frameScene(viewer, upArr, startView) {
  const mesh = viewer?.getSplatMesh?.()
  if (!mesh || !viewer.controls) return
  const { center: c, radius: r } = sceneBounds(mesh)
  if (startView) {
    // Stand where the phone stood and look where it looked: the first view is
    // then as sharp as one of the original video frames.
    const pos = new Vector3(...startView.position)
    const fwd = new Vector3(...startView.forward).normalize()
    viewer.camera.position.copy(pos)
    viewer.controls.target.copy(pos).addScaledVector(fwd, r * 0.6)
    viewer.camera.lookAt(viewer.controls.target)
    viewer.controls.update()
    refreshSort(viewer)
    return
  }
  const up = new Vector3(...upArr).normalize()
  const helper = Math.abs(up.x) > 0.9 ? new Vector3(0, 0, 1) : new Vector3(1, 0, 0)
  const side = new Vector3().crossVectors(up, helper).normalize()
  const side2 = new Vector3().crossVectors(up, side).normalize()
  // Camera sits inside/near the room, like a person standing in it, looking across.
  viewer.camera.position.copy(c).addScaledVector(side, r * 0.9).addScaledVector(side2, r * 0.9).addScaledVector(up, r * 0.15)
  viewer.controls.target.copy(c)
  viewer.camera.lookAt(c)
  viewer.controls.update()
  refreshSort(viewer)
}

const NO_WEBGL2 = 'webgl2-unavailable'

export default function SplatViewer({ url, ext, up = ORIENTATIONS[0].up, startView, onLoad, onError }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  // Keep callbacks in refs so they don't retrigger the viewer effect.
  const onLoadRef = useRef(onLoad)
  const onErrorRef = useRef(onError)
  onLoadRef.current = onLoad
  onErrorRef.current = onError

  // `up` and `startView` arrive as fresh arrays/objects whenever the scan data is re-fetched. Rebuilding
  // the viewer for an identical value would throw away the loaded model (and break a running walkthrough
  // or recording), so the effect depends on their values, not their identity.
  const upKey = up.join()
  const startKey = JSON.stringify(startView ?? null)
  const latest = useRef({})
  latest.current = { up, startView }

  useEffect(() => {
    if (!url) return
    let cancelled = false
    const { up, startView } = latest.current

    const init = async () => {
      try {
        setStatus('loading')
        setError(null)

        // Without WebGL2 (graphics acceleration off, or a blocked GPU) nothing can be drawn.
        const probe = document.createElement('canvas').getContext('webgl2')
        if (!probe) throw new Error(NO_WEBGL2)

        const GaussianSplats3D = await import('@mkkellogg/gaussian-splats-3d')
        if (cancelled || !containerRef.current) return

        const viewer = new GaussianSplats3D.Viewer({
          // The library appends its own renderer canvas here and manages
          // resizing internally via a ResizeObserver.
          rootElement: containerRef.current,
          // Without COOP/COEP headers (Vite dev does not send them) there is no
          // SharedArrayBuffer, so the default `sharedMemoryForWorkers: true`
          // leaves the splat sorter worker broken and nothing ever renders.
          sharedMemoryForWorkers: false,
          cameraUp: up,
          // The default reveals the model with a fade that needs a stream of rendered frames. Where frames
          // are throttled (a background tab, a slow GPU) it stalls half-way and the view stays blank.
          sceneRevealMode: GaussianSplats3D.SceneRevealMode.Instant,
        })
        viewerRef.current = viewer

        // The signed URL has no usable file extension, so name the format explicitly.
        const format = ext === '.splat' ? GaussianSplats3D.SceneFormat.Splat : GaussianSplats3D.SceneFormat.Ply
        await viewer.addSplatScene(url, {
          format,
          splatAlphaRemovalThreshold: 5,
          showLoadingUI: false,
          progressiveLoad: false,
        })
        if (cancelled) return

        viewer.start()
        frameScene(viewer, up, startView)
        setStatus('ready')
        if (import.meta.env.DEV) window.__splatViewer = viewer
        onLoadRef.current?.(viewer)
      } catch (err) {
        console.error('[SplatViewer]', err)
        if (cancelled) return
        const msg = err?.message || String(err)
        setStatus('error')
        setError(msg)
        onErrorRef.current?.(msg)
      }
    }

    init()

    return () => {
      cancelled = true
      const v = viewerRef.current
      viewerRef.current = null
      if (!v) return

      // dispose() removes the library's canvas from rootElement and then tries
      // document.body.removeChild(rootElement). Since rootElement is a React
      // node (not a body child) that second call rejects, so swallow it.
      // Never clear innerHTML ourselves: the library still owns children here.
      try {
        const p = v.dispose()
        if (p && typeof p.catch === 'function') p.catch(() => {})
      } catch {
        /* ignore teardown errors */
      }
    }
  }, [url, ext, upKey, startKey])

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      {status === 'loading' && (
        <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-viewport text-[#9db0be]">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-flag border-t-transparent" />
          <span className="text-sm">Loading 3D scene…</span>
        </div>
      )}

      {status === 'error' && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 overflow-y-auto bg-viewport p-6 text-center">
          {error === NO_WEBGL2 ? (
            <>
              <span className="font-display text-lg font-semibold text-paper">Your browser is not using the graphics card</span>
              <span className="max-w-md text-sm text-[#b8c7d3]">
                3D needs WebGL2. In Chrome or Edge, turn on <b>Use graphics acceleration when available</b> (Settings &gt; System)
                and restart the browser. On a laptop with two graphics chips, open Windows <b>Settings &gt; System &gt; Display &gt;
                Graphics</b>, add the browser and choose <b>High performance</b>.
              </span>
              <span className="max-w-md text-xs text-[#7e92a2]">Tip: open chrome://gpu to check that WebGL2 says "Hardware accelerated".</span>
            </>
          ) : (
            <>
              <span className="font-display text-lg font-semibold text-paper">This 3D file could not be shown</span>
              <span className="max-w-md break-words text-xs text-[#7e92a2]">{error}</span>
              <span className="max-w-md text-xs text-[#7e92a2]">Supported files: .splat, .ply or .spz exported from a splat trainer.</span>
            </>
          )}
        </div>
      )}
    </div>
  )
}