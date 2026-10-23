<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Kind, BatchResult } from '../api/types'
import { write } from '../api/client'
import { useAction } from '../lib/useResource'
import { today, kinds } from '../lib/format'
import StudentSelect from '../components/StudentSelect.vue'
import Field from '../components/Field.vue'
import FormFeedback from '../components/FormFeedback.vue'
import WalletSummary from '../components/WalletSummary.vue'
const kind=ref<Kind>('group'), occurred=ref(today()), rows=ref([{student_id:null as number|null,note:'',operation_key:crypto.randomUUID()}]), result=ref<BatchResult|null>(null)
const {busy,error,run}=useAction()
let key=crypto.randomUUID()
watch(()=>JSON.stringify([kind.value,occurred.value,rows.value.map(row=>[row.student_id,row.note])]),()=>{key=crypto.randomUUID();for(const row of rows.value)row.operation_key=crypto.randomUUID()},{flush:'sync'})
async function save(){const value=await run(()=>write<BatchResult>('/api/v1/coach/lessons/batch/',{kind:kind.value,occurred_on:occurred.value,operation_key:key,items:rows.value.map(row=>({...row,exercises:[]}))}));if(value)result.value=value}
function add(){rows.value.push({student_id:null,note:'',operation_key:crypto.randomUUID()})}
function reset(){result.value=null;rows.value=[{student_id:null,note:'',operation_key:crypto.randomUUID()}]}
</script>
<template><RouterLink class="back-link" to="/coach/">返回记课</RouterLink><div class="page-heading"><div><h1>批量记课</h1><p>同一课包类型、同一日期；全部成功后才会扣课。</p></div></div><FormFeedback :error="error" /><section v-if="result" class="surface"><h2>已为 {{result.items.length}} 位学员记课</h2><div v-for="item in result.items" :key="item.id" class="section"><h3>{{item.student.name}} · {{kinds[item.kind]}}</h3><WalletSummary :wallets="result.wallets.find(row=>row.student_id===item.student.id)?.wallets || []" /></div><div class="actions"><RouterLink class="button primary" to="/coach/lessons/">查看上课记录</RouterLink><button class="button secondary" @click="reset">继续记另一批</button></div></section><form v-else class="surface stack-form" @submit.prevent="save"><div class="form-grid"><Field label="课包类型"><select v-model="kind" :disabled="busy"><option value="group">小班课</option><option value="private">一对一私教</option></select></Field><Field label="上课日期"><input v-model="occurred" :disabled="busy" type="date" :max="today()" required /></Field></div><fieldset v-for="(row,index) in rows" :key="index" class="batch-item" :disabled="busy"><legend>学员 {{index+1}}</legend><StudentSelect v-model="row.student_id" :disabled="busy" /><Field label="训练记录（选填）"><textarea v-model="row.note" maxlength="4000" rows="2" /></Field><button v-if="rows.length>1" class="text-button danger" type="button" @click="rows.splice(index,1)">移除此学员</button></fieldset><div class="actions"><button class="button secondary" type="button" :disabled="busy || rows.length>=100" @click="add">再加一位学员</button><button class="button primary" :disabled="busy || rows.some(row=>!row.student_id)">{{busy?'正在整批保存…':`确认记课 · ${rows.length} 人各扣1次`}}</button></div><p class="hint">任一学员课时不足、已过期或资料有误时，整批不会保存。已有对应预约请从预约中确认，避免重复记课。</p></form></template>
