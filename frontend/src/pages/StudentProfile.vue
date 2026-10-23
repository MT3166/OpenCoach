<script setup lang="ts">
import {ref} from 'vue'
import type {Student,Wallet,Credit,Page} from '../api/types'
import {useResource} from '../lib/useResource'
import {date,kinds} from '../lib/format'
import WalletSummary from '../components/WalletSummary.vue'
import ResourceState from '../components/ResourceState.vue'
import Pagination from '../components/Pagination.vue'
const page=ref(1)
const {data,error,loading,refresh}=useResource<{student:Student;wallets:Wallet[]}>(()=>'/api/v1/student/profile/')
const credits=useResource<Page<Credit>>(()=>`/api/v1/student/credits/?page=${page.value}`)
</script>
<template><div class="page-heading"><div><h1>我的课包</h1><p>剩余、已约和可约次数，一起核对。</p></div></div><ResourceState :error="error" :loading="loading" @retry="refresh" /><WalletSummary v-if="data" :wallets="data.wallets" /><p class="hint">预约预占课时，完课后才消耗。续课请联系教练，录入后这里会同步更新。</p><section class="section"><h2>课时流水</h2><ResourceState :error="credits.error.value" :loading="credits.loading.value" @retry="credits.refresh" /><div v-if="credits.data.value" class="surface ledger"><div v-for="entry in credits.data.value.items" :key="entry.id" class="ledger-row"><div class="grow"><h3>{{entry.title}}</h3><p>{{kinds[entry.kind]}} · {{date(entry.created_at)}}<template v-if="entry.entry_type==='purchase'"> · {{entry.expires_on ? `${date(entry.expires_on)} 到期` : '长期有效'}}</template></p></div><strong :class="entry.entry_type==='purchase'?'positive':''">{{entry.entry_type==='purchase'?'+':'−'}}{{entry.units}} 次</strong></div><p v-if="!credits.data.value.items.length" class="empty-note">还没有课时流水。</p></div><Pagination v-if="credits.data.value" :page="page" :page-size="credits.data.value.pagination.page_size" :total="credits.data.value.pagination.total" @change="page=$event" /></section></template>
