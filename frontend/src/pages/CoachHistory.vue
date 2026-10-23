<script setup lang="ts">
import { ref } from 'vue'
import type { Lesson, Page } from '../api/types'
import { useResource } from '../lib/useResource'
import LessonList from '../components/LessonList.vue'
import Pagination from '../components/Pagination.vue'
import ResourceState from '../components/ResourceState.vue'
const page=ref(1)
const {data,error,loading,refresh}=useResource<Page<Lesson>>(() => `/api/v1/coach/lessons/?page=${page.value}`)
</script>
<template><div class="page-heading"><div><h1>课程记录</h1><p>直接记课与预约课程，一起回看。</p></div><RouterLink class="button primary" to="/coach/lessons/new/">记一节课</RouterLink></div><ResourceState :error="error" :loading="loading" @retry="refresh" /><div v-if="data" class="surface list-surface"><LessonList :items="data.items" coach /></div><Pagination v-if="data" :page="page" :page-size="data.pagination.page_size" :total="data.pagination.total" @change="page=$event" /></template>
