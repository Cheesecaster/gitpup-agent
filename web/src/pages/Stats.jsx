import { useState, useEffect } from 'react'
import { fetchJson, MOOD_EMOJI } from '../hooks/api'

export default function StatsPage() {
  const [stats, setStats] = useState(null)
  const [moods, setMoods] = useState({})

  useEffect(() => {
    fetchJson('/api/journals').then(d => {
      setStats(d.stats)
      // Count moods
      const m = {}
      d.entries.forEach(e => { m[e.mood] = (m[e.mood] || 0) + 1 })
      setMoods(m)
    }).catch(() => {})
  }, [])

  const maxMoodVal = Math.max(...Object.values(moods), 1)
  const totalEntries = Object.values(moods).reduce((a, b) => a + b, 0)

  return (
    <div>
      <h2 className="text-xl font-bold text-sky-800 mb-6 flex items-center gap-2">
        <span className="text-3xl">📊</span> Garden Stats
      </h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <StatBox label="Total Runs" value={stats?.total_runs || 0} emoji="🔄" bg="bg-grass-100" />
        <StatBox label="Total Commits" value={stats?.total_commits || 0} emoji="💾" bg="bg-sky-100" />
        <StatBox label="Total Cost" value={`$${(stats?.total_cost || 0).toFixed(2)}`} emoji="💸" bg="bg-wood-100" />
        <StatBox label="Journal Entries" value={totalEntries} emoji="📔" bg="bg-flower-pink/15" />
      </div>

      {/* Mood distribution */}
      <section className="mb-8">
        <h3 className="text-lg font-bold text-sky-800 mb-4">🎭 Mood Distribution</h3>
        <div className="flex flex-col gap-2 max-w-md">
          {Object.entries(moods).sort((a, b) => b[1] - a[1]).map(([mood, count]) => (
            <div key={mood} className="flex items-center gap-3">
              <span className="w-28 text-sm font-bold text-sky-800">
                {MOOD_EMOJI[mood] || '🌱'} {mood}
              </span>
              <div className="flex-1 bg-white rounded-full h-6 border border-sky-100 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 flex items-center justify-end pr-2 text-xs font-bold text-white"
                  style={{
                    width: `${Math.max(8, (count / maxMoodVal) * 100)}%`,
                    backgroundColor: getMoodColor(mood),
                  }}
                >
                  {count}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Cost info */}
      {stats?.total_cost > 0 && (
        <section className="mb-8">
          <h3 className="text-lg font-bold text-sky-800 mb-4">💰 Cost Breakdown</h3>
          <div className="journal-card max-w-md">
            <p className="text-3xl font-bold text-amber-600">${stats.total_cost.toFixed(2)}</p>
            <p className="text-sky-600 text-sm mt-1">total cost so far</p>
            {stats?.total_tokens > 0 && (
              <p className="text-sky-600 text-xs mt-2 font-mono">
                {stats.total_tokens.toLocaleString()} tokens processed
              </p>
            )}
          </div>
        </section>
      )}

      {totalEntries === 0 && (
        <div className="text-center text-sky-600 py-12">
          <div className="text-5xl mb-3">🌱</div>
          <p>No stats yet. The garden hasn't started growing!</p>
        </div>
      )}
    </div>
  )
}

function getMoodColor(mood) {
  const colors = {
    neutral: '#9ca3af', curious: '#3b82f6', proud: '#10b981',
    confused: '#a855f7', excited: '#f59e0b', thoughtful: '#6366f1', peaceful: '#22c55e',
  }
  return colors[mood] || '#22c55e'
}

function StatBox({ label, value, emoji, bg }) {
  return (
    <div className={`${bg} rounded-2xl p-4 border-2 border-white/60 text-center`}>
      <div className="text-3xl mb-1">{emoji}</div>
      <div className="text-2xl font-bold text-sky-800">{value}</div>
      <div className="text-xs text-sky-600 font-bold uppercase tracking-wide">{label}</div>
    </div>
  )
}
