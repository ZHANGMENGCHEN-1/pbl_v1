import type { Trace } from './types'

/** Show the latest model turn while keeping structured purchase JSON out of the UI. */
export function streamAnswer(events: Trace[], structured = false): string {
  const final = events.findLast(event => event.type === 'final')
  if (final) return String(final.data.answer || '')
  const start = events.findLastIndex(event => event.type === 'llm_start')
  const text = events.slice(start + 1).filter(event => event.type === 'llm_delta').map(event => event.data.text || '').join('')
  if (!structured) return text
  const match = text.match(/"answer"\s*:\s*"((?:[^"\\]|\\.)*)/)
  if (!match) return ''
  let fragment = match[1] || ''
  // A chunk can end in the middle of an escaped Unicode character.
  for (let i = 0; i < 7; i++) {
    try { return JSON.parse('"' + fragment + '"') as string } catch { fragment = fragment.slice(0, -1) }
  }
  return ''
}
