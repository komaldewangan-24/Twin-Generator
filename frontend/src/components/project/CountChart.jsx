import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { classLabel } from '../../lib/format'

const tick = { fontFamily: 'IBM Plex Mono, monospace', fontSize: 12, fill: '#0e1b26' }

export default function CountChart({ detections }) {
  const data = [...detections].sort((a, b) => b.count - a.count).map((d) => ({ name: classLabel(d.class), count: d.count }))
  return (
    <div style={{ height: data.length * 44 + 16 }} role="img" aria-label="Bar chart of object counts">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 36, bottom: 0, left: 0 }}>
          <XAxis type="number" hide domain={[0, 'dataMax']} />
          <YAxis type="category" dataKey="name" width={92} tick={tick} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: 'rgba(14,27,38,0.05)' }} contentStyle={{ border: '1px solid #0e1b26', borderRadius: 3, fontFamily: 'IBM Plex Mono, monospace', fontSize: 12 }} />
          <Bar dataKey="count" radius={[0, 2, 2, 0]} barSize={22} label={{ position: 'right', ...tick, fontWeight: 500 }} isAnimationActive={false}>
            {data.map((_, i) => <Cell key={i} fill={i === 0 ? '#ff5a1f' : '#0e1b26'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
