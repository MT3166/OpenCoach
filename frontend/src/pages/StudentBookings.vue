<script setup lang="ts">
import {ref} from 'vue'
import type {Booking,Page} from '../api/types'
import {write} from '../api/client'
import {useResource,useAction} from '../lib/useResource'
import {date,time,statuses,kinds} from '../lib/format'
import ResourceState from '../components/ResourceState.vue'
import FormFeedback from '../components/FormFeedback.vue'
import Pagination from '../components/Pagination.vue'
import RescheduleBooking from '../components/RescheduleBooking.vue'
import WaitlistPanel from '../components/WaitlistPanel.vue'
const page=ref(1),prompt=ref<number | null>(null)
const {data,error:loadError,loading,refresh}=useResource<Page<Booking>>(()=>`/api/v1/student/bookings/?page=${page.value}`)
const {busy,error,notice,run}=useAction()
async function cancel(id:number){const result=await run(()=>write<Booking>(`/api/v1/student/bookings/${id}/cancel/`),'预约已取消，预占课时已释放。');if(result){prompt.value=null;await refresh()}}
</script>
<template><div class="page-heading"><div><h1>我的预约</h1><p>预约与出勤结果，都可回看。</p></div><RouterLink class="button primary" to="/student/sessions/">继续约课</RouterLink></div><FormFeedback :error="error" :notice="notice" /><ResourceState :error="loadError" :loading="loading" @retry="refresh" /><div v-if="data" class="booking-list"><section v-if="!data.items.length" class="empty-state"><h2>还没有预约</h2><p>去选择第一节合适的课程。</p></section><section v-for="item in data.items" :key="item.id" class="surface booking-item"><div class="section-heading"><h2>{{item.session.title}}</h2><span class="badge" :class="item.status">{{statuses[item.status]}}</span></div><p>{{date(item.session.start)}} · {{time(item.session.start)}}—{{time(item.session.end)}}</p><p>{{item.session.location}} · {{kinds[item.session.kind]}}</p><div v-if="item.can_cancel" class="actions"><button class="button secondary" @click="prompt=item.id">取消预约</button></div><p v-else-if="item.status==='booked'" class="hint">距开课不足12小时，请联系教练处理取消。</p><RescheduleBooking v-if="item.can_cancel" :booking="item" role="student" @changed="refresh" /><RouterLink v-if="item.status==='completed'" class="text-link section-link" to="/student/training/">查看课程记录</RouterLink><div v-if="prompt===item.id" class="confirm-inline"><p>确认取消这笔预约？预占课时将释放。</p><div class="actions"><button class="button danger-button" :disabled="busy" @click="cancel(item.id)">确认取消</button><button class="button secondary" @click="prompt=null">返回</button></div></div></section></div><Pagination v-if="data" :page="page" :page-size="data.pagination.page_size" :total="data.pagination.total" @change="page=$event" /><WaitlistPanel /></template>
