<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { Exercise, Plan } from '../api/types'
import { write } from '../api/client'
import { useAction } from '../lib/useResource'
import { today } from '../lib/format'
import Field from './Field.vue'
import ExerciseEditor from './ExerciseEditor.vue'
import FormFeedback from './FormFeedback.vue'
const props=defineProps<{studentId:number;bookingId?:number}>()
const title=ref('课后练习'),day=ref(today()),note=ref('')
const rows=ref<Exercise[]>([{name:'',sets:null,reps:null,weight:null,duration:null}])
const {busy,error,run}=useAction(),router=useRouter()
async function save(){const result=await run(() => write<Plan>('/api/v1/coach/plans/',{student_id:props.studentId,booking_id:props.bookingId || null,title:title.value,due_date:day.value,exercises:rows.value,note:note.value}));if(result)await router.push(`/coach/plans/${result.id}/`)}
</script>
<template><form class="stack-form" @submit.prevent="save"><div class="form-grid"><Field label="练习名称"><input v-model="title" maxlength="80" required /></Field><Field label="完成日期"><input v-model="day" type="date" required /></Field></div><ExerciseEditor v-model="rows" /><Field label="给学员的说明"><textarea v-model="note" rows="3" maxlength="4000" /></Field><FormFeedback :error="error" /><button class="button primary" :disabled="busy">布置课后练习</button></form></template>
