function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function renderInline(text) {
  return text
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/_([^_]+)_/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
}

export function renderMarkdownToHtml(markdown = '') {
  const lines = escapeHtml(markdown).split(/\r?\n/)
  const html = []
  let paragraph = []
  let listType = null
  let listItems = []
  let inCodeBlock = false
  let codeLanguage = ''
  let codeLines = []

  function flushParagraph() {
    if (!paragraph.length) return
    html.push(`<p>${renderInline(paragraph.join(' '))}</p>`)
    paragraph = []
  }

  function flushList() {
    if (!listType || !listItems.length) return
    html.push(
      `<${listType}>${listItems.map((item) => `<li>${renderInline(item)}</li>`).join('')}</${listType}>`,
    )
    listType = null
    listItems = []
  }

  function flushCodeBlock() {
    const languageClass = codeLanguage ? ` class="language-${codeLanguage}"` : ''
    html.push(`<pre><code${languageClass}>${codeLines.join('\n')}</code></pre>`)
    codeLines = []
    codeLanguage = ''
  }

  for (const line of lines) {
    const codeFence = line.match(/^```([\w-]+)?\s*$/)
    if (codeFence) {
      flushParagraph()
      flushList()
      if (inCodeBlock) {
        flushCodeBlock()
        inCodeBlock = false
      } else {
        inCodeBlock = true
        codeLanguage = codeFence[1] || ''
        codeLines = []
      }
      continue
    }

    if (inCodeBlock) {
      codeLines.push(line)
      continue
    }

    const trimmed = line.trim()
    if (!trimmed) {
      flushParagraph()
      flushList()
      continue
    }

    const heading = trimmed.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      flushParagraph()
      flushList()
      const level = heading[1].length
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`)
      continue
    }

    const ordered = trimmed.match(/^\d+\.\s+(.*)$/)
    if (ordered) {
      flushParagraph()
      if (listType && listType !== 'ol') flushList()
      listType = 'ol'
      listItems.push(ordered[1])
      continue
    }

    const unordered = trimmed.match(/^[-*+]\s+(.*)$/)
    if (unordered) {
      flushParagraph()
      if (listType && listType !== 'ul') flushList()
      listType = 'ul'
      listItems.push(unordered[1])
      continue
    }

    const quote = trimmed.match(/^>\s?(.*)$/)
    if (quote) {
      flushParagraph()
      flushList()
      html.push(`<blockquote>${renderInline(quote[1])}</blockquote>`)
      continue
    }

    flushList()
    paragraph.push(trimmed)
  }

  if (inCodeBlock) flushCodeBlock()
  flushParagraph()
  flushList()

  return html.join('')
}
