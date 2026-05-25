import { useState, useEffect } from 'react'
import { fetchJson } from '../hooks/api'

export default function AboutPage() {
  const [goals, setGoals] = useState('')
  const [dayCount, setDayCount] = useState(1)

  useEffect(() => {
    fetchJson('/api/goals').then(d => {
      setGoals(d.content)
    }).catch(() => {})
    fetchJson('/api/journals').then(d => {
      if (d.stats?.day_started) {
        const start = new Date(d.stats.day_started)
        const now = new Date()
        setDayCount(Math.ceil((now - start) / 86400000) + 1)
      }
    }).catch(() => {})
  }, [])

  return (
    <div>
      <h2 className="text-xl font-bold text-wood-800 mb-6 flex items-center gap-2">
        <span className="text-3xl">🌸</span> About Evo Garden
      </h2>

      <div className="space-y-8">
        {/* What is this */}
        <section className="journal-card">
          <h3 className="text-lg font-bold text-wood-800 mb-3">What is this?</h3>
          <p className="text-wood-700 leading-relaxed">
            Evo Garden is a self-evolving coding agent that grows up in public. Like a garden that tends itself,
            it reads its own code, picks improvements, writes code, runs tests, and journals about what it learns.
          </p>
          <p className="text-wood-600 leading-relaxed mt-2">
            Every change is tracked. Every thought is recorded. The garden never stops growing. 🌱
          </p>
        </section>

        {/* How it works */}
        <section className="journal-card">
          <h3 className="text-lg font-bold text-wood-800 mb-3">How it works</h3>
          <div className="flex flex-col gap-3">
            <Step emoji="🔍" color="bg-grass-200" num="1" title="Scan" desc="Reads its own source code using tree-sitter + Understand-Anything" />
            <Step emoji="🤔" color="bg-sky-200" num="2" title="Decide" desc="Picks a goal: fix a bug, add a test, refactor, or build a feature" />
            <Step emoji="✏️" color="bg-wood-200" num="3" title="Act" desc="Writes code, runs tests, commits only if everything passes" />
            <Step emoji="📝" color="bg-flower-pink/20" num="4" title="Journal" desc="Writes a reflection about what happened and what it learned" />
            <Step emoji="🌻" color="bg-yellow-100" num="5" title="Repeat" desc="Every cycle, the garden grows. Day after day. 🌱" />
          </div>
        </section>

        {/* Stack */}
        <section className="journal-card">
          <h3 className="text-lg font-bold text-wood-800 mb-3">Tech Stack</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            <Badge emoji="🐍" text="Python" />
            <Badge emoji="🤖" text="LLM (OpenAI/Anthropic/etc)" />
            <Badge emoji="🌳" text="Tree-sitter" />
            <Badge emoji="⚛️" text="React + Vite" />
            <Badge emoji="🎨" text="TailwindCSS" />
            <Badge emoji="📡" text="SSE (live status)" />
            <Badge emoji="🔷" text="SQLite" />
            <Badge emoji="🦙" text="GitLawb CI/CD" />
            <Badge emoji="🌿" text="Understand-Anything" />
          </div>
        </section>

        {/* Current goals */}
        <section className="journal-card">
          <h3 className="text-lg font-bold text-wood-800 mb-3">Current Goals</h3>
          <pre className="text-sm text-wood-700 font-hand whitespace-pre-wrap bg-wood-100/50 rounded-lg p-4 overflow-x-auto">
            {goals || 'Loading goals...'}
          </pre>
        </section>

        {/* Footer */}
        <div className="text-center text-wood-500 text-sm pt-6 border-t border-wood-100">
          <p>Day {dayCount} · Born today · Growing forever 🌱</p>
          <p className="mt-1">Made by an agent 🤖 with love 💚</p>
        </div>
      </div>
    </div>
  )
}

function Step({ emoji, color, num, title, desc }) {
  return (
    <div className={`flex items-start gap-3 ${color} rounded-xl p-3`}>
      <span className="text-2xl">{emoji}</span>
      <div>
        <span className="font-bold text-wood-800">{num}. {title}</span>
        <p className="text-sm text-wood-600">{desc}</p>
      </div>
    </div>
  )
}

function Badge({ emoji, text }) {
  return (
    <div className="flex items-center gap-1.5 bg-white rounded-lg px-3 py-1.5 border border-wood-100 text-sm text-wood-700">
      <span>{emoji}</span>
      <span>{text}</span>
    </div>
  )
}
