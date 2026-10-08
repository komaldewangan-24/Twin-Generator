import { useEffect, useRef, useState } from 'react'

export default function SplatViewer({ url, onLoad, onError }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  // Keep callbacks in refs so they don't retrigger the viewer effect.
  const onLoadRef = useRef(onLoad)
  const onErrorRef = useRef(onError)
  onLoadRef.current = onLoad
  onErrorRef.current = onError

  useEffect(() => {
    if (!url) return
    let cancelled = false

    const init = async () => {
      try {
        setStatus('loading')
        setError(null)

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
          cameraUp: [0, -1, -0.6],
          initialCameraPosition: [-1, -4, 6],
          initialCameraLookAt: [1, 4, 0],
        })
        viewerRef.current = viewer

        await viewer.addSplatScene(url, {
          splatAlphaRemovalThreshold: 5,
          showLoadingUI: false,
          progressiveLoad: false,
        })
        if (cancelled) return

        viewer.start()
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
  }, [url])

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      {status === 'loading' && (
        <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-slate-950 text-slate-400">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
          <span className="text-sm">Loading 3D scene…</span>
        </div>
      )}

      {status === 'error' && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-slate-950 p-6 text-center">
          <span className="text-3xl">⚠️</span>
          <span className="text-sm font-semibold text-slate-200">Could not render the splat file</span>
          <span className="max-w-md break-words text-xs text-slate-500">{error}</span>
          <span className="max-w-md text-xs text-slate-600">
            Supported exports: .splat or .ply from Colab / Luma AI.
          </span>
        </div>
      )}
    </div>
  )
}