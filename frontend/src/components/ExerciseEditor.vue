<script setup lang="ts">
import type { Exercise } from '../api/types'
import Field from './Field.vue'
const rows = defineModel<Exercise[]>({ required:true })
defineProps<{ fixed?: boolean; readonly?: boolean }>()
function add() { rows.value.push({ name:'',sets:null,reps:null,weight:null,duration:null }) }
</script>
<template><div class="exercises"><div v-for="(row,index) in rows" :key="index" class="exercise-row"><Field label="动作"><input v-model="row.name" :readonly="fixed || readonly" required maxlength="80" /></Field><Field label="组数"><input v-model.number="row.sets" type="number" min="1" max="1000000" step="1" :readonly="readonly" /></Field><Field label="次数"><input v-model.number="row.reps" type="number" min="1" max="1000000" step="1" :readonly="readonly" /></Field><Field label="重量（kg）"><input v-model="row.weight" type="number" min="0" max="1000000" step="0.01" :readonly="readonly" /></Field><Field label="时长（秒）"><input v-model.number="row.duration" type="number" min="1" max="1000000" step="1" :readonly="readonly" /></Field><button v-if="!fixed && !readonly" class="remove-action" type="button" @click="rows.splice(index,1)" :aria-label="`移除动作 ${row.name || index+1}`">移除</button></div><button v-if="!fixed && !readonly && rows.length<50" class="text-button" type="button" @click="add">添加一个动作</button></div></template>
