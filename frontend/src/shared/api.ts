import type { Trace } from './types'
const key = 'orbit-session-v1'
let session = localStorage.getItem(key)
if (!session) {
  // Public-IP HTTP previews lack randomUUID; getRandomValues works there too.
  session = typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('')
  localStorage.setItem(key, session)
}
export const sessionId = session
export async function request<T>(projectId: string, path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(path.startsWith('/api') ? path : '/api/projects/' + projectId + path, { method, headers: { 'Content-Type': 'application/json', 'X-Session-ID': sessionId }, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(typeof data.detail === 'string' ? data.detail : `请求失败 (${response.status})`) }
  return response.json()
}
export async function streamRun(projectId: string, body: unknown, signal: AbortSignal, onEvent: (e: Trace) => void) {
  const response = await fetch('/api/projects/' + projectId + '/runs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-ID': sessionId }, body: JSON.stringify(body), signal })
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(typeof data.detail === 'string' ? data.detail : `运行请求失败 (${response.status})`) }
  if (!response.body) throw new Error('浏览器不支持流式响应')
  const reader = response.body.getReader(), decoder = new TextDecoder()
  let buffer = '', ended = false
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2)
        const data = frame.split('\n').filter(l => l.startsWith('data:')).map(l => l.slice(5).trimStart()).join('\n')
        if (data) { const event: Trace = JSON.parse(data); onEvent(event); if (event.type === 'done') ended = true }
      }
      if (done) break
    }
    if (!ended) throw new Error('连接已中断，可在历史记录中检查本次运行状态。')
  } finally { reader.releaseLock() }
}
