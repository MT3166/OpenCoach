import { ref, shallowRef, watch, onScopeDispose } from 'vue'
import { api, ApiError } from '../api/client'
export function useResource<T>(path: () => string) {
  const data = shallowRef<T | null>(null), error = shallowRef<ApiError | null>(null), loading = ref(false)
  let controller: AbortController | null = null
  let stamp = 0
  async function refresh() {
    controller?.abort(); controller = new AbortController()
    const current = ++stamp
    const target = path()
    if (!target) { data.value = null; error.value = null; loading.value = false; return }
    loading.value = true; error.value = null
    try { const result = await api<T>(target,{ signal: controller.signal }); if (stamp === current) data.value = result }
    catch (err) { if (stamp === current && !(err instanceof Error && err.name === 'AbortError')) error.value = err as ApiError }
    finally { if (stamp === current) loading.value = false }
  }
  watch(path,() => { data.value = null; void refresh() },{ immediate: true })
  onScopeDispose(() => { stamp++; controller?.abort() })
  return { data, error, loading, refresh }
}
export function useAction() {
  const busy = ref(false), error = shallowRef<ApiError | null>(null), notice = ref('')
  async function run<T>(action: () => Promise<T>, message = ''): Promise<T | undefined> {
    if (busy.value) return
    busy.value = true; error.value = null; notice.value = ''
    try { const result = await action(); notice.value = message; return result }
    catch (err) { if (!(err instanceof Error && err.name === 'AbortError')) error.value = err as ApiError }
    finally { busy.value = false }
  }
  return { busy, error, notice, run }
}
