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
  min-width: 0;
}

.filter-chip {
  cursor: pointer;
  user-select: none;
}

@media (max-width: 760px) {
  .summary-strip {
    flex-wrap: nowrap;
    overflow-x: auto;
    padding-bottom: 4px;
    scrollbar-width: thin;
    -webkit-overflow-scrolling: touch;
  }

  .filter-chip {
    flex: 0 0 auto;
  }
}
</style>
