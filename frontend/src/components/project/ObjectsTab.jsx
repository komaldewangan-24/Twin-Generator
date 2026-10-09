import ObjectGlyph from '../ObjectGlyph'
import { classLabel, classSingular, totalObjects } from '../../lib/format'

export default function ObjectsTab({ detections, meta, onShow3D }) {
  const inSpace = meta?.unit === 'm'
  if (detections.length === 0 && meta?.detector_error) {
    return (
      <div className="sheet p-10 text-center">
        <h2 className="text-2xl font-semibold">Objects could not be detected</h2>
        <p className="mx-auto mt-2 max-w-md text-graphite">
          The object detector is not set up on this computer, so only the 3D model and room size are available.
          Export the detector model once (see the README, "Model weights") and process the video again, or run{' '}
          <span className="font-mono text-sm">python backend/scripts/doctor.py</span> to see what is missing.
        </p>
      </div>
    )
  }
  if (detections.length === 0) {
    return (
      <div className="sheet p-10 text-center">
        <h2 className="text-2xl font-semibold">No furniture found</h2>
        <p className="mx-auto mt-2 max-w-md text-graphite">
          The detector did not find anything it recognises above its confidence threshold. Try a slower video
          with better light, filmed so each piece of furniture stays in view for a few seconds.
        </p>
      </div>
    )
  }
  const sorted = [...detections].sort((a, b) => b.count - a.count)
  const max = sorted[0].count

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-2xl font-semibold">What was found</h2>
        <p className="figure text-sm text-graphite">{totalObjects(detections)} objects · {detections.length} kinds</p>
      </div>

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sorted.map((d, i) => {
          const avg = d.positions.length ? d.positions.reduce((s, p) => s + p.confidence, 0) / d.positions.length : 0
          return (
            <li key={d.class} className="sheet rise p-4" style={{ animationDelay: `${i * 40}ms` }}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <span className="grid h-10 w-10 place-items-center rounded-[3px] border border-rule-strong bg-white"><ObjectGlyph cls={d.class} size={26} /></span>
                  <h3 className="text-lg font-semibold">{classLabel(d.class)}</h3>
                </div>
                <span className="figure text-4xl leading-none">{d.count}</span>
              </div>
              <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-[#dde4e9]" aria-hidden>
                <div className={`h-full ${i === 0 ? 'bg-flag' : 'bg-ink'}`} style={{ width: `${(d.count / max) * 100}%` }} />
              </div>
              <p className="label mt-3 !text-[10px]">Average confidence <span className="figure ml-1 text-ink">{Math.round(avg * 100)}%</span></p>
              {onShow3D && d.positions.some((p) => p.world) && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {d.positions.map((p, n) => p.world && (
                    <button
                      key={n}
                      onClick={() => onShow3D(d.class, n)}
                      className="rounded-[3px] border border-rule-strong bg-white px-2 py-1 font-mono text-[11px] font-medium uppercase tracking-wider transition hover:border-ink hover:bg-flag-soft"
                      title={`Fly to ${classSingular(d.class).toLowerCase()} ${n + 1} in the 3D model`}
                    >
                      {d.count > 1 ? `#${n + 1} · ` : ''}Show in 3D
                    </button>
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ul>

      <div className="mt-6 grid gap-3 text-sm text-graphite md:grid-cols-2">
        {inSpace ? (
          <p className="border-l-2 border-go pl-3">
            Counted in 3D: each object is placed on the floor and merged across video frames, and must be seen in at
            least {2} frames to count. Counts can still be off if a piece is hidden or looks like another.
          </p>
        ) : (
          <p className="border-l-2 border-flag pl-3">
            {meta?.reconstruction_error
              ? `No 3D camera path was found (${meta.reconstruction_error}), so counts come from the camera view and can double-count.`
              : 'Counts come from the camera view, so one object seen from two angles can be counted twice.'}
          </p>
        )}
        <p className="border-l-2 border-rule-strong pl-3">
          Doors, windows, counters and lights are not detected unless the optional open-vocabulary model is installed.
        </p>
      </div>
    </div>
  )
}
