import { Icon } from '../ui'

const STEPS = [
  { key: 'UPLOADED', label: 'Video received' },
  { key: 'EXTRACTING', label: 'Extracting frames' },
  { key: 'POSES', label: 'Finding the camera path' },
  { key: 'DETECTING', label: 'Detecting and placing objects' },
  { key: 'TRAINING_3D', label: 'Building the 3D model' },
]

export default function ProcessingPanel({ status, frameCount, progress, fromPhotos = false }) {
  const steps = fromPhotos
    ? STEPS.map((s) => (s.key === 'UPLOADED' ? { ...s, label: 'Photos received' } : s.key === 'EXTRACTING' ? { ...s, label: 'Preparing the photos' } : s))
    : STEPS
  const active = Math.max(0, steps.findIndex((s) => s.key === status))
  const pct = progress ? Math.round(progress.fraction * 100) : null
  return (
    <div className="grid overflow-hidden rounded-[3px] border border-ink bg-viewport text-paper md:grid-cols-[1.4fr_1fr]">
      {/* "Scanning" field: a sweep line over a faint grid */}
      <div
        className="relative min-h-[280px] overflow-hidden border-b border-viewport-line md:border-b-0 md:border-r"
        style={{
          backgroundImage:
            'linear-gradient(#17242f 1px, transparent 1px), linear-gradient(90deg, #17242f 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      >
        <div className="absolute inset-x-0 top-0 h-full">
          <div className="animate-scan h-full">
            <div className="h-0.5 w-full bg-flag shadow-[0_0_18px_3px_rgb(255_90_31/0.55)]" />
          </div>
        </div>
        <div className="absolute bottom-5 left-6 right-6">
          <p className="label !text-flag">Analysing</p>
          <p className="mt-1 font-display text-3xl font-semibold">{steps[active].label}</p>
          <p className="figure mt-1 text-sm text-[#9db0be]" aria-live="polite">
            {progress?.message ?? (frameCount ? `${frameCount} frames extracted` : 'Starting')}
          </p>
          {pct != null && (
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-viewport-line" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full bg-flag transition-all duration-500" style={{ width: `${pct}%` }} />
            </div>
          )}
        </div>
      </div>

      <ol className="space-y-1 p-6" aria-label="Processing steps">
        {steps.map((s, i) => {
          const done = i < active
          const current = i === active
          return (
            <li key={s.key} className="flex items-center gap-3 py-2" aria-current={current ? 'step' : undefined}>
              <span
                className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border text-xs ${
                  done ? 'border-flag bg-flag text-ink' : current ? 'border-flag text-flag' : 'border-viewport-line text-[#5d7385]'
                }`}
              >
                {done ? <Icon.check /> : current ? <span className="h-2 w-2 animate-pulse rounded-full bg-flag" /> : ''}
              </span>
              <span className={current ? 'font-semibold' : done ? 'text-[#c7d4de]' : 'text-[#5d7385]'}>{s.label}</span>
            </li>
          )
        })}
        <li className="pt-3 text-sm text-[#7e92a2]">You can leave this page. Progress is saved. Building a 3D model can take 10 to 30 minutes.</li>
      </ol>
    </div>
  )
}
