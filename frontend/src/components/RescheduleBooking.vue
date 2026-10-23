<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { Booking, Course, Page, Role } from '../api/types'
import { write } from '../api/client'
import { useResource, useAction } from '../lib/useResource'
import { date, time } from '../lib/format'
import Field from './Field.vue'
import ResourceState from './ResourceState.vue'
import FormFeedback from './FormFeedback.vue'
import Pagination from './Pagination.vue'
const props=defineProps<{booking:Booking;role:Role}>()
const emit=defineEmits<{changed:[]}>()
const router=useRouter(), opened=ref(false), day=ref(''), page=ref(1), selected=ref<number | null>(null)
const {data,error:loadError,loading,refresh}=useResource<Page<Course>>(()=>opened.value ? `/api/v1/${props.role}/sessions/?kind=${props.booking.session.kind}&day=${day.value}&page=${page.value}` : '')
const {busy,error,notice,run}=useAction()
let key=crypto.randomUUID()
function newIntent(){key=crypto.randomUUID()}
watch([day,page,()=>props.booking.id],()=>{selected.value=null;newIntent()})
async function move(){
  const result=await run(()=>write<Booking>(`/api/v1/${props.role}/bookings/${props.booking.id}/reschedule/`,{session_id:selected.value,operation_key:key}),'改期成功，原预约已保留为取消记录。')
  if(result){opened.value=false;newIntent();emit('changed');if(props.role==='coach')await router.push(`/coach/bookings/${result.id}/`)}
  else if(error.value?.status===409)await refresh()
}
</script>
<template><div class="section"><button class="button secondary" :disabled="busy" @click="opened=!opened">{{opened?'收起改期':'改期到其他课次'}}</button><FormFeedback :error="error" :notice="notice" /><form v-if="opened" class="stack-form" @submit.prevent="move"><p class="hint">改期成功后预占转移，目标满员或课时失效时会保留原预约。</p><Field label="目标上课日期（可选）"><input v-model="day" type="date" :disabled="busy" @change="page=1" /></Field><ResourceState :error="loadError" :loading="loading" @retry="refresh" /><Field v-if="data" label="目标课次"><select v-model="selected" :disabled="busy" required @change="newIntent"><option :value="null" disabled>选择新的课次</option><option v-for="item in data.items.filter(row=>row.id!==booking.session.id && !row.cancelled && row.slots_left>0 && !row.my_booking_id && new Date(row.start)>new Date())" :key="item.id" :value="item.id">{{date(item.start)}} {{time(item.start)}} · {{item.title}} · 余{{item.slots_left}}名</option></select></Field><Pagination v-if="data" :page="page" :page-size="data.pagination.page_size" :total="data.pagination.total" @change="page=$event" /><button class="button primary" :disabled="busy || !selected">{{busy?'正在改期…':'确认改期'}}</button></form></div></template>
