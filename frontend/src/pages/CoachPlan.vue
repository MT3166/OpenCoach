<script setup lang="ts">
import {ref,watch} from 'vue'
import {useRoute} from 'vue-router'
import type {Plan,Submission} from '../api/types'
import {write} from '../api/client'
import {useResource,useAction} from '../lib/useResource'
import {date} from '../lib/format'
import ResourceState from '../components/ResourceState.vue'
import FormFeedback from '../components/FormFeedback.vue'
import Field from '../components/Field.vue'
const route=useRoute(),feedback=ref('')
const {data,error:loadError,loading,refresh}=useResource<Plan>(()=>`/api/v1/coach/plans/${route.params.id}/`)
const {busy,error,notice,run}=useAction()
let initialized=false
watch(data,value=>{if(value && !initialized){feedback.value=value.submission?.feedback || '';initialized=true}})
async function save(){if(!data.value?.submission)return;const result=await run(()=>write<Submission>(`/api/v1/coach/submissions/${data.value?.submission?.id}/feedback/`,{feedback:feedback.value},'PUT'),'点评已发送。');if(result && data.value)data.value={...data.value,submission:result}}
</script>
<template><RouterLink class="back-link" to="/coach/plans/">返回课后指导</RouterLink><ResourceState :error="loadError" :loading="loading" @retry="refresh" /><template v-if="data"><div class="page-heading"><div><h1>{{data.title}}</h1><p>{{data.student?.name}} · {{date(data.due_date)}}前完成</p></div></div><section class="surface"><h2>练习内容</h2><p class="record-text">{{data.note}}</p><div v-for="(row,index) in data.exercises" :key="index" class="exercise-read"><strong>{{row.name}}</strong><span>{{row.sets?`${row.sets}组`:''}} {{row.reps?`${row.reps}次`:''}} {{row.weight!==null?`${row.weight}kg`:''}} {{row.duration?`${row.duration}秒`:''}}</span></div></section><section v-if="data.submission?.submitted_at" class="surface section"><h2>学员完成情况</h2><p class="record-text">{{data.submission.note}}</p><div v-for="(row,index) in data.submission.exercises" :key="index" class="exercise-read"><strong>{{row.name}}</strong><span>{{row.sets?`${row.sets}组`:''}} {{row.reps?`${row.reps}次`:''}} {{row.weight!==null?`${row.weight}kg`:''}} {{row.duration?`${row.duration}秒`:''}}</span></div><form class="stack-form" @submit.prevent="save"><Field label="给学员的点评"><textarea v-model="feedback" required maxlength="4000" rows="4" placeholder="肯定进步，再给一个具体建议。" /></Field><FormFeedback :error="error" :notice="notice" /><button class="button primary" :disabled="busy">保存点评</button></form></section><p v-else class="empty-note">学员尚未正式提交，提交后可以点评。</p></template></template>
