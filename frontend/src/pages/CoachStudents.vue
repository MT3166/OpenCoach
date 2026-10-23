<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { Student, Page } from '../api/types'
import { write } from '../api/client'
import { useResource, useAction } from '../lib/useResource'
import Field from '../components/Field.vue'
import FormFeedback from '../components/FormFeedback.vue'
import ResourceState from '../components/ResourceState.vue'
import Pagination from '../components/Pagination.vue'
import Icon from '../components/Icon.vue'
const query=ref(''),page=ref(1),name=ref(''),adding=ref(false),router=useRouter()
const {data,error:loadError,loading,refresh}=useResource<Page<Student>>(() => `/api/v1/coach/students/?q=${encodeURIComponent(query.value)}&page=${page.value}`)
const {busy,error,run}=useAction()
async function add() { const result=await run(() => write<Student>('/api/v1/coach/students/',{name:name.value})); if(result) await router.push(`/coach/students/${result.id}/`) }
</script>
<template><div class="page-heading"><div><h1>学员</h1><p>每个人的课时与记录，都在这里。</p></div><button class="button primary" @click="adding=!adding"><Icon name="plus" />添加学员</button></div><form v-if="adding" class="surface inline-form" @submit.prevent="add"><Field label="学员姓名" :errors="error?.fields.name"><input v-model="name" required maxlength="50" placeholder="输入姓名即可创建档案" /></Field><button class="button primary" :disabled="busy">创建档案</button><FormFeedback :error="error" /></form><div class="search"><label class="sr-only" for="student-search">搜索学员</label><input id="student-search" v-model="query" type="search" placeholder="搜索学员姓名" @input="page=1" /></div><ResourceState :error="loadError" :loading="loading && !data" @retry="refresh" /><div v-if="data" class="surface list-surface"><div v-if="!data.items.length" class="empty-state"><h2>{{ query ? '没有找到这位学员' : '从第一位学员开始' }}</h2><p>{{ query ? '试试其他姓名。' : '先创建档案，就可以录入课包、记课。' }}</p></div><RouterLink v-for="item in data.items" :key="item.id" :to="`/coach/students/${item.id}/`" class="list-row"><div class="avatar">{{ item.name.slice(0,1) }}</div><div class="grow"><h3>{{ item.name }}</h3><p>{{ item.registered ? '账号已绑定' : '尚未接受邀请，可直接记课' }}</p></div><Icon name="arrow" /></RouterLink></div><Pagination v-if="data" :page="page" :page-size="data.pagination.page_size" :total="data.pagination.total" @change="page=$event" /></template>
