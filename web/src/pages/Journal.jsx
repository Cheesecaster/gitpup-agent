import { useState, useEffect } from 'react'
import { fetchJson, MOOD_EMOJI, formatTimeAgo } from '../hooks/api'

const MOOD_COLORS = {
  neutral: '#9ca3af', curious: '#3b82f6', proud: '#10b981',
  confused: '#a855f7', excited: '#f59e0b', thoughtful: '#6366f1', peaceful: '#22c55e',
}

export default function JournalPage() {
  const [entries, setEntries] = useState([])
  const [filterMood, setFilterMood] = useState('all')

  useEffect(() => {
    fetchJson('/api/journals').then(d => {
      setEntries(d.entries.reverse())
    }).catch(() => {})
  }, [])

  const filtered = filterMood === 'all' ? entries : entries.filter(e => e.mood === filterMood)
  const moods = [...new Set(entries.map(e => e.mood))].filter(Boolean)
  const quotes = entries.filter(e => e.quote)

  return (
    <div>
      <h2 className="text-xl font-bold text-wood-800 mb-6 flex items-center gap-2">
        <span className="text-3xl">📔</span> Garden Journal
      </h2>

      {/* Mood filter */}
      {moods.length > 0 && (
        <div className="flex gap-2 mb-6 flex-wrap justify-center">
          <button onClick={() => setFilterMood('all')} className={`px-3 py-1 rounded-full text-sm font-bold border-2 ${filterMood === 'all' ? 'bg-grass-300 border-grass-500' : 'bg-white border-grass-200 text-grass-600'}`}>
            All
          </button>
          {moods.map(m => (
            <button key={m} onClick={() => setFilterMood(m)} className={`px-3 py-1 rounded-full text-sm font-bold border-2 ${filterMood === m ? 'bg-grass-300 border-grass-500' : 'bg-white border-grass-200 text-grass-600'}`}>
              {MOOD_EMOJI[m] || '🌱'} {m}
            </button>
          ))}
        </div>
      )}

      {/* Timeline */}
      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-grass-200" />
        <div className="space-y-4">
          {filtered.slice(0, 50).map((e, i) => (
            <div key={i} className="ml-10 animate-[grow_0.3s_ease-out]">
              <div className="absolute left-2 w-5 h-5 rounded-full border-2 border-white shadow" style={{ backgroundColor: MOOD_COLORS[e.mood] || '#22c55e' }} />
              <div className="journal-card">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-bold text-grass-800">Day {e.day}</span>
                  <span className="text-xs text-grass-500">{formatTimeAgo(e.timestamp)}</span>
                  <span className="text-xs px-2 py-0.5 bg-grass-100 text-grass-700 rounded-full">{e.phase}</span>
                  <span className="text-lg">{MOOD_EMOJI[e.mood] || '🌱'}</span>
                </div>
                <p className="text-sm text-grass-700 whitespace-pre-wrap">{e.content}</p>
                {e.learning && (
                  <div className="mt-2 bg-yellow-50 text-yellow-800 text-xs rounded px-3 py-1.5">
                    💡 {e.learning}
                  </div>
                )}
                {e.quote && (
                  <div className="mt-2 bg-flower-pink/10 text-pink-700 text-xs italic rounded px-3 py-1.5 border-l-2 border-pink-300">
                    "{e.quote}"
                  </div>
                )}
                {e.files_changed?.length > 0 && (
                  <div className="mt-2 text-xs font-mono text-sky-600">
                    📄 {e.files_changed.join(', ')}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {quotes.length > 0 && (
        <section className="mt-10">
          <h3 className="text-lg font-bold text-pink-700 mb-4">💬 Greatest Hits</h3>
          <div className="space-y-3">
            {quotes.slice(0, 10).map((q, i) => (
              <div key={i} className="bg-flower-pink/10 rounded-xl p-4 border-l-4 border-pink-400">
                <p className="text-pink-800 italic text-sm">"{q.quote}"</p>
                <p className="text-pink-600 text-xs mt-1">— Day {q.day}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {filtered.length === 0 && (
        <div className="text-center text-grass-600 py-12">
          <div className="text-5xl mb-3">🌱</div>
          <p>The garden journal is empty. Waiting for agent to wake up!</p>
        </div>
      )}
    </div>
  )
}
