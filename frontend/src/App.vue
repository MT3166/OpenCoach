<script setup lang="ts">
import {ref,computed,watch,onMounted} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {session,loadSession,ensureSession} from './state/session'
import AppShell from './components/AppShell.vue'
const route=useRoute(),router=useRouter(),bootError=ref('')
const identity=computed(()=>session.value?.user?`${session.value.user.id}:${session.value.user.role}`:'')
watch(identity,(current,previous)=>{
  if(previous && current!==previous && route.meta.role) void router.replace(current?(session.value?.user?.role==='coach'?'/coach/':'/student/'):'/login/')
})
watch(()=>session.value?.brand.display_name,name=>{if(name)document.title=name},{immediate:true})
onMounted(()=>{void ensureSession().catch(()=>{bootError.value='暂时无法连接，请检查网络后重试。'})})
async function retry(){try{await loadSession();bootError.value='';await router.replace(route.fullPath)}catch{bootError.value='仍未连接成功，请稍后重试。'}}
</script>
<template><div v-if="bootError" class="empty-state"><h1>暂时无法打开</h1><p>{{bootError}}</p><button class="button primary" @click="retry">重新连接</button></div><AppShell v-else-if="session?.user && route.meta.role" :key="identity"><RouterView :key="`${identity}:${route.fullPath}`" /></AppShell><p v-else-if="route.meta.role" class="loading" role="status">正在确认登录状态…</p><RouterView v-else :key="route.fullPath" /></template>
