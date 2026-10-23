<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { LessonResult, Exercise } from '../api/types'
import { write } from '../api/client'
import { useResource, useAction } from '../lib/useResource'
import { date, kinds } from '../lib/format'
import Field from '../components/Field.vue'
import FormFeedback from '../components/FormFeedback.vue'
import ResourceState from '../components/ResourceState.vue'
import ExerciseEditor from '../components/ExerciseEditor.vue'
const route=useRoute(),note=ref(''),rows=ref<Exercise[]>([])
const {data,error:loadError,loading,refresh}=useResource<LessonResult>(() => `/api/v1/coach/lessons/${route.params.id}/`)
const {busy,error,notice,run}=useAction()
let initialized=false
watch(data,value => { if(value && !initialized){note.value=value.lesson.note;rows.value=structuredClone(value.lesson.exercises);initialized=true} })
async function save(){const result=await run(() => write<LessonResult>(`/api/v1/coach/lessons/${route.params.id}/`,{note:note.value,exercises:rows.value},'PATCH'),'记录已保存，课时没有再次扣除。');if(result)data.value=result}
</script>
<template><RouterLink class="back-link" to="/coach/lessons/">返回课程记录</RouterLink><ResourceState :error="loadError" :loading="loading" @retry="refresh" /><template v-if="data"><div class="page-heading"><div><h1>{{ data.lesson.student.name }}的这节课</h1><p>{{ date(data.lesson.occurred_on) }} · {{ kinds[data.lesson.kind] }} · 已记课并消耗1次</p></div></div><section class="surface form-surface"><form class="stack-form" @submit.prevent="save"><Field label="训练内容与课后总结（选填）"><textarea v-model="note" rows="5" maxlength="4000" placeholder="写一句，也是一份记录。" /></Field><details class="secondary-section"><summary>详细动作（选填）</summary><ExerciseEditor v-model="rows" /></details><FormFeedback :error="error" :notice="notice" /><button class="button primary" :disabled="busy">{{ busy ? '正在保存…' : '保存文字与动作' }}</button></form><RouterLink class="text-link section-link" :to="`/coach/students/${data.lesson.student.id}/`">查看学员课包与历史</RouterLink></section></template></template>
