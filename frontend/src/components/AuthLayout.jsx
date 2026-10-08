import { Logo } from './ui'
import RoomWireframe from './RoomWireframe'

const POINTS = [
  'Upload a walkthrough video from your phone',
  'See every chair, table and couch counted and placed on a plan',
  'Ask questions in plain English: capacity, free space, layout',
]

export default function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-viewport p-10 text-paper lg:flex">
        <Logo to="/login" dark />
        <div>
          <RoomWireframe />
          <h2 className="mt-4 max-w-md text-4xl font-semibold leading-[1.05]">
            Scan a room.<br />Count what's in it.
          </h2>
          <ul className="mt-6 max-w-md space-y-2.5 text-[15px] text-[#b8c7d3]">
            {POINTS.map((p) => (
              <li key={p} className="flex gap-3">
                <span className="mt-[9px] h-px w-4 shrink-0 bg-flag" aria-hidden />
                {p}
              </li>
            ))}
          </ul>
        </div>
        <p className="label !text-[#6f8394]">For restaurants, property managers, agents and designers</p>
      </aside>

      <main className="flex items-center justify-center px-5 py-12">
        <div className="rise w-full max-w-[400px]">
          <div className="mb-10 lg:hidden"><Logo to="/login" /></div>
          <h1 className="text-[34px] font-semibold">{title}</h1>
          <p className="mt-1.5 text-graphite">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <p className="mt-8 text-sm text-graphite">{footer}</p>
        </div>
      </main>
    </div>
  )
}
