import { useState } from 'react'
import { dist, formatLength, parseLength } from '../../lib/measure'

/**
 * The list of measurements, and the way to correct the scan's scale from one of them:
 * "this one is really 2.1 m" fixes every size in the app.
 */
export default function MeasurePanel({ items, metersPerUnit, estimated, measured, hasPending, onRemove, onClear, onCalibrate, onReset }) {
  const [editing, setEditing] = useState(null)
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const open = (id) => { setEditing(id); setText(''); setError('') }

  const submit = async (e, item) => {
    e.preventDefault()
    const metres = parseLength(text)
    if (!metres) return setError('Enter a length such as 2.1, 210 cm or 7 ft.')
    setBusy(true)
    const failure = await onCalibrate(item, metres)
    setBusy(false)
    if (failure) setError(failure)
    else setEditing(null)
  }

  return (
    <section
      aria-label="Measure"
      className="absolute left-4 top-16 z-20 w-72 max-w-[calc(100%-2rem)] rounded-[3px] border border-viewport-line bg-viewport/90 p-3 text-sm text-[#c7d4de] shadow-xl backdrop-blur"
    >
      <p className="font-display text-base font-semibold text-paper">Measure</p>
      <p className="mt-1 text-xs text-[#9db0be]" role="status">
        {hasPending ? 'Now click the second point.' : items.length ? 'Click two more points for another measurement.' : 'Click two points on the model to measure between them.'}
      </p>

      {items.length > 0 && (
        <ul className="mt-3 space-y-2">
          {items.map((it, i) => (
            <li key={it.id} className="rounded-[3px] border border-viewport-line p-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-paper">
                  <span className="mr-2 text-[#7e92a2]">{i + 1}</span>
                  {estimated ? '≈ ' : ''}{formatLength(dist(it.a, it.b) * metersPerUnit)}
                </span>
                <span className="flex items-center gap-1">
                  <button onClick={() => (editing === it.id ? setEditing(null) : open(it.id))} className="rounded px-2 py-1 text-xs font-semibold text-flag hover:bg-white/10" aria-expanded={editing === it.id}>
                    I know this length
                  </button>
                  <button onClick={() => onRemove(it.id)} aria-label={`Remove measurement ${i + 1}`} className="grid h-6 w-6 place-items-center rounded text-[#9db0be] hover:bg-white/10 hover:text-paper">×</button>
                </span>
              </div>
              {editing === it.id && (
                <form onSubmit={(e) => submit(e, it)} className="mt-2">
                  <label className="block text-xs text-[#9db0be]">
                    Its real length
                    <span className="mt-1 flex gap-2">
                      <input
                        autoFocus
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        placeholder="2.1 m, 210 cm, 7 ft"
                        className="min-w-0 flex-1 rounded-[3px] border border-viewport-line bg-black/30 px-2 py-1.5 font-mono text-paper placeholder:text-[#5f7384] focus:border-flag focus:outline-none"
                      />
                      <button type="submit" disabled={busy || !text.trim()} className="btn btn-flag !px-3 !py-1.5 text-xs">{busy ? 'Saving' : 'Set scale'}</button>
                    </span>
                  </label>
                  {error && <p role="alert" className="mt-1.5 text-xs text-[#f3b9a6]">{error}</p>}
                  <p className="mt-1.5 text-xs text-[#7e92a2]">Pick two ends of something you can measure: a door frame, a sheet of paper, a tape laid on the floor. Floor plan, sizes and PDF all follow.</p>
                </form>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex items-center justify-between gap-2 text-xs">
        <span className="text-[#9db0be]">
          {measured ? 'Scale set from your measurement' : 'Scale estimated from camera height'}
        </span>
        <span className="flex gap-1">
          {measured && <button onClick={onReset} className="rounded px-2 py-1 font-semibold text-flag hover:bg-white/10">Reset</button>}
          {items.length > 0 && <button onClick={onClear} className="rounded px-2 py-1 font-semibold text-[#c7d4de] hover:bg-white/10">Clear all</button>}
        </span>
      </div>
    </section>
  )
}
