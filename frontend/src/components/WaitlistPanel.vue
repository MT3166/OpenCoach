<script setup lang="ts">
import { ref } from 'vue'
import type { Page, WaitlistEntry } from '../api/types'
import { write } from '../api/client'
import { useResource, useAction } from '../lib/useResource'
import { date,time } from '../lib/format'
import ResourceState from './ResourceState.vue'
import FormFeedback from './FormFeedback.vue'
import Pagination from './Pagination.vue'
const props=defineProps<{sessionId?:number}>(), page=ref(1)
const {data,error:loadError,loading,refresh}=useResource<Page<WaitlistEntry>>(()=>props.sessionId ? `/api/v1/coach/sessions/${props.sessionId}/waitlist/?page=${page.value}` : `/api/v1/student/waitlist/?page=${page.value}`)
const {busy,error,notice,run}=useAction()
async function leave(id:number){const result=await run(()=>write<WaitlistEntry>(`/api/v1/student/waitlist/${id}/leave/`),'已退出候补。');if(result)await refresh()}
defineExpose({refresh})
</script>
<template><section class="section"><div class="section-heading"><h2>{{sessionId?'候补队列':'我的候补'}}</h2><button class="text-button" :disabled="loading" @click="refresh">刷新状态</button></div><p class="hint">按加入顺序递补；转正时检查有效课时与时间冲突。加入候补不预占课时。</p><FormFeedback :error="error" :notice="notice" /><ResourceState :error="loadError" :loading="loading" @retry="refresh" /><div v-if="data" class="surface list-surface"><p v-if="!data.items.length" class="empty-note">暂无候补记录。</p><div v-for="item in data.items" :key="item.id" class="list-row"><div class="grow"><h3>{{sessionId?item.student?.name:item.session.title}}</h3><p>{{date(item.session.start)}} {{time(item.session.start)}} · {{item.status==='waiting'?`候补第 ${item.position} 位`:item.status==='promoted'?'已递补为正式预约':'已退出 / 课程取消'}}</p></div><button v-if="!sessionId && item.status==='waiting'" class="button secondary" :disabled="busy" @click="leave(item.id)">退出候补</button><RouterLink v-if="item.status==='promoted'" class="text-link" :to="sessionId?`/coach/bookings/${item.booking_id}/`:'/student/bookings/'">查看预约</RouterLink></div></div><Pagination v-if="data" :page="page" :page-size="data.pagination.page_size" :total="data.pagination.total" @change="page=$event" /></section></template>
