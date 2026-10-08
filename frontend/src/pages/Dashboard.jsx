import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import { useAuthStore } from '../stores/authStore'

const STATUS_STYLE = {
  CREATED: 'bg-slate-500/20 text-slate-300',
  EXTRACTING: 'bg-amber-500/20 text-amber-300',
  TRAINING_3D: 'bg-blue-500/20 text-blue-300',
  DETECTING: 'bg-purple-500/20 text-purple-300',
  DONE: 'bg-emerald-500/20 text-emerald-300',
  FAILED: 'bg-red-500/20 text-red-300',
}

function Card({ project, onRename, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(project.name)

  const saveName = () => {
    onRename(project.id, name.trim())
    setEditing(false)
  }

  return (
    <div className="group rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-lg transition hover:border-slate-700">
      <Link to={`/project/${project.id}`} className="block">
        <div className="flex items-start justify-between gap-3">
          {editing ? (
            <input
              value={name}
              autoFocus
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => setName(e.target.value)}
              onBlur={saveName}
              onKeyDown={(e) => e.key === 'Enter' && saveName()}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-2 py-1 text-lg font-semibold text-white outline-none"
            />
          ) : (
            <h3 className="text-lg font-semibold text-white group-hover:text-emerald-300">{project.name}</h3>
          )}
          <div className="flex gap-1" onClick={(e) => e.preventDefault()} onKeyDown={(e) => e.preventDefault()}>
            <button
              onClick={(e) => {
                e.preventDefault()
                setEditing(true)
              }}
              title="Rename"
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-800 hover:text-white"
            >
              ✎
            </button>
            <button
              onClick={(e) => {
                e.preventDefault()
                onDelete(project.id)
              }}
              title="Delete"
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-red-500/10 hover:text-red-400"
            >
              🗑
            </button>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <span
            className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLE[project.status] ?? STATUS_STYLE.CREATED}`}
          >
            {project.status}
          </span>
          <span className="text-xs text-slate-500">
            {new Date(project.scan_date).toLocaleDateString(undefined, {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
            })}
          </span>
        </div>

        {project.status === 'FAILED' && project.error_message && (
          <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-400">
            {project.error_message}
          </p>
        )}

        <p className="mt-4 text-xs font-semibold text-slate-500 transition group-hover:text-emerald-400">
          Open workspace →
        </p>
      </Link>
    </div>
  )
}

export default function Dashboard() {
  const [projects, setProjects] = useState([])
  const [newName, setNewName] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const logout = useAuthStore((s) => s.logout)

  const fetchProjects = useCallback(async () => {
    try {
      const { data } = await api.get('/projects')
      setProjects(data)
      setError('')
    } catch {
      setError('Failed to load projects')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  const createProject = async (e) => {
    e.preventDefault()
    if (!newName.trim()) return
    try {
      await api.post('/projects', { name: newName.trim() })
      setNewName('')
      fetchProjects()
    } catch {
      setError('Failed to create project')
    }
  }

  const renameProject = async (id, name) => {
    if (!name) return
    try {
      await api.patch(`/projects/${id}`, { name })
      fetchProjects()
    } catch {
      setError('Failed to rename project')
    }
  }

  const deleteProject = async (id) => {
    if (!window.confirm('Delete this project permanently?')) return
    try {
      await api.delete(`/projects/${id}`)
      fetchProjects()
    } catch {
      setError('Failed to delete project')
    }
  }

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="border-b border-slate-800 bg-slate-900/50">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-bold text-white">AI Digital Twin Generator</h1>
            <p className="text-sm text-slate-400">Your scan projects</p>
          </div>
          <button
            onClick={logout}
            className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:border-red-500/50 hover:text-red-400"
          >
            Log out
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <form onSubmit={createProject} className="mb-8 flex gap-3">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New scan name (e.g. Living Room)"
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-white placeholder-slate-500 outline-none focus:border-slate-500"
          />
          <button
            type="submit"
            className="rounded-lg bg-emerald-600 px-6 py-2.5 font-semibold text-white transition hover:bg-emerald-500"
          >
            New Scan
          </button>
        </form>

        {error && (
          <p className="mb-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-400">
            {error}
          </p>
        )}

        {loading ? (
          <p className="text-slate-500">Loading projects...</p>
        ) : projects.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center text-slate-500">
            No scans yet. Create your first project above.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <Card
                key={project.id}
                project={project}
                onRename={renameProject}
                onDelete={deleteProject}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}