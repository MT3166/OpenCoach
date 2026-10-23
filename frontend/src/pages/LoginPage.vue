<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { login, session, logout, loadSession, logoutPending, authMessage } from '../state/session'
import { useAction } from '../lib/useResource'
import Field from '../components/Field.vue'
import FormFeedback from '../components/FormFeedback.vue'
const username = ref(''), password = ref('')
const { busy, error, run } = useAction()
const router = useRouter(), route = useRoute()
async function submit() {
  const result = await run(() => login(username.value,password.value))
  if (result) {
    password.value = ''
    const next = typeof route.query.next==='string' ? route.query.next : ''
    await router.replace(next.startsWith('/') && !next.startsWith('//') && router.resolve(next).matched.length ? next : result.user?.role==='coach' ? '/coach/' : '/student/')
  }
}
async function retryLogout() { await run(async () => { await loadSession(); await logout() }) }
</script>
<template><main class="auth-page"><div class="auth-layout"><section class="auth-story"><div class="brand"><span class="brand-mark">{{ session?.brand.coach_name.slice(0,1) }}</span>{{ session?.brand.display_name }}</div><h1>每一节课，<br />都有迹可循。</h1><p>把上课、课时和训练记录放在一起。<br />下次见面，接着上次的进步继续。</p><div class="auth-story-bottom">与你的教练，一起认真记录。</div></section><section class="auth-form"><h2>欢迎回来</h2><p>登录，查看课程与记录。</p><div v-if="logoutPending" class="stack-form"><p class="feedback error" role="alert">{{ authMessage }}</p><button class="button primary" :disabled="busy" @click="retryLogout">重试退出</button><FormFeedback :error="error" /></div><form v-else class="stack-form" @submit.prevent="submit"><Field label="账号" :errors="error?.fields.username"><input v-model="username" name="username" autocomplete="username" required maxlength="150" placeholder="输入你的账号" /></Field><Field label="密码" :errors="error?.fields.password"><input v-model="password" name="password" autocomplete="current-password" type="password" required placeholder="输入密码" /></Field><FormFeedback :error="error" /><button class="button primary full" :disabled="busy">{{ busy ? '正在登录…' : '登录' }}</button></form><p class="auth-help">首次加入？使用教练发给你的邀请链接设置账号。</p></section></div></main></template>
