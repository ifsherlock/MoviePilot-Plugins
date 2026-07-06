<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  task: {
    type: Object,
    required: true,
  },
  selected: {
    type: Boolean,
    default: false,
  },
  operating: {
    type: Boolean,
    default: false,
  },
  canCancel: {
    type: Boolean,
    default: false,
  },
  canRestart: {
    type: Boolean,
    default: false,
  },
  canDelete: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['toggle-task', 'cancel', 'restart', 'delete'])
const expanded = ref(false)

const statusColor = computed(() => ({
  pending: 'info',
  in_progress: 'warning',
  completed: 'success',
  failed: 'error',
  cancelled: 'default',
  ignored: 'default',
  no_audio: 'default',
})[props.task?.status] || 'default')

const sourceText = computed(() => {
  const source = props.task?.resolved_source_label
    || props.task?.source_policy_label
    || props.task?.source_label
    || props.task?.source
    || '未标记来源'
  const asset = props.task?.source_asset_name || props.task?.source_subtitle_name || ''
  return asset ? `${source} · ${asset}` : source
})

const timeText = computed(() => props.task?.complete_time || props.task?.add_time || '-')
const outputText = computed(() => props.task?.output_name || '尚未生成输出文件')
const messageText = computed(() => props.task?.message || '')
const hasDetails = computed(() => Boolean(props.task?.video_file || messageText.value || outputText.value))

function toggleExpanded() {
  expanded.value = !expanded.value
}
</script>

<template>
  <article class="task-mobile-card" :class="{ selected }">
    <header class="task-mobile-header">
      <VCheckbox
        class="task-mobile-check mobile-touch-target"
        :model-value="selected"
        density="compact"
        hide-details
        :aria-label="`选择 ${task.video_name || '任务'}`"
        @update:model-value="value => emit('toggle-task', task, value)"
      />
      <div class="task-mobile-title-block">
        <div class="task-mobile-title">{{ task.video_name || '未知视频' }}</div>
        <div class="task-mobile-subline">
          <VChip class="task-mobile-status" size="x-small" variant="tonal" :color="statusColor">
            {{ task.status_label || task.status }}
          </VChip>
          <span class="task-mobile-time">{{ timeText }}</span>
        </div>
      </div>
    </header>

    <section class="task-mobile-summary" aria-label="任务摘要">
      <div class="task-mobile-meta-row">
        <span class="task-mobile-meta-label">来源</span>
        <span class="task-mobile-meta-value">{{ sourceText }}</span>
      </div>
      <div class="task-mobile-meta-row">
        <span class="task-mobile-meta-label">输出</span>
        <span class="task-mobile-meta-value">{{ outputText }}</span>
      </div>
      <p v-if="messageText" class="task-mobile-message">{{ messageText }}</p>
    </section>

    <div class="task-mobile-actions">
      <VBtn
        class="task-primary-action mobile-touch-target"
        color="primary"
        variant="tonal"
        :disabled="!canRestart || operating"
        @click="emit('restart', task)"
      >
        重新生成
      </VBtn>
      <VBtn
        v-if="canCancel"
        class="task-secondary-action mobile-touch-target"
        color="warning"
        variant="text"
        :disabled="operating"
        @click="emit('cancel', task)"
      >
        取消
      </VBtn>
      <VBtn
        v-if="hasDetails"
        class="task-detail-action mobile-touch-target"
        variant="text"
        :aria-expanded="expanded"
        @click="toggleExpanded"
      >
        {{ expanded ? '收起' : '详情' }}
      </VBtn>
    </div>

    <section v-if="expanded" class="task-mobile-details" aria-label="任务详情">
      <div v-if="task.video_file" class="task-mobile-detail-block">
        <span class="task-mobile-detail-label">视频路径</span>
        <p class="task-mobile-code">{{ task.video_file }}</p>
      </div>
      <div v-if="messageText" class="task-mobile-detail-block">
        <span class="task-mobile-detail-label">完整原因</span>
        <p>{{ messageText }}</p>
      </div>
      <div class="task-mobile-detail-block">
        <span class="task-mobile-detail-label">输出文件</span>
        <p class="task-mobile-code">{{ outputText }}</p>
      </div>
      <div v-if="canDelete" class="task-mobile-danger">
        <VBtn
          class="task-danger-action mobile-touch-target"
          color="error"
          variant="tonal"
          :disabled="operating"
          @click="emit('delete', task)"
        >
          删除记录
        </VBtn>
      </div>
    </section>
  </article>
</template>

<style scoped>
.task-mobile-card {
  display: none;
}

@media (max-width: 760px) {
  .task-mobile-card {
    display: grid;
    gap: 12px;
    min-width: 0;
    border: 1px solid rgba(var(--v-border-color), 0.16);
    border-radius: 8px;
    background: rgb(var(--v-theme-surface));
    padding: 12px;
  }

  .task-mobile-card.selected {
    border-color: rgba(var(--v-theme-primary), 0.45);
    background: rgba(var(--v-theme-primary), 0.055);
  }

  .task-mobile-header {
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr);
    gap: 8px;
    align-items: start;
    min-width: 0;
  }

  .task-mobile-check {
    align-self: start;
    justify-self: start;
  }

  .task-mobile-title-block {
    display: grid;
    gap: 6px;
    min-width: 0;
  }

  .task-mobile-title {
    color: rgb(var(--v-theme-on-surface));
    font-size: 15px;
    font-weight: 650;
    line-height: 1.45;
    overflow-wrap: anywhere;
  }

  .task-mobile-subline {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    color: rgba(var(--v-theme-on-surface), 0.62);
    font-size: 12px;
    line-height: 1.4;
  }

  .task-mobile-time {
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .task-mobile-summary {
    display: grid;
    gap: 8px;
    min-width: 0;
  }

  .task-mobile-meta-row {
    display: grid;
    grid-template-columns: 42px minmax(0, 1fr);
    gap: 8px;
    min-width: 0;
    color: rgba(var(--v-theme-on-surface), 0.72);
    font-size: 13px;
    line-height: 1.45;
  }

  .task-mobile-meta-label,
  .task-mobile-detail-label {
    color: rgba(var(--v-theme-on-surface), 0.56);
    font-size: 12px;
    font-weight: 600;
  }

  .task-mobile-meta-value {
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .task-mobile-message {
    display: -webkit-box;
    margin: 0;
    color: rgba(var(--v-theme-on-surface), 0.78);
    font-size: 13px;
    line-height: 1.55;
    overflow: hidden;
    overflow-wrap: anywhere;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .task-mobile-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: 8px;
    align-items: center;
    min-width: 0;
  }

  .task-primary-action,
  .task-secondary-action,
  .task-detail-action,
  .task-danger-action {
    min-width: 44px;
    min-height: 46px;
    touch-action: manipulation;
  }

  .task-primary-action {
    justify-self: stretch;
  }

  .task-mobile-details {
    display: grid;
    gap: 10px;
    min-width: 0;
    border-top: 1px solid rgba(var(--v-border-color), 0.14);
    padding-top: 10px;
  }

  .task-mobile-detail-block {
    display: grid;
    gap: 4px;
    min-width: 0;
    color: rgba(var(--v-theme-on-surface), 0.76);
    font-size: 13px;
    line-height: 1.55;
  }

  .task-mobile-detail-block p {
    margin: 0;
    overflow-wrap: anywhere;
  }

  .task-mobile-code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px;
  }

  .task-mobile-danger {
    display: flex;
    justify-content: flex-end;
    border-top: 1px dashed rgba(var(--v-theme-error), 0.24);
    padding-top: 10px;
  }
}

@media (max-width: 430px) {
  .task-mobile-actions {
    grid-template-columns: 1fr 76px 76px;
  }
}
</style>
