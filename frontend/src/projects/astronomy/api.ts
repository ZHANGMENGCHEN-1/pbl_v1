import { request as sharedRequest, streamRun as sharedStream } from '../../shared/api'
import type { Trace } from '../../shared/types'

export const PROJECT_ID = 'astronomy-lab'
export function request<T>(path: string, method = 'GET', body?: unknown) { return sharedRequest<T>(PROJECT_ID, path, method, body) }
export function streamRun(body: unknown, signal: AbortSignal, receive: (event: Trace) => void) { return sharedStream(PROJECT_ID, body, signal, receive) }
