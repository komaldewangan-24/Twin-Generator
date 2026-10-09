import { lazy, Suspense, useState } from 'react'
import { Spinner } from '../ui'
import { formatDate, totalObjects } from '../../lib/format'

const CountChart = lazy(() => import('./CountChart'))

function Row({ label, value, hint }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-dashed border-rule-strong py-3 last:border-0">
      <dt>
        <span className="label">{label}</span>
        {hint && <span className="mt-0.5 block text-xs text-graphite">{hint}</span>}
      </dt>
      <dd className="figure text-right text-xl">{value}</dd>
    </div>
  )
}

export default function AnalyticsTab({ analytics, detections, onCalibrate, onResetScale }) {
  const [w, setW] = useState('')
  const [d, setD] = useState('')
  const [busy, setBusy] = useState(false)

  const cal = analytics?.area?.calibration
  const layout = analytics?.layout
  const empty = analytics?.empty_space
  const seats = analytics?.seating_capacity
  const estimated = layout?.source === 'estimated'

  const submit = async (e) => {
    e.preventDefault()
    const width = parseFloat(w)
    const depth = d ? parseFloat(d) : undefined
    if (!(width > 0)) return
    setBusy(true)
    try { await onCalibrate(width, depth) } finally { setBusy(false) }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="sheet p-6">
        <h2 className="text-2xl font-semibold">Space at a glance</h2>
        <dl className="mt-3">
          <Row label="Zones" value={analytics?.rooms?.count ?? '–'} hint="Groups of furniture that sit together" />
          <Row label="Objects" value={totalObjects(detections)} />
          <Row
            label="Seating capacity"
            value={seats ? seats.total : '–'}
            hint={seats ? `${seats.breakdown.chairs} chairs, ${seats.breakdown.couch_seats} couch seats, ${seats.breakdown.bench_seats} bench seats` : undefined}
          />
          {layout ? (
            <>
              <Row
                label="Room size"
                value={`${estimated ? '~' : ''}${layout.width_m.toFixed(1)} × ${layout.depth_m.toFixed(1)} m`}
                hint={estimated ? 'Estimated from camera height. Measure something in the 3D view, or enter the room below, to correct it.' : 'Scaled to your measurement'}
              />
              <Row label="Floor area" value={`${estimated ? '~' : ''}${layout.area_m2} m²`} />
              <Row label="Ceiling height" value={`${estimated ? '~' : ''}${layout.ceiling_height_m} m`} />
              <Row
                label="Free floor space"
                value={empty?.percent != null ? `${empty.percent}%` : '–'}
                hint={empty ? `${empty.free_m2} m² · ${empty.note}` : undefined}
              />
            </>
          ) : (
            <Row
              label="Floor area"
              value={cal?.area_m2 != null ? `${cal.area_m2} m²` : 'Not set'}
              hint={cal ? 'From the size you entered' : 'No camera path was found, so size needs a measurement'}
            />
          )}
          <Row label="Scan date" value={formatDate(analytics?.scan_date)} />
        </dl>

        <form onSubmit={submit} className="mt-6 border-t border-ink pt-5">
          <h3 className="text-lg font-semibold">{layout ? 'Correct the scale' : 'Set the real size'}</h3>
          <p className="mt-1 text-sm text-graphite">
            {layout
              ? 'Sizes are estimated by assuming the phone was held at 1.4 m. Enter the real length of the room to make every size here exact. It is saved with the scan.'
              : 'Measure the scanned area with a tape. Width is the left-to-right distance in the video; depth is the distance from the camera to the far wall.'}
          </p>
          <div className="mt-4 grid grid-cols-[1fr_1fr_auto] items-end gap-3">
            <label className="block">
              <span className="label">{layout ? 'Longer side (m)' : 'Width (m)'}</span>
              <input type="number" inputMode="decimal" step="0.1" min="0.5" required value={w} onChange={(e) => setW(e.target.value)} className="field mt-1.5 figure" />
            </label>
            <label className="block">
              <span className="label">{layout ? 'Shorter side (m)' : 'Depth (m)'} · optional</span>
              <input type="number" inputMode="decimal" step="0.1" min="0.5" value={d} onChange={(e) => setD(e.target.value)} className="field mt-1.5 figure" />
            </label>
            <button type="submit" disabled={busy || !w} className="btn btn-ink">{busy ? 'Applying' : 'Apply'}</button>
          </div>
          {layout && !estimated && (
            <p className="mt-3 text-sm text-graphite">
              The scale is set from your measurement and saved with this scan.{' '}
              <button type="button" onClick={onResetScale} className="font-semibold text-ink underline decoration-flag decoration-2 underline-offset-4">Go back to the estimate</button>
            </p>
          )}
          {layout && (
            <p className="mt-3 text-sm text-graphite">Prefer to measure on the model? Open the 3D viewer, press Measure, click the two ends of something you know the length of.</p>
          )}
        </form>
      </section>

      <section className="sheet p-6">
        <h2 className="text-2xl font-semibold">Objects by kind</h2>
        <div className="mt-4">
          {detections.length ? (
            <Suspense fallback={<div className="grid h-40 place-items-center text-graphite"><Spinner /></div>}>
              <CountChart detections={detections} />
            </Suspense>
          ) : (
            <p className="text-graphite">Nothing to chart: no furniture was detected in this scan.</p>
          )}
        </div>
        {layout?.notes?.length > 0 && (
          <ul className="mt-4 space-y-1 border-l-2 border-flag pl-3 text-sm text-graphite">
            {layout.notes.map((n) => <li key={n}>{n}</li>)}
          </ul>
        )}
      </section>
    </div>
  )
}
