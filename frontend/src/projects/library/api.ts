import { request, streamRun } from '../../shared/api'
import type { Trace } from '../../shared/types'
export const PROJECT_ID = 'library-recommendation'
export function api<T>(path: string, method = 'GET', body?: unknown) { return request<T>(PROJECT_ID, path, method, body) }
export function runStream(body: unknown, signal: AbortSignal, receive: (event: Trace) => void) { return streamRun(PROJECT_ID, body, signal, receive) }
