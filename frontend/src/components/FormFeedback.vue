<script setup lang="ts">
import type { ApiError } from '../api/client'
defineProps<{ error?: ApiError | null; notice?: string }>()
</script>
<template>
  <div v-if="error" class="feedback error" role="alert"><p>{{ error.message }}</p><ul v-if="Object.keys(error.fields || {}).length"><li v-for="(messages,key) in error.fields" :key="key">{{ messages.join('；') }}</li></ul></div>
  <p v-if="notice" class="feedback success" role="status">{{ notice }}</p>
</template>
