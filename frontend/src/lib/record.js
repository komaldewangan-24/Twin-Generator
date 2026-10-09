// Record the 3D view as a video, so a walkthrough can be shared or put in a presentation.

// MP4 plays everywhere (Chrome 126+, Safari, Edge); older browsers can only make WebM.
const TYPES = [
  ['video/mp4;codecs=avc1.640028', 'mp4'],
  ['video/mp4', 'mp4'],
  ['video/webm;codecs=vp9', 'webm'],
  ['video/webm;codecs=vp8', 'webm'],
  ['video/webm', 'webm'],
]

const pickType = () => (typeof MediaRecorder === 'undefined' ? null : TYPES.find(([t]) => MediaRecorder.isTypeSupported(t)) ?? null)

export const canRecord = () => !!pickType() && typeof HTMLCanvasElement !== 'undefined' && !!HTMLCanvasElement.prototype.captureStream

/**
 * Start recording a canvas. Returns {ext, stop()}; stop() resolves to the finished video Blob.
 * Only what the canvas draws is recorded, so labels, measurements and buttons stay out of the video.
 */
export function startRecording(canvas, { fps = 30, bitsPerSecond = 8_000_000 } = {}) {
  const found = pickType()
  if (!found || !canvas?.captureStream) throw new Error('This browser cannot record video. Try Chrome, Edge or Safari.')
  const [mimeType, ext] = found
  const stream = canvas.captureStream(fps)
  const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: bitsPerSecond })
  const chunks = []
  recorder.ondataavailable = (e) => { if (e.data?.size) chunks.push(e.data) }
  const finished = new Promise((resolve, reject) => {
    recorder.onstop = () => resolve(new Blob(chunks, { type: mimeType.split(';')[0] }))
    recorder.onerror = (e) => reject(e.error ?? new Error('The recording failed.'))
  })
  recorder.start(1000)
  return {
    ext,
    stop() {
      if (recorder.state !== 'inactive') recorder.stop()
      stream.getTracks().forEach((t) => t.stop())
      return finished
    },
  }
}

export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

export const safeName = (name) => String(name || 'scan').replace(/[^\w-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'scan'
