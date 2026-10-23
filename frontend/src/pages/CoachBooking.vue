<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { BookingDetail, Booking, BookingStatus, Exercise, Record } from '../api/types'
import { write } from '../api/client'
import { useResource, useAction } from '../lib/useResource'
import { date, time, kinds, statuses } from '../lib/format'
import ResourceState from '../components/ResourceState.vue'
import FormFeedback from '../components/FormFeedback.vue'
import Field from '../components/Field.vue'
import ExerciseEditor from '../components/ExerciseEditor.vue'
import CreatePlan from '../components/CreatePlan.vue'
import RescheduleBooking from '../components/RescheduleBooking.vue'
const route=useRoute(),note=ref(''),rows=ref<Exercise[]>([]),cancelPrompt=ref(false)
const {data,error:loadError,loading,refresh}=useResource<BookingDetail>(() => `/api/v1/coach/bookings/${route.params.id}/`)
const {busy,error,notice,run}=useAction()
let initialized=false
watch(data,value=>{if(value && !initialized){note.value=value.record?.note || '';rows.value=structuredClone(value.record?.exercises || []);initialized=true}})
async function finish(outcome:BookingStatus){const result=await run(()=>write<Booking>(`/api/v1/coach/bookings/${route.params.id}/finish/`,{outcome}),'出勤已确认，课时账目已同步。');if(result)await refresh()}
async function cancel(){const result=await run(()=>write<Booking>(`/api/v1/coach/bookings/${route.params.id}/cancel/`),'预约已取消，预占已释放。');if(result){cancelPrompt.value=false;await refresh()}}
async function save(){const result=await run(()=>write<Record>(`/api/v1/coach/bookings/${route.params.id}/record/`,{note:note.value,exercises:rows.value},'PUT'),'这节课的记录已保存。');if(result && data.value)data.value={...data.value,record:result}}
</script>
<template><RouterLink class="back-link" to="/coach/">返回今天的课</RouterLink><ResourceState :error="loadError" :loading="loading && !data" @retry="refresh" /><template v-if="data"><div class="page-heading"><div><h1>{{ data.student.name }}的这节课</h1><p>{{ date(data.booking.session.start) }} · {{ time(data.booking.session.start) }} · {{ data.booking.session.title }}</p></div><span class="badge" :class="data.booking.status">{{ statuses[data.booking.status] }}</span></div><p>{{ kinds[data.booking.session.kind] }} · {{ data.booking.session.location }}</p><FormFeedback :error="error" :notice="notice" /><section v-if="data.booking.status==='booked'" class="surface attendance-panel"><h2>确认真实出勤</h2><p v-if="!data.booking.can_finish">课程尚未开始，开始后可确认完课或缺席。</p><div class="actions"><button class="button primary" :disabled="busy || !data.booking.can_finish" @click="finish('completed')">确认完课 · 扣1次</button><button class="button secondary" :disabled="busy || !data.booking.can_finish" @click="finish('no_show_charged')">缺席并消课</button><button class="button secondary" :disabled="busy || !data.booking.can_finish" @click="finish('no_show_waived')">缺席免消课</button></div><button class="text-button danger" @click="cancelPrompt=true">取消这笔预约</button><div v-if="cancelPrompt" class="confirm-inline"><p>取消{{ data.student.name }}的这笔预约，并释放预占课时？</p><div class="actions"><button class="button danger-button" :disabled="busy" @click="cancel">确认取消</button><button class="button secondary" @click="cancelPrompt=false">返回</button></div></div></section><RescheduleBooking v-if="data.booking.status==='booked'" :booking="data.booking" role="coach" @changed="refresh" /><section v-if="data.booking.status==='completed'" class="surface form-surface section"><h2>这节课的记录</h2><p>写一句就好，也可以之后补充。</p><form class="stack-form" @submit.prevent="save"><Field label="实际训练 / 课后总结（选填）"><textarea v-model="note" rows="4" maxlength="4000" placeholder="今天练了什么，有什么要注意？" /></Field><details class="secondary-section"><summary>详细动作（选填）</summary><ExerciseEditor v-model="rows" /></details><button class="button primary" :disabled="busy">保存记录</button></form></section><details v-if="data.booking.status!=='cancelled'" class="secondary-section"><summary>布置课后练习（按需使用）</summary><CreatePlan :student-id="data.student.id" :booking-id="data.booking.id" /></details><RouterLink class="text-link section-link" :to="`/coach/students/${data.student.id}/`">查看学员课包与历史</RouterLink></template></template>
