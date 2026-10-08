import { drawFloorPlan } from './floorplan'
import { classLabel, formatDate, totalObjects } from './format'

const INK = [14, 27, 38]
const FLAG = [255, 90, 31]
const GRAPHITE = [74, 89, 102]

/** Builds and downloads the PDF. jsPDF is imported lazily so it stays out of the main bundle. */
export async function downloadReport({ project, detections, meta, analytics }) {
  const { jsPDF } = await import('jspdf')
  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const W = 210, H = 297, M = 16
  let y = 0

  const ensure = (needed) => {
    if (y + needed > H - 18) { doc.addPage(); y = M }
  }
  const heading = (text) => {
    ensure(16)
    doc.setFont('helvetica', 'bold'); doc.setFontSize(13); doc.setTextColor(...INK)
    doc.text(text, M, y)
    doc.setDrawColor(...INK); doc.setLineWidth(0.5); doc.line(M, y + 2, W - M, y + 2)
    y += 9
  }

  // Cover band
  doc.setFillColor(...INK); doc.rect(0, 0, W, 38, 'F')
  doc.setFillColor(...FLAG); doc.rect(0, 38, W, 1.6, 'F')
  doc.setTextColor(233, 238, 241); doc.setFont('helvetica', 'bold'); doc.setFontSize(21)
  doc.text('Space report', M, 18)
  doc.setFont('helvetica', 'normal'); doc.setFontSize(11)
  doc.text(project.name, M, 27)
  doc.setFontSize(9); doc.setTextColor(157, 176, 190)
  doc.text(`Scanned ${formatDate(project.scan_date)}  ·  Generated ${new Date().toLocaleDateString()}`, M, 33)
  y = 50

  // Key figures
  const cal = analytics?.area?.calibration
  const seats = analytics?.seating_capacity?.total
  const figures = [
    ['OBJECTS', totalObjects(detections)],
    ['ZONES', analytics?.rooms?.count ?? '–'],
    ['SEATS', seats ?? '–'],
    ['AREA', cal?.area_m2 != null ? `${cal.area_m2} m²` : 'not set'],
  ]
  const cw = (W - 2 * M) / figures.length
  figures.forEach(([label, value], i) => {
    const x = M + i * cw
    doc.setDrawColor(163, 175, 185); doc.setLineWidth(0.3); doc.rect(x, y, cw, 22)
    doc.setFont('helvetica', 'normal'); doc.setFontSize(7.5); doc.setTextColor(...GRAPHITE)
    doc.text(label, x + 4, y + 6)
    doc.setFont('courier', 'bold'); doc.setFontSize(18); doc.setTextColor(...INK)
    doc.text(String(value), x + 4, y + 16)
  })
  y += 34

  // Objects
  heading('Detected objects')
  if (detections.length === 0) {
    doc.setFont('helvetica', 'normal'); doc.setFontSize(10); doc.setTextColor(...GRAPHITE)
    doc.text('No furniture was detected in this scan.', M, y); y += 8
  } else {
    const sorted = [...detections].sort((a, b) => b.count - a.count)
    const max = sorted[0].count
    for (const d of sorted) {
      ensure(9)
      const avg = d.positions.length ? d.positions.reduce((s, p) => s + p.confidence, 0) / d.positions.length : 0
      doc.setFont('helvetica', 'normal'); doc.setFontSize(10); doc.setTextColor(...INK)
      doc.text(classLabel(d.class), M, y)
      doc.setFillColor(222, 228, 233); doc.rect(60, y - 3.4, 80, 3.6, 'F')
      doc.setFillColor(...(d === sorted[0] ? FLAG : INK)); doc.rect(60, y - 3.4, 80 * (d.count / max), 3.6, 'F')
      doc.setFont('courier', 'bold'); doc.text(String(d.count), 144, y)
      doc.setFont('courier', 'normal'); doc.setFontSize(8.5); doc.setTextColor(...GRAPHITE)
      doc.text(`conf ${Math.round(avg * 100)}%`, W - M, y, { align: 'right' })
      y += 8
    }
  }
  y += 4

  // Seating
  if (analytics?.seating_capacity) {
    const b = analytics.seating_capacity.breakdown
    heading('Seating capacity')
    doc.setFont('helvetica', 'normal'); doc.setFontSize(10); doc.setTextColor(...INK)
    doc.text(`${analytics.seating_capacity.total} seats  (${b.chairs} chairs, ${b.couch_seats} couch seats, ${b.bench_seats} bench seats; ${b.dining_tables} dining tables)`, M, y)
    y += 12
  }

  // Floor plan, drawn by the same code as the on-screen plan
  const cv = document.createElement('canvas')
  const cw2 = 1100, ch2 = 750
  cv.width = cw2; cv.height = ch2
  drawFloorPlan(cv.getContext('2d'), cw2, ch2, { detections, rooms: analytics?.rooms?.details ?? [], layout: analytics?.layout ?? null, calibration: cal ?? null })
  const imgW = W - 2 * M
  const imgH = (imgW * ch2) / cw2
  ensure(imgH + 16) // heading and drawing stay together on one page
  heading('Floor plan')
  doc.addImage(cv.toDataURL('image/jpeg', 0.92), 'JPEG', M, y, imgW, imgH)
  doc.setDrawColor(...INK); doc.setLineWidth(0.4); doc.rect(M, y, imgW, imgH)
  y += imgH + 8

  // Notes
  ensure(24)
  doc.setFont('helvetica', 'italic'); doc.setFontSize(8.5); doc.setTextColor(...GRAPHITE)
  const note = doc.splitTextToSize(
    'Counts and positions are estimates computed from camera frames and are not surveyed measurements. The plan is schematic: object positions come from the camera view and are not to scale unless a real size was entered.',
    W - 2 * M,
  )
  doc.text(note, M, y)

  // Footer
  const pages = doc.getNumberOfPages()
  for (let i = 1; i <= pages; i++) {
    doc.setPage(i)
    doc.setFont('helvetica', 'normal'); doc.setFontSize(8); doc.setTextColor(...GRAPHITE)
    doc.text('Digital Twin Generator', M, H - 9)
    doc.text(`${i} / ${pages}`, W - M, H - 9, { align: 'right' })
    if (meta?.backend && i === 1) doc.text(`Detector: ${meta.backend}`, W / 2, H - 9, { align: 'center' })
  }

  doc.save(`${project.name.replace(/[^\w-]+/g, '_')}_report.pdf`)
}
