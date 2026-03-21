import { useRef, useEffect, useState } from 'react'
import WelcomeScreen from '../chat/WelcomeScreen'
import MessageList   from '../chat/MessageList'
import ChatInput     from '../input/ChatInput'
import { AlertTriangle, X } from 'lucide-react'

export default function ChatLayout({
  messages, loading, error, onClearError,
  onSend, onSuggestion,
  files, fileError, onAddFiles, onRemoveFile, onClearFiles,
  customerDetails, onSetCustomerDetails,
}) {
  const hasMessages = messages.length > 0

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* Message area */}
      {hasMessages
        ? <MessageList messages={messages} />
        : (
          <WelcomeScreen
            onSuggestion={text => {
              onSuggestion(text)
            }}
          />
        )
      }

      {/* Error banner */}
      {error && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--danger-dim)', borderTop: '1px solid var(--border)',
          padding: '8px 20px',
        }}>
          <AlertTriangle size={13} style={{ color: 'var(--danger)', flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: 'var(--danger)', flex: 1 }}>{error}</span>
          <button onClick={onClearError} style={{ color: 'var(--danger)' }}>
            <X size={13} />
          </button>
        </div>
      )}

      {/* Input */}
      <ChatInput
        onSend={onSend}
        loading={loading}
        files={files}
        fileError={fileError}
        onAddFiles={onAddFiles}
        onRemoveFile={onRemoveFile}
        onClearFiles={onClearFiles}
        customerDetails={customerDetails}
        onSetCustomerDetails={onSetCustomerDetails}
      />
    </div>
  )
}