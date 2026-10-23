<script setup lang="ts">
import {ref} from 'vue'
import {useRoute} from 'vue-router'
import type {Course,Booking,Page} from '../api/types'
import {write} from '../api/client'
import {useResource,useAction} from '../lib/useResource'
import {date,time,kinds,statuses} from '../lib/format'
import ResourceState from '../components/ResourceState.vue'
import FormFeedback from '../components/FormFeedback.vue'
import Pagination from '../components/Pagination.vue'
import WaitlistPanel from '../components/WaitlistPanel.vue'
const route=useRoute(),page=ref(1),prompt=ref(false),queue=ref<InstanceType<typeof WaitlistPanel> | null>(null)
const {data,error:loadError,loading,refresh}=useResource<Course>(()=>`/api/v1/coach/sessions/${route.params.id}/`)
const bookings=useResource<Page<Booking>>(()=>`/api/v1/coach/sessions/${route.params.id}/bookings/?page=${page.value}`)
const {busy,error,notice,run}=useAction()
async function cancel(){const result=await run(()=>write<Course>(`/api/v1/coach/sessions/${route.params.id}/cancel/`),'课程已取消，未消耗的预占课时已释放。');if(result){data.value=result;prompt.value=false;await bookings.refresh();await queue.value?.refresh()}}
</script>
<template><RouterLink class="back-link" to="/coach/sessions/">返回排课</RouterLink><ResourceState :error="loadError" :loading="loading" @retry="refresh" /><template v-if="data"><div class="page-heading"><div><h1>{{data.title}}</h1><p>{{date(data.start)}} · {{time(data.start)}}—{{time(data.end)}}</p></div><span class="badge">{{data.cancelled?'已取消':kinds[data.kind]}}</span></div><p>{{data.location}} · {{data.occupied}} / {{data.capacity}} 人</p><FormFeedback :error="error" :notice="notice" /><section class="section"><h2>逐位学员处理</h2><ResourceState :error="bookings.error.value" @retry="bookings.refresh" /><div v-if="bookings.data.value" class="surface list-surface"><p v-if="!bookings.data.value.items.length" class="empty-note">还没有学员预约这节课。</p><RouterLink v-for="item in bookings.data.value.items" :key="item.id" :to="`/coach/bookings/${item.id}/`" class="list-row"><div class="avatar">{{item.student?.name.slice(0,1)}}</div><div class="grow"><h3>{{item.student?.name}}</h3><p>{{statuses[item.status]}}</p></div><span class="text-link">查看与确认</span></RouterLink></div><Pagination v-if="bookings.data.value" :page="page" :page-size="bookings.data.value.pagination.page_size" :total="bookings.data.value.pagination.total" @change="page=$event" /></section><WaitlistPanel ref="queue" :session-id="data.id" /><button v-if="!data.cancelled" class="text-button danger" @click="prompt=true">取消整堂课程</button><section v-if="prompt" class="confirm-inline"><p>确认取消这堂课程，并释放仍在预约中的课时？已产生消课时，请逐人处理。</p><div class="actions"><button class="button danger-button" :disabled="busy" @click="cancel">确认取消课程</button><button class="button secondary" @click="prompt=false">返回</button></div></section></template></template>
