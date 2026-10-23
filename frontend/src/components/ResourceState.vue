<script setup lang="ts">
import type { ApiError } from '../api/client'
defineProps<{ loading?: boolean; error?: ApiError | null }>()
defineEmits<{ retry: [] }>()
</script>
<template><div v-if="error" class="empty-state" role="alert"><h2>{{ error.status===404 ? '找不到这条记录' : '暂时没有加载成功' }}</h2><p>{{ error.message }}</p><button class="button secondary" @click="$emit('retry')">重新加载</button></div><p v-else-if="loading" class="loading" role="status">正在读取记录…</p></template>
