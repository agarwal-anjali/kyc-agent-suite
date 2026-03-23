import { useState, useCallback } from 'react'
import { sendMessage }   from '../lib/api'
import { parseSSEStream } from '../lib/sse'
import { toBase64 }      from '../lib/utils'

// Map status strings to pipeline step keys
function resolveStepKey(msg) {
  const m = msg.toLowerCase()
  if (m.includes('document') || m.includes('analys')) return 'doc'
  if (m.includes('regulat'))                           return 'reg'
  if (m.includes('risk'))                              return 'risk'
  if (m.includes('generat') || m.includes('response')) return 'report'
  return null
}

export function useChat({ sessionId, onFirstMessage }) {
  const [messages, setMessages] = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  const clearMessages = useCallback(() => setMessages([]), [])

  const sendChat = useCallback(async ({ query, files, customerDetails }) => {
    if (loading) return
    setError(null)
    setLoading(true)

    const userMsgId      = Date.now()
    const assistantMsgId = Date.now() + 1

    // Append user message immediately
    const userMsg = {
      id:              userMsgId,
      type:            'user',
      content:         query || '(attached documents)',
      attachments:     files.map(f => f.name),
      customerDetails,
      timestamp:       new Date(),
    }
    setMessages(prev => [...prev, userMsg])

    // Append streaming placeholder
    setMessages(prev => [...prev, {
      id:           assistantMsgId,
      type:         'assistant',
      content:      '',
      isStreaming:  true,
      intent:       null,
      plan:         null,
      planSteps:    null,
      stepStatuses: {},
      riskScore:    null,
      verdict:      null,
      timestamp:    new Date(),
    }])

    onFirstMessage?.(query)

    try {
      const docsB64 = await Promise.all(files.map(toBase64))
      const reader  = await sendMessage({ sessionId, query, docsB64, customerDetails })
      let streamError = null

      await parseSSEStream(reader, (type, data) => {
        if (type === 'error') {
          streamError = new Error(data.trim())
          return
        }

        setMessages(prev => prev.map(m => {
          if (m.id !== assistantMsgId) return m

          if (type === 'plan') {
            try {
              const plan = JSON.parse(data)
              return { ...m, plan, intent: plan.intent, planSteps: plan.steps }
            } catch { return m }
          }

          if (type === 'step_update') {
            const [key, status] = data.trim().split(':')
            return { ...m, stepStatuses: { ...m.stepStatuses, [key]: status } }
          }

          if (type === 'status') {
            const key = resolveStepKey(data)
            if (!key) return m
            const next = { ...m.stepStatuses }
            // Mark previous running step done before starting next
            Object.keys(next).forEach(k => { if (next[k] === 'running') next[k] = 'done' })
            next[key] = 'running'
            if (data.toLowerCase().includes('complete')) {
              Object.keys(next).forEach(k => { next[k] = 'done' })
            }
            return { ...m, stepStatuses: next }
          }

          if (type === 'risk_score') {
            try {
              const score = JSON.parse(data)
              const verdictMap = { LOW: 'PASS', MEDIUM: 'REFER', HIGH: 'FAIL' }
              return {
                ...m,
                riskScore: score,
                verdict:   verdictMap[score.overall_risk_tier] || 'REFER',
              }
            } catch { return m }
          }

          if (type === 'report_token') {
            return { ...m, content: m.content + data }
          }

          if (type === 'report_complete') {
            return { ...m, content: data, isStreaming: false }
          }

          return m
        }))
      })

      if (streamError) throw streamError

    } catch (e) {
      const message = e?.message?.trim() || 'Something went wrong while generating the response.'
      setError(message)
      setMessages(prev => prev.map(m => {
        if (m.id !== assistantMsgId) return m
        return {
          ...m,
          content: `I couldn't complete this request.\n\nError: ${message}`,
          isStreaming: false,
          stepStatuses: Object.fromEntries(
            Object.entries(m.stepStatuses).map(([k]) => [k, 'done'])
          ),
        }
      }))
    } finally {
      setLoading(false)
      // Mark all steps done and stop streaming cursor
      setMessages(prev => prev.map(m => {
        if (m.id !== assistantMsgId) return m
        const finalSteps = Object.fromEntries(
          Object.entries(m.stepStatuses).map(([k]) => [k, 'done'])
        )
        return { ...m, isStreaming: false, stepStatuses: finalSteps }
      }))
    }
  }, [sessionId, loading, onFirstMessage])

  return { messages, loading, error, setError, sendChat, clearMessages }
}
