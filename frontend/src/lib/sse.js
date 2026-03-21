/**
 * Parse an SSE stream from a ReadableStream reader.
 * Calls onEvent(type, data) for each complete SSE event received.
 */
function parseEventBlock(block, onEvent) {
  if (!block.trim()) return

  let eventType = null
  const dataLines = []

  for (const rawLine of block.split(/\r?\n/)) {
    const line = rawLine.replace(/\r$/, '')

    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim()
    }

    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^\s/, ''))
    }
  }

  if (eventType && dataLines.length > 0) {
    onEvent(eventType, dataLines.join('\n'))
  }
}

export async function parseSSEStream(reader, onEvent) {
  const decoder = new TextDecoder()
  let   buffer  = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split(/\r?\n\r?\n/)
    buffer = events.pop() // keep incomplete event in buffer

    for (const block of events) {
      parseEventBlock(block, onEvent)
    }
  }

  const finalBlock = buffer.trim()
  if (finalBlock) {
    parseEventBlock(finalBlock, onEvent)
  }
}
