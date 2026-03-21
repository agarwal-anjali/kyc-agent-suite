import { useState, useCallback } from 'react'
import { MAX_FILES, ACCEPTED_TYPES } from '../constants'

export function useFileUpload() {
  const [files, setFiles]         = useState([])
  const [fileError, setFileError] = useState(null)

  const addFiles = useCallback((incoming) => {
    setFileError(null)
    const candidates = Array.from(incoming).filter(f => ACCEPTED_TYPES.includes(f.type))

    if (candidates.length !== incoming.length) {
      setFileError(`Only PDF, JPG, PNG files are accepted.`)
    }

    setFiles(prev => {
      const combined = [...prev, ...candidates]
      if (combined.length > MAX_FILES) {
        setFileError(`Maximum ${MAX_FILES} documents per message.`)
        return combined.slice(0, MAX_FILES)
      }
      return combined
    })
  }, [])

  const removeFile = useCallback((index) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
    setFileError(null)
  }, [])

  const clearFiles = useCallback(() => {
    setFiles([])
    setFileError(null)
  }, [])

  return { files, fileError, addFiles, removeFile, clearFiles }
}