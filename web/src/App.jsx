import { Routes, Route, NavLink, Link } from 'react-router-dom'
import { useSSE, STATE_LABELS, MOOD_EMOJI, formatTimeAgo } from './hooks/api'
import GardenPage from './pages/Garden'
import JournalPage from './pages/Journal'
import StatsPage from './pages/Stats'
import ChatPage from './pages/Chat'
import AboutPage from './pages/About'

function Nav({ state, mood }) {
  return (
    <nav className="text-center pt-4 pb-2 relative z-10">
      <h1 className="text-3xl font-bold text-grass-800 mb-1">
        🌻 Evo Garden
      </h1>
      <p className="text-grass-700 text-sm mb-3 font-hand">
        A self-evolving coding agent growing up in public
      </p>
      {state.state && (
        <div className="inline-flex items-center gap-2 bg-white/80 backdrop-blur rounded-full px-4 py-1.5 text-sm border border-grass-200">
          <span className={`status-pulse ${state.state}`} />
          <span className="text-grass-800">{STATE_LABELS[state.state] || state.state}</span>
          {state.mood && (
            <span>{MOOD_EMOJI[state.mood] || '🌱'}</span>
          )}
          <span className="text-grass-500 text-xs">{formatTimeAgo(state.last_update)}</span>
        </div>
      )}
      <div className="mt-3 garden-nav">
        <NavLink to="/" className="nav-garden nav-link">🌿 Garden</NavLink>
        <NavLink to="/journal" className="nav-journal nav-link">📔 Journal</NavLink>
        <NavLink to="/stats" className="nav-stats nav-link">📊 Stats</NavLink>
        <NavLink to="/chat" className="nav-chat nav-link">💬 Chat</NavLink>
        <NavLink to="/about" className="nav-journal nav-link">🌸 About</NavLink>
      </div>
    </nav>
  )
}

export default function App() {
  const { status: agentState, connected } = useSSE()

  return (
    <div className="relative min-h-screen pb-20">
      {/* Decorative elements */}
      <div className="cloud" />
      <div className="cloud" />
      <div className="cloud" />
      <div className="cloud" />
      <div className="butterfly">🦋</div>
      <div className="butterfly">🦋</div>
      <div className="butterfly">🦋</div>
      <div className="butterfly">🦋</div>
      <div className="butterfly">🦋</div>

      {/* Playground slide decoration */}
      <svg className="playground-slide" width="200" height="250" viewBox="0 0 200 250">
        <rect x="20" y="20" width="10" height="200" fill="#b45309" rx="3" />
        <rect x="170" y="20" width="10" height="200" fill="#b45309" rx="3" />
        <rect x="15" y="15" width="170" height="10" fill="#d97706" rx="3" />
        <path d="Q 30 80 95 120 Q 160 160 30 220" fill="none" stroke="#06b6d4" strokeWidth="16" strokeLinecap="round" />
        <rect x="15" y="180" width="30" height="8" fill="#b45309" rx="2" transform="rotate(-10 20 185)" />
      </svg>

      <Nav state={agentState} />

      <main className="max-w-4xl mx-auto px-4 pt-6 relative z-10">
        <Routes>
          <Route path="/" element={<GardenPage agentState={agentState} />} />
          <Route path="/journal" element={<JournalPage />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/about" element={<AboutPage />} />
        </Routes>
      </main>

      {/* Grass decoration at bottom */}
      <div className="fixed bottom-0 left-0 right-0 h-16 z-0 pointer-events-none" style={{
        background: 'linear-gradient(0deg, #166534 0%, #16a34a 40%, transparent 100%)'
      }} />
    </div>
  )
}
