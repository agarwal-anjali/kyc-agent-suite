import { useEffect, useRef } from 'react'
import UserMessage     from './UserMessage'
import AssistantMessage from './AssistantMessage'

export default function MessageList({ messages }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '60px 0 10px' }}>
      <div style={{ maxWidth: 700, margin: '0 auto', padding: '0 15px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
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
