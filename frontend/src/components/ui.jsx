import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { STATUS_LABEL } from '../lib/format'

/** Registration marks in the four corners, like the crop marks on a drawing. */
export function Corners({ className = '', color = 'currentColor', size = 10 }) {
  const base = { position: 'absolute', width: size, height: size, borderColor: color, borderStyle: 'solid', borderWidth: 0 }
  return (
    <span aria-hidden className={`pointer-events-none ${className}`}>
      <span style={{ ...base, top: 6, left: 6, borderTopWidth: 1.5, borderLeftWidth: 1.5 }} />
      <span style={{ ...base, top: 6, right: 6, borderTopWidth: 1.5, borderRightWidth: 1.5 }} />
      <span style={{ ...base, bottom: 6, left: 6, borderBottomWidth: 1.5, borderLeftWidth: 1.5 }} />
      <span style={{ ...base, bottom: 6, right: 6, borderBottomWidth: 1.5, borderRightWidth: 1.5 }} />
    </span>
  )
}

export function Logo({ to = '/', dark = false, compact = false }) {
  return (
    <Link to={to} className="flex items-center gap-2.5" aria-label="Digital Twin Generator, home">
      <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden>
        <path d="M13 2 23 7.5v11L13 24 3 18.5v-11L13 2Z" stroke={dark ? '#e9eef1' : '#0e1b26'} strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M3 7.5 13 13l10-5.5M13 13v11" stroke={dark ? '#e9eef1' : '#0e1b26'} strokeWidth="1.6" strokeLinejoin="round" />
        <circle cx="13" cy="13" r="2.6" fill="#ff5a1f" stroke={dark ? '#e9eef1' : '#0e1b26'} strokeWidth="1.2" />
      </svg>
      <span className={`whitespace-nowrap font-display text-[17px] font-semibold tracking-tight ${compact ? 'hidden sm:inline' : ''} ${dark ? 'text-paper' : 'text-ink'}`}>
        Digital Twin <span className="font-normal opacity-70">Generator</span>
      </span>
    </Link>
  )
}

const PILL = {
  CREATED: 'border-rule-strong bg-white text-graphite',
  UPLOADED: 'border-plumb/40 bg-plumb-soft text-plumb',
  EXTRACTING: 'border-plumb/40 bg-plumb-soft text-plumb',
  POSES: 'border-plumb/40 bg-plumb-soft text-plumb',
  DETECTING: 'border-plumb/40 bg-plumb-soft text-plumb',
  TRAINING_3D: 'border-plumb/40 bg-plumb-soft text-plumb',
  DONE: 'border-go/40 bg-go-soft text-go',
  FAILED: 'border-fail/40 bg-fail-soft text-fail',
}

export function StatusPill({ status, className = '' }) {
  const busy = ['UPLOADED', 'EXTRACTING', 'POSES', 'DETECTING', 'TRAINING_3D'].includes(status)
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-wider ${PILL[status] ?? PILL.CREATED} ${className}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full bg-current ${busy ? 'animate-pulse' : ''}`}
        aria-hidden
      />
      {STATUS_LABEL[status] ?? status}
    </span>
  )
}

export function Spinner({ className = 'h-5 w-5' }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
    />
  )
}

/** Native <dialog>: focus trap, Esc to close and backdrop come for free. */
export function ConfirmDialog({ open, title, body, confirmLabel, onConfirm, onCancel }) {
  const ref = useRef(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onCancel}
      onClick={(e) => e.target === ref.current && onCancel()}
      className="m-auto w-[min(92vw,420px)] rounded-[3px] border border-ink bg-sheet p-0 text-ink shadow-[6px_6px_0_var(--color-ink)] backdrop:bg-ink/50"
    >
      <div className="p-6">
        <h2 className="text-xl font-semibold">{title}</h2>
        <p className="mt-2 text-graphite">{body}</p>
        <div className="mt-6 flex justify-end gap-2">
          <button className="btn btn-ghost" onClick={onCancel} autoFocus>Cancel</button>
          <button className="btn btn-ink" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </dialog>
  )
}

export function IconButton({ label, children, className = '', ...props }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={`grid h-8 w-8 place-items-center rounded-[3px] border border-transparent text-graphite transition hover:border-rule-strong hover:bg-white hover:text-ink ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

export const Icon = {
  pencil: (p) => (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" {...p}><path d="m11 2.5 2.5 2.5L5.5 13H3v-2.5L11 2.5Z" /></svg>
  ),
  trash: (p) => (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.5 8.5h6l.5-8.5" /></svg>
  ),
  mic: (p) => (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" {...p}><rect x="7.5" y="2" width="5" height="10" rx="2.5" /><path d="M4.5 9.5a5.5 5.5 0 0 0 11 0M10 15v3" /></svg>
  ),
  expand: (p) => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M2 6V2h4M14 6V2h-4M2 10v4h4M14 10v4h-4" /></svg>
  ),
  camera: (p) => (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" {...p}><path d="M2.5 6.5h3L7 4h6l1.5 2.5h3v9h-15v-9Z" /><circle cx="10" cy="11" r="3" /></svg>
  ),
  upload: (p) => (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M10 13V3M6 7l4-4 4 4M3 13v4h14v-4" /></svg>
  ),
  file: (p) => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" {...p}><path d="M3.5 1.5h6l3 3v10h-9v-13Z M9.5 1.5v3h3" /></svg>
  ),
  check: (p) => (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="m2.5 7.5 3 3 6-7" /></svg>
  ),
}
