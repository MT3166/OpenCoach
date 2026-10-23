<script setup lang="ts">
defineProps<{ label: string; hint?: string; errors?: string[] }>()
</script>
<template><label class="field"><span class="field-label">{{ label }}</span><slot /><small v-if="hint" class="hint">{{ hint }}</small><small v-for="message in errors" :key="message" class="field-error">{{ message }}</small></label></template>
