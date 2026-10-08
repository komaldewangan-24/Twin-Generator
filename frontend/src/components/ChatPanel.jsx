import { useEffect, useRef, useState } from 'react'
import api from '../lib/api'
import { totalObjects } from '../lib/format'
import { Icon } from './ui'

const SUGGESTIONS = [
  'How many chairs are there?',
  'How big is the room?',
  'Where is the TV?',
  'Suggest a better layout',
]

export default function ChatPanel({ projectId, detections, onShow3D }) {
  const [messages, setMessages] = useState([
    { role: 'ai', text: `I can see ${totalObjects(detections)} objects in this scan. Ask me about counts, seating, free space or layout.` },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const recog = useRef(null)
  const end = useRef(null)
  const SR = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null

  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [messages, busy])

  const send = async (text) => {
    const q = (text ?? input).trim()
    if (!q || busy) return
    setMessages((m) => [...m, { role: 'user', text: q }])
    setInput('')
    setBusy(true)
    try {
      const history = messages.filter((m, i) => i > 0 && !m.error).slice(-6).map((m) => ({ role: m.role, text: m.text }))
      const { data } = await api.post(`/projects/${projectId}/ask`, { question: q, history })
      setMessages((m) => [...m, { role: 'ai', text: data.answer, focus: data.focus }])
    } catch (err) {
      const detail = err.response?.data?.detail
      setMessages((m) => [...m, { role: 'ai', error: true, text: typeof detail === 'string' ? detail : 'I could not reach the server. Try again in a moment.' }])
    } finally {
      setBusy(false)
    }
  }

  const toggleVoice = () => {
    if (!SR) return
    if (listening) return recog.current?.stop()
    const rec = new SR()
    rec.lang = 'en-US'
    rec.interimResults = false
    rec.onresult = (e) => { const t = e.results[0][0].transcript; setInput(t); send(t) }
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    rec.start()
    recog.current = rec
    setListening(true)
  }

  return (
    <div className="sheet flex h-[min(70vh,600px)] min-h-[420px] flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-5" aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[88%] whitespace-pre-wrap px-4 py-2.5 text-[15px] ${
                m.role === 'user'
                  ? 'rounded-[3px] bg-ink text-paper'
                  : m.error
                    ? 'border-l-[3px] border-fail bg-fail-soft text-ink'
                    : 'border-l-[3px] border-flag bg-white text-ink shadow-[0_1px_0_rgb(14_27_38/0.06)]'
              }`}
            >
              {m.text}
              {m.focus && onShow3D && (
                <div className="mt-2.5"><button onClick={() => onShow3D(m.focus.class, m.focus.index)} className="btn btn-ink !px-3 !py-1.5 !text-[13px]">Show in 3D</button></div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex" aria-label="Assistant is typing">
            <div className="flex gap-1 border-l-[3px] border-flag bg-white px-4 py-3">
              {[0, 1, 2].map((i) => <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-graphite" style={{ animationDelay: `${i * 120}ms` }} />)}
            </div>
          </div>
        )}
        <div ref={end} />
      </div>

      {messages.length < 2 && (
        <div className="flex flex-wrap gap-2 px-5 pb-3">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => send(s)} className="rounded-full border border-rule-strong bg-white px-3.5 py-1.5 text-sm transition hover:border-ink">
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); send() }} className="flex items-center gap-2 border-t border-rule-strong p-3">
        {SR && (
          <button type="button" onClick={toggleVoice} aria-pressed={listening} aria-label={listening ? 'Stop listening' : 'Ask by voice'}
            className={`grid h-10 w-10 place-items-center rounded-[3px] border transition ${listening ? 'border-flag bg-flag text-ink' : 'border-rule-strong hover:border-ink'}`}>
            <Icon.mic />
          </button>
        )}
        <label className="sr-only" htmlFor="chat-input">Your question</label>
        <input id="chat-input" value={input} onChange={(e) => setInput(e.target.value)} placeholder={listening ? 'Listening…' : 'Ask about this space'} className="field" autoComplete="off" />
        <button type="submit" disabled={busy || !input.trim()} className="btn btn-ink h-10">Ask</button>
      </form>
    </div>
  )
}
