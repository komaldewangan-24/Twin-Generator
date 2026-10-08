import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import AppHeader from '../components/AppHeader'
import { ConfirmDialog, Corners, Icon, IconButton, StatusPill } from '../components/ui'
import api, { apiErrorMessage } from '../lib/api'
import { useFileUrl } from '../lib/useFileUrl'
import { PROCESSING, formatDate, friendlyError } from '../lib/format'

function Thumb({ project }) {
  const [broken, setBroken] = useState(false)
  const signed = useFileUrl(project.id, project.has_preview ? 'preview.jpg' : null)
  const src = signed && !broken ? signed : null
  return (
    <div className="relative aspect-[16/10] overflow-hidden border-b border-rule-strong bg-[#dfe6eb]">
      {src ? (
        <img src={src} alt="" loading="lazy" onError={() => setBroken(true)} className="h-full w-full object-cover" />
      ) : (
        <div
          className="grid h-full w-full place-items-center text-rule-strong"
          style={{
            backgroundImage:
              'repeating-linear-gradient(135deg, transparent 0 9px, rgb(163 175 185 / 0.35) 9px 10px)',
          }}
        >
          <svg width="44" height="44" viewBox="0 0 26 26" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" aria-hidden>
            <path d="M13 2 23 7.5v11L13 24 3 18.5v-11L13 2Z" /><path d="M3 7.5 13 13l10-5.5M13 13v11" />
          </svg>
        </div>
      )}
      <Corners className="text-ink/60" />
    </div>
  )
}

function Card({ project, onRename, onAskDelete }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(project.name)
  const inputRef = useRef(null)

  const commit = () => {
    setEditing(false)
    const next = name.trim()
    if (next && next !== project.name) onRename(project.id, next)
    else setName(project.name)
  }

  const failed = project.status === 'FAILED'
  const busy = PROCESSING.includes(project.status)

  return (
    <article className="sheet group rise flex flex-col transition-transform hover:-translate-y-0.5">
      {/* The whole card is one link via this overlay; the controls sit above it. */}
      {!editing && (
        <Link to={`/project/${project.id}`} className="absolute inset-0 z-10 rounded-[3px]" aria-label={`Open ${project.name}`} />
      )}
      <Thumb project={project} />
      <div className="absolute left-3 top-3 z-20">
        <StatusPill status={project.status} className="bg-sheet/95 backdrop-blur" />
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-2">
          {editing ? (
            <input
              ref={inputRef}
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={commit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commit()
                if (e.key === 'Escape') { setName(project.name); setEditing(false) }
              }}
              aria-label="Scan name"
              className="field relative z-20 py-1.5 font-display text-lg font-semibold"
            />
          ) : (
            <h3 className="min-w-0 truncate text-lg font-semibold">{project.name}</h3>
          )}
          <div className="relative z-20 -mr-1.5 flex shrink-0">
            <IconButton label="Rename scan" onClick={() => setEditing(true)}><Icon.pencil /></IconButton>
            <IconButton label="Delete scan" onClick={() => onAskDelete(project)} className="hover:!text-fail"><Icon.trash /></IconButton>
          </div>
        </div>

        {failed && (
          <p className="rounded-[3px] border border-fail/30 bg-fail-soft px-2.5 py-1.5 text-[13px] leading-snug text-fail" title={project.error_message ?? ''}>
            {friendlyError(project.error_message)}
          </p>
        )}

        <dl className="mt-auto flex items-center justify-between border-t border-dashed border-rule-strong pt-3">
          <div>
            <dt className="label !text-[10px]">Scanned</dt>
            <dd className="figure text-[13px]">{formatDate(project.scan_date)}</dd>
          </div>
          <div className="text-right">
            <dt className="label !text-[10px]">Frames</dt>
            <dd className="figure text-[13px]">{project.frame_count ?? (busy ? '…' : '–')}</dd>
          </div>
        </dl>
      </div>
    </article>
  )
}

function Skeleton() {
  return (
    <div className="sheet overflow-hidden" aria-hidden>
      <div className="aspect-[16/10] animate-pulse bg-[#dfe6eb]" />
      <div className="space-y-3 p-4">
        <div className="h-5 w-2/3 animate-pulse rounded bg-[#dfe6eb]" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-[#e9eef1]" />
      </div>
    </div>
  )
}

const STEPS = [
  ['Name a scan', 'Give the space a name, like "Main dining room".'],
  ['Upload a walkthrough', 'A slow 30 to 60 second video, shot on your phone.'],
  ['Explore the results', 'Objects, floor plan, analytics and an assistant that answers questions.'],
]

export default function Dashboard() {
  const [projects, setProjects] = useState(null)
  const [newName, setNewName] = useState('')
  const [error, setError] = useState('')
  const [toDelete, setToDelete] = useState(null)

  const fetchProjects = useCallback(async () => {
    try {
      const { data } = await api.get('/projects')
      setProjects(data)
      setError('')
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not load your scans. Check that the server is running.'))
      setProjects((p) => p ?? [])
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchProjects()
  }, [fetchProjects])

  // Keep cards live while anything is processing.
  const anyBusy = projects?.some((p) => PROCESSING.includes(p.status))
  useEffect(() => {
    if (!anyBusy) return
    const t = setInterval(fetchProjects, 4000)
    return () => clearInterval(t)
  }, [anyBusy, fetchProjects])

  const createProject = async (e) => {
    e.preventDefault()
    const name = newName.trim()
    if (!name) return
    try {
      await api.post('/projects', { name })
      setNewName('')
      fetchProjects()
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not create the scan.'))
    }
  }

  const renameProject = async (id, name) => {
    try {
      await api.patch(`/projects/${id}`, { name })
      fetchProjects()
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not rename the scan.'))
    }
  }

  const confirmDelete = async () => {
    const target = toDelete
    setToDelete(null)
    try {
      await api.delete(`/projects/${target.id}`)
      fetchProjects()
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not delete the scan.'))
    }
  }

  const ready = projects?.filter((p) => p.status === 'DONE').length ?? 0
  const working = projects?.filter((p) => PROCESSING.includes(p.status)).length ?? 0

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="label">Your scans</p>
            <h1 className="mt-1 text-4xl font-semibold sm:text-5xl">
              Scans
              {projects && <span className="figure ml-3 align-top text-2xl text-graphite">{String(projects.length).padStart(2, '0')}</span>}
            </h1>
            {projects?.length > 0 && (
              <p className="figure mt-2 text-[13px] text-graphite">
                {ready} ready · {working} processing
              </p>
            )}
          </div>

          <form onSubmit={createProject} className="flex w-full gap-2 md:max-w-md">
            <label className="sr-only" htmlFor="new-scan">New scan name</label>
            <input
              id="new-scan"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Name a new scan, e.g. Main dining room"
              maxLength={120}
              className="field"
            />
            <button type="submit" disabled={!newName.trim()} className="btn btn-flag">New scan</button>
          </form>
        </div>

        {error && (
          <p role="alert" className="mt-6 rounded-[3px] border border-fail/40 bg-fail-soft px-4 py-2.5 text-sm text-fail">{error}</p>
        )}

        <section className="mt-8" aria-live="polite">
          {projects === null ? (
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"><Skeleton /><Skeleton /><Skeleton /></div>
          ) : projects.length === 0 ? (
            <div className="sheet px-6 py-12 sm:px-12">
              <Corners className="text-ink/50" />
              <h2 className="text-2xl font-semibold">No scans yet</h2>
              <p className="mt-1 max-w-lg text-graphite">Name your first scan above. Here is how a scan goes:</p>
              <ol className="mt-8 grid gap-6 sm:grid-cols-3">
                {STEPS.map(([title, text], i) => (
                  <li key={title} className="border-t-2 border-ink pt-3">
                    <span className="figure text-sm text-flag-ink">{i + 1}</span>
                    <h3 className="mt-1 text-lg font-semibold">{title}</h3>
                    <p className="mt-1 text-sm text-graphite">{text}</p>
                  </li>
                ))}
              </ol>
            </div>
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {projects.map((p) => (
                <Card key={p.id} project={p} onRename={renameProject} onAskDelete={setToDelete} />
              ))}
            </div>
          )}
        </section>
      </main>

      <ConfirmDialog
        open={!!toDelete}
        title={`Delete "${toDelete?.name ?? ''}"?`}
        body="The video, extracted frames, results and any 3D model are removed for good."
        confirmLabel="Delete scan"
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </div>
  )
}
