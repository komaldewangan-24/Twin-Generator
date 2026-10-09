import { useCallback, useEffect, useRef, useState } from 'react'
import ErrorBoundary from '../ErrorBoundary'
import SplatViewer, { ORIENTATIONS, frameScene } from '../SplatViewer'
import StructureView from '../StructureView'
import Pins from '../Pins'
import MeasureLayer from '../MeasureLayer'
import MeasurePanel from './MeasurePanel'
import { flyToObject, playTour, settleLookAround, tourDuration, turnToObject } from '../../lib/camera'
import { dist, pickSplat } from '../../lib/measure'
import { canRecord, safeName, saveBlob, startRecording } from '../../lib/record'
import { Corners, Icon, Spinner } from '../ui'

const btn = 'btn btn-ghost-dark !px-3 !py-2 backdrop-blur'

const clockText = (ms) => {
  const s = Math.max(0, Math.round(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** What the Measure tool needs from the photoreal viewer. */
const splatSurface = (v) => ({
  camera: v.camera,
  canvas: v.renderer.domElement,
  pick: (x, y) => pickSplat(v, x, y),
  // the viewer re-centres on every click; while measuring, a click must only place a point
  pauseClicks() {
    v.onMouseClick = () => {}
    return () => { delete v.onMouseClick }
  },
})

export default function ViewerTab({
  splatUrl, splatExt, startView, splatProgress, onAttach, onDemo, building, progress, error, up,
  pins = [], focus, tour, unitsPerMeter = 1, structureUrl, recon,
  scaleMeasured = null, onMeasureCalibrate, onResetScale, name,
}) {
  const stage = useRef(null)
  const fileInput = useRef(null)
  const viewer = useRef(null)
  const [full, setFull] = useState(false)
  const [orient, setOrient] = useState(0)
  const [ready, setReady] = useState(false)
  const [showPins, setShowPins] = useState(true)
  const [touring, setTouring] = useState(false)
  const [selected, setSelected] = useState(null)
  const [choice, setChoice] = useState(null)       // 'photo' | 'structure' once the user picks
  const [resetKey, setResetKey] = useState(0)      // bumps to re-frame the structure view
  const stopMotion = useRef(() => {})
  const [measuring, setMeasuring] = useState(false)
  const [surface, setSurface] = useState(null)        // what the Measure tool clicks on, from whichever viewer shows
  const [measures, setMeasures] = useState([])        // [{id, a, b}] in the model's own units
  const [pending, setPending] = useState(null)        // first point of the next measurement
  const [recording, setRecording] = useState(null)    // {startedAt, total} while the walkthrough is being filmed
  const [clock, setClock] = useState(0)
  const [recordError, setRecordError] = useState('')
  const recorder = useRef(null)

  const hasPhoto = !!splatUrl
  // A video filmed by turning on the spot has almost no depth in it: the model is only right from where the phone was.
  const lookAround = !!recon?.low_parallax && !!startView
  const hasStructure = !!structureUrl
  const mode = choice ?? (hasPhoto ? 'photo' : 'structure')

  // When the camera path gave us a reliable "up", offer it first and use it by default.
  const options = up ? [{ id: 'auto', label: 'Auto', up }, ...ORIENTATIONS] : ORIENTATIONS
  const o = options[orient % options.length]

  const finishRecording = async () => {
    const r = recorder.current
    recorder.current = null
    setRecording(null)
    if (!r) return
    try {
      const blob = await r.stop()
      if (blob.size) saveBlob(blob, `${safeName(name)}-walkthrough.${r.ext}`)
    } catch {
      setRecordError('The video could not be saved. Try again.')
    }
  }

  // Show an object: fly to it, or in look-around mode turn towards it without leaving the filming spot.
  const goTo = (world) => (lookAround && o.id === 'auto' ? turnToObject(viewer.current, world) : flyToObject(viewer.current, world, o.up, unitsPerMeter))

  const halt = () => {
    stopMotion.current()
    stopMotion.current = () => {}
    setTouring(false)
    if (lookAround) settleLookAround(viewer.current)
    if (recorder.current) finishRecording()          // whatever was filmed so far is still saved
  }
  useEffect(() => () => {
    stopMotion.current()
    recorder.current?.stop().catch(() => {})         // leaving the page: drop the recording
    recorder.current = null
  }, [])

  useEffect(() => {
    if (!recording) return undefined
    const id = setInterval(() => setClock(performance.now() - recording.startedAt), 250)
    return () => clearInterval(id)
  }, [recording])

  // Film the walkthrough: play the tour while the 3D view is recorded, then save the video.
  const startRecord = () => {
    halt()
    setRecordError('')
    try {
      recorder.current = startRecording(surface.canvas)
    } catch (err) {
      return setRecordError(err.message)
    }
    setClock(0)
    setRecording({ startedAt: performance.now(), total: tourDuration(tour) })
    setTouring(true)
    stopMotion.current = playTour(viewer.current, tour, unitsPerMeter, () => { setTouring(false); finishRecording() })
  }

  const chooseMode = (next) => {
    halt()
    setReady(false)
    setSurface(null)
    setPending(null)
    setChoice(next)
  }

  const canMeasure = !!recon && unitsPerMeter > 0
  const metersPerUnit = 1 / unitsPerMeter
  const placePoint = useCallback((p) => {
    if (!pending) return setPending(p)
    if (dist(pending, p) * metersPerUnit < 0.02) return          // same spot twice: keep waiting for a real second point
    setMeasures((m) => [...m, { id: crypto.randomUUID(), a: pending, b: p }])
    setPending(null)
  }, [pending, metersPerUnit])

  const stopMeasuring = () => { setMeasuring(false); setPending(null) }
  useEffect(() => {
    if (!measuring) return undefined
    const onKey = (e) => {
      if (e.key !== 'Escape') return
      if (pending) setPending(null)
      else setMeasuring(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [measuring, pending])

  // "Show in 3D" from the objects list, floor plan or assistant: fly to that object.
  useEffect(() => {
    if (!focus || !ready || mode !== 'photo') return
    const pin = pins.find((p) => p.id === focus.id)
    if (!pin) return
    stopMotion.current()
    setTouring(false)
    setSelected(pin.id)
    stopMotion.current = goTo(pin.world)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus, ready])

  const toggleTour = () => {
    if (touring) return halt()
    halt()
    setTouring(true)
    stopMotion.current = playTour(viewer.current, tour, unitsPerMeter, () => { setTouring(false); if (lookAround) settleLookAround(viewer.current) })
  }

  const toggleFull = async () => {
    const el = stage.current
    if (!el) return
    if (document.fullscreenElement) await document.exitFullscreen()
    else await el.requestFullscreen?.()
    setFull(!!document.fullscreenElement)
  }

  const attachInput = (
    <input ref={fileInput} type="file" accept=".ply,.splat,.spz" hidden onChange={(e) => { onAttach(e.target.files?.[0]); e.target.value = '' }} />
  )

  // ---- something to show: the photoreal model, the structure recovered from the video, or both
  if (hasPhoto || hasStructure) {
    return (
      <div
        ref={stage}
        onPointerDownCapture={(e) => { if (!recorder.current && !e.target.closest?.('button')) halt() }}
        className="relative h-[min(72vh,640px)] min-h-[360px] overflow-hidden rounded-[3px] border border-ink bg-viewport"
      >
        {mode === 'photo' && hasPhoto ? (
          <ErrorBoundary title="The 3D viewer hit an error">
            <SplatViewer url={splatUrl} ext={splatExt} up={o.up} startView={o.id === 'auto' ? startView : undefined} lookAround={lookAround && o.id === 'auto'} onLoad={(v) => { viewer.current = v; setReady(true); setSurface(splatSurface(v)) }} />
          </ErrorBoundary>
        ) : (
          <ErrorBoundary title="The 3D structure view hit an error">
            <StructureView url={structureUrl} recon={recon} pins={pins} showPins={showPins} resetKey={resetKey} onSurface={setSurface} />
          </ErrorBoundary>
        )}
        <Corners className="text-paper/40" />
        {mode === 'photo' && ready && showPins && pins.length > 0 && (
          <Pins viewerRef={viewer} pins={pins} selectedId={selected} onPick={(pin) => { halt(); setSelected(pin.id); stopMotion.current = goTo(pin.world) }} />
        )}

        {canMeasure && (
          <MeasureLayer
            surface={surface}
            active={measuring}
            items={measures}
            pending={pending}
            metersPerUnit={metersPerUnit}
            estimated={!scaleMeasured}
            onPick={placePoint}
          />
        )}
        {measuring && (
          <MeasurePanel
            items={measures}
            metersPerUnit={metersPerUnit}
            estimated={!scaleMeasured}
            measured={scaleMeasured}
            hasPending={!!pending}
            onRemove={(id) => setMeasures((m) => m.filter((x) => x.id !== id))}
            onClear={() => { setMeasures([]); setPending(null) }}
            onCalibrate={(item, metres) => onMeasureCalibrate(item.a, item.b, metres)}
            onReset={onResetScale}
          />
        )}

        {mode === 'photo' && lookAround && o.id === 'auto' && !recording && !measuring && (
          <p className="absolute bottom-12 left-4 z-20 max-w-md rounded-[3px] border border-viewport-line bg-viewport/85 px-3 py-2 text-xs text-[#c7d4de] backdrop-blur" role="status">
            <b className="text-paper">Look-around mode.</b> This video was filmed by turning in one place, so it holds almost no depth: the model is only right from where the phone stood, and anything the phone never pointed at is black. Drag to look around, scroll to zoom. To explore the room, film while walking.
          </p>
        )}
        {recording && <div className="absolute inset-0 z-[15]" aria-hidden />}
        {recording && (
          <div className="absolute inset-x-4 top-4 z-20 flex items-center justify-between gap-3 rounded-[3px] border border-fail/60 bg-viewport/90 px-4 py-2.5 text-paper backdrop-blur" role="status">
            <span className="flex items-center gap-3 font-mono text-sm">
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-fail" aria-hidden />
              Recording the walkthrough
              <span className="figure text-[#9db0be]">{clockText(clock)} / {clockText(recording.total)}</span>
            </span>
            <button onClick={halt} className="btn btn-flag !px-3 !py-1.5">■ Stop and save</button>
          </div>
        )}

        {!recording && hasPhoto && hasStructure && (
          <div role="group" aria-label="What to show" className="absolute left-4 top-4 z-20 flex overflow-hidden rounded-[3px] border border-viewport-line backdrop-blur">
            {[['photo', 'Photoreal'], ['structure', 'Structure']].map(([id, label]) => (
              <button
                key={id}
                onClick={() => chooseMode(id)}
                aria-pressed={mode === id}
                className={`px-3 py-2 font-display text-sm font-semibold transition ${mode === id ? 'bg-flag text-ink' : 'bg-viewport/60 text-[#c7d4de] hover:text-paper'}`}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {!recording && <div className="absolute right-4 top-4 z-20 flex flex-wrap justify-end gap-2">
          {mode === 'photo' && tour?.length > 1 && (
            <button onClick={toggleTour} className={`btn !px-3 !py-2 backdrop-blur ${touring ? 'btn-flag' : 'btn-ghost-dark'}`} aria-pressed={touring}>
              {touring ? '■ Stop walkthrough' : '▶ Walkthrough'}
            </button>
          )}
          {mode === 'photo' && tour?.length > 1 && !touring && surface && canRecord() && (
            <button onClick={startRecord} className={btn} title="Play the walkthrough and save it as a video">
              <span className="text-fail" aria-hidden>●</span> Record
            </button>
          )}
          {canMeasure && (
            <button onClick={() => { halt(); measuring ? stopMeasuring() : setMeasuring(true) }} className={`btn !px-3 !py-2 backdrop-blur ${measuring ? 'btn-flag' : 'btn-ghost-dark'}`} aria-pressed={measuring}>
              Measure
            </button>
          )}
          {pins.length > 0 && (
            <button onClick={() => setShowPins((v) => !v)} className={btn} aria-pressed={showPins}>
              Labels: {showPins ? 'on' : 'off'}
            </button>
          )}
          {mode === 'photo' ? (
            <>
              <button onClick={() => { halt(); setSurface(null); setOrient((orient + 1) % options.length) }} className={btn} title="If the room looks sideways or upside down, try another orientation">
                Orientation: {o.label}
              </button>
              <button onClick={() => { halt(); setSelected(null); frameScene(viewer.current, o.up, o.id === 'auto' ? startView : undefined, { lookAround: lookAround && o.id === 'auto' }) }} className={btn}>Reset view</button>
            </>
          ) : (
            <button onClick={() => setResetKey((k) => k + 1)} className={btn}>Reset view</button>
          )}
          <button onClick={toggleFull} className={btn} aria-label={full ? 'Exit fullscreen' : 'Enter fullscreen'}>
            <Icon.expand /> {full ? 'Exit' : 'Fullscreen'}
          </button>
        </div>}
        {recordError && (
          <p role="alert" className="absolute right-4 top-16 z-20 max-w-xs rounded-[3px] border border-fail/60 bg-viewport/90 px-3 py-2 text-xs text-[#f3b9a6]">{recordError}</p>
        )}

        {!hasPhoto && (
          <div className="absolute inset-x-4 bottom-12 z-20 mx-auto max-w-xl rounded-[3px] border border-viewport-line bg-viewport/85 p-3 text-center text-sm text-[#c7d4de] backdrop-blur" role="status">
            {building ? (
              <>
                This is the 3D structure already recovered from your video. The photoreal model is still training
                {progress?.stage === 'train' ? ` (${Math.round(progress.fraction * 100)}%)` : ''} and will appear here.
              </>
            ) : (
              <>
                The photoreal model could not be built{error ? `: ${error}` : '.'} This is the 3D structure recovered from your video.
                {' '}Run <span className="font-mono">python backend/scripts/doctor.py --gpu-test</span> to find out why, or{' '}
                <button className="underline decoration-flag decoration-2 underline-offset-4" onClick={() => fileInput.current?.click()}>attach a model you trained elsewhere</button>.
              </>
            )}
            {splatProgress != null && <span className="figure ml-2">{splatProgress}%</span>}
          </div>
        )}
        <p className="label pointer-events-none absolute bottom-4 left-5 z-20 !text-[#7e92a2]">
          Drag to orbit · Scroll to zoom · Right-drag to pan
        </p>
        {attachInput}
      </div>
    )
  }

  // ---- nothing to show yet
  if (building) {
    const pct = progress?.stage === 'train' ? Math.round(progress.fraction * 100) : null
    return (
      <div className="relative grid min-h-[420px] place-items-center overflow-hidden rounded-[3px] border border-ink bg-viewport px-6 py-12 text-center text-paper">
        <Corners className="text-paper/30" />
        <div className="w-full max-w-md" role="status">
          <Spinner className="h-7 w-7 text-flag" />
          <h2 className="mt-4 text-3xl font-semibold">Building your 3D model</h2>
          <p className="mt-3 text-[#b8c7d3]">
            Your objects and floor plan are ready in the other tabs. The photorealistic 3D model is still training and
            can take 10 to 30 minutes. You can leave this page.
          </p>
          <div className="mt-6 h-2 overflow-hidden rounded-full border border-viewport-line">
            <div className="h-full bg-flag transition-all duration-500" style={{ width: `${pct ?? 3}%` }} />
          </div>
          <p className="figure mt-2 text-sm text-[#9db0be]">{pct != null ? `${pct}%` : 'Starting'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="relative grid min-h-[420px] place-items-center overflow-hidden rounded-[3px] border border-ink bg-viewport px-6 py-12 text-center text-paper">
      <Corners className="text-paper/30" />
      <div className="max-w-xl">
        <p className="label !text-flag">3D viewer</p>
        <h2 className="mt-2 text-3xl font-semibold">{error ? 'No 3D model could be built' : 'No 3D model attached yet'}</h2>
        {error ? (
          <>
            <p className="mt-3 text-[#f3b9a6]">{error}</p>
            <p className="mt-2 text-sm text-[#9db0be]">
              To find out why, run <span className="font-mono">python backend/scripts/doctor.py --gpu-test</span> on the computer that runs the server.
            </p>
          </>
        ) : (
          <p className="mt-3 text-[#b8c7d3]">
            3D models are built automatically from a new video. For older scans, train a Gaussian splat with a tool like
            Luma, Polycam, KIRI Engine or Brush and attach the exported file here.
          </p>
        )}
        {splatProgress == null ? (
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <button className="btn btn-flag" onClick={() => fileInput.current?.click()}><Icon.upload /> Attach .ply or .splat</button>
            <button className="btn btn-ghost-dark" onClick={onDemo}>Open the demo scan</button>
          </div>
        ) : (
          <div className="mx-auto mt-7 w-64" role="status">
            <div className="h-2 overflow-hidden rounded-full border border-viewport-line"><div className="h-full bg-flag transition-all" style={{ width: `${splatProgress}%` }} /></div>
            <p className="figure mt-2 text-sm text-[#9db0be]">{splatProgress}%</p>
          </div>
        )}
        {attachInput}
      </div>
    </div>
  )
}
