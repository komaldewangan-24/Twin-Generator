const STEPS = [
  { key: 'UPLOADED', label: 'Video uploaded' },
  { key: 'EXTRACTING', label: 'Extracting frames' },
  { key: 'DETECTING', label: 'Detecting objects' },
  { key: 'DONE', label: 'Analysis complete' },
]

export default function StatusTimeline({ status, errorMessage, splatReady }) {
  const activeIndex = STEPS.findIndex((s) => s.key === status)

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
      <div className="space-y-3">
        {STEPS.map((step, i) => {
          const done = status === 'DONE' || (status !== 'FAILED' && i <= activeIndex && status !== 'CREATED')
          const active = status !== 'FAILED' && i === activeIndex
          return (
            <div key={step.key} className="flex items-center gap-3">
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                  done
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : active
                      ? 'bg-blue-500/20 text-blue-400'
                      : 'bg-slate-800 text-slate-600'
                }`}
              >
                {done ? '✓' : active ? '•' : i + 1}
              </span>
              <span className={`text-sm ${done ? 'text-slate-200' : active ? 'text-blue-300' : 'text-slate-600'}`}>
                {step.label}
                {active && <span className="ml-2 text-xs text-blue-400">processing…</span>}
              </span>
            </div>
          )
        })}
        <div className="flex items-center gap-3">
          <span
            className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
              splatReady ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-600'
            }`}
          >
            {splatReady ? '✓' : '5'}
          </span>
          <span className={`text-sm ${splatReady ? 'text-slate-200' : 'text-slate-500'}`}>
            3D model{splatReady ? '' : ' (attach .ply to enable viewer)'}
          </span>
        </div>
      </div>

      {errorMessage && (
        <div className="mt-4 rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400">
          <span className="font-semibold">Pipeline failed:</span> {errorMessage}
        </div>
      )}
    </div>
  )
}