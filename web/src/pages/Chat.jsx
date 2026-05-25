import { useState, useEffect, useRef } from 'react'
import { postJson, fetchJson, formatTimeAgo } from '../hooks/api'

export default function ChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const chatEndRef = useRef(null)

  useEffect(() => {
    // Load existing messages (agent chat history from status manager)
    fetchJson('/api/status').catch(() => {})
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])

    try {
      const res = await postJson('/api/chat', { message: userMsg })
      setMessages(prev => [...prev, { role: 'assistant', content: res.response }])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: '🌿 Oops! Something went wrong. Try again later!' }])
    }
    setLoading(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div>
      <h2 className="text-xl font-bold text-pink-800 mb-6 flex items-center gap-2">
        <span className="text-3xl">🌸</span> Chat with the Garden
      </h2>

      <div className="bg-white/80 backdrop-blur rounded-2xl border-2 border-pink-100 overflow-hidden" style={{ minHeight: 400 }}>
        {/* Messages */}
        <div className="p-4 space-y-3 overflow-y-auto" style={{ maxHeight: 400 }}>
          {messages.length === 0 && (
            <div className="text-center text-pink-400 py-12">
              <div className="text-5xl mb-3">🌻</div>
              <p className="font-bold">Say hello to the garden!</p>
              <p className="text-sm mt-1">Ask about the codebase, goals, or just chat.</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role} animate-[grow_0.2s_ease-out]`}>
              {m.content}
            </div>
          ))}
          {loading && (
            <div className="chat-bubble assistant">
              <span className="animate-pulse">🌱</span> thinking...
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-pink-100 p-3 flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            className="flex-1 bg-pink-50 border border-pink-200 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pink-300 focus:border-transparent"
            disabled={loading}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="bg-pink-400 hover:bg-pink-500 disabled:bg-pink-200 text-white font-bold px-5 py-2 rounded-xl transition-colors text-sm"
          >
            {loading ? '🌱' : '🌿 Send'}
          </button>
        </div>
      </div>

      <p className="text-center text-pink-500 text-xs mt-3">
        🌿 Chat is powered by the agent. Responses may take a moment while it thinks.
      </p>
    </div>
  )
}
