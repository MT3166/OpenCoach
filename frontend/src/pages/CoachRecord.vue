<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import type { StudentDetail, Booking, Page, Kind, LessonResult, Record } from '../api/types'
import { write } from '../api/client'
import { useResource, useAction } from '../lib/useResource'
import { today, date, time, kinds } from '../lib/format'
import StudentSelect from '../components/StudentSelect.vue'
import Field from '../components/Field.vue'
import FormFeedback from '../components/FormFeedback.vue'
import ResourceState from '../components/ResourceState.vue'
import Icon from '../components/Icon.vue'
const route = useRoute()
const studentId = ref<number | null>(Number(route.query.student) || null)
const kind = ref<Kind | ''>(''), day = ref(today()), note = ref(''), direct = ref(false)
const saved = ref<LessonResult | null>(null), finished = ref<Booking | null>(null), pendingNote = ref(false)
let operationKey = crypto.randomUUID(), kindTouched = false, attemptedNote: string | null = null
const { data: profile, error: profileError, loading: profileLoading, refresh: refreshProfile } = useResource<StudentDetail>(() => studentId.value ? `/api/v1/coach/students/${studentId.value}/` : '')
const { data: matches, error: matchesError, loading: matchesLoading, refresh: refreshMatches } = useResource<Page<Booking>>(() => studentId.value && kind.value ? `/api/v1/coach/bookings/?student_id=${studentId.value}&day=${day.value}&kind=${kind.value}&status=booked&page_size=100` : '')
const { busy, error, notice, run } = useAction()
const wallet = computed(() => profile.value?.wallets.find(item => item.kind===kind.value))
function resetIntent() { operationKey=crypto.randomUUID(); attemptedNote=null; direct.value=false; saved.value=null; finished.value=null; pendingNote.value=false }
watch(studentId,() => { kindTouched=false; kind.value=''; resetIntent() })
watch(profile,value => { const available=value?.wallets.filter(item => item.available>0); if (!saved.value && !finished.value && !kindTouched && available?.length===1) kind.value=available[0].kind })
watch([kind,day],resetIntent)
async function saveSavedNote() {
  if (!saved.value) return
  const result=await run(() => write<LessonResult>(`/api/v1/coach/lessons/${saved.value?.lesson.id}/`,{note:note.value},'PATCH'),'最新文字已保存，课时没有再次扣除。')
  if (result) { saved.value=result; pendingNote.value=false }
}
async function save() {
  kindTouched=true
  if (attemptedNote===null) attemptedNote=note.value.trim()
  const result=await run(() => write<LessonResult>('/api/v1/coach/lessons/',{student_id:studentId.value,kind:kind.value,occurred_on:day.value,note:attemptedNote,operation_key:operationKey}))
  if (result) {
    saved.value=result
    if (note.value.trim()!==attemptedNote) { pendingNote.value=true; await saveSavedNote() }
    await refreshProfile()
  }
}
async function saveFinishedNote() {
  if (!finished.value) return
  const result=await run(() => write<Record>(`/api/v1/coach/bookings/${finished.value?.id}/record/`,{note:note.value,exercises:[]},'PUT'),'这节预约的文字已保存，课时没有再次扣除。')
  if (result) pendingNote.value=false
}
async function finish(item: Booking) {
  kindTouched=true
  const result=await run(() => write<Booking>(`/api/v1/coach/bookings/${item.id}/finish/`,{outcome:'completed'}))
  if (result) {
    finished.value=result
    notice.value='这节预约已确认完课，课时账目已同步。'
    await refreshProfile(); await refreshMatches()
    if (note.value.trim()) { pendingNote.value=true; await saveFinishedNote() }
  }
}
function next() { resetIntent(); note.value=''; error.value=null; notice.value='' }
</script>
<template>
  <RouterLink class="back-link" to="/coach/">返回今天的课</RouterLink>
  <div class="page-heading"><div><h1>记一节课</h1><p>上完了，记一下就好。</p></div></div>
  <div class="record-layout">
    <section class="surface form-surface">
      <template v-if="saved">
        <div class="saved-mark"><Icon name="check" /></div><h2>这节课，记好了</h2>
        <p>{{ saved.lesson.student.name }} · {{ date(saved.lesson.occurred_on) }} · {{ kinds[saved.lesson.kind] }}</p>
        <p class="saved-balance">剩余 <strong>{{ saved.wallets.find(item => item.kind===saved?.lesson.kind)?.remaining }}</strong> 次</p>
        <FormFeedback :error="error" :notice="notice" />
        <div v-if="pendingNote" class="stack-form"><p>记课与扣课已完成，最新文字还未保存。</p><Field label="补写的文字"><textarea v-model="note" rows="3" maxlength="4000" /></Field><button class="button primary" :disabled="busy" @click="saveSavedNote">重试保存文字</button></div>
        <div class="actions"><RouterLink class="button secondary" :to="`/coach/lessons/${saved.lesson.id}/`">查看 / 补写记录</RouterLink><button class="button primary" :disabled="busy || pendingNote" @click="next">再记一节</button></div>
      </template>
      <template v-else-if="finished">
        <div class="saved-mark"><Icon name="check" /></div><h2>这节预约已完成</h2>
        <p>{{ finished.student?.name }} · {{ date(finished.session.start) }} · {{ finished.session.title }}</p>
        <p class="balance-note">完课和消课已确认。这里补写文字，不会再次扣课。</p>
        <FormFeedback :error="error" :notice="notice" />
        <form class="stack-form" @submit.prevent="saveFinishedNote"><Field label="这节课的文字记录（选填）"><textarea v-model="note" rows="3" maxlength="4000" /></Field><button class="button primary" :disabled="busy">{{ pendingNote ? '重试保存文字' : '保存这节课的文字' }}</button></form>
        <div class="actions"><RouterLink class="button secondary" :to="`/coach/bookings/${finished.id}/`">查看这节预约</RouterLink><button class="button secondary" :disabled="busy || pendingNote" @click="next">另记一节独立课程</button></div>
      </template>
      <form v-else class="stack-form" @submit.prevent="save">
        <StudentSelect v-model="studentId" :disabled="busy" />
        <ResourceState :error="profileError" :loading="profileLoading" @retry="refreshProfile" />
        <div class="form-grid"><Field label="课包类型"><select v-model="kind" :disabled="busy" required @change="kindTouched=true"><option value="" disabled>选择本节课的课包</option><option value="private">一对一私教</option><option value="group">小班课</option></select></Field><Field label="上课日期" :errors="error?.fields.occurred_on"><input v-model="day" type="date" :disabled="busy" :max="today()" required /></Field></div>
        <p v-if="wallet" class="balance-note">{{ kinds[wallet.kind] }}剩余 <strong>{{ wallet.remaining }}</strong> 次，其中已预约 {{ wallet.reserved }} 次，可用 {{ wallet.available }} 次。</p>
        <Field label="今天练了什么 / 有什么要注意（选填）" :errors="error?.fields.note"><textarea v-model="note" rows="3" maxlength="4000" placeholder="例如：深蹲、划船，注意膝盖方向。" /></Field>
        <FormFeedback :error="error" :notice="notice" /><ResourceState :error="matchesError" :loading="matchesLoading" @retry="refreshMatches" />
        <section v-if="matches?.items.length && !direct" class="matching-bookings"><h3>这一天已有预约</h3><p>确认对应的预约，使用已预占的课时。</p><div v-for="item in matches.items" :key="item.id" class="list-row"><div class="grow"><h3>{{ item.session.title }}</h3><p>{{ time(item.session.start) }} · {{ item.session.location }}</p></div><button type="button" class="button primary" :disabled="busy || !item.can_finish" @click="finish(item)">{{ item.can_finish ? '确认完课 · 扣1次' : '尚未开课' }}</button></div><button type="button" class="text-button" :disabled="busy" @click="direct=true">是另一节独立课程，直接记课</button></section>
        <button v-else class="button primary full" :disabled="busy || matchesLoading || !!matchesError || !studentId || !wallet || wallet.available<1">{{ busy ? '正在保存…' : '记一节课 · 扣1次' }}</button>
        <p v-if="wallet && wallet.available<1" class="hint">可用课时不足，请先核对预约预占，或在学员档案录入续课。</p>
        <RouterLink v-if="studentId" class="text-link" :to="`/coach/students/${studentId}/`">查看学员历史与课包</RouterLink>
        <p v-if="error?.code==='network_error' || error?.code==='invalid_response'" class="hint">可以重试这次保存；更改学员或日期前，请先核对历史记录。</p>
      </form>
    </section>
    <aside class="record-aside"><h2>留下这一节，<br />接着下一节。</h2><p>日期默认今天。记录可简单，也可以之后慢慢补充。</p><p>下次上课前，回看上一节的动作和注意事项。</p></aside>
  </div>
</template>
