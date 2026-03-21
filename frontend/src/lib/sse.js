/**
 * Parse an SSE stream from a ReadableStream reader.
 * Calls onEvent(type, data) for each complete SSE event received.
 */
export async function parseSSEStream(reader, onEvent) {
  const decoder = new TextDecoder()
  let   buffer  = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() // keep incomplete event in buffer

    for (const block of events) {
      if (!block.trim()) continue
      let eventType = null
      let eventData = null

      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim()
        if (line.startsWith('data:'))  eventData = line.slice(5)  // preserve whitespace
      }

      if (eventType && eventData !== null) {
        onEvent(eventType, eventData)
      }
    }
  }
}