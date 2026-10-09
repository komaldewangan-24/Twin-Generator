import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppHeader from '../components/AppHeader'
import ChatPanel from '../components/ChatPanel'
import ErrorBoundary from '../components/ErrorBoundary'
import FloorPlan from '../components/FloorPlan'
import AnalyticsTab from '../components/project/AnalyticsTab'
import ObjectsTab from '../components/project/ObjectsTab'
import ProcessingPanel from '../components/project/ProcessingPanel'
import TitleBlock from '../components/project/TitleBlock'
import UploadPanel from '../components/project/UploadPanel'
import ViewerTab from '../components/project/ViewerTab'
import { Spinner, StatusPill } from '../components/ui'
import api, { apiErrorMessage } from '../lib/api'
import { useFileUrl } from '../lib/useFileUrl'
import { PROCESSING, classSingular, formatDate, friendlyError, splitObjects, totalObjects } from '../lib/format'
import { downloadReport } from '../lib/report'

const TABS = [
  { id: 'viewer', label: '3D viewer' },
  { id: 'objects', label: 'Objects' },
  { id: 'floor', label: 'Floor plan' },
  { id: 'analytics', label: 'Analytics' },
  { id: 'chat', label: 'Assistant' },
]

export default function ProjectDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [project, setProject] = useState(null)
  const [objects, setObjects] = useState(null) // { detections, meta }
  const [analytics, setAnalytics] = useState(null)
  const [progress, setProgress] = useState(null)
  const [pickedTab, setTab] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [splatProgress, setSplatProgress] = useState(null)
  const [showReplace, setShowReplace] = useState(false)
  const [reportBusy, setReportBusy] = useState(false)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)
  const [focus, setFocus] = useState(null)
  const objectsRef = useRef(null)

  const fetchProject = useCallback(async () => {
    try {
      const { data } = await api.get(`/projects/${id}`)
      setProject(data)
      return data
    } catch {
      setNotFound(true)
      return null
    }
  }, [id])

  const fetchData = useCallback(async () => {
    // Independent requests: /objects 404s legitimately when nothing was detected,
    // and that must not throw away the analytics.
    const [obj, ana] = await Promise.allSettled([
      api.get(`/projects/${id}/objects`),
      api.get(`/projects/${id}/analytics`),
    ])
    setObjects(obj.status === 'fulfilled' ? splitObjects(obj.value.data) : { detections: [], meta: null })
    if (ana.status === 'fulfilled') setAnalytics(ana.value.data)
  }, [id])

  useEffect(() => {
    fetchProject().then((p) => {
      if (p && (!PROCESSING.includes(p.status) || p.status === 'TRAINING_3D')) fetchData()
    })
  }, [fetchProject, fetchData])

  objectsRef.current = objects
  const status = project?.status
  useEffect(() => {
    if (!PROCESSING.includes(status)) return
    const timer = setInterval(async () => {
      try {
        const { data } = await api.get(`/projects/${id}/status`)
        setProgress(data.progress)
        setProject((prev) => ({ ...prev, status: data.status, error_message: data.error_message, frame_count: data.frame_count }))
        if (data.status === 'TRAINING_3D' && data.has_detections && !objectsRef.current) {
          fetchData()
          fetchProject() // the 3D structure file exists by now
        }
        if (data.status === 'DONE') {
          clearInterval(timer)
          fetchProject()
          fetchData()
        } else if (data.status === 'FAILED') {
          clearInterval(timer)
        }
      } catch {
        clearInterval(timer)
      }
    }, 2500)
    return () => clearInterval(timer)
  }, [status, id, fetchData, fetchProject])

  const uploadFile = async (url, file, onProgress) => {
    const fd = new FormData()
    fd.append('file', file)
    await api.post(url, fd, {
      onUploadProgress: (e) => e.total && onProgress(Math.round((e.loaded / e.total) * 100)),
    })
  }

  const uploadVideo = async (file) => {
    if (!file) return
    setError('')
    setUploadProgress(0)
    try {
      await uploadFile(`/projects/${id}/upload`, file, setUploadProgress)
      setObjects(null)
      setAnalytics(null)
      setShowReplace(false)
      await fetchProject()
    } catch (err) {
      setError(apiErrorMessage(err, 'The upload failed. Check your connection and try again.'))
    } finally {
      setUploadProgress(null)
    }
  }

  const attachSplat = async (file) => {
    if (!file) return
    setError('')
    setSplatProgress(0)
    try {
      await uploadFile(`/projects/${id}/splat`, file, setSplatProgress)
      await fetchProject()
    } catch (err) {
      setError(apiErrorMessage(err, 'The 3D file could not be uploaded.'))
    } finally {
      setSplatProgress(null)
    }
  }

  // The demo is its own scan (its 3D model and its object positions belong together).
  const openDemo = async () => {
    setError('')
    try {
      const { data } = await api.post('/projects/demo')
      navigate(`/project/${data.id}`)
    } catch (err) {
      setError(apiErrorMessage(err, 'The demo scan is not available.'))
    }
  }

  // The real size of the room, from a tape measure or from two points picked in the 3D view.
  // It is saved with the scan, so the floor plan, analytics, assistant and PDF all follow it.
  const saveScale = async (body, fallback) => {
    try {
      const { data } = await api.post(`/projects/${id}/calibrate`, body)
      setAnalytics(data)
      return null
    } catch (err) {
      return apiErrorMessage(err, fallback)
    }
  }
  const calibrate = async (width, depth) => {
    setError('')
    const failure = await saveScale({ longer_side_m: width, ...(depth ? { shorter_side_m: depth } : {}) }, 'Could not apply that size.')
    if (failure) setError(failure)
  }
  const calibrateByPoints = (a, b, realMetres) => saveScale({ a, b, real_m: realMetres }, 'Could not set the scale.')
  const resetScale = async () => {
    setError('')
    try {
      const { data } = await api.delete(`/projects/${id}/calibrate`)
      setAnalytics(data)
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not go back to the estimate.'))
    }
  }

  const makeReport = async () => {
    setReportBusy(true)
    try {
      await downloadReport({ project, detections: objects?.detections ?? [], meta: objects?.meta, analytics })
    } catch {
      setError('The PDF could not be created. Try again.')
    } finally {
      setReportBusy(false)
    }
  }

  // 3D pins: every detected object that has a position in the 3D model.
  const pins = useMemo(
    () => (objects?.detections ?? []).flatMap((d) =>
      d.positions.map((p, i) => (p.world ? { id: `${d.class}:${i}`, label: classSingular(d.class), world: p.world } : null)).filter(Boolean),
    ),
    [objects],
  )
  const showIn3D = (cls, index) => {
    setFocus({ id: `${cls}:${index}`, nonce: Date.now() })
    setTab('viewer')
  }

  const splatName = project?.has_splat ? `model${project.splat_ext}` : null
  const splatUrl = useFileUrl(id, splatName)
  const structureUrl = useFileUrl(id, project?.has_structure ? 'structure.points' : null)

  if (notFound) {
    return (
      <div className="min-h-screen">
        <AppHeader />
        <div className="mx-auto max-w-md px-6 py-24 text-center">
          <h1 className="text-3xl font-semibold">Scan not found</h1>
          <p className="mt-2 text-graphite">It may have been deleted, or it belongs to another account.</p>
          <button onClick={() => navigate('/dashboard')} className="btn btn-ink mt-6">Back to your scans</button>
        </div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="grid min-h-screen place-items-center text-graphite"><Spinner className="h-7 w-7" /></div>
    )
  }

  // The 3D model is the headline of a scan, so open on it whenever there is something to show.
  const tab = pickedTab ?? (project.has_splat || project.has_structure ? 'viewer' : 'objects')
  const training = project.status === 'TRAINING_3D'
  const processing = PROCESSING.includes(project.status) && !(training && objects)
  const done = project.status === 'DONE' || (training && !!objects)
  const finished = project.status === 'DONE'
  const failed = project.status === 'FAILED'
  const detections = objects?.detections ?? []
  const needsVideo = !processing && !done
  const recon = objects?.meta?.reconstruction ?? null
  // metres per model unit: the estimate, or the person's measurement once they have made one
  const metersPerUnit = analytics?.layout?.meters_per_unit ?? recon?.meters_per_unit
  const unitsPerMeter = metersPerUnit ? 1 / metersPerUnit : 1

  const stats = [
    { label: 'Scanned', value: formatDate(project.scan_date, { month: 'short', day: 'numeric', year: 'numeric' }) },
    { label: 'Frames', value: project.frame_count ?? '–', big: true },
    { label: 'Objects', value: done && objects ? totalObjects(detections) : '–', big: true },
    { label: 'Zones', value: done ? analytics?.rooms?.count ?? '–' : '–', big: true },
    { label: 'Seats', value: done ? analytics?.seating_capacity?.total ?? '–' : '–', big: true },
    { label: 'Detector', value: done ? (objects?.meta?.backend ?? '–').replace('onnxruntime: ', '') : '–' },
  ]

  return (
    <div className="min-h-screen">
      <AppHeader crumb={project.name} />
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <StatusPill status={project.status} />
            <h1 className="mt-3 truncate text-4xl font-semibold sm:text-5xl">{project.name}</h1>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            {finished && project.has_video && (
              <button className="btn btn-ghost" onClick={() => setShowReplace((v) => !v)}>
                {showReplace ? 'Cancel' : 'Upload a new video'}
              </button>
            )}
            {finished && objects && (
              <button className="btn btn-ink" onClick={makeReport} disabled={reportBusy}>
                {reportBusy ? <><Spinner className="h-4 w-4" /> Creating PDF</> : 'Download PDF report'}
              </button>
            )}
          </div>
        </div>

        {error && (
          <p role="alert" className="mt-5 rounded-[3px] border border-fail/40 bg-fail-soft px-4 py-2.5 text-sm text-fail">{error}</p>
        )}

        <div className="mt-6"><TitleBlock items={stats} /></div>

        <div className="mt-6">
          {processing && <ProcessingPanel status={project.status} frameCount={project.frame_count} progress={progress} />}

          {failed && (
            <div role="alert" className="mb-5 rounded-[3px] border border-fail/40 bg-fail-soft px-5 py-4">
              <p className="font-display text-xl font-semibold text-fail">This video could not be processed</p>
              <p className="mt-1 text-ink">{friendlyError(project.error_message)}</p>
            </div>
          )}

          {(needsVideo || showReplace) && (
            <UploadPanel onUpload={uploadVideo} progress={uploadProgress} replacing={done} />
          )}

          {done && !showReplace && (
            <>
              <div role="tablist" aria-label="Scan results" className="mb-5 flex gap-1 overflow-x-auto overflow-y-hidden border-b border-rule-strong [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    role="tab"
                    id={`tab-${t.id}`}
                    aria-selected={tab === t.id}
                    aria-controls={`panel-${t.id}`}
                    onClick={() => setTab(t.id)}
                    className={`-mb-px whitespace-nowrap border-b-[3px] px-4 py-3 font-display text-[15px] font-semibold transition ${
                      tab === t.id ? 'border-flag text-ink' : 'border-transparent text-graphite hover:text-ink'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} key={tab} className="rise">
                {!objects ? (
                  <div className="grid h-48 place-items-center text-graphite"><Spinner className="h-6 w-6" /></div>
                ) : (
                  <ErrorBoundary title="This tab hit an error">
                    {tab === 'viewer' && (
                      <ViewerTab splatUrl={splatUrl} splatExt={project.splat_ext} splatProgress={splatProgress} onAttach={attachSplat} onDemo={openDemo} building={training} progress={progress} error={objects?.meta?.splat_error} up={recon?.up} startView={recon?.start_view} structureUrl={structureUrl} recon={recon} pins={pins} focus={focus} tour={recon?.tour} unitsPerMeter={unitsPerMeter} scaleMeasured={analytics?.layout?.measured ?? null} onMeasureCalibrate={calibrateByPoints} onResetScale={resetScale} name={project.name} />
                    )}
                    {tab === 'objects' && <ObjectsTab detections={detections} meta={objects?.meta} onShow3D={project.has_splat ? showIn3D : null} />}
                    {tab === 'floor' && (
                      <section className="sheet p-5">
                        <h2 className="mb-4 text-2xl font-semibold">Floor plan</h2>
                        <FloorPlan analytics={analytics} detections={detections} onSelect={project.has_splat ? showIn3D : undefined} />
                        <p className="mt-4 border-l-2 border-flag pl-3 text-sm text-graphite">
                          {analytics?.layout
                            ? 'Objects are placed on the floor in 3D from your video and drawn at typical sizes, so distances are real-world estimates. Walls are fitted as a rectangle. Sizes assume the phone was held at about 1.4 m: enter a measured size on the Analytics tab to correct them. Click an object for details.'
                            : 'This is a schematic. No camera path was found, so positions come from where objects appear in the camera view: the plan shows how things relate to each other, not exact distances. Dashed boxes are zones of nearby objects.'}
                        </p>
                      </section>
                    )}
                    {tab === 'analytics' && <AnalyticsTab analytics={analytics} detections={detections} onCalibrate={calibrate} onResetScale={resetScale} />}
                    {tab === 'chat' && <ChatPanel projectId={id} detections={detections} onShow3D={project.has_splat ? showIn3D : null} />}
                  </ErrorBoundary>
                )}
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  )
}
