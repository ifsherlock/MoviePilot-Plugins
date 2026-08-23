<script setup>
import { computed, onMounted } from 'vue'
import { useAutoSubTasks } from '../composables/useAutoSubTasks'
import RestartDialog from './tasks/RestartDialog.vue'
import TaskStatusFilter from './tasks/TaskStatusFilter.vue'
import TaskTable from './tasks/TaskTable.vue'
import TaskToolbar from './tasks/TaskToolbar.vue'

const props = defineProps({
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'AutoSubv3',
  },
})

const emit = defineEmits(['close'])
const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoSubv3'}`)

const {
  loading,
  operating,
  operation,
  sortOrder,
  statusFilter,
  selectedTaskIds,
  error,
  message,
  status,
  tasks,
  restartDialog,
  restartTargets,
  restartSourcePolicy,
  restartSourceOptions,
  visibleTasks,
  allVisibleSelected,
  cancellableSelected,
  restartableSelected,
  deletableSelected,
  statusChips,
  loadTasks,
  cancelTasks,
  restartTasks,
  confirmRestartTasks,
  deleteTasks,
  toggleTask,
  toggleAll,
  canCancelTask,
  canRestartTask,
  canDeleteTask,
  setStatusFilter,
} = useAutoSubTasks({
  api: () => props.api,
  pluginBase,
})

onMounted(loadTasks)
</script>

<template>
  <div class="autosub-page">
    <TaskToolbar
      v-model:sort-order="sortOrder"
      :status="status"
      :visible-tasks="visibleTasks"
      :all-visible-selected="allVisibleSelected"
      :cancellable-selected="cancellableSelected"
      :restartable-selected="restartableSelected"
      :deletable-selected="deletableSelected"
      :operating="operating"
      :operation="operation"
      :loading="loading"
      @toggle-all="toggleAll"
      @cancel-selected="cancelTasks(cancellableSelected)"
      @restart-selected="restartTasks(restartableSelected)"
      @delete-selected="deleteTasks(deletableSelected)"
      @refresh="loadTasks"
      @close="emit('close')"
    />
    <VDivider />

    <main class="autosub-content">
      <VAlert v-if="error" class="mb-4" type="error" variant="tonal" :text="error" />
      <VAlert v-if="message" class="mb-4" type="success" variant="tonal" :text="message" />

      <TaskStatusFilter
        :status-chips="statusChips"
        :status-filter="statusFilter"
        @select="setStatusFilter"
      />

      <TaskTable
        :loading="loading"
        :tasks="tasks"
        :visible-tasks="visibleTasks"
        :selected-task-ids="selectedTaskIds"
        :operating="operating"
        :can-cancel-task="canCancelTask"
        :can-restart-task="canRestartTask"
        :can-delete-task="canDeleteTask"
        @toggle-task="toggleTask"
        @cancel="task => cancelTasks([task])"
        @restart="task => restartTasks([task])"
        @delete="task => deleteTasks([task])"
      />
    </main>

    <RestartDialog
      v-model="restartDialog"
      v-model:restart-source-policy="restartSourcePolicy"
      :restart-targets="restartTargets"
      :restart-source-options="restartSourceOptions"
      :operation="operation"
      :operating="operating"
      @confirm="confirmRestartTasks"
    />
  </div>
</template>

<style scoped>
.autosub-page {
  min-height: 100%;
  background: rgb(var(--v-theme-background));
}

.autosub-content {
  padding: 18px;
}
</style>
