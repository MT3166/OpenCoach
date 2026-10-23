<script setup lang="ts">
import {ref} from 'vue'
import type {Lesson,Plan,Page} from '../api/types'
import {useResource} from '../lib/useResource'
import {date} from '../lib/format'
import LessonList from '../components/LessonList.vue'
import ResourceState from '../components/ResourceState.vue'
import Pagination from '../components/Pagination.vue'
const page=ref(1),planPage=ref(1)
const {data,error,loading,refresh}=useResource<Page<Lesson>>(()=>`/api/v1/student/lessons/?page=${page.value}`)
const plans=useResource<Page<Plan>>(()=>`/api/v1/student/plans/?page=${planPage.value}`)
const labels={pending:'待练习',draft:'已存草稿',submitted:'等待点评',reviewed:'已点评'}
</script>
<template><div class="page-heading"><div><h1>每一节的记录</h1><p>回看练过的内容和教练的总结。</p></div></div><ResourceState :error="error" :loading="loading" @retry="refresh" /><div v-if="data" class="surface list-surface"><LessonList :items="data.items" /></div><Pagination v-if="data" :page="page" :page-size="data.pagination.page_size" :total="data.pagination.total" @change="page=$event" /><details v-if="plans.data.value?.pagination.total" class="secondary-section"><summary>教练布置的课后练习</summary><ResourceState :error="plans.error.value" @retry="plans.refresh" /><RouterLink v-for="item in plans.data.value?.items" :key="item.id" :to="`/student/plans/${item.id}/`" class="list-row"><div class="grow"><h3>{{item.title}}</h3><p>{{date(item.due_date)}}前完成</p></div><span class="badge">{{labels[item.status]}}</span></RouterLink><Pagination v-if="plans.data.value" :page="planPage" :page-size="plans.data.value.pagination.page_size" :total="plans.data.value.pagination.total" @change="planPage=$event" /></details></template>
