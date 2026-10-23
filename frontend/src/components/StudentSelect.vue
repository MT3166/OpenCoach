<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { Student, StudentDetail, Page } from '../api/types'
import { api } from '../api/client'
import { useResource } from '../lib/useResource'
import Field from './Field.vue'
const selected = defineModel<number | null>({ required:true })
defineProps<{ disabled?: boolean }>()
const query = ref(''), extra = ref<Student | null>(null)
const { data, error } = useResource<Page<Student>>(() => `/api/v1/coach/students/?page_size=100&q=${encodeURIComponent(query.value)}`)
const options = computed(() => {
  const items = [...(data.value?.items || [])]
  if (extra.value && !items.some(item => item.id===extra.value?.id)) items.unshift(extra.value)
  return items
})
watch(selected,async id => {
  if (id && !options.value.some(item => item.id===id)) {
    try { extra.value = (await api<StudentDetail>(`/api/v1/coach/students/${id}/`)).student } catch { extra.value=null }
  }
},{ immediate:true })
</script>
<template><div><Field v-if="(data?.pagination.total || 0)>100 || query" label="查找学员"><input v-model="query" :disabled="disabled" type="search" placeholder="输入姓名" /></Field><Field label="学员"><select v-model="selected" :disabled="disabled" required><option :value="null" disabled>选择这节课的学员</option><option v-for="item in options" :key="item.id" :value="item.id">{{ item.name }}</option></select></Field><p v-if="error" class="field-error">{{ error.message }}</p></div></template>
