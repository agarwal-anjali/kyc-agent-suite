import { ENDPOINTS, USE_MOCK } from '../constants'

export async function createSession() {
  const res  = await fetch(ENDPOINTS.newSession(), { method: 'POST' })
  if (!res.ok) throw new Error('Failed to create session')
  return res.json()
}

export async function getHistory(sessionId) {
  const res = await fetch(ENDPOINTS.history(sessionId))
  if (!res.ok) throw new Error('Failed to fetch history')
  return res.json()
}

export function getStreamEndpoint(sessionId) {
  return USE_MOCK ? ENDPOINTS.mockStream() : ENDPOINTS.stream(sessionId)
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