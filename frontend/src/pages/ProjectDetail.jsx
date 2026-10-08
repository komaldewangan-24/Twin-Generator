import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api, { API_URL, apiErrorMessage } from '../lib/api'
import StatusTimeline from '../components/StatusTimeline'
import FloorPlan from '../components/FloorPlan'
import ChatPanel from '../components/ChatPanel'
import ErrorBoundary from '../components/ErrorBoundary'
import SplatViewer from '../components/SplatViewer'

const PROCESSING = ['UPLOADED', 'EXTRACTING', 'DETECTING']

const STATUS_COLOR = {
  CREATED: 'bg-slate-500/20 text-slate-300',
  UPLOADED: 'bg-amber-500/20 text-amber-300',
  EXTRACTING: 'bg-amber-500/20 text-amber-300',
  DETECTING: 'bg-purple-500/20 text-purple-300',
  DONE: 'bg-emerald-500/20 text-emerald-300',
  FAILED: 'bg-red-500/20 text-red-300',
}

const TABS = [
  { id: 'viewer', label: '3D' },
  { id: 'objects', label: 'Objects' },
  { id: 'floor', label: 'Floor Plan' },
  { id: 'analytics', label: 'Analytics' },
  { id: 'chat', label: 'Chat' },
]

export default function ProjectDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [project, setProject] = useState(null)
  const [detections, setDetections] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [tab, setTab] = useState('viewer')
  const [uploadProgress, setUploadProgress] = useState(null)
  const [splatProgress, setSplatProgress] = useState(null)
  const [error, setError] = useState('')
  const [calW, setCalW] = useState('')
  const [calH, setCalH] = useState('')
  const [showHeatmap, setShowHeatmap] = useState(false)
  const [reportSaving, setReportSaving] = useState(false)
  const videoInputRef = useRef(null)
  const splatInputRef = useRef(null)

  const fetchProject = useCallback(async () => {
    try {
      const { data } = await api.get(`/projects/${id}`)
      setProject(data)
      return data
    } catch {
      setError('Project not found')
      return null
    }
  }, [id])

  const fetchData = useCallback(async () => {
      // Fetch independently: /objects 404s legitimately when a scan produced
      // no detections, and must not discard the analytics payload.
      const [objRes, anaRes] = await Promise.allSettled([
        api.get(`/projects/${id}/objects`),
        api.get(`/projects/${id}/analytics`),
      ])
      if (objRes.status === 'fulfilled') setDetections(objRes.value.data)
      else setDetections([])
      if (anaRes.status === 'fulfilled') setAnalytics(anaRes.value.data)
    }, [id])

  useEffect(() => {
    fetchProject().then((p) => {
      if (p && !PROCESSING.includes(p.status)) fetchData()
    })
  }, [fetchProject, fetchData])

  useEffect(() => {
    if (!project || !PROCESSING.includes(project.status)) return
    const timer = setInterval(async () => {
      try {
        const { data } = await api.get(`/projects/${id}/status`)
        setProject((prev) => ({ ...prev, status: data.status, error_message: data.error_message }))
        if (data.status === 'DONE') {
          clearInterval(timer)
          fetchData()
        } else if (data.status === 'FAILED') {
          clearInterval(timer)
        }
      } catch {
        clearInterval(timer)
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [project?.status, id, fetchData])

  const uploadVideo = async (file) => {
    if (!file) return
    setError('')
    setUploadProgress(0)
    const fd = new FormData()
    fd.append('file', file)
    try {
      await api.post(`/projects/${id}/upload`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) setUploadProgress(Math.round((e.loaded / e.total) * 100))
        },
      })
      setUploadProgress(100)
      fetchProject()
    } catch (err) {
      setError(apiErrorMessage(err, 'Upload failed'))
      setUploadProgress(null)
    }
  }

  const loadDemoSplat = async () => {
    try {
      await api.post(`/projects/${id}/splat/demo`)
      fetchProject()
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not load the demo model'))
    }
  }

  const uploadSplat = async (file) => {
    if (!file) return
    setError('')
    setSplatProgress(0)
    const fd = new FormData()
    fd.append('file', file)
    try {
      await api.post(`/projects/${id}/splat`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) setSplatProgress(Math.round((e.loaded / e.total) * 100))
        },
      })
      setSplatProgress(100)
      setTimeout(() => setSplatProgress(null), 800)
      fetchProject()
    } catch (err) {
      setError(apiErrorMessage(err, 'Splat upload failed'))
      setSplatProgress(null)
    }
  }

  const recalibrate = async (e) => {
    e.preventDefault()
    const w = parseFloat(calW)
    const h = parseFloat(calH)
    if (!w || !h || w <= 0 || h <= 0) return
    try {
      const { data } = await api.get(`/projects/${id}/analytics`, {
        params: { room_width_m: w, room_height_m: h },
      })
      setAnalytics(data)
    } catch {
      setError('Calibration request failed')
    }
  }

  const downloadReport = async () => {
    setReportSaving(true)
    try {
      const { jsPDF } = await import('jspdf')
      const doc = new jsPDF()
      let y = 18
      doc.setFontSize(18)
      doc.text('AI Digital Twin — Analysis Report', 14, y)
      y += 9
      doc.setFontSize(11)
      doc.text(`Project: ${project.name}`, 14, y)
      y += 6
      doc.text(`Generated: ${new Date().toLocaleString()}`, 14, y)
      y += 10

      const dets = detections || []
      doc.setFontSize(13)
      doc.text('Detected objects', 14, y)
      y += 7
      doc.setFontSize(10)
      let total = 0
      for (const d of dets) {
        total += d.count
        doc.text(`${d.class}: ${d.count}`, 18, y)
        y += 6
      }
      doc.text(`Total instances: ${total}`, 14, y + 6)
      y += 14

      if (analytics) {
        doc.setFontSize(13)
        doc.text('Analytics', 14, y)
        y += 7
        doc.setFontSize(10)
        const roomCount = analytics.rooms?.count ?? '–'
        doc.text(`Segmented rooms: ${roomCount}`, 18, y)
        y += 6
        if (analytics.area_m2 != null) doc.text(`Estimated area: ${analytics.area_m2} m²`, 18, y)
        doc.save(`${project.name.replace(/\s+/g, '_')}_report.pdf`)
      }
    } finally {
      setReportSaving(false)
    }
  }

  if (error && !project) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
        <div className="text-center">
          <p className="mb-4">{error}</p>
          <button onClick={() => navigate('/dashboard')} className="text-emerald-400 hover:underline">
            Back to dashboard
          </button>
        </div>
      </div>
    )
  }

  if (!project) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-500">Loading…</div>
  }

  const processing = PROCESSING.includes(project.status)
  const ready = detections != null || project.status === 'DONE'
  const splatUrl = project.splat_path ? `${API_URL}/splats/${project.splat_path.split(/[\\/]/).pop()}` : null

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/dashboard')}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 transition hover:border-slate-500"
            >
              ← Back
            </button>
            <h1 className="truncate text-lg font-bold text-white">{project.name}</h1>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_COLOR[project.status] ?? STATUS_COLOR.CREATED}`}>
              {project.status}
            </span>
          </div>
          <div className="flex gap-2">
            {ready && (
              <button
                onClick={downloadReport}
                disabled={reportSaving}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:border-emerald-500 hover:text-emerald-300 disabled:opacity-50"
              >
                {reportSaving ? 'Generating…' : '📄 PDF Report'}
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {error && <p className="mb-6 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-400">{error}</p>}

        {/* Video upload */}
        {!project.video_path && (
          <div className="mb-6">
            {uploadProgress == null ? (
              <button
                onClick={() => videoInputRef.current?.click()}
                className="flex w-full flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-slate-700 bg-slate-900 p-10 transition hover:border-emerald-500"
              >
                <span className="text-4xl">🎬</span>
                <span className="text-white">Click to upload the walkthrough video</span>
                <span className="text-xs text-slate-500">MP4 / MOV / WebM · up to 500 MB</span>
              </button>
            ) : (
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                <div className="mb-2 flex justify-between text-sm text-slate-300">
                  <span>Uploading…</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full bg-emerald-500 transition-all"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                {uploadProgress === 100 && (
                  <p className="mt-3 text-sm text-emerald-400">Uploaded! Extracting frames…</p>
                )}
              </div>
            )}
            <input
              ref={videoInputRef}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={(e) => uploadVideo(e.target.files?.[0])}
            />
          </div>
        )}

        {/* Progress / ready split */}
        {processing ? (
          <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-8 text-center">
              <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
              <p className="text-slate-300">Analyzing your space with YOLOv8…</p>
              <p className="mt-1 text-xs text-slate-500">
                Frame extraction → object detection → room segmentation
              </p>
            </div>
            <StatusTimeline status={project.status} errorMessage={project.error_message} />
          </div>
        ) : ready ? (
          <>
            <div className="mb-4 flex gap-2 overflow-x-auto">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                    tab === t.id
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-900 text-slate-400 hover:text-white'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {tab === 'viewer' && (
              <div className="rounded-2xl border border-slate-800 bg-slate-950 p-2" style={{ height: 560 }}>
                {splatUrl ? (
                  <ErrorBoundary>
                    <SplatViewer url={splatUrl} />
                  </ErrorBoundary>
                ) : (
                  <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                    <span className="text-4xl">🧊</span>
                    <p className="text-slate-300">
                      No 3D model attached yet. The Gaussian splat is trained externally
                      (Google Colab / Luma AI) because this machine has no NVIDIA GPU.
                    </p>
                    <p className="text-xs text-slate-500">Attach the exported .ply to unlock the interactive viewer.</p>
                    {splatProgress == null ? (
                      <div className="flex gap-3">
                        <button
                          onClick={loadDemoSplat}
                          className="rounded-lg border border-emerald-600 px-5 py-2.5 text-sm font-semibold text-emerald-400 transition hover:bg-emerald-600 hover:text-white"
                        >
                          Try a demo model
                        </button>
                        <button
                          onClick={() => splatInputRef.current?.click()}
                          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-500"
                        >
                          Attach .ply / .splat
                        </button>
                      </div>
                    ) : (
                      <div className="w-64">
                        <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                          <div className="h-full bg-emerald-500 transition-all" style={{ width: `${splatProgress}%` }} />
                        </div>
                        <p className="mt-2 text-xs text-slate-500">{splatProgress}%</p>
                      </div>
                    )}
                    <input
                      ref={splatInputRef}
                      type="file"
                      accept=".ply,.splat,.spz"
                      className="hidden"
                      onChange={(e) => uploadSplat(e.target.files?.[0])}
                    />
                  </div>
                )}
              </div>
            )}

            {tab === 'objects' && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-white">Detected Objects</h2>
                  <span className="text-sm text-slate-400">
                    {detections?.reduce((s, d) => s + d.count, 0) ?? 0} instances across{' '}
                    {analytics?.rooms?.count ?? 0} zone(s)
                  </span>
                </div>
                {detections?.length === 0 ? (
                  <p className="text-slate-500">No furniture detected above the confidence threshold.</p>
                ) : (
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {detections?.map((d) => (
                      <div key={d.class} className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold capitalize text-slate-200">{d.class}</span>
                          <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-sm font-bold text-emerald-400">
                            {d.count}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-500">top confidence {(d.positions[0]?.confidence ?? 0).toFixed(2)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {tab === 'floor' && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-white">Floor Plan</h2>
                  <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-400">
                    <input
                      type="checkbox"
                      checked={showHeatmap}
                      onChange={(e) => setShowHeatmap(e.target.checked)}
                      className="accent-emerald-500"
                    />
                    Density heatmap
                  </label>
                </div>
                <FloorPlan analytics={analytics} detections={detections} showHeatmap={showHeatmap} />
                <p className="mt-3 text-xs text-slate-500">
                  Object floor positions are estimated from the bottom edge of detection boxes in normalized scene
                  coordinates. Zones (dashed) are segmented with DBSCAN clustering.
                </p>
              </div>
            )}

            {tab === 'analytics' && (
              <div className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                  <h2 className="mb-4 text-lg font-semibold text-white">Room Insights</h2>
                  <dl className="space-y-3">
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Zones / rooms</dt>
                      <dd className="font-semibold text-white">{analytics?.rooms?.count ?? '–'}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Total objects</dt>
                      <dd className="font-semibold text-white">
                        {detections?.reduce((s, d) => s + d.count, 0) ?? '–'}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Estimated area</dt>
                      <dd className="font-semibold text-white">
                        {analytics?.area_m2 != null ? `${analytics.area_m2} m²` : 'Not calibrated'}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Capture backend</dt>
                      <dd className="font-mono text-xs font-semibold text-emerald-400">
                        {analytics?.meta?.backend ?? '–'}
                      </dd>
                    </div>
                  </dl>

                  <div className="mt-6 border-t border-slate-800 pt-4">
                    <h3 className="mb-3 text-sm font-semibold text-white">Calibrate to real size</h3>
                    <form onSubmit={recalibrate} className="flex items-end gap-2">
                      <label className="flex-1 text-xs text-slate-500">
                        Room width (m)
                        <input
                          value={calW}
                          onChange={(e) => setCalW(e.target.value)}
                          type="number"
                          step="0.1"
                          min="0"
                          className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none focus:border-emerald-500"
                        />
                      </label>
                      <label className="flex-1 text-xs text-slate-500">
                        Room height (m)
                        <input
                          value={calH}
                          onChange={(e) => setCalH(e.target.value)}
                          type="number"
                          step="0.1"
                          min="0"
                          className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none focus:border-emerald-500"
                        />
                      </label>
                      <button
                        type="submit"
                        className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500"
                      >
                        Apply
                      </button>
                    </form>
                    <p className="mt-2 text-[11px] text-slate-600">
                      Area is derived from the bounding box of detected floor positions; real-size inputs improve the
                      estimate.
                    </p>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                  <h2 className="mb-4 text-lg font-semibold text-white">Occupancy by Object</h2>
                  {Array.isArray(detections) && detections.length > 0 ? (
                    <div className="space-y-3">
                      {detections
                        .slice()
                        .sort((a, b) => b.count - a.count)
                        .map((d) => (
                          <div key={d.class}>
                            <div className="mb-1 flex justify-between text-sm">
                              <span className="capitalize text-slate-300">{d.class}</span>
                              <span className="text-slate-500">×{d.count}</span>
                            </div>
                            <div className="h-2.5 overflow-hidden rounded-full bg-slate-800">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400"
                                style={{
                                  width: `${(d.count / Math.max(1, ...detections.map((x) => x.count))) * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        ))}
                    </div>
                  ) : (
                    <p className="text-slate-500">No object data.</p>
                  )}
                </div>
              </div>
            )}

            {tab === 'chat' && (
              <div className="h-[560px]">
                <ChatPanel projectId={id} detections={detections} />
              </div>
            )}
          </>
        ) : (
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-10 text-center text-slate-500">
            <StatusTimeline status={project.status} errorMessage={project.error_message} />
          </div>
        )}

        {project.status === 'FAILED' && (
          <div className="mt-6 rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-center">
            <p className="text-red-300">The pipeline failed for this video.</p>
            <p className="mt-1 text-sm text-red-400/80">{project.error_message}</p>
            <button
              onClick={() => videoInputRef.current?.click()}
              className="mt-4 rounded-lg bg-red-500/20 px-5 py-2 text-sm font-semibold text-red-200 transition hover:bg-red-500/30"
            >
              Re-upload video
            </button>
          </div>
        )}
      </main>
    </div>
  )
}