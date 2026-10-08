import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { Logo } from './ui'

export default function AppHeader({ crumb }) {
  const logout = useAuthStore((s) => s.logout)
  return (
    <header className="sticky top-0 z-30 border-b border-rule-strong bg-paper/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Logo to="/dashboard" compact={!!crumb} />
          {crumb && (
            <>
              <span className="hidden text-rule-strong sm:inline" aria-hidden>/</span>
              <Link to="/dashboard" className="label hidden hover:text-ink sm:inline">Scans</Link>
              <span className="text-rule-strong" aria-hidden>/</span>
              <span className="label truncate text-ink">{crumb}</span>
            </>
          )}
        </div>
        <button onClick={logout} className="btn btn-ghost py-2">Log out</button>
      </div>
    </header>
  )
}
