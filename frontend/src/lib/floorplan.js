// Draws the schematic floor plan. Used by the on-screen canvas AND the PDF
// report, so both always show the same drawing.

export const INK = '#0e1b26'
export const FLAG = '#ff5a1f'
const RULE = '#dfe5ea'
const RULE_STRONG = '#b8c3cc'
const SHEET = '#fafbfb'
const GRAPHITE = '#4a5966'

// Symbols are drawn in a local box centred on (0,0): [width, height] in px.
const SIZE = {
  chair: [15, 15],
  couch: [38, 17],
  'dining table': [34, 22],
  bed: [32, 24],
  'potted plant': [16, 16],
  tv: [28, 7],
  sink: [20, 14],
  refrigerator: [18, 20],
  bench: [30, 9],
  microwave: [18, 12],
  oven: [20, 18],
  toilet: [12, 18],
  clock: [14, 14],
}

function rr(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, r)
}

export function drawSymbol(ctx, cls, cx, cy, { active = false } = {}) {
  const [w, h] = SIZE[cls] ?? [14, 14]
  ctx.save()
  ctx.translate(cx, cy)
  ctx.lineWidth = active ? 2.2 : 1.5
  ctx.strokeStyle = INK
  ctx.fillStyle = active ? '#ffe4d9' : SHEET
  const x = -w / 2
  const y = -h / 2

  switch (cls) {
    case 'chair':
      rr(ctx, x, y, w, h, 2); ctx.fill(); ctx.stroke()
      ctx.lineWidth = 3.4; ctx.beginPath(); ctx.moveTo(x + 1, y + 1); ctx.lineTo(x + w - 1, y + 1); ctx.stroke()
      break
    case 'couch':
      rr(ctx, x, y, w, h, 3); ctx.fill(); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(x + 5, y); ctx.lineTo(x + 5, y + h); ctx.moveTo(x + w - 5, y); ctx.lineTo(x + w - 5, y + h); ctx.stroke()
      break
    case 'dining table':
      rr(ctx, x, y, w, h, 3); ctx.fill(); ctx.stroke()
      ctx.lineWidth = 0.9; rr(ctx, x + 4, y + 4, w - 8, h - 8, 1.5); ctx.stroke()
      break
    case 'bed':
      rr(ctx, x, y, w, h, 2); ctx.fill(); ctx.stroke()
      rr(ctx, x + 3, y + 3, w - 6, 6, 1.5); ctx.stroke()
      break
    case 'potted plant':
      ctx.beginPath(); ctx.arc(0, 0, w / 2, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
      ctx.lineWidth = 1; ctx.beginPath()
      for (let i = 0; i < 4; i++) { const a = (i * Math.PI) / 2 + Math.PI / 4; ctx.moveTo(0, 0); ctx.lineTo(Math.cos(a) * 5.5, Math.sin(a) * 5.5) }
      ctx.stroke()
      break
    case 'tv':
      rr(ctx, x, y, w, h, 1.5); ctx.fillStyle = INK; ctx.fill(); ctx.stroke()
      break
    case 'clock':
      ctx.beginPath(); ctx.arc(0, 0, w / 2, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
      ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -4); ctx.moveTo(0, 0); ctx.lineTo(3, 1); ctx.stroke()
      break
    case 'sink':
      rr(ctx, x, y, w, h, 2); ctx.fill(); ctx.stroke()
      ctx.beginPath(); ctx.ellipse(0, 1, 5.5, 3.5, 0, 0, Math.PI * 2); ctx.stroke()
      break
    case 'refrigerator':
      rr(ctx, x, y, w, h, 2); ctx.fill(); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(x, y + h * 0.38); ctx.lineTo(x + w, y + h * 0.38); ctx.stroke()
      break
    default:
      rr(ctx, x, y, w, h, 2); ctx.fill(); ctx.stroke()
  }
  ctx.restore()
}

function tick(ctx, x1, y1, x2, y2) {
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
}

/** Dimension line with end ticks and a centred label. */
function dimension(ctx, x1, y1, x2, y2, label, { vertical = false } = {}) {
  ctx.save()
  ctx.strokeStyle = GRAPHITE
  ctx.fillStyle = GRAPHITE
  ctx.lineWidth = 1
  tick(ctx, x1, y1, x2, y2)
  const d = 5
  if (vertical) { tick(ctx, x1 - d, y1, x1 + d, y1); tick(ctx, x2 - d, y2, x2 + d, y2) }
  else { tick(ctx, x1, y1 - d, x1, y1 + d); tick(ctx, x2, y2 - d, x2, y2 + d) }
  ctx.font = '500 11px "IBM Plex Mono", monospace'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  const mx = (x1 + x2) / 2
  const my = (y1 + y2) / 2
  const tw = ctx.measureText(label).width + 10
  ctx.save()
  ctx.translate(mx, my)
  if (vertical) ctx.rotate(-Math.PI / 2)
  ctx.fillStyle = SHEET
  ctx.fillRect(-tw / 2, -8, tw, 16)
  ctx.fillStyle = INK
  ctx.fillText(label, 0, 0.5)
  ctx.restore()
  ctx.restore()
}

/**
 * @param layout  real-world layout from the backend (metres), or null for the
 *                legacy camera-view mode.
 * @returns hit targets [{x, y, r, cls, confidence}] in canvas px, for tooltips.
 */
function drawSchematic(ctx, W, H, { detections = [], rooms = [], layout = null, calibration = null, showHeatmap = false, hover = null } = {}) {
  ctx.clearRect(0, 0, W, H)
  ctx.fillStyle = SHEET
  ctx.fillRect(0, 0, W, H)

  // drafting grid
  for (let x = 0; x <= W; x += 20) {
    ctx.strokeStyle = x % 100 === 0 ? RULE_STRONG : RULE
    ctx.lineWidth = x % 100 === 0 ? 0.8 : 0.5
    tick(ctx, x + 0.5, 0, x + 0.5, H)
  }
  for (let y = 0; y <= H; y += 20) {
    ctx.strokeStyle = y % 100 === 0 ? RULE_STRONG : RULE
    ctx.lineWidth = y % 100 === 0 ? 0.8 : 0.5
    tick(ctx, 0, y + 0.5, W, y + 0.5)
  }

  const k = layout ? layout.scale_factor ?? 1 : 1
  const points = []
  for (const d of detections) {
    ;(d.positions ?? []).forEach((p, idx) => points.push({ x: p.x * k, z: p.z * k, cls: d.class, confidence: p.confidence, idx }))
  }
  const polygon = layout?.polygon ?? []
  const path = layout?.camera_path ?? []

  if (points.length === 0 && polygon.length === 0) {
    ctx.fillStyle = GRAPHITE
    ctx.font = '500 13px "IBM Plex Mono", monospace'
    ctx.textAlign = 'center'
    ctx.fillText('NO OBJECTS TO PLOT', W / 2, H / 2)
    return []
  }

  const padL = 92, padR = 40, padT = 92, padB = 56
  const xs = [...points.map((p) => p.x), ...polygon.map((p) => p[0])]
  const zs = [...points.map((p) => p.z), ...polygon.map((p) => p[1])]
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minZ = Math.min(...zs), maxZ = Math.max(...zs)
  const spanX = Math.max(maxX - minX, 0.08)
  const spanZ = Math.max(maxZ - minZ, 0.08)
  // Uniform scale keeps the layout's proportions honest.
  const scale = Math.min((W - padL - padR) / spanX, (H - padT - padB) / spanZ)
  const drawW = spanX * scale
  const drawH = spanZ * scale
  const ox = padL + (W - padL - padR - drawW) / 2
  const oy = padT + (H - padT - padB - drawH) / 2
  const toCanvas = (x, z) => [ox + (x - minX) * scale, oy + (z - minZ) * scale]

  // room outline from the reconstructed floor footprint
  if (polygon.length > 2) {
    ctx.save()
    ctx.beginPath()
    polygon.forEach(([x, z], i) => {
      const [cx, cy] = toCanvas(x, z)
      if (i === 0) ctx.moveTo(cx, cy)
      else ctx.lineTo(cx, cy)
    })
    ctx.closePath()
    ctx.fillStyle = 'rgba(14,27,38,0.04)'
    ctx.fill()
    ctx.lineWidth = 2.2
    ctx.strokeStyle = INK
    ctx.lineJoin = 'round'
    ctx.stroke()
    ctx.restore()
  }

  // where the phone walked
  if (path.length > 1) {
    ctx.save()
    ctx.setLineDash([2, 5])
    ctx.lineWidth = 1.2
    ctx.globalAlpha = 0.55
    ctx.strokeStyle = FLAG
    ctx.beginPath()
    path.forEach(([x, z], i) => {
      const [cx, cy] = toCanvas(x, z)
      if (i === 0) ctx.moveTo(cx, cy)
      else ctx.lineTo(cx, cy)
    })
    ctx.stroke()
    ctx.restore()
    ctx.globalAlpha = 1
    const [sx, sy] = toCanvas(path[0][0], path[0][1])
    ctx.fillStyle = FLAG
    ctx.beginPath(); ctx.arc(sx, sy, 4.5, 0, Math.PI * 2); ctx.fill()
    ctx.strokeStyle = INK; ctx.lineWidth = 1.2; ctx.stroke()
  }

  // density heatmap (same transform as the symbols, so the two always line up)
  if (showHeatmap) {
    for (const p of points) {
      const [cx, cy] = toCanvas(p.x, p.z)
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, 64)
      g.addColorStop(0, 'rgba(255,90,31,0.30)')
      g.addColorStop(1, 'rgba(255,90,31,0)')
      ctx.fillStyle = g
      ctx.fillRect(cx - 64, cy - 64, 128, 128)
    }
  }

  // zones
  ctx.font = '500 11px "IBM Plex Mono", monospace'
  rooms.forEach((room, i) => {
    const [x1, z1, x2, z2] = room.bounds
    const [a, b] = toCanvas(x1, z1)
    const [c, d] = toCanvas(x2, z2)
    const pad = 20
    const rx = Math.min(a, c) - pad, ry = Math.min(b, d) - pad
    const rw = Math.abs(c - a) + pad * 2, rh = Math.abs(d - b) + pad * 2
    ctx.save()
    ctx.fillStyle = 'rgba(14,27,38,0.035)'
    ctx.fillRect(rx, ry, rw, rh)
    ctx.setLineDash([7, 4])
    ctx.lineWidth = 1.6
    ctx.strokeStyle = INK
    ctx.strokeRect(rx, ry, rw, rh)
    ctx.restore()
    const label = `Z${i + 1} · ${room.objects} obj`
    const tw = ctx.measureText(label).width + 12
    ctx.fillStyle = INK
    ctx.fillRect(rx, ry - 18, tw, 18)
    ctx.fillStyle = '#fafbfb'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillText(label, rx + 6, ry - 8.5)
  })

  // overall extent dimensions
  const [x0, y0] = toCanvas(minX, minZ)
  const [x1d, y1d] = toCanvas(maxX, maxZ)
  let widthLabel, heightLabel, note
  if (layout) {
    const est = layout.source !== 'user'
    widthLabel = `${est ? '~' : ''}${layout.width_m.toFixed(1)} m`
    heightLabel = `${est ? '~' : ''}${layout.depth_m.toFixed(1)} m`
    note = est ? 'SCALE ESTIMATED FROM CAMERA HEIGHT' : 'SCALE FROM YOUR MEASUREMENT'
  } else {
    widthLabel = calibration?.width_m ? `${calibration.width_m.toFixed(1)} m` : 'uncalibrated'
    heightLabel = calibration?.height_m ? `${calibration.height_m.toFixed(1)} m` : 'uncalibrated'
    note = calibration ? 'SCALE: USER-CALIBRATED WIDTH' : 'SCHEMATIC · NOT TO SCALE'
  }
  // 56px clear of the extents so zone labels (which sit above their boxes) never touch it
  dimension(ctx, x0, y0 - 56, x1d, y0 - 56, widthLabel)
  dimension(ctx, x0 - 56, y0, x0 - 56, y1d, heightLabel, { vertical: true })

  // symbols
  const hits = []
  for (const p of points) {
    const [cx, cy] = toCanvas(p.x, p.z)
    const active = hover && hover.cls === p.cls && Math.abs(hover.x - cx) < 1 && Math.abs(hover.y - cy) < 1
    drawSymbol(ctx, p.cls, cx, cy, { active })
    hits.push({ x: cx, y: cy, r: 16, cls: p.cls, confidence: p.confidence, idx: p.idx })
  }

  // real scale bar (only when positions are in metres)
  if (layout) {
    const bar = [0.5, 1, 2, 5].find((m) => m * scale >= 60) ?? 5
    const bx = 20, by = H - 26
    ctx.strokeStyle = INK; ctx.lineWidth = 2
    tick(ctx, bx, by, bx + bar * scale, by)
    tick(ctx, bx, by - 5, bx, by + 5)
    tick(ctx, bx + bar * scale, by - 5, bx + bar * scale, by + 5)
    ctx.fillStyle = INK
    ctx.font = '500 11px "IBM Plex Mono", monospace'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'alphabetic'
    ctx.fillText(`${bar} m`, bx, by - 9)
  }

  ctx.fillStyle = GRAPHITE
  ctx.font = '500 10px "IBM Plex Mono", monospace'
  ctx.textAlign = 'right'
  ctx.textBaseline = 'alphabetic'
  ctx.fillText(note, W - 14, H - 14)

  return hits
}


// ===========================================================================================
// Modern floor plan: straight walls, furniture at real size, quiet background, pan and zoom.
// ===========================================================================================

const PLAN_FONT = '"Hanken Grotesk Variable", system-ui, sans-serif'
const MONO = '"IBM Plex Mono", monospace'

// Typical footprint in metres [width, depth]. Orientation is not known, so shapes are axis-aligned.
const METERS = {
  chair: [0.46, 0.46], couch: [1.9, 0.9], 'dining table': [1.4, 0.85], bed: [2.0, 1.5], 'potted plant': [0.4, 0.4],
  tv: [1.0, 0.1], sink: [0.6, 0.45], refrigerator: [0.7, 0.7], bench: [1.2, 0.4], microwave: [0.5, 0.4],
  oven: [0.6, 0.6], toilet: [0.4, 0.7], clock: [0.3, 0.3], door: [0.9, 0.12], window: [1.2, 0.12], light: [0.3, 0.3],
  counter: [1.8, 0.6], cabinet: [0.9, 0.45], shelf: [0.9, 0.3], picture: [0.6, 0.05], curtain: [1.2, 0.1],
}

// Colour by what the thing is for, from the app's own palette.
const GROUPS = [
  { names: ['chair', 'couch', 'bench', 'bed'], stroke: '#1d55b8', fill: '#dbe6fa' },                     // seating
  { names: ['dining table', 'counter', 'cabinet', 'shelf'], stroke: '#b23300', fill: '#ffe4d9' },        // surfaces
  { names: ['tv', 'microwave', 'oven', 'refrigerator', 'sink', 'toilet'], stroke: '#0e1b26', fill: '#e3e9ee' }, // appliances
  { names: ['potted plant', 'clock', 'picture', 'curtain', 'light', 'window', 'door'], stroke: '#17724f', fill: '#d6efe4' }, // decor
]
const groupOf = (cls) => GROUPS.find((g) => g.names.includes(cls)) ?? { stroke: GRAPHITE, fill: '#e9eef1' }

function rrect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, Math.min(r, w / 2, h / 2))
}

/** A small rounded label. */
function chip(ctx, text, x, y, { align = 'center', bg = '#fff', fg = INK, border = RULE_STRONG, font = `500 11px ${MONO}`, padX = 8, h = 20 } = {}) {
  ctx.save()
  ctx.font = font
  const w = ctx.measureText(text).width + padX * 2
  const left = align === 'center' ? x - w / 2 : align === 'right' ? x - w : x
  ctx.shadowColor = 'rgba(14,27,38,0.12)'
  ctx.shadowBlur = 6
  ctx.shadowOffsetY = 1
  rrect(ctx, left, y - h / 2, w, h, h / 2)
  ctx.fillStyle = bg
  ctx.fill()
  ctx.shadowColor = 'transparent'
  if (border) { ctx.strokeStyle = border; ctx.lineWidth = 1; ctx.stroke() }
  ctx.fillStyle = fg
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, left + padX, y + 0.5)
  ctx.restore()
  return { left, w }
}

function furniture(ctx, cls, cx, cy, w, h, { hover = false, selected = false } = {}) {
  const g = groupOf(cls)
  ctx.save()
  ctx.translate(cx, cy)
  const r = Math.min(w, h) * 0.22
  ctx.shadowColor = hover || selected ? 'rgba(14,27,38,0.38)' : 'rgba(14,27,38,0.2)'
  ctx.shadowBlur = hover || selected ? 16 : 9
  ctx.shadowOffsetY = hover || selected ? 5 : 3
  ctx.fillStyle = g.fill
  ctx.strokeStyle = g.stroke
  ctx.lineWidth = 1.6
  ctx.lineJoin = 'round'

  const body = () => { rrect(ctx, -w / 2, -h / 2, w, h, r); ctx.fill(); ctx.shadowColor = 'transparent'; ctx.stroke() }

  switch (cls) {
    case 'potted plant':
    case 'clock':
    case 'light': {
      ctx.beginPath(); ctx.ellipse(0, 0, w / 2, h / 2, 0, 0, Math.PI * 2); ctx.fill(); ctx.shadowColor = 'transparent'; ctx.stroke()
      ctx.lineWidth = 1.2
      ctx.beginPath()
      if (cls === 'potted plant') for (let i = 0; i < 6; i++) { const a = (i * Math.PI) / 3; ctx.moveTo(0, 0); ctx.lineTo(Math.cos(a) * w * 0.38, Math.sin(a) * h * 0.38) }
      else { ctx.moveTo(0, 0); ctx.lineTo(0, -h * 0.3); ctx.moveTo(0, 0); ctx.lineTo(w * 0.22, h * 0.1) }
      ctx.stroke()
      break
    }
    case 'tv': {
      rrect(ctx, -w / 2, -h / 2, w, h, h / 2); ctx.fillStyle = INK; ctx.fill(); ctx.shadowColor = 'transparent'; ctx.stroke()
      break
    }
    case 'chair': {
      body()
      ctx.fillStyle = g.stroke
      rrect(ctx, -w / 2 + 1, -h / 2 + 1, w - 2, Math.max(4, h * 0.2), 2); ctx.fill()   // the back rest
      break
    }
    case 'couch': {
      body()
      ctx.fillStyle = g.stroke
      rrect(ctx, -w / 2 + 1, -h / 2 + 1, w - 2, h * 0.26, 3); ctx.fill()                  // back
      rrect(ctx, -w / 2 + 1, -h / 2 + 1, w * 0.1, h - 2, 3); ctx.fill()                   // arms
      rrect(ctx, w / 2 - 1 - w * 0.1, -h / 2 + 1, w * 0.1, h - 2, 3); ctx.fill()
      break
    }
    case 'bed': {
      body()
      ctx.fillStyle = '#fff'
      rrect(ctx, -w / 2 + w * 0.06, -h / 2 + h * 0.08, w * 0.4, h * 0.22, 3); ctx.fill(); ctx.stroke()   // pillows
      rrect(ctx, w / 2 - w * 0.46, -h / 2 + h * 0.08, w * 0.4, h * 0.22, 3); ctx.fill(); ctx.stroke()
      break
    }
    case 'dining table':
    case 'counter': {
      body()
      ctx.lineWidth = 1
      rrect(ctx, -w / 2 + w * 0.1, -h / 2 + h * 0.14, w * 0.8, h * 0.72, r * 0.6); ctx.stroke()
      break
    }
    default: {
      body()
      ctx.lineWidth = 1
      ctx.beginPath(); ctx.moveTo(-w * 0.25, 0); ctx.lineTo(w * 0.25, 0); ctx.stroke()
    }
  }

  if (selected) {
    ctx.shadowColor = 'transparent'
    ctx.strokeStyle = FLAG
    ctx.lineWidth = 3
    rrect(ctx, -w / 2 - 5, -h / 2 - 5, w + 10, h + 10, r + 4)
    ctx.stroke()
  }
  ctx.restore()
}

// Doors and windows are parts of the wall, not furniture on the floor: they are drawn as openings in it.
const OPENING_WIDTH_M = { door: 0.9, window: 1.2 }
const SNAP_TO_WALL_M = 1.0   // a door further than this from every wall is shown as a plain marker instead

/** Closest point of the room outline (metres) to (x, z), with the wall's direction and its inward normal. */
function nearestWall(outline, x, z) {
  const cx = outline.reduce((s, p) => s + p[0], 0) / outline.length
  const cz = outline.reduce((s, p) => s + p[1], 0) / outline.length
  let best = null
  for (let i = 0; i < outline.length; i++) {
    const [ax, az] = outline[i]
    const [bx, bz] = outline[(i + 1) % outline.length]
    const len = Math.hypot(bx - ax, bz - az)
    if (len < 1e-6) continue
    const tx = (bx - ax) / len
    const tz = (bz - az) / len
    const along = Math.max(0, Math.min(len, (x - ax) * tx + (z - az) * tz))
    const px = ax + tx * along
    const pz = az + tz * along
    const d = Math.hypot(x - px, z - pz)
    if (best && d >= best.d) continue
    let nx = -tz
    let nz = tx
    if (nx * (cx - px) + nz * (cz - pz) < 0) { nx = -nx; nz = -nz }
    best = { d, ax, az, tx, tz, nx, nz, len, along }
  }
  return best
}

/** Where an opening of `width` metres sits on its wall: the centre, kept clear of the corners. */
function openingOnWall(wall, width) {
  const half = Math.min(width, wall.len) / 2
  const s = Math.max(half, Math.min(wall.len - half, wall.along))
  return { x: wall.ax + wall.tx * s, z: wall.az + wall.tz * s, half }
}

/** The gap in the wall, then the door leaf with its swing, or the window's glazing lines. */
function drawOpening(ctx, cls, wall, centre, P, m2px, wallW, { active = false } = {}) {
  const [cx, cy] = P(centre.x, centre.z)
  const half = centre.half * m2px
  const t = [wall.tx, wall.tz]
  const n = [wall.nx, wall.nz]
  const a = [cx - t[0] * half, cy - t[1] * half]
  const b = [cx + t[0] * half, cy + t[1] * half]
  ctx.save()
  ctx.lineCap = 'butt'
  if (active) {
    ctx.strokeStyle = 'rgba(255,90,31,0.4)'
    ctx.lineWidth = wallW + 12
    ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke()
  }
  // cut the opening out of the wall
  ctx.strokeStyle = cls === 'window' ? '#e3f1fa' : '#fffdf9'
  ctx.lineWidth = wallW + 1.5
  ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke()

  if (cls === 'window') {
    ctx.strokeStyle = INK
    ctx.lineWidth = 1.3
    ctx.beginPath()
    for (const k of [-0.5, 0.5]) {
      ctx.moveTo(a[0] + n[0] * wallW * k, a[1] + n[1] * wallW * k)
      ctx.lineTo(b[0] + n[0] * wallW * k, b[1] + n[1] * wallW * k)
    }
    ctx.stroke()
    ctx.strokeStyle = '#4f86b5'
    ctx.lineWidth = 1.8
    ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke()
  } else {
    // jambs, the open leaf at right angles to the wall, and the quarter circle it sweeps
    ctx.strokeStyle = INK
    ctx.lineWidth = 2
    ctx.beginPath()
    for (const e of [a, b]) {
      ctx.moveTo(e[0] - n[0] * wallW * 0.5, e[1] - n[1] * wallW * 0.5)
      ctx.lineTo(e[0] + n[0] * wallW * 0.5, e[1] + n[1] * wallW * 0.5)
    }
    ctx.stroke()
    const leaf = 2 * half
    const hx = a[0]
    const hy = a[1]
    ctx.lineWidth = 2.6
    ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(hx + n[0] * leaf, hy + n[1] * leaf); ctx.stroke()
    const open = Math.atan2(n[1], n[0])
    const shut = Math.atan2(t[1], t[0])
    let sweep = shut - open
    while (sweep > Math.PI) sweep -= 2 * Math.PI
    while (sweep < -Math.PI) sweep += 2 * Math.PI
    ctx.lineWidth = 1.1
    ctx.setLineDash([4, 3])
    ctx.beginPath(); ctx.arc(hx, hy, leaf, open, shut, sweep < 0); ctx.stroke()
  }
  ctx.restore()
  return { x: cx, y: cy, half }
}

function polygonArea(poly) {
  let a = 0
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i]
    const [x2, y2] = poly[(i + 1) % poly.length]
    a += x1 * y2 - x2 * y1
  }
  return Math.abs(a) / 2
}

export const DEFAULT_VIEW = { k: 1, tx: 0, ty: 0 }

/**
 * Modern plan. World coordinates are metres with the room's corner at (0, 0).
 * `view` is the user's zoom/pan on top of an automatic fit. Returns hit targets in canvas pixels.
 */
function drawModern(ctx, W, H, {
  detections = [], rooms = [], layout, showHeatmap = false, showPath = false, showLabels = false,
  view = DEFAULT_VIEW, hover = null, selected = null,
} = {}) {
  const fac = layout.scale_factor ?? 1
  const rw = layout.width_m
  const rd = layout.depth_m
  const estimated = layout.source !== 'user'
  const pts = []
  for (const d of detections) (d.positions ?? []).forEach((p, idx) => pts.push({ cls: d.class, idx, x: p.x * fac, z: p.z * fac, confidence: p.confidence }))
  const path = layout.camera_path ?? []

  // Walls: a clean rectangle when it describes the room well, otherwise the scanned outline.
  const hull = layout.polygon ?? []
  const useHull = hull.length > 2 && polygonArea(hull) / (rw * rd) < 0.6
  const outline = useHull ? hull : [[0, 0], [rw, 0], [rw, rd], [0, rd]]

  // Fit the room (and any object outside it) into the canvas, leaving room for the dimension lines.
  const xs = [0, rw, ...pts.map((p) => p.x), ...(showPath ? path.map((p) => p[0]) : [])]
  const zs = [0, rd, ...pts.map((p) => p.z), ...(showPath ? path.map((p) => p[1]) : [])]
  const minX = Math.min(...xs), maxX = Math.max(...xs), minZ = Math.min(...zs), maxZ = Math.max(...zs)
  const padL = 74, padR = 36, padT = 78, padB = 64
  const m2px0 = Math.min((W - padL - padR) / (maxX - minX), (H - padT - padB) / (maxZ - minZ))
  const ox0 = padL + (W - padL - padR - (maxX - minX) * m2px0) / 2
  const oy0 = padT + (H - padT - padB - (maxZ - minZ) * m2px0) / 2
  const m2px = m2px0 * view.k
  const P = (x, z) => [(ox0 + (x - minX) * m2px0) * view.k + view.tx, (oy0 + (z - minZ) * m2px0) * view.k + view.ty]

  // background with a quiet dot grid every half metre
  ctx.clearRect(0, 0, W, H)
  ctx.fillStyle = '#eef2f5'
  ctx.fillRect(0, 0, W, H)
  const step = 0.5 * m2px
  if (step > 8) {
    const [gx, gy] = P(0, 0)
    ctx.fillStyle = '#c3cdd5'
    for (let x = gx % step; x < W; x += step) for (let y = gy % step; y < H; y += step) ctx.fillRect(x - 0.75, y - 0.75, 1.5, 1.5)
  }

  const tracePath = (poly) => {
    ctx.beginPath()
    poly.forEach(([x, z], i) => { const [px, py] = P(x, z); if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py) })
    ctx.closePath()
  }

  // floor, with a soft shadow so the room lifts off the page
  ctx.save()
  ctx.shadowColor = 'rgba(14,27,38,0.2)'
  ctx.shadowBlur = 30
  ctx.shadowOffsetY = 10
  tracePath(outline)
  ctx.fillStyle = '#fffdf9'
  ctx.fill()
  ctx.restore()

  // everything inside the room is clipped to it
  ctx.save()
  tracePath(outline)
  ctx.clip()

  // faint area figure behind the furniture
  const [cX, cY] = P(rw / 2, rd / 2)
  ctx.fillStyle = 'rgba(14,27,38,0.06)'
  ctx.font = `700 ${Math.max(26, Math.min(90, m2px * 0.8))}px ${PLAN_FONT}`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(`${estimated ? '~' : ''}${layout.area_m2} m²`, cX, cY)

  if (showHeatmap) {
    for (const p of pts) {
      const [x, y] = P(p.x, p.z)
      const radius = 1.1 * m2px
      const gr = ctx.createRadialGradient(x, y, 0, x, y, radius)
      gr.addColorStop(0, 'rgba(255,90,31,0.38)')
      gr.addColorStop(1, 'rgba(255,90,31,0)')
      ctx.fillStyle = gr
      ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2)
    }
  }

  // zones as soft tinted areas
  const ZONE_TINTS = ['rgba(29,85,184,0.07)', 'rgba(255,90,31,0.08)', 'rgba(23,114,79,0.08)']
  rooms.forEach((room, i) => {
    const [x1, z1, x2, z2] = room.bounds
    const pad = 0.3
    const [ax, ay] = P(x1 - pad, z1 - pad)
    const [bx, by] = P(x2 + pad, z2 + pad)
    rrect(ctx, ax, ay, bx - ax, by - ay, 14)
    ctx.fillStyle = ZONE_TINTS[i % ZONE_TINTS.length]
    ctx.fill()
    ctx.setLineDash([6, 5])
    ctx.strokeStyle = 'rgba(14,27,38,0.35)'
    ctx.lineWidth = 1.2
    ctx.stroke()
    ctx.setLineDash([])
  })

  if (showPath && path.length > 1) {
    ctx.save()
    ctx.strokeStyle = 'rgba(255,90,31,0.55)'
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.setLineDash([1, 7])
    ctx.beginPath()
    const q = path.map(([x, z]) => P(x, z))
    ctx.moveTo(q[0][0], q[0][1])
    for (let i = 1; i < q.length - 1; i++) ctx.quadraticCurveTo(q[i][0], q[i][1], (q[i][0] + q[i + 1][0]) / 2, (q[i][1] + q[i + 1][1]) / 2)
    ctx.lineTo(q[q.length - 1][0], q[q.length - 1][1])
    ctx.stroke()
    ctx.restore()
    ctx.fillStyle = FLAG
    ctx.beginPath(); ctx.arc(q[0][0], q[0][1], 5, 0, Math.PI * 2); ctx.fill()
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke()
  }

  // doors and windows that sit on a wall are drawn with the walls; the rest of the room's contents on the floor
  const openings = []
  const onFloor = []
  for (const p of pts) {
    const width = OPENING_WIDTH_M[p.cls]
    const wall = width ? nearestWall(outline, p.x, p.z) : null
    if (wall && wall.d <= SNAP_TO_WALL_M) openings.push({ p, wall, centre: openingOnWall(wall, width) })
    else onFloor.push(p)
  }

  // furniture at real size
  const hits = []
  for (const p of onFloor) {
    const [mw, md] = METERS[p.cls] ?? [0.5, 0.5]
    const w = Math.max(mw * m2px, 20)
    const h = Math.max(md * m2px, p.cls === 'tv' ? 8 : 20)
    const [x, y] = P(p.x, p.z)
    const isHover = hover && hover.cls === p.cls && hover.idx === p.idx
    const isSel = selected && selected.cls === p.cls && selected.idx === p.idx
    furniture(ctx, p.cls, x, y, w, h, { hover: !!isHover, selected: !!isSel })
    hits.push({ x, y, hh: h / 2, r: Math.max(w, h) / 2 + 8, cls: p.cls, idx: p.idx, confidence: p.confidence, wx: p.x, wz: p.z })
  }
  ctx.restore() // end of the room clip

  // walls on top: thick, round-cornered, dark ink
  const wallW = Math.max(5, Math.min(14, m2px * 0.1))
  tracePath(outline)
  ctx.strokeStyle = INK
  ctx.lineWidth = wallW
  ctx.lineJoin = 'round'
  ctx.stroke()

  // openings cut into those walls
  for (const o of openings) {
    const active = (hover && hover.cls === o.p.cls && hover.idx === o.p.idx) || (selected && selected.cls === o.p.cls && selected.idx === o.p.idx)
    const at = drawOpening(ctx, o.p.cls, o.wall, o.centre, P, m2px, wallW, { active: !!active })
    hits.push({ x: at.x, y: at.y, hh: wallW / 2 + 4, r: Math.max(at.half, 14) + 6, cls: o.p.cls, idx: o.p.idx, confidence: o.p.confidence, wx: o.p.x, wz: o.p.z })
  }

  // object names: always on request, otherwise only the one you are pointing at or have selected
  for (const h of hits) {
    const isHover = hover && hover.cls === h.cls && hover.idx === h.idx
    const isSel = selected && selected.cls === h.cls && selected.idx === h.idx
    if (!(showLabels || isHover || isSel)) continue
    chip(ctx, classNameFor(h.cls), h.x, h.y + h.hh + 16, { font: `600 12px ${PLAN_FONT}`, bg: isSel ? FLAG : '#fff', fg: INK, border: isSel ? INK : RULE_STRONG, h: 22 })
  }

  // dimension lines in the margin, with the size in a chip
  const [x0, y0] = P(0, 0)
  const [x1, y1] = P(rw, rd)
  const dimLine = (ax, ay, bx, by, label, vertical) => {
    ctx.save()
    ctx.strokeStyle = GRAPHITE
    ctx.lineWidth = 1.2
    ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by)
    const cap = 6
    if (vertical) { ctx.moveTo(ax - cap, ay); ctx.lineTo(ax + cap, ay); ctx.moveTo(bx - cap, by); ctx.lineTo(bx + cap, by) }
    else { ctx.moveTo(ax, ay - cap); ctx.lineTo(ax, ay + cap); ctx.moveTo(bx, by - cap); ctx.lineTo(bx, by + cap) }
    ctx.stroke()
    ctx.restore()
    chip(ctx, label, (ax + bx) / 2, (ay + by) / 2)
  }
  const tilde = estimated ? '~' : ''
  dimLine(x0, Math.max(30, y0 - 34), x1, Math.max(30, y0 - 34), `${tilde}${rw.toFixed(1)} m`, false)
  dimLine(Math.max(30, x0 - 36), y0, Math.max(30, x0 - 36), y1, `${tilde}${rd.toFixed(1)} m`, true)

  // scale bar and the honest note
  const bar = [0.5, 1, 2, 5].find((m) => m * m2px >= 70) ?? 5
  const bx = 22
  const by = H - 26
  ctx.save()
  ctx.strokeStyle = INK
  ctx.lineWidth = 2
  ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx + bar * m2px, by); ctx.moveTo(bx, by - 5); ctx.lineTo(bx, by + 5); ctx.moveTo(bx + bar * m2px, by - 5); ctx.lineTo(bx + bar * m2px, by + 5); ctx.stroke()
  ctx.restore()
  chip(ctx, `${bar} m`, bx + (bar * m2px) / 2, by - 16, { h: 18, font: `500 10px ${MONO}`, padX: 6 })
  chip(ctx, estimated ? 'Scale estimated from camera height' : 'Scale from your measurement', W - 16, H - 22, { align: 'right', h: 22, font: `500 10px ${MONO}`, fg: GRAPHITE })

  return hits
}

const CLASS_NAMES = {
  chair: 'Chair', couch: 'Couch', 'dining table': 'Table', bed: 'Bed', 'potted plant': 'Plant', tv: 'TV', sink: 'Sink',
  refrigerator: 'Fridge', bench: 'Bench', microwave: 'Microwave', oven: 'Oven', toilet: 'Toilet', clock: 'Clock',
  door: 'Door', window: 'Window', light: 'Light', counter: 'Counter', cabinet: 'Cabinet', shelf: 'Shelf', picture: 'Picture', curtain: 'Curtain',
}
const classNameFor = (c) => CLASS_NAMES[c] ?? c.charAt(0).toUpperCase() + c.slice(1)

/**
 * Draws the plan. With a 3D layout (metres) it is the modern plan; without one (no camera path)
 * it falls back to the schematic of camera-view positions.
 */
export function drawFloorPlan(ctx, W, H, options = {}) {
  return options.layout ? drawModern(ctx, W, H, options) : drawSchematic(ctx, W, H, options)
}
