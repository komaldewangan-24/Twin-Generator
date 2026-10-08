/** Turn raw server errors into something a restaurant owner can act on. */
export function friendlyError(raw) {
  const msg = String(raw || '')
  if (!msg) return 'Processing failed. Upload the video again.'
  if (/interrupted/i.test(msg)) return 'Processing was interrupted by a server restart. Upload the video again.'
  if (/ffmpeg/i.test(msg)) return 'The server could not read the video. Try an MP4 or MOV, or ask the admin to check that FFmpeg is installed.'
  if (/no frames extracted|valid video/i.test(msg)) return 'No frames could be read from this file. Is it a valid video?'
  if (/detection backend|onnx|torch/i.test(msg)) return 'The object detector is not set up on the server yet.'
  if (/opencv|vconcat|assertion/i.test(msg)) return 'Something went wrong while preparing the preview. Upload the video again.'
  return 'Processing failed. Upload the video again.'
}

export function formatDate(iso, opts = { year: 'numeric', month: 'short', day: 'numeric' }) {
  if (!iso) return '–'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  return d.toLocaleDateString(undefined, opts)
}

export const PROCESSING = ['UPLOADED', 'EXTRACTING', 'POSES', 'DETECTING', 'TRAINING_3D']

export const STATUS_LABEL = {
  CREATED: 'Waiting for video',
  UPLOADED: 'Queued',
  EXTRACTING: 'Extracting frames',
  POSES: 'Finding camera path',
  DETECTING: 'Detecting objects',
  TRAINING_3D: 'Building 3D model',
  DONE: 'Ready',
  FAILED: 'Failed',
}

export const CLASS_LABEL = {
  chair: 'Chairs',
  couch: 'Couches',
  'dining table': 'Tables',
  bed: 'Beds',
  'potted plant': 'Plants',
  tv: 'TVs',
  sink: 'Sinks',
  refrigerator: 'Fridges',
  bench: 'Benches',
  microwave: 'Microwaves',
  oven: 'Ovens',
  toilet: 'Toilets',
  clock: 'Clocks',
  door: 'Doors',
  window: 'Windows',
  light: 'Lights',
  counter: 'Counters',
  cabinet: 'Cabinets',
  shelf: 'Shelves',
  picture: 'Pictures',
  curtain: 'Curtains',
}

export const classLabel = (c) => CLASS_LABEL[c] ?? c.charAt(0).toUpperCase() + c.slice(1)

/** Backend returns {detections:[...], meta:{...}}; the UI works with the array. */
export function splitObjects(payload) {
  if (Array.isArray(payload)) return { detections: payload, meta: null }
  return { detections: payload?.detections ?? [], meta: payload?.meta ?? null }
}

export const totalObjects = (detections) => (detections ?? []).reduce((s, d) => s + d.count, 0)

export const SINGULAR = {
  chair: 'Chair', couch: 'Couch', 'dining table': 'Table', bed: 'Bed', 'potted plant': 'Plant', tv: 'TV',
  sink: 'Sink', refrigerator: 'Fridge', bench: 'Bench', microwave: 'Microwave', oven: 'Oven', toilet: 'Toilet',
  clock: 'Clock', door: 'Door', window: 'Window', light: 'Light', counter: 'Counter', cabinet: 'Cabinet',
  shelf: 'Shelf', picture: 'Picture', curtain: 'Curtain',
}
export const classSingular = (c) => SINGULAR[c] ?? c.charAt(0).toUpperCase() + c.slice(1)
