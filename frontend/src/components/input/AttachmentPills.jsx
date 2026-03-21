import { FileText, User, X } from 'lucide-react'

function Pill({ children, color = 'var(--text-muted)', onRemove }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: 'var(--bg-hover)', border: '1px solid var(--border)',
      borderRadius: 5, padding: '3px 8px',
      fontSize: 11, fontFamily: 'var(--font-mono)', color,
    }}>
      {children}
      {onRemove && (
        <button onClick={onRemove} style={{ display: 'flex', alignItems: 'center', opacity: 0.6 }}>
          <X size={9} />
        </button>
      )}
    </div>
  )
}

export default function AttachmentPills({ files, customerDetails, onRemoveFile, onClearCustomer }) {
  const hasContent = files.length > 0 || customerDetails

  if (!hasContent) return null

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '6px 0 2px' }}>
      {files.map((f, i) => (
        <Pill key={i} onRemove={() => onRemoveFile(i)}>
          <FileText size={9} style={{ color: 'var(--gold)' }} />
          <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {f.name}
          </span>
        </Pill>
      ))}
      {customerDetails && !customerDetails.is_empty && (
        <Pill color="var(--gold)" onRemove={onClearCustomer}>
          <User size={9} />
          {customerDetails.full_name || customerDetails.customer_id}
        </Pill>
      )}
    </div>
  )
}