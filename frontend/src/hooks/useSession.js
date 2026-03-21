import { useState, useCallback } from 'react'
import { createSession } from '../lib/api'
import { generateId, formatDate, truncateWords } from '../lib/utils'
import { USE_MOCK } from '../constants'

export function useSession() {
  const [sessions, setSessions]           = useState([])
  const [activeSessionId, setActiveId]    = useState(null)

  const newSession = useCallback(async () => {
    let sessionId

    if (USE_MOCK) {
      sessionId = `mock-${generateId()}`
    } else {
      const data = await createSession()
      sessionId  = data.session_id
    }

    const session = {
      id:         sessionId,
      preview:    'New conversation',
      createdAt:  new Date(),
      dateLabel:  formatDate(new Date()),
    }

    setSessions(prev => [session, ...prev])
    setActiveId(sessionId)
    return sessionId
  }, [])

  const updatePreview = useCallback((sessionId, preview) => {
    setSessions(prev =>
      prev.map(s => s.id === sessionId ? { ...s, preview: truncateWords(preview, 8) } : s)
    )
  }, [])

  const deleteSession = useCallback((sessionId) => {
    setSessions(prev => prev.filter(s => s.id !== sessionId))
    setActiveId(prev => prev === sessionId ? null : prev)
  }, [])

  return {
    sessions,
    activeSessionId,
    setActiveId,
    newSession,
    updatePreview,
    deleteSession,
  }
}
