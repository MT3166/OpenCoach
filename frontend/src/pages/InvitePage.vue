<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { acceptInvite, session } from '../state/session'
import { useResource, useAction } from '../lib/useResource'
import Field from '../components/Field.vue'
import FormFeedback from '../components/FormFeedback.vue'
import ResourceState from '../components/ResourceState.vue'
const route = useRoute(), router = useRouter()
const { data, error: loadError, loading, refresh } = useResource<{student_name:string;expires_at:string}>(() => `/api/v1/invitations/${encodeURIComponent(String(route.params.token))}/`)
const username = ref(''), password = ref(''), confirmation = ref('')
const { busy, error, run } = useAction()
async function submit() {
  const result = await run(() => acceptInvite(String(route.params.token),username.value,password.value,confirmation.value))
  if (!error.value && !busy.value && session.value?.user) { password.value=''; confirmation.value=''; await router.replace('/student/') }
}
</script>
<template><main class="invite-page"><div class="brand"><span class="brand-mark">{{ session?.brand.coach_name.slice(0,1) }}</span>{{ session?.brand.display_name }}</div><ResourceState :error="loadError" :loading="loading" @retry="refresh" /><section v-if="data" class="surface"><h1>{{ data.student_name }}，欢迎加入</h1><p>设置账号，查看你的课时与每一节课的记录。</p><form class="stack-form" @submit.prevent="submit"><Field label="设置账号" :errors="error?.fields.username"><input v-model="username" required autocomplete="username" maxlength="150" /></Field><Field label="设置密码" hint="至少8位，建议组合字母与数字" :errors="error?.fields.password"><input v-model="password" required type="password" autocomplete="new-password" minlength="8" /></Field><Field label="再次输入密码" :errors="error?.fields.password_confirm"><input v-model="confirmation" required type="password" autocomplete="new-password" /></Field><FormFeedback :error="error" /><button class="button primary full" :disabled="busy">{{ busy ? '正在加入…' : '加入并登录' }}</button></form></section><RouterLink class="text-link" to="/login/">已有账号？前往登录</RouterLink></main></template>
