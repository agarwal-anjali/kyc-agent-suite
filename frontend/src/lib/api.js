import { ENDPOINTS, USE_MOCK } from '../constants'

// In development, call the backend directly to avoid Vite proxy buffering SSE.
// VITE_API_URL is set in .env.development to http://localhost:8000
// In production this will be an empty string so relative URLs are used.
const BASE = import.meta.env.VITE_API_URL || ''

export async function createSession() {
  const res = await fetch(`${BASE}${ENDPOINTS.newSession()}`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to create session')
  return res.json()
}

export async function getHistory(sessionId) {
  const res = await fetch(`${BASE}${ENDPOINTS.history(sessionId)}`)
  if (!res.ok) throw new Error('Failed to fetch history')
  return res.json()
}

export function getStreamEndpoint(sessionId) {
  return USE_MOCK
    ? `${BASE}${ENDPOINTS.mockStream()}`
    : `${BASE}${ENDPOINTS.stream(sessionId)}`
}

export async function sendMessage({ sessionId, query, docsB64, customerDetails }) {
  const endpoint = getStreamEndpoint(sessionId)
  const res = await fetch(endpoint, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id:       sessionId,
      query,
      documents_b64:    docsB64,
      customer_details: customerDetails,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.body.getReader()
}