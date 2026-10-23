<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { Course, Page, Kind } from '../api/types'
import { write } from '../api/client'
import { useResource,useAction } from '../lib/useResource'
import { date,time,localTime,kinds } from '../lib/format'
import Field from '../components/Field.vue'
import ResourceState from '../components/ResourceState.vue'
import FormFeedback from '../components/FormFeedback.vue'
import Pagination from '../components/Pagination.vue'
const day=ref(''),kind=ref(''),page=ref(1),creating=ref(false)
const {data,error:loadError,loading,refresh}=useResource<Page<Course>>(()=>`/api/v1/coach/sessions/?page=${page.value}&day=${day.value}&kind=${kind.value}`)
const title=ref(''),type=ref<Kind>('private'),start=ref(''),end=ref(''),location=ref(''),capacity=ref(1)
const {busy,error,run}=useAction(),router=useRouter()
async function create(){const result=await run(()=>write<Course>('/api/v1/coach/sessions/',{title:title.value,kind:type.value,start:localTime(start.value),end:localTime(end.value),location:location.value,capacity:type.value==='private'?1:capacity.value}));if(result)await router.push(`/coach/sessions/${result.id}/`)}
</script>
<template><div class="page-heading"><div><h1>排课</h1><p>安排一对一时段或小班，学员可以自行预约。</p></div><button class="button primary" @click="creating=!creating">发布课程</button></div><form v-if="creating" class="surface stack-form form-surface" @submit.prevent="create"><Field label="课程名称" :errors="error?.fields.title"><input v-model="title" required maxlength="80" /></Field><div class="form-grid"><Field label="课程类型"><select v-model="type" @change="capacity=type==='group'?2:1"><option value="private">一对一私教</option><option value="group">小班课</option></select></Field><Field label="人数上限" :errors="error?.fields.capacity"><input v-model.number="capacity" type="number" :readonly="type==='private'" :min="type==='group'?2:1" max="100" required /></Field><Field label="开始时间（上海时间）" :errors="error?.fields.start"><input v-model="start" type="datetime-local" required /></Field><Field label="结束时间（上海时间）" :errors="error?.fields.end"><input v-model="end" type="datetime-local" required /></Field></div><Field label="上课地点"><input v-model="location" required maxlength="120" /></Field><FormFeedback :error="error" /><button class="button primary" :disabled="busy">确认发布</button></form><div class="filters"><Field label="日期"><input v-model="day" type="date" @change="page=1" /></Field><Field label="类型"><select v-model="kind" @change="page=1"><option value="">全部</option><option value="private">私教</option><option value="group">小班</option></select></Field><button class="text-button" @click="day='';kind='';page=1">重置筛选</button></div><ResourceState :error="loadError" :loading="loading" @retry="refresh" /><div v-if="data" class="surface list-surface"><p v-if="!data.items.length" class="empty-note">这个筛选下还没有课程。</p><RouterLink v-for="item in data.items" :key="item.id" :to="`/coach/sessions/${item.id}/`" class="list-row"><div class="time-column"><strong>{{ time(item.start) }}</strong><small>{{ date(item.start) }}</small></div><div class="grow"><h3>{{ item.title }}</h3><p>{{ item.location }} · {{ kinds[item.kind] }}</p></div><span class="badge">{{ item.cancelled?'已取消':`${item.occupied}/${item.capacity}人` }}</span></RouterLink></div><Pagination v-if="data" :page="page" :page-size="data.pagination.page_size" :total="data.pagination.total" @change="page=$event" /></template>
