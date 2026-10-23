<script setup lang="ts">
import type { Lesson } from '../api/types'
import { date, kinds } from '../lib/format'
import Icon from './Icon.vue'
defineProps<{ items: Lesson[]; coach?: boolean }>()
</script>
<template><div class="lesson-list"><div v-if="!items.length" class="empty-state"><h3>记录会从第一节课开始</h3><p>{{ coach ? '上完一节课，记一下就好。' : '教练完成记课后，你可以在这里回看。' }}</p></div><component :is="coach ? 'RouterLink' : 'div'" v-for="item in items" :key="`${item.source}:${item.id}`" :to="coach ? `/coach/${item.source==='direct' ? 'lessons' : 'bookings'}/${item.id}/` : undefined" class="history-row"><div class="history-date">{{ date(item.occurred_on) }}</div><div class="grow"><h3>{{ coach ? item.student.name : kinds[item.kind] }}</h3><p class="record-text">{{ item.note || '本节已完成，教练暂未添加文字记录。' }}</p><small>{{ kinds[item.kind] }} · {{ item.source==='direct' ? '直接记课' : '预约课程' }}</small><div v-if="!coach && item.exercises.length" class="exercise-summary"><span v-for="(row,index) in item.exercises" :key="index">{{ row.name }}<template v-if="row.sets"> · {{ row.sets }}组</template><template v-if="row.reps"> × {{ row.reps }}次</template><template v-if="row.weight!==null"> · {{ row.weight }}kg</template></span></div></div><Icon v-if="coach" name="arrow" /></component></div></template>
