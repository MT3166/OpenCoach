<script setup lang="ts">
import type { Wallet } from '../api/types'
import { date } from '../lib/format'
defineProps<{ wallets: Wallet[] }>()
</script>
<template><div class="wallets"><section v-for="wallet in wallets" :key="wallet.kind" class="wallet" :class="wallet.kind"><h3>{{ wallet.label }}</h3><p class="wallet-value"><strong>{{ wallet.remaining - wallet.expired }}</strong> 次有效</p><div class="wallet-details"><span>已预占 {{ wallet.reserved }}</span><span>可用 {{ wallet.available }}</span></div><p class="hint">已过期 {{ wallet.expired }} 次</p><details v-if="wallet.expiring.length" class="expiry-reminder"><summary>7天内有课时到期</summary><p v-for="(item,index) in wallet.expiring" :key="index">{{ date(item.expires_on) }} 到期 · {{ item.units }} 次（含预占）</p><p>到期日当天有效，续课请联系教练。</p></details></section></div></template>
