import { X } from 'lucide-react'

const FIELDS = [
  { key: 'customer_id', label: 'Customer ID', type: 'text',   span: 2 },
  { key: 'full_name',   label: 'Full Name',              type: 'text',   span: 2 },
  { key: 'nationality', label: 'Nationality (ISO)',       type: 'text',   span: 1 },
  { key: 'age',         label: 'Age',                    type: 'number', span: 1 },
  { key: 'address',     label: 'Current Address',        type: 'text',   span: 2 },
  { key: 'occupation',  label: 'Occupation',             type: 'text',   span: 1 },
  { key: 'email',       label: 'Email',                  type: 'email',  span: 1 },
]

const inputStyle = {
  width: '100%', padding: '8px 10px',
  background: 'var(--bg-surface)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)',
  fontSize: 13, fontFamily: 'var(--font-body)',
  transition: 'border-color 0.2s',
}

const labelStyle = {
  display: 'block', marginBottom: 5,
  fontSize: 10, fontFamily: 'var(--font-mono)',
  color: 'var(--text-muted)', letterSpacing: '0.08em',
  textTransform: 'uppercase',
}

export default function CustomerDetailsModal({ value, onChange, onClose }) {
  const handleSubmit = (e) => {
    e.preventDefault()
    const fd   = new FormData(e.target)
    const data = Object.fromEntries(fd.entries())
    // Remove empty strings — treat them as null
    Object.keys(data).forEach(k => { if (!data[k]) data[k] = null })
    // If everything is null after cleanup, pass null instead of an empty object
    const hasAnyValue = Object.values(data).some(v => v !== null)
    onChange(hasAnyValue ? data : null)
    onClose()
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, backdropFilter: 'blur(4px)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--bg-surface)', border: '1px solid var(--border-bright)',
          borderRadius: 'var(--radius-lg)', padding: 28,
          width: 480, maxWidth: '92vw', maxHeight: '85vh', overflowY: 'auto',
          boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
        }}
        onClick={e => e.stopPropagation()}
        className="animate-fade-up"
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <h2 className="font-display" style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 3 }}>
              Customer Details
            </h2>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              All fields optional — fill in what is available
            </p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--text-muted)', padding: 4 }}>
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            {FIELDS.map(f => (
              <div key={f.key} style={{ gridColumn: `span ${f.span}` }}>
                <label style={labelStyle}>{f.label}</label>
                <input
                  type={f.type}
                  name={f.key}
                  defaultValue={value?.[f.key] || ''}
                  placeholder={f.key === 'customer_id' ? 'e.g. CUST-001' : ''}
                  style={inputStyle}
                  onFocus={e => { e.target.style.borderColor = 'var(--gold)' }}
                  onBlur={e =>  { e.target.style.borderColor = 'var(--border)' }}
                />
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 10, marginTop: 22 }}>
            <button
              type="button" onClick={onClose}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)', color: 'var(--text-secondary)',
                fontSize: 13, transition: 'border-color 0.2s',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              style={{
                flex: 2, padding: '10px 0', borderRadius: 'var(--radius-sm)',
                background: 'var(--gold)', border: 'none',
                color: '#0d0f14', fontSize: 13, fontWeight: 500,
                fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
                cursor: 'pointer',
              }}
            >
              Save Details
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
