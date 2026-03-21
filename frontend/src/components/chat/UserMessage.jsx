import { User, FileText } from 'lucide-react'
import { formatTime } from '../../lib/utils'

export default function UserMessage({ message }) {
  const { content, attachments = [], customerDetails, timestamp } = message

  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}
      className="animate-fade-up">

      <div style={{ maxWidth: '72%' }}>
        {/* Attachment indicators */}
        {(attachments.length > 0 || customerDetails) && (
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'flex-end', gap: 5, marginBottom: 5 }}>
            {attachments.map((name, i) => (
              <span key={i} style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                background: 'var(--bg-hover)', border: '1px solid var(--border)',
                borderRadius: 4, padding: '2px 7px',
                fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
              }}>
                <FileText size={9} style={{ color: 'var(--gold)' }} />
                <span style={{ maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {name}
                </span>
              </span>
            ))}
            {customerDetails && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)',
                borderRadius: 4, padding: '2px 7px',
                fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--gold)',
              }}>
                <User size={9} />
                {customerDetails.full_name || customerDetails.customer_id}
              </span>
            )}
          </div>
        )}

        {/* Message bubble */}
        <div style={{
          background: 'var(--gold)', color: '#0d0f14',
          borderRadius: '10px 2px 10px 10px',
          padding: '10px 14px', fontSize: 14, lineHeight: 1.65,
        }}>
          {content}
        </div>

        {/* Timestamp */}
        <p style={{
          fontSize: 10, color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)', textAlign: 'right', marginTop: 4,
        }}>
          {formatTime(timestamp)}
        </p>
      </div>

      {/* Avatar */}
      <div style={{
        width: 30, height: 30, borderRadius: 8, flexShrink: 0,
        background: 'var(--bg-hover)', border: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 2,
      }}>
        <User size={13} style={{ color: 'var(--text-muted)' }} />
      </div>
    </div>
  )
}