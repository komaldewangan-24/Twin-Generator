import { useEffect, useRef, useState } from 'react'
import api from '../lib/api'

export default function ChatPanel({ projectId, detections }) {
  const [messages, setMessages] = useState([
    {
      role: 'ai',
      text: `Hi! Ask me anything about your ${detections?.length ?? 0} detected objects — counts, layouts, or what to declutter.`,
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (text) => {
    const q = (text ?? input).trim()
    if (!q || busy) return
    setMessages((m) => [...m, { role: 'user', text: q }])
    setInput('')
    setBusy(true)
    try {
      const { data } = await api.post(`/projects/${projectId}/ask`, { question: q })
      setMessages((m) => [...m, { role: 'ai', text: data.answer }])
    } catch {
      setMessages((m) => [...m, { role: 'ai', text: 'Sorry, something went wrong. Try again.' }])
    } finally {
      setBusy(false)
    }
  }

  const toggleVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    if (listening) {
      recogRef.current?.stop()
      return
    }
    const rec = new SR()
    rec.lang = 'en-US'
    rec.interimResults = false
    rec.onresult = (e) => setInput(e.results[0][0].transcript)
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    rec.start()
    recogRef.current = rec
    setListening(true)
  }

  const examples = [
    'How many chairs did you find?',
    'What is the biggest object?',
    'Suggest a declutter plan',
  ]

  const classes = [...new Set((detections || []).map((d) => d.class))]

  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-800 bg-slate-900">
      <div className="border-b border-slate-800 px-4 py-3 text-sm font-semibold text-white">
        AI Assistant
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
                m.role === 'user'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-800 text-slate-200'
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-slate-800 px-4 py-2 text-sm text-slate-400">…typing</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {messages.length < 2 && (
        <div className="flex flex-wrap gap-2 px-4 pb-2">
          {examples.map((chip) => (
            <button
              key={chip}
              onClick={() => send(chip)}
              className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 transition hover:border-emerald-500 hover:text-emerald-300"
            >
              {chip}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 border-t border-slate-800 p-3">
        <button
          onClick={toggleVoice}
          title="Voice input"
          className={`rounded-lg p-2 text-lg transition ${
            listening ? 'bg-red-500/20 text-red-400' : 'text-slate-400 hover:bg-slate-800'
          }`}
        >
          🎤
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder={classes.length ? `Ask about ${classes.slice(0, 3).join(', ')}…` : 'Ask anything…'}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-slate-500"
        />
        <button
          onClick={() => send()}
          disabled={busy}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-50"
        >
          Send
        </button>
      </div>
      {!('SpeechRecognition' in window) && !('webkitSpeechRecognition' in window) && (
        <p className="px-4 pb-2 text-[11px] text-slate-600">Voice input not supported in this browser.</p>
      )}
    </div>
  )
}