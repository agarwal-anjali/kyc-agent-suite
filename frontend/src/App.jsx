import { useEffect, useState, useCallback } from 'react'
import Sidebar    from './components/layout/Sidebar'
import ChatLayout from './components/layout/ChatLayout'
import { useSession }    from './hooks/useSession'
import { useChat }       from './hooks/useChat'
import { useFileUpload } from './hooks/useFileUpload'

export default function App() {
  const {
    sessions, activeSessionId,
    setActiveId, newSession, updatePreview, deleteSession,
  } = useSession()

  const [customerDetails, setCustomerDetails] = useState(null)

  // Initialise with one session on mount
  useEffect(() => { newSession() }, [newSession])

  // Per-session chat state
  const onFirstMessage = useCallback((query) => {
    if (activeSessionId) updatePreview(activeSessionId, query)
  }, [activeSessionId, updatePreview])

  const {
    messages, loading, error, setError, sendChat, clearMessages,
  } = useChat({ sessionId: activeSessionId, onFirstMessage })

  const {
    files, fileError, addFiles, removeFile, clearFiles,
  } = useFileUpload()

  // Switch session
  const handleSelectSession = (sid) => {
    setActiveId(sid)
    clearMessages()
    setCustomerDetails(null)
    clearFiles()
  }

  const handleNewChat = async () => {
    clearMessages()
    setCustomerDetails(null)
    clearFiles()
    await newSession()
  }

  const handleSend = ({ query, files, customerDetails }) => {
    sendChat({ query, files, customerDetails })
  }
  const handleSuggestion = (text) => {
    // We fire it as a message directly
    sendChat({ query: text, files: [], customerDetails })
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        onDeleteSession={deleteSession}
      />
      <ChatLayout
        messages={messages}
        loading={loading}
        error={error}
        onClearError={() => setError(null)}
        onSend={handleSend}
        onSuggestion={handleSuggestion}
        files={files}
        fileError={fileError}
        onAddFiles={addFiles}
        onRemoveFile={removeFile}
        onClearFiles={clearFiles}
        customerDetails={customerDetails}
        onSetCustomerDetails={setCustomerDetails}
      />
    </div>
  )
}
