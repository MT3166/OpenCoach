import { shallowRef, ref } from 'vue'
import { api, write, resetRequests, setCsrfToken, ApiError } from '../api/client.ts'
import type { SessionState } from '../api/types'
export const session = shallowRef<SessionState | null>(null)
export const logoutPending = ref(false)
export const authMessage = ref('')
try { logoutPending.value = localStorage.getItem('opencoach:logout-pending') === '1' } catch { /* Optional local signal. */ }
if (logoutPending.value) authMessage.value = '退出尚未完成，请联网后重试退出。'
let pending: Promise<SessionState> | null = null
export function resetPrivateData() { resetRequests() }
export async function loadSession() {
  const next = await api<SessionState>('/api/v1/session/')
  if (logoutPending.value) next.user = null
  if (session.value && (session.value.user?.id !== next.user?.id || session.value.user?.role !== next.user?.role)) resetPrivateData()
  session.value = next; setCsrfToken(next.csrf_token)
  return next
}
export function ensureSession() {
  if (session.value) return Promise.resolve(session.value)
  if (!pending) pending = loadSession().finally(() => { pending = null })
  return pending
}
function signalChange() {
  try { localStorage.setItem('opencoach:auth-change',crypto.randomUUID()) } catch { /* Private browser storage may be unavailable. */ }
}
export async function login(username: string, password: string) {
  if (logoutPending.value) throw new ApiError('请先完成退出，再登录其他账号。')
  resetPrivateData()
  const next = await write<SessionState>('/api/v1/auth/login/',{ username, password })
  session.value = next; setCsrfToken(next.csrf_token); signalChange()
  return next
}
export async function logout() {
  resetPrivateData()
  if (session.value) session.value = { ...session.value, user: null }
  logoutPending.value = true
  try { localStorage.setItem('opencoach:logout-pending','1') } catch { /* The current tab still blocks private pages. */ }
  try {
    const next = await write<SessionState>('/api/v1/auth/logout/')
    session.value = next; setCsrfToken(next.csrf_token)
    logoutPending.value = false; authMessage.value = ''
    try { localStorage.removeItem('opencoach:logout-pending') } catch { /* Optional local signal. */ }
    signalChange()
  } catch (error) {
    authMessage.value = '退出尚未完成，请恢复网络后重试退出。'
    throw error
  }
}
export async function acceptInvite(token: string, username: string, password: string, password_confirm: string) {
  resetPrivateData()
  const next = await write<SessionState>(`/api/v1/invitations/${encodeURIComponent(token)}/accept/`,{username,password,password_confirm})
  session.value = next; setCsrfToken(next.csrf_token); signalChange()
}
window.addEventListener('opencoach:unauthenticated',() => {
  resetPrivateData(); session.value = null
  window.dispatchEvent(new Event('opencoach:login-required'))
})
window.addEventListener('opencoach:refresh-session',() => { void loadSession().catch(() => {}) })
window.addEventListener('focus',() => { if (session.value) void loadSession().catch(() => {}) })
window.addEventListener('storage',event => {
  if (event.key === 'opencoach:logout-pending') {
    logoutPending.value = event.newValue === '1'
    if (logoutPending.value) {
      resetPrivateData()
      if (session.value) session.value = { ...session.value, user: null }
      authMessage.value = '退出正在进行，暂时隐藏个人记录。'
      window.dispatchEvent(new Event('opencoach:login-required'))
    } else { authMessage.value=''; void loadSession().catch(() => {}) }
  }
  if (event.key === 'opencoach:auth-change') void loadSession().catch(() => {})
})
