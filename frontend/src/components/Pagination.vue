<script setup lang="ts">
defineProps<{ page: number; pageSize: number; total: number }>()
defineEmits<{ change: [page: number] }>()
</script>
<template><div v-if="total>pageSize" class="pagination"><button class="button secondary" :disabled="page<=1" @click="$emit('change',page-1)">上一页</button><span>第 {{ page }} / {{ Math.ceil(total/pageSize) }} 页</span><button class="button secondary" :disabled="page*pageSize>=total" @click="$emit('change',page+1)">下一页</button></div></template>
