<script setup lang="ts">
import {ref} from 'vue'
import {useRoute} from 'vue-router'
import type {Booking,Page} from '../api/types'
import {useResource} from '../lib/useResource'
import {date,time,statuses} from '../lib/format'
import ResourceState from '../components/ResourceState.vue'
import Pagination from '../components/Pagination.vue'
const route=useRoute(),status=ref(String(route.query.status || 'booked')),page=ref(1)
const {data,error,loading,refresh}=useResource<Page<Booking>>(()=>`/api/v1/coach/bookings/?status=${status.value}&page=${page.value}`)
</script>
<template><div class="page-heading"><div><h1>预约记录</h1><p>选择学员的预约，确认真实出勤。</p></div></div><div class="filters"><label>状态<select v-model="status" @change="page=1"><option value="">全部</option><option v-for="(label,value) in statuses" :key="value" :value="value">{{label}}</option></select></label></div><ResourceState :error="error" :loading="loading" @retry="refresh" /><div v-if="data" class="surface list-surface"><p v-if="!data.items.length" class="empty-note">没有符合筛选的预约。</p><RouterLink v-for="item in data.items" :key="item.id" :to="`/coach/bookings/${item.id}/`" class="list-row"><div class="grow"><h3>{{item.student?.name}} · {{item.session.title}}</h3><p>{{date(item.session.start)}} · {{time(item.session.start)}}</p></div><span class="badge" :class="item.status">{{statuses[item.status]}}</span></RouterLink></div><Pagination v-if="data" :page="page" :page-size="data.pagination.page_size" :total="data.pagination.total" @change="page=$event" /></template>
