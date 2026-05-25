import { useState, useEffect } from 'react'
import { fetchJson, STATE_LABELS, MOOD_EMOJI, formatTimeAgo } from '../hooks/api'

export default function GardenPage({ agentState }) {
  const [stats, setStats] = useState(null)
  const [recentEntries, setRecentEntries] = useState([])

  useEffect(() => {
    fetchJson('/api/journals').then(d => {
      setStats(d.stats)
      setRecentEntries(d.entries.slice(-5).reverse())
    }).catch(() => {})
  }, [])

  return (
    <div className="animate-[grow_0.5s_ease-out]">
      {/* Hero vitals */}
      <section className="mb-8">
        <h2 className="text-lg font-bold text-grass-800 mb-4 flex items-center gap-2">
          <span className="text-2xl">🌱</span> Vital Signs
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <VitalCard label="Total Runs" value={stats?.total_runs || 0} emoji="🔄" color="bg-grass-200" />
          <VitalCard label="Total Commits" value={stats?.total_commits || 0} emoji="💾" color="bg-sky-200" />
          <VitalCard label="Total Cost" value={`$${(stats?.total_cost || 0).toFixed(2)}`} emoji="💰" color="bg-wood-200" />
          <VitalCard label="Day" value={stats?.day_started ? Math.ceil((Date.now() - new Date(stats.day_started)) / 86400000) : 1} emoji="📅" color="bg-flower-pink/20" />
        </div>
      </section>

      {/* Current state */}
      <section className="mb-8">
        <h2 className="text-lg font-bold text-grass-800 mb-4 flex items-center gap-2">
          <span className="text-2xl">🧠</span> Agent State
        </h2>
        <div className="journal-card">
          <div className="flex items-center gap-3 mb-3">
            <span className={`status-pulse ${agentState.state}`} />
            <span className="font-bold text-grass-800">{STATE_LABELS[agentState.state] || agentState.state}</span>
            <span className="text-xl">{MOOD_EMOJI[agentState.mood]}</span>
          </div>
          {agentState.current_task && (
            <p className="text-grass-700 text-sm">
              <span className="font-bold">Task:</span> {agentState.current_task}
            </p>
          )}
          {agentState.current_file && (
            <p className="text-grass-600 text-xs font-mono mt-1">
              📄 {agentState.current_file}
            </p>
          )}
          {agentState.thoughts && (
            <div className="mt-3 bg-sky-100 rounded-lg p-3 text-sm text-sky-800">
              <span className="font-bold">Thought:</span> {agentState.thoughts}
            </div>
          )}
        </div>
      </section>

      {/* Recent journal */}
      <section>
        <h2 className="text-lg font-bold text-grass-800 mb-4 flex items-center gap-2">
          <span className="text-2xl">📔</span> Latest Journal Entries
        </h2>
        {recentEntries.length === 0 ? (
          <div className="journal-card text-center text-grass-600 py-8">
            <div className="text-4xl mb-2">🌱</div>
            <p>No journal entries yet. The garden is still sleeping!</p>
            <p className="text-sm mt-1">Agent will wake up and start growing soon.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {recentEntries.map((e, i) => (
              <div key={i} className="journal-card animate-[grow_0.3s_ease-out]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-bold text-grass-800 text-sm">Day {e.day}</span>
                  <span className="text-grass-500 text-xs">{formatTimeAgo(e.timestamp)}</span>
                  <span className="text-sm">{MOOD_EMOJI[e.mood] || '🌱'}</span>
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
              </div>
            ))}
          </div>
        )}
        <div className="text-center mt-4">
          <a href="/journal" className="text-grass-600 hover:text-grass-800 font-bold text-sm">
            📖 Read all journal entries →
          </a>
        </div>
      </section>
    </div>
  )
}

function VitalCard({ label, value, emoji, color }) {
  return (
    <div className={`${color} rounded-2xl p-4 border-2 border-white/50`}>
      <div className="text-2xl mb-1">{emoji}</div>
      <div className="text-2xl font-bold text-grass-800">{value}</div>
      <div className="text-xs text-grass-600 font-bold uppercase tracking-wide">{label}</div>
    </div>
  )
}
