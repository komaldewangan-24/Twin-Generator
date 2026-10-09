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
  // parts of the room: a door in its wall with the swing, a window as glazing lines, a ceiling light
  door: (<><path d="M3 20h18" stroke="#0e1b26" strokeWidth="2.2" strokeLinecap="round" /><path d="M6 20V6" stroke="#0e1b26" strokeWidth="2" strokeLinecap="round" /><path d="M6 6a14 14 0 0 1 14 14" fill="none" stroke="#0e1b26" strokeWidth="1.1" strokeDasharray="2.5 2" /></>),
  window: (<><rect x="3" y="9.5" width="18" height="5" {...P} fill="#e3f1fa" /><path d="M3 12h18" stroke="#4f86b5" strokeWidth="1.6" /></>),
  light: (<><circle cx="12" cy="12" r="5" {...P} /><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" stroke="#0e1b26" strokeWidth="1.2" strokeLinecap="round" /></>),
  cabinet: (<><rect x="4" y="5" width="16" height="14" rx="1.5" {...P} /><path d="M12 5v14M10 12v-1.5M14 12v-1.5" stroke="#0e1b26" strokeWidth="1.2" strokeLinecap="round" /></>),
  shelf: (<><rect x="4" y="4" width="16" height="16" rx="1.5" {...P} /><path d="M4 9.3h16M4 14.7h16" stroke="#0e1b26" strokeWidth="1.2" /></>),
  counter: (<><rect x="2.5" y="7" width="19" height="10" rx="1.5" {...P} /><path d="M2.5 11h19" stroke="#0e1b26" strokeWidth="1" /></>),
  picture: (<><rect x="4" y="5" width="16" height="14" rx="1" {...P} /><path d="M6.5 16l3.5-4 3 3 2-2 2.5 3" fill="none" stroke="#0e1b26" strokeWidth="1.2" strokeLinejoin="round" /></>),
  curtain: (<><path d="M4 4h16M5 4v16M19 4v16" stroke="#0e1b26" strokeWidth="1.6" strokeLinecap="round" /><path d="M5 4c3 5 3 11 0 16M19 4c-3 5-3 11 0 16" fill="none" stroke="#0e1b26" strokeWidth="1.2" /></>),
}

export default function ObjectGlyph({ cls, size = 24 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      {GLYPHS[cls] ?? <rect x="5" y="5" width="14" height="14" rx="2" {...P} />}
    </svg>
  )
}
