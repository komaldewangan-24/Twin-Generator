// Isometric room, drawn line by line. Pure SVG, no assets.
const S = 38
const iso = (x, y, z) => [260 + (x - y) * 0.866 * S, 150 + (x + y) * 0.5 * S - z * S]
const pt = (x, y, z) => iso(x, y, z).map((n) => n.toFixed(1)).join(',')

function poly(points, key, delay, fill = 'none') {
  return (
    <polygon
      key={key}
      points={points.map((p) => pt(...p)).join(' ')}
      fill={fill}
      pathLength="1"
      className="animate-draw"
      style={{ strokeDasharray: 1, strokeDashoffset: 1, animationDelay: `${delay}s` }}
    />
  )
}

function box(x, y, w, d, h, key, delay, bg) {
  const z0 = 0
  return [
    poly([[x, y + d, z0], [x + w, y + d, z0], [x + w, y + d, h], [x, y + d, h]], `${key}a`, delay, bg),
    poly([[x + w, y, z0], [x + w, y + d, z0], [x + w, y + d, h], [x + w, y, h]], `${key}b`, delay + 0.1, bg),
    poly([[x, y, h], [x + w, y, h], [x + w, y + d, h], [x, y + d, h]], `${key}c`, delay + 0.2, bg),
  ]
}

export default function RoomWireframe({ bg = '#0b141c' }) {
  const W = 7, D = 6, H = 3.2
  const grid = []
  for (let i = 1; i < W; i++) grid.push(<line key={`gx${i}`} x1={pt(i, 0, 0).split(',')[0]} y1={pt(i, 0, 0).split(',')[1]} x2={pt(i, D, 0).split(',')[0]} y2={pt(i, D, 0).split(',')[1]} />)
  for (let j = 1; j < D; j++) grid.push(<line key={`gy${j}`} x1={pt(0, j, 0).split(',')[0]} y1={pt(0, j, 0).split(',')[1]} x2={pt(W, j, 0).split(',')[0]} y2={pt(W, j, 0).split(',')[1]} />)

  const pins = [
    { at: [3.4, 3.2, 1.1], label: 'table ×1', dx: 36, dy: -46 },
    { at: [2.2, 4.6, 0.9], label: 'chair ×4', dx: -118, dy: 6 },
  ]

  return (
    <svg viewBox="0 10 520 430" role="img" aria-label="Wireframe of a room with a table, chairs and a sofa" className="mx-auto w-full max-h-[40vh]">
      <g fill="none" stroke="#2c4152" strokeWidth="0.8">{grid}</g>
      <g fill="none" stroke="#e9eef1" strokeWidth="1.4" strokeLinejoin="round">
        {poly([[0, 0, 0], [W, 0, 0], [W, D, 0], [0, D, 0]], 'floor', 0)}
        {poly([[0, 0, 0], [W, 0, 0], [W, 0, H], [0, 0, H]], 'wallR', 0.3)}
        {poly([[0, 0, 0], [0, D, 0], [0, D, H], [0, 0, H]], 'wallL', 0.5)}
        {/* window */}
        {poly([[2, 0, 1.2], [4.6, 0, 1.2], [4.6, 0, 2.7], [2, 0, 2.7]], 'win', 0.9)}
        {/* table and chairs */}
        {box(2.6, 2.4, 2.0, 1.4, 0.9, 't', 1.1, bg)}
        {box(2.8, 1.5, 0.7, 0.7, 0.55, 'c1', 1.4, bg)}
        {box(3.9, 1.5, 0.7, 0.7, 0.55, 'c2', 1.5, bg)}
        {box(2.8, 4.0, 0.7, 0.7, 0.55, 'c3', 1.6, bg)}
        {box(3.9, 4.0, 0.7, 0.7, 0.55, 'c4', 1.7, bg)}
        {/* sofa */}
        {box(5.2, 0.5, 1.4, 2.4, 0.8, 's', 1.9, bg)}
      </g>
      {pins.map((p, i) => {
        const [x, y] = iso(...p.at)
        return (
          <g key={p.label} className="animate-rise" style={{ animationDelay: `${2 + i * 0.25}s` }}>
            <path d={`M${x} ${y} L${x + p.dx * 0.6} ${y + p.dy * 0.6} H${x + p.dx}`} fill="none" stroke="#ff5a1f" strokeWidth="1.2" />
            <circle cx={x} cy={y} r="4" fill="#ff5a1f" stroke="#0b141c" strokeWidth="1.5" />
            <text x={x + p.dx + (p.dx > 0 ? 6 : -6)} y={y + p.dy * 0.6 + 4} textAnchor={p.dx > 0 ? 'start' : 'end'} fill="#ff5a1f" fontFamily="IBM Plex Mono, monospace" fontSize="11" fontWeight="500">
              {p.label}
            </text>
          </g>
        )
      })}
      <g className="animate-rise" style={{ animationDelay: '2.4s' }} fill="none" stroke="#8fa3b3" strokeWidth="1">
        <path d={`M${pt(0, D + 0.5, 0)} L${pt(W, D + 0.5, 0)} M${pt(0, D + 0.35, 0)} v${S * 0.3} M${pt(W, D + 0.35, 0)} v${S * 0.3}`.replace(/(\d),(\d)/g, '$1 $2')} />
        <text x={iso(W / 2, D + 0.9, 0)[0]} y={iso(W / 2, D + 0.9, 0)[1] + 14} textAnchor="middle" fill="#8fa3b3" stroke="none" fontFamily="IBM Plex Mono, monospace" fontSize="11">4.2 m</text>
      </g>
    </svg>
  )
}
