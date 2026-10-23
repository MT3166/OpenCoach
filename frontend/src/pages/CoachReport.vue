<script setup lang="ts">
import { ref } from 'vue'
import type { MonthlyReport } from '../api/types'
import { useResource } from '../lib/useResource'
import { today } from '../lib/format'
import Field from '../components/Field.vue'
import ResourceState from '../components/ResourceState.vue'
const month=ref(today().slice(0,7))
const {data,error,loading,refresh}=useResource<MonthlyReport>(()=>`/api/v1/coach/reports/monthly/?month=${month.value}`)
</script>
<template><div class="page-heading"><div><h1>月度经营报表</h1><p>按上海时间统计实际出勤、直接记课、候补与课时到期。</p></div></div><div class="filters"><Field label="统计月份"><input v-model="month" type="month" required /></Field><button class="button secondary" :disabled="loading" @click="refresh">刷新报表</button></div><ResourceState :error="error" :loading="loading" @retry="refresh" /><section v-if="data" class="surface"><h2>{{data.month}} 经营概览</h2><dl class="report-rows"><div><dt>预约到课</dt><dd>{{data.scheduled_attended}} 次</dd></div><div><dt>预约缺席</dt><dd>{{data.scheduled_missed}} 次</dd></div><div><dt>预约取消</dt><dd>{{data.scheduled_cancelled}} 次</dd></div><div><dt>已到时间待确认</dt><dd>{{data.pending}} 次</dd></div><div><dt>直接记课</dt><dd>{{data.direct_attended}} 次</dd></div><div><dt>候补递补转正</dt><dd>{{data.waitlist_promoted}} 人次</dd></div><div><dt>过期未用课时</dt><dd>{{data.credit_expired}} 次</dd></div><div><dt>预约到课率</dt><dd>{{data.scheduled_denominator?`${data.scheduled_rate}%`:'暂无已处理预约'}}</dd></div></dl><p class="hint">到课率仅按已处理预约计算（本月分母 {{data.scheduled_denominator}} 次），排除整堂取消；直接记课单独展示。过期流失在到期日次日计入，已使用课时不计流失。</p></section></template>
