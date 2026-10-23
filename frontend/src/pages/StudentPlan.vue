<script setup lang="ts">
import {ref,watch,computed} from 'vue'
import {useRoute} from 'vue-router'
import type {Plan,Submission,Exercise} from '../api/types'
import {write} from '../api/client'
import {useResource,useAction} from '../lib/useResource'
import {date} from '../lib/format'
import ResourceState from '../components/ResourceState.vue'
import FormFeedback from '../components/FormFeedback.vue'
import Field from '../components/Field.vue'
import ExerciseEditor from '../components/ExerciseEditor.vue'
const route=useRoute(),note=ref(''),rows=ref<Exercise[]>([]),confirming=ref(false)
const {data,error:loadError,loading,refresh}=useResource<Plan>(()=>`/api/v1/student/plans/${route.params.id}/`)
const {busy,error,notice,run}=useAction(),locked=computed(()=>!!data.value?.submission?.submitted_at)
let initialized=false
watch(data,value=>{if(value && !initialized){note.value=value.submission?.note || '';rows.value=value.submission?structuredClone(value.submission.exercises):value.exercises.map(row=>({name:row.name,sets:null,reps:null,weight:null,duration:null}));initialized=true}})
async function save(intent:'draft'|'submit'){const result=await run(()=>write<Submission>(`/api/v1/student/plans/${route.params.id}/submission/`,{exercises:rows.value,note:note.value,intent},'PUT'),intent==='draft'?'草稿已保存。':'已提交，等待教练点评。');if(result && data.value){data.value={...data.value,submission:result};confirming.value=false}}
</script>
<template><RouterLink class="back-link" to="/student/training/">返回记录</RouterLink><ResourceState :error="loadError" :loading="loading" @retry="refresh" /><template v-if="data"><div class="page-heading"><div><h1>{{data.title}}</h1><p>{{date(data.due_date)}}前完成</p></div><span v-if="locked" class="badge">已正式提交</span></div><section class="surface"><h2>教练的安排</h2><p class="record-text">{{data.note}}</p><div v-for="(row,index) in data.exercises" :key="index" class="exercise-read"><strong>{{row.name}}</strong><span>{{row.sets?`${row.sets}组`:''}} {{row.reps?`${row.reps}次`:''}} {{row.weight!==null?`${row.weight}kg`:''}} {{row.duration?`${row.duration}秒`:''}}</span></div></section><section class="surface section"><h2>我的实际完成</h2><form class="stack-form" @submit.prevent="save('draft')"><ExerciseEditor v-model="rows" fixed :readonly="locked" /><Field label="完成情况 / 训练感受"><textarea v-model="note" rows="3" maxlength="4000" :readonly="locked" /></Field><FormFeedback :error="error" :notice="notice" /><div v-if="!locked" class="actions"><button class="button secondary" :disabled="busy">保存草稿</button><button class="button primary" type="button" :disabled="busy" @click="confirming=true">正式提交</button></div><div v-if="confirming" class="confirm-inline"><p>正式提交后将锁定内容，交给教练点评。确认现在提交？</p><div class="actions"><button class="button primary" type="button" :disabled="busy" @click="save('submit')">确认提交</button><button class="button secondary" type="button" @click="confirming=false">继续编辑</button></div></div></form></section><section v-if="data.submission?.reviewed_at" class="coach-feedback section"><h2>教练给你的反馈</h2><p class="record-text">{{data.submission.feedback}}</p></section></template></template>
