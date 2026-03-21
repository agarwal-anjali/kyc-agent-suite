export const toBase64 = (file) =>
  new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload  = () => resolve(r.result.split(',')[1])
    r.onerror = reject
    r.readAsDataURL(file)
  })

export const generateId = () =>
  Math.random().toString(36).slice(2, 10).toUpperCase()

export const formatTime = (date) => {
  const d = date instanceof Date ? date : new Date(date)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export const formatDate = (date) => {
  const d = date instanceof Date ? date : new Date(date)
  const today     = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)

  if (d.toDateString() === today.toDateString())     return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

export const truncate = (str, n = 50) =>
  str?.length > n ? str.slice(0, n) + '…' : str

export const truncateWords = (str, wordCount = 8) => {
  if (!str) return ''
  const words = str.trim().split(/\s+/)
  if (words.length <= wordCount) return words.join(' ')
  return `${words.slice(0, wordCount).join(' ')}…`
}
