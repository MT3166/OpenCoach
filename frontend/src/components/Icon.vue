<script setup lang="ts">
defineProps<{ name: string }>()
const paths: Record<string,string> = {
  home:'M3 10l9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z M9 21v-8h6v8',
  people:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M16 3a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-3.87 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  calendar:'M4 5h16v16H4z M16 3v4 M8 3v4 M4 11h16',
  book:'M12 6v15 M3 3h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5v17h-5a4 4 0 0 0-4 1 4 4 0 0 0-4-1H3z',
  plus:'M12 5v14 M5 12h14',
  arrow:'M5 12h14 M12 5l7 7-7 7',
  check:'M5 12l4 4L19 6',
  logout:'M9 21H4V3h5 M13 8l5 4-5 4 M8 12h13',
}
</script>
<template><svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name] || paths.book" /></svg></template>
