import { useEffect, useRef } from 'react'
import UserMessage     from './UserMessage'
import AssistantMessage from './AssistantMessage'

export default function MessageList({ messages }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '20px 0' }}>
      <div style={{ maxWidth: 720, margin: '0 auto', padding: '0 20px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {messages.map(m =>
            m.type === 'user'
              ? <UserMessage      key={m.id} message={m} />
              : <AssistantMessage key={m.id} message={m} />
          )}
        </div>
        <div ref={bottomRef} style={{ height: 16 }} />
      </div>
    </div>
  )
}