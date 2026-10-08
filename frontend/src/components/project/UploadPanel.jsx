import { useRef, useState } from 'react'
import { Corners, Icon } from '../ui'

const MAX_BYTES = 2048 * 1024 * 1024
const OK_EXT = /\.(mp4|mov|webm)$/i

const TIPS = [
  'Walk slowly around the edge of the room, then once through the middle.',
  'Keep the lighting even. Avoid pointing the camera at bare windows.',
  '30 to 60 seconds is plenty. A longer video only means a longer wait.',
  'Textured rooms scan better than blank walls.',
]

export default function UploadPanel({ onUpload, progress, replacing = false }) {
  const pick = useRef(null)
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

  return (
    <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files?.[0]) }}
        className={`sheet flex min-h-[300px] flex-col items-center justify-center gap-5 px-6 py-10 text-center transition ${drag ? '!border-flag bg-flag-soft' : ''}`}
      >
        <Corners className="text-ink/50" />
        {uploading ? (
          <div className="w-full max-w-sm" role="status">
            <p className="font-display text-xl font-semibold">{progress < 100 ? 'Uploading your video' : 'Saving and starting analysis'}</p>
            <div className="mt-4 h-2.5 overflow-hidden rounded-full border border-ink bg-white">
              <div className="h-full bg-flag transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
            <p className="figure mt-2 text-sm">{progress}%</p>
          </div>
        ) : (
          <>
            <div>
              <h2 className="text-2xl font-semibold">{replacing ? 'Upload a new video' : 'Add a walkthrough video'}</h2>
              <p className="mx-auto mt-1.5 max-w-sm text-graphite">
                Drop a video here, choose one from your device, or record it now on your phone.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-3">
              <button className="btn btn-flag" onClick={() => pick.current?.click()}><Icon.upload /> Choose video</button>
              <button className="btn btn-ghost" onClick={() => record.current?.click()}><Icon.camera /> Record with camera</button>
            </div>
            <p className="label">MP4, MOV or WebM · up to 2 GB</p>
          </>
        )}
        {localError && <p role="alert" className="text-sm font-medium text-fail">{localError}</p>}

        <input ref={pick} type="file" accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm" hidden onChange={(e) => { handle(e.target.files?.[0]); e.target.value = '' }} />
        <input ref={record} type="file" accept="video/*" capture="environment" hidden onChange={(e) => { handle(e.target.files?.[0]); e.target.value = '' }} />
      </div>

      <aside className="sheet p-6">
        <p className="label">For a good scan</p>
        <ul className="mt-4 space-y-3.5">
          {TIPS.map((t) => (
            <li key={t} className="flex gap-3 text-[15px]">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 bg-flag" aria-hidden />
              {t}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  )
}
