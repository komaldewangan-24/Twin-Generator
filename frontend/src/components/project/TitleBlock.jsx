// The title block in the corner of an architectural drawing, repurposed as the
// scan's key figures. Every cell is real data from the project.
export default function TitleBlock({ items }) {
  return (
    <dl className="sheet grid grid-cols-2 gap-px overflow-hidden !bg-rule-strong sm:grid-cols-3 lg:grid-cols-6">
      {items.map((it) => (
        <div key={it.label} className="bg-sheet px-4 py-3">
          <dt className="label !text-[10px]">{it.label}</dt>
          <dd className={`figure mt-0.5 truncate ${it.big ? 'text-[28px] leading-9' : 'text-[15px] leading-9'}`} title={String(it.value)}>
            {it.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}
