<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { session, logout } from '../state/session'
import { useAction } from '../lib/useResource'
import Icon from './Icon.vue'
import FormFeedback from './FormFeedback.vue'
const router = useRouter()
const { busy, error, run } = useAction()
const coach = computed(() => session.value?.user?.role==='coach')
const links = computed(() => coach.value ? [
  { to:'/coach/',label:'记课',icon:'home' },{to:'/coach/students/',label:'学员',icon:'people'},
  {to:'/coach/sessions/',label:'排课',icon:'calendar'}, {to:'/coach/reports/',label:'月报',icon:'book'}, {to:'/coach/plans/',label:'课后指导',icon:'book'},
] : [{to:'/student/',label:'首页',icon:'home'},{to:'/student/sessions/',label:'约课',icon:'calendar'},
  {to:'/student/training/',label:'记录',icon:'book'},{to:'/student/profile/',label:'我的课包',icon:'people'}])
async function exit() { try { await run(logout) } finally { await router.replace('/login/') } }
</script>
<template><div class="app-shell"><header class="app-header"><RouterLink :to="coach ? '/coach/' : '/student/'" class="brand"><span class="brand-mark">{{ session?.brand.coach_name.slice(0,1) }}</span><span>{{ session?.brand.display_name }}</span></RouterLink><div class="account"><span>{{ session?.user?.display_name }}</span><button class="text-button exit" :disabled="busy" @click="exit"><Icon name="logout" /><span>退出</span></button></div></header><nav class="app-nav" aria-label="主要导航"><RouterLink v-for="link in links" :key="link.to" :to="link.to" :class="{active: link.to.endsWith('/coach/') || link.to.endsWith('/student/') ? $route.path===link.to || (coach && $route.path.startsWith('/coach/lessons/')) : $route.path.startsWith(link.to)}"><Icon :name="link.icon" /><span>{{ link.label }}</span></RouterLink><p class="nav-note">每一节课，<br />都留下值得回看的记录。</p></nav><main class="main"><FormFeedback :error="error" /><slot /></main></div></template>
