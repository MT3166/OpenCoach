<script setup lang="ts">
import {ref} from 'vue'
import {useRouter} from 'vue-router'
import type {Course,Booking,Page,Student,Wallet} from '../api/types'
import {write} from '../api/client'
import {useResource,useAction} from '../lib/useResource'
import {date,time,kinds} from '../lib/format'
import Field from '../components/Field.vue'
import ResourceState from '../components/ResourceState.vue'
import FormFeedback from '../components/FormFeedback.vue'
import Pagination from '../components/Pagination.vue'
const day=ref(''),kind=ref(''),page=ref(1),router=useRouter()
const {data,error:loadError,loading,refresh}=useResource<Page<Course>>(()=>`/api/v1/student/sessions/?day=${day.value}&kind=${kind.value}&page=${page.value}`)
const profile=useResource<{student:Student;wallets:Wallet[]}>(()=>'/api/v1/student/profile/')
const {busy,error,notice,run}=useAction(),keys=new Map<number,string>(),waitKeys=new Map<number,string>()
function available(type:string){return profile.data.value?.wallets.find(item=>item.kind===type)?.available || 0}
async function reserve(item:Course){if(!keys.has(item.id))keys.set(item.id,crypto.randomUUID());const result=await run(()=>write<Booking>('/api/v1/student/bookings/',{session_id:item.id,operation_key:keys.get(item.id)}));if(result){keys.delete(item.id);await router.push('/student/bookings/')}else if(error.value?.status===409){await refresh();await profile.refresh()}}
async function joinWaitlist(item:Course){if(!waitKeys.has(item.id))waitKeys.set(item.id,crypto.randomUUID());const result=await run(()=>write(`/api/v1/student/sessions/${item.id}/waitlist/`,{operation_key:waitKeys.get(item.id)}),'已加入候补，可在我的预约中查看顺位。');if(result){waitKeys.delete(item.id);await refresh()}else if(error.value?.status===409)await refresh()}
</script>
<template><div class="page-heading"><div><h1>约一节课</h1><p>选择适合你的时间。</p></div><RouterLink class="button secondary" to="/student/bookings/">我的预约</RouterLink></div><div class="filters"><Field label="上课日期"><input v-model="day" type="date" @change="page=1" /></Field><Field label="课程类型"><select v-model="kind" @change="page=1"><option value="">全部</option><option value="private">一对一私教</option><option value="group">小班课</option></select></Field></div><FormFeedback :error="error" :notice="notice" /><ResourceState :error="loadError || profile.error.value" :loading="loading && !data" @retry="refresh();profile.refresh()" /><div v-if="data" class="course-grid"><div v-if="!data.items.length" class="empty-state"><h2>这个时间还没有可约课程</h2><p>换个日期看看，或联系教练安排。</p></div><section v-for="item in data.items" :key="item.id" class="surface course"><span class="badge">{{kinds[item.kind]}}</span><h2>{{item.title}}</h2><p class="course-date">{{date(item.start,{weekday:'short'})}}</p><p class="course-time">{{time(item.start)}}<span>—{{time(item.end)}}</span></p><p>{{item.location}}</p><div class="course-bottom"><span>{{item.slots_left}} 个名额 · 可约 {{available(item.kind)}} 次</span><RouterLink v-if="item.my_booking_id" class="button secondary" to="/student/bookings/">已预约</RouterLink><RouterLink v-else-if="item.my_waitlist_id" class="button secondary" to="/student/bookings/">候补中</RouterLink><button v-else-if="item.slots_left===0" class="button secondary" :disabled="busy" @click="joinWaitlist(item)">加入候补</button><button v-else class="button primary" :disabled="busy || item.slots_left<1 || available(item.kind)<1" @click="reserve(item)">{{item.slots_left<1?'已满员':available(item.kind)<1?'课时不足':'预约这节课'}}</button></div></section></div><Pagination v-if="data" :page="page" :page-size="data.pagination.page_size" :total="data.pagination.total" @change="page=$event" /></template>
