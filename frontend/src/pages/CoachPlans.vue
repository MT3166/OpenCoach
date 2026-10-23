<script setup lang="ts">
import {ref} from 'vue'
import type {Plan,Page} from '../api/types'
import {useResource} from '../lib/useResource'
import {date} from '../lib/format'
import ResourceState from '../components/ResourceState.vue'
import Pagination from '../components/Pagination.vue'
const page=ref(1)
const {data,error,loading,refresh}=useResource<Page<Plan>>(()=>`/api/v1/coach/plans/?page=${page.value}`)
const labels={pending:'待练习',draft:'草稿',submitted:'待点评',reviewed:'已点评'}
</script>
<template><div class="page-heading"><div><h1>课后指导</h1><p>按需布置练习，阅读学员提交并给予反馈。</p></div></div><ResourceState :error="error" :loading="loading" @retry="refresh" /><div v-if="data" class="surface list-surface"><p v-if="!data.items.length" class="empty-note">还没有课后练习，可以在学员档案按需布置。</p><RouterLink v-for="item in data.items" :key="item.id" :to="`/coach/plans/${item.id}/`" class="list-row"><div class="grow"><h3>{{item.student?.name}} · {{item.title}}</h3><p>{{date(item.due_date)}}前完成</p></div><span class="badge">{{labels[item.status]}}</span></RouterLink></div><Pagination v-if="data" :page="page" :page-size="data.pagination.page_size" :total="data.pagination.total" @change="page=$event" /></template>
