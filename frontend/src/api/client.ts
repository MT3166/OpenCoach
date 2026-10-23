export class ApiError extends Error {
  status: number
  code: string
  fields: Record<string, string[]>
  constructor(message: string, status = 0, code = 'network_error', fields: Record<string, string[]> = {}) {
    super(message); this.status = status; this.code = code; this.fields = fields
  }
}
let csrfToken = ''
let generation = 0
const requests = new Set<AbortController>()
export function setCsrfToken(token: string) { csrfToken = token }
export function resetRequests() {
  generation++
  for (const controller of requests) controller.abort()
  requests.clear()
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!path.startsWith('/api/v1/')) throw new ApiError('接口地址无效')
  const stamp = generation
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (init.signal?.aborted) controller.abort()
  init.signal?.addEventListener('abort', abort, { once: true })
  requests.add(controller)
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (!['GET','HEAD'].includes((init.method || 'GET').toUpperCase())) {
    headers.set('Content-Type', 'application/json')
    headers.set('X-CSRFToken', csrfToken)
  }
  try {
    let response: Response
    try { response = await fetch(path, { ...init, headers, signal: controller.signal, credentials: 'same-origin', cache: 'no-store' }) }
    catch (err) {
      if (controller.signal.aborted || (err instanceof Error && err.name === 'AbortError')) throw new DOMException('请求已取消','AbortError')
      throw new ApiError('网络连接中断，内容已保留，请稍后重试。')
    }
    if (stamp !== generation) throw new DOMException('身份已改变','AbortError')
    let payload: { data?: T; error?: { message: string; code: string; fields?: Record<string,string[]> } }
    try { payload = await response.json() }
    catch { throw new ApiError('暂时无法读取服务器结果，请刷新后核对记录。',response.status,'invalid_response') }
    if (stamp !== generation) throw new DOMException('身份已改变','AbortError')
    if (!response.ok || payload.error) {
      const error = new ApiError(payload.error?.message || '操作没有完成，请重试。', response.status, payload.error?.code || 'request_failed', payload.error?.fields)
      if (error.code === 'unauthenticated' && typeof window !== 'undefined') window.dispatchEvent(new Event('opencoach:unauthenticated'))
      if (error.code === 'csrf_failed' && typeof window !== 'undefined') window.dispatchEvent(new Event('opencoach:refresh-session'))
      throw error
    }
    return payload.data as T
  } finally {
    requests.delete(controller)
    init.signal?.removeEventListener('abort', abort)
  }
}
export function write<T>(path: string, data: unknown = {}, method = 'POST') {
  return api<T>(path, { method, body: JSON.stringify(data) })
}
