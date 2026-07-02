<script setup>
defineProps({
  statusChips: {
    type: Array,
    default: () => [],
  },
  statusFilter: {
    type: String,
    default: 'all',
  },
})

const emit = defineEmits(['select'])
</script>

<template>
  <div class="summary-strip">
    <VChip
      v-for="chip in statusChips"
      :key="chip.value"
      size="small"
      class="filter-chip"
      :variant="statusFilter === chip.value ? 'flat' : 'tonal'"
      :color="chip.color || (statusFilter === chip.value ? 'primary' : undefined)"
      @click="emit('select', chip.value)"
    >
      {{ chip.label }} {{ chip.count }}
    </VChip>
  </div>
</template>

<style scoped>
.summary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.filter-chip {
  cursor: pointer;
  user-select: none;
}
</style>
