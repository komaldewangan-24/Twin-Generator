import { useRef, useState } from 'react'
import { Corners, Icon } from '../ui'

const MAX_BYTES = 2048 * 1024 * 1024
const OK_EXT = /\.(mp4|mov|webm)$/i
const OK_PHOTO = /\.(jpe?g|png|webp|heic|heif)$/i
const MIN_PHOTOS = 15
const MAX_PHOTOS = 300
const MAX_PHOTO_BYTES = 80 * 1024 * 1024

const VIDEO_TIPS = [
  'Walk slowly around the edge of the room, then once through the middle.',
  'Keep the lighting even. Avoid pointing the camera at bare windows.',
  '30 to 60 seconds is plenty. A longer video only means a longer wait.',
  'Textured rooms scan better than blank walls.',
]

const PHOTO_TIPS = [
  `${MIN_PHOTOS} to ${MAX_PHOTOS} photos. About 60 to 100 is a good number for a room.`,
  'Each photo should share more than half of its view with the one before it.',
  'Step sideways between shots along the walls. Turning on the spot gives no depth.',
  'Same camera and lens, no zoom, steady light, sharp, no flash.',
  'Keep furniture and wall details in view; blank walls cannot be matched.',
]

export default function UploadPanel({ onUpload, onUploadPhotos, progress, replacing = false }) {
  const pick = useRef(null)
  const pickPhotos = useRef(null)
  const record = useRef(null)
  const [drag, setDrag] = useState(false)
  const [localError, setLocalError] = useState('')
  const uploading = progress != null

  const handle = (file) => {
    setLocalError('')
    if (!file) return
    if (!OK_EXT.test(file.name)) return setLocalError('This file type is not supported. Use MP4, MOV or WebM.')
    if (file.size > MAX_BYTES) return setLocalError('This video is over 2 GB. Record a shorter one.')
    onUpload(file)
  }

  const handlePhotos = (list) => {
    setLocalError('')
    const files = [...(list ?? [])]
    if (!files.length) return
    const bad = files.find((f) => !OK_PHOTO.test(f.name))
    if (bad) return setLocalError(`${bad.name} is not a photo this app can read. Use JPG, PNG, WebP or HEIC.`)
    if (files.length < MIN_PHOTOS) return setLocalError(`Choose at least ${MIN_PHOTOS} photos (you chose ${files.length}). They must overlap: photos of the same place taken while moving.`)
    if (files.length > MAX_PHOTOS) return setLocalError(`Choose at most ${MAX_PHOTOS} photos (you chose ${files.length}). About 240 are used.`)
    if (files.some((f) => f.size > MAX_PHOTO_BYTES)) return setLocalError('One of the photos is over 80 MB.')
    if (files.reduce((sum, f) => sum + f.size, 0) > MAX_BYTES) return setLocalError('The photos add up to more than 2 GB.')
    onUploadPhotos(files)
  }

  // Dropped files: several photos, or one video.
  const handleDrop = (list) => {
    const files = [...(list ?? [])]
    if (files.length > 0 && files.every((f) => OK_PHOTO.test(f.name))) return handlePhotos(files)
    if (files.length === 1) return handle(files[0])
    setLocalError('Drop one video, or several photos (not a mix).')
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handleDrop(e.dataTransfer.files) }}
        className={`sheet flex min-h-[300px] flex-col items-center justify-center gap-5 px-6 py-10 text-center transition ${drag ? '!border-flag bg-flag-soft' : ''}`}
      >
        <Corners className="text-ink/50" />
        {uploading ? (
          <div className="w-full max-w-sm" role="status">
            <p className="font-display text-xl font-semibold">{progress < 100 ? 'Uploading' : 'Saving and starting analysis'}</p>
            <div className="mt-4 h-2.5 overflow-hidden rounded-full border border-ink bg-white">
              <div className="h-full bg-flag transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
            <p className="figure mt-2 text-sm">{progress}%</p>
          </div>
        ) : (
          <>
            <div>
              <h2 className="text-2xl font-semibold">{replacing ? 'Upload a new video or photos' : 'Add a walkthrough video or photos'}</h2>
              <p className="mx-auto mt-1.5 max-w-sm text-graphite">
                Drop a video or several photos here, choose them from your device, or record a video now on your phone.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-3">
              <button className="btn btn-flag" onClick={() => pick.current?.click()}><Icon.upload /> Choose video</button>
              <button className="btn btn-ink" onClick={() => pickPhotos.current?.click()}><Icon.upload /> Choose photos</button>
              <button className="btn btn-ghost" onClick={() => record.current?.click()}><Icon.camera /> Record with camera</button>
            </div>
            <p className="label">Video: MP4, MOV or WebM, up to 2 GB · Photos: {MIN_PHOTOS} to {MAX_PHOTOS} JPG, PNG, WebP or HEIC</p>
          </>
        )}
        {localError && <p role="alert" className="text-sm font-medium text-fail">{localError}</p>}

        <input ref={pick} type="file" accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm" hidden onChange={(e) => { handle(e.target.files?.[0]); e.target.value = '' }} />
        <input ref={pickPhotos} type="file" multiple accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif" hidden onChange={(e) => { handlePhotos(e.target.files); e.target.value = '' }} />
        <input ref={record} type="file" accept="video/*" capture="environment" hidden onChange={(e) => { handle(e.target.files?.[0]); e.target.value = '' }} />
      </div>

      <aside className="sheet p-6">
        {[['For a good video', VIDEO_TIPS], ['Or, with photos', PHOTO_TIPS]].map(([title, tips], i) => (
          <div key={title} className={i ? 'mt-6 border-t border-rule-strong pt-5' : ''}>
            <p className="label">{title}</p>
            <ul className="mt-4 space-y-3.5">
              {tips.map((t) => (
                <li key={t} className="flex gap-3 text-[15px]">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 bg-flag" aria-hidden />
                  {t}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </aside>
    </div>
  )
}
