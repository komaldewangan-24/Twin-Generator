// Small architectural-plan symbols (same vocabulary as lib/floorplan.js).
const P = { fill: '#fafbfb', stroke: '#0e1b26', strokeWidth: 1.4, strokeLinejoin: 'round' }

const GLYPHS = {
  chair: (<><rect x="5" y="5" width="14" height="14" rx="2" {...P} /><path d="M6 6.5h12" stroke="#0e1b26" strokeWidth="3.2" strokeLinecap="round" /></>),
  couch: (<><rect x="2" y="7" width="20" height="10" rx="2.5" {...P} /><path d="M6.5 7v10M17.5 7v10" stroke="#0e1b26" strokeWidth="1.2" /></>),
  'dining table': (<><rect x="3" y="6" width="18" height="12" rx="2" {...P} /><rect x="6" y="9" width="12" height="6" rx="1" {...P} strokeWidth="0.9" /></>),
  bed: (<><rect x="3" y="4" width="18" height="16" rx="2" {...P} /><rect x="5.5" y="6.5" width="13" height="4" rx="1" {...P} strokeWidth="1" /></>),
  'potted plant': (<><circle cx="12" cy="12" r="7" {...P} /><path d="M12 12 8 8M12 12l4-4M12 12l-4 4M12 12l4 4" stroke="#0e1b26" strokeWidth="1" /></>),
  tv: (<rect x="2.5" y="10" width="19" height="4" rx="1" fill="#0e1b26" stroke="#0e1b26" strokeWidth="1.4" />),
  clock: (<><circle cx="12" cy="12" r="7" {...P} /><path d="M12 12V8M12 12l3 1.5" stroke="#0e1b26" strokeWidth="1.2" strokeLinecap="round" /></>),
  sink: (<><rect x="3" y="6" width="18" height="12" rx="2" {...P} /><ellipse cx="12" cy="12.5" rx="5" ry="3.2" {...P} strokeWidth="1" /></>),
  refrigerator: (<><rect x="6" y="3" width="12" height="18" rx="2" {...P} /><path d="M6 9h12" stroke="#0e1b26" strokeWidth="1.2" /></>),
  bench: (<rect x="2.5" y="9" width="19" height="6" rx="1.5" {...P} />),
}

export default function ObjectGlyph({ cls, size = 24 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      {GLYPHS[cls] ?? <rect x="5" y="5" width="14" height="14" rx="2" {...P} />}
    </svg>
  )
}
