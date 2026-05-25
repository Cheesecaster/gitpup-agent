import { useState, useEffect, useRef, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export function useSSE() {
  const [status, setStatus] = useState({
    state: 'sleeping',
    current_task: '',
    current_file: '',
    thoughts: '',
    last_update: 0,
    mood: 'peaceful',
  })
  const [connected, setConnected] = useState(false)
  const eventSourceRef = useRef(null)

  useEffect(() => {
    const url = `${API_BASE}/sse`
    const es = new EventSource(url)
    eventSourceRef.current = es

    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)
    es.onmessage = (e) => {
      try {
        setStatus(JSON.parse(e.data))
      } catch { /* keep existing */ }
    }

    return () => { es.close(); eventSourceRef.current = null }
  }, [])

  return { status, connected }
}

export async function fetchJson(path) {
  const res = await fetch(`${API_BASE}${path}`)
  return res.json()
}

export async function postJson(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

export function formatTimeAgo(ts) {
  if (!ts) return 'never'
  const diff = Date.now() / 1000 - ts
  if (diff < 10) return 'just now'
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export const STATE_LABELS = {
  sleeping: '🌿 Resting in the garden',
  thinking: '🤔 Pondering next move...',
  writing_code: '✏️ Writing code...',
  running_tests: '🧪 Testing the plants...',
  committing: '💾 Saving to the soil...',
  chatting: '💬 Having a conversation!',
}

export const MOOD_EMOJI = {
  peaceful: '😌', focused: '🎯', curious: '🔍', excited: '🎉', confused: '🤔', proud: '🏆',
}
