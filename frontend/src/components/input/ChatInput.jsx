import { useRef, useEffect, useState } from 'react'
import { Paperclip, User, Send, Loader2 } from 'lucide-react'
import AttachmentPills from './AttachmentPills'
import CustomerDetailsModal from './CustomerDetailsModal'
import { MAX_FILES } from '../../constants'

export default function ChatInput({
  onSend, loading,
  files, fileError, onAddFiles, onRemoveFile, onClearFiles,
  customerDetails, onSetCustomerDetails,
}) {
  const [query, setQuery]               = useState('')
  const [showModal, setShowModal]       = useState(false)
  const [isDragging, setIsDragging]     = useState(false)
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [query])

  const canSend = (query.trim() || files.length > 0) && !loading

  const handleSend = () => {
    if (!canSend) return
    onSend({ query: query.trim(), files, customerDetails })
    setQuery('')
    onClearFiles()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    onAddFiles(e.dataTransfer.files)
  }

  const hasAttachments = files.length > 0 || (customerDetails && !customerDetails.is_empty)

  return (
    <>
      <div style={{ padding: '10px 16px 18px'}}>
        <div style={{ maxWidth: 800, margin: '0 auto' }}>

          {/* Attachment pills */}
          {hasAttachments && (
            <AttachmentPills
              files={files}
              customerDetails={customerDetails}
              onRemoveFile={onRemoveFile}
              onClearCustomer={() => onSetCustomerDetails(null)}
            />
          )}

          {/* File error */}
          {fileError && (
            <p style={{ fontSize: 11, color: 'var(--danger)', fontFamily: 'var(--font-mono)', margin: '4px 0' }}>
              {fileError}
            </p>
          )}

          {/* Input box */}
          <div
            onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            style={{
              display: 'flex', alignItems: 'flex-end', gap: 8,
              background: 'var(--bg-card)',
              border: `1px solid ${isDragging ? 'var(--gold)' : 'var(--border-bright)'}`,
              borderRadius: 'var(--radius-md)', padding: '8px 10px',
              transition: 'border-color 0.2s',
              boxShadow: isDragging ? `0 0 0 3px var(--gold-dim)` : 'none',
            }}
          >
            {/* Attach */}
            <button
              title={`Attach documents (max ${MAX_FILES})`}
              onClick={() => fileInputRef.current?.click()}
              style={{
                flexShrink: 0, padding: 6, borderRadius: 6,
                color: files.length > 0 ? 'var(--gold)' : 'var(--text-muted)',
                transition: 'color 0.2s',
              }}
            >
              <Paperclip size={16} />
            </button>
            <input
              ref={fileInputRef} type="file"
              accept=".pdf,image/*" multiple
              style={{ display: 'none' }}
              onChange={e => { onAddFiles(e.target.files); e.target.value = '' }}
            />

            {/* Customer details */}
            <button
              title={customerDetails ? 'Edit customer details' : 'Add customer details'}
              onClick={() => setShowModal(true)}
              style={{
                flexShrink: 0, padding: 6, borderRadius: 6,
                color: customerDetails ? 'var(--gold)' : 'var(--text-muted)',
                transition: 'color 0.2s',
              }}
            >
              <User size={16} />
            </button>

            {/* Textarea */}
            <textarea
              ref={textareaRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a compliance question, run a KYC check, or analyse documents…"
              rows={1}
              style={{
                flex: 1, resize: 'none', lineHeight: 1.6,
                maxHeight: 160, overflowY: 'auto',
                fontSize: 14, background: 'none',
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-body)',
                padding: '6px 8px',
              }}
            />

            {/* Send */}
            <button
              onClick={handleSend}
              disabled={!canSend}
              style={{
                flexShrink: 0, width: 34, height: 34, borderRadius: 8,
                background: canSend ? 'var(--gold)' : 'var(--bg-hover)',
                color: canSend ? '#0d0f14' : 'var(--text-muted)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.2s', border: 'none',
              }}
            >
              {loading
                ? <Loader2 size={15} className="animate-spin" />
                : <Send size={15} />
              }
            </button>
          </div>

          <p style={{ fontSize: 10, color: 'var(--text-muted)', textAlign: 'center', marginTop: 6, fontFamily: 'var(--font-mono)' }}>
            Drag & drop · Enter to send · Shift+Enter for new line · Max {MAX_FILES} files
          </p>
        </div>
      </div>

      {showModal && (
        <CustomerDetailsModal
          value={customerDetails}
          onChange={onSetCustomerDetails}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  )
}