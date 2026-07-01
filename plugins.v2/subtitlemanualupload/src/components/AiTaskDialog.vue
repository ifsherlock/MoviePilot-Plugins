<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  aiTaskDialogTarget: { type: Object, default: null },
  compactTargetName: { type: Function, required: true },
  aiSummaryText: { type: String, default: '' },
  aiDialogHasActiveTasks: { type: Boolean, default: false },
  aiCancelling: { type: Boolean, default: false },
  aiAvailable: { type: Boolean, default: false },
  aiDialogTasks: { type: Array, default: () => [] },
  aiDialogHasExistingTasks: { type: Boolean, default: false },
  aiDialogSelectedAllowedTasks: { type: Array, default: () => [] },
  aiSubmitting: { type: Boolean, default: false },
  aiDialogActionText: { type: String, default: '' },
  aiTasksLoading: { type: Boolean, default: false },
  aiStatus: { type: Object, default: () => ({}) },
  aiRestartSourcePolicy: { type: String, default: '' },
  aiRestartSourceOptions: { type: Array, default: () => [] },
  aiDialogSourceLabel: { type: String, default: '' },
  aiRestartSubtitlePath: { type: String, default: '' },
  aiRestartSubtitleOptions: { type: Array, default: () => [] },
  aiSelectedTaskIds: { type: Array, default: () => [] },
  isAiTaskAllowed: { type: Function, required: true },
  aiTaskIconForTask: { type: Function, required: true },
  aiStatusText: { type: Function, required: true },
})

defineEmits([
  'update:modelValue',
  'update:aiRestartSourcePolicy',
  'update:aiRestartSubtitlePath',
  'update:aiSelectedTaskIds',
  'cancel-dialog-ai-tasks',
  'regenerate-dialog-ai-tasks',
  'load-ai-tasks',
  'regenerate-single-ai-task',
])
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="860"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <VCard class="ai-task-dialog" rounded="xl">
      <VCardTitle class="dialog-title">
        <div>
          <span>{{ aiTaskDialogTarget ? `AI 状态 · ${compactTargetName(aiTaskDialogTarget)}` : 'AI 字幕生成状态' }}</span>
          <p>{{ aiSummaryText }} · 状态来自 AI字幕生成(联动版) 队列</p>
        </div>
        <div class="online-title-actions">
          <VBtn
            v-if="aiDialogHasActiveTasks"
            variant="tonal"
            color="error"
            prepend-icon="mdi-cancel"
            :loading="aiCancelling"
            @click="$emit('cancel-dialog-ai-tasks')"
          >
            取消任务
          </VBtn>
          <VBtn
            v-if="aiAvailable && (aiTaskDialogTarget || aiDialogTasks.length)"
            variant="tonal"
            color="warning"
            prepend-icon="mdi-robot-happy-outline"
            :disabled="aiDialogHasExistingTasks && !aiDialogSelectedAllowedTasks.length"
            :loading="aiSubmitting"
            @click="$emit('regenerate-dialog-ai-tasks')"
          >
            {{ aiDialogActionText }}
          </VBtn>
          <VBtn
            variant="tonal"
            color="primary"
            prepend-icon="mdi-refresh"
            :loading="aiTasksLoading"
            @click="$emit('load-ai-tasks')"
          >
            刷新
          </VBtn>
        </div>
        <VBtn class="dialog-close-btn" icon="mdi-close" variant="text" @click="$emit('update:modelValue', false)" />
      </VCardTitle>
      <VDivider />
      <VCardText>
        <VAlert
          v-if="!aiAvailable"
          class="mb-4"
          type="warning"
          variant="tonal"
          :text="aiStatus.message || '请先安装并启用 AI字幕生成(联动版)'"
        />
        <div v-if="aiAvailable && (aiTaskDialogTarget || aiDialogTasks.length)" class="ai-restart-options">
          <VSelect
            :model-value="aiRestartSourcePolicy"
            :items="aiRestartSourceOptions"
            :label="aiDialogSourceLabel"
            density="comfortable"
            hint="改选来源会写入来源变体后缀，如 .aiasr.srt 或 .aiembedded.srt"
            persistent-hint
            @update:model-value="$emit('update:aiRestartSourcePolicy', $event)"
          />
          <VSelect
            v-if="aiRestartSourcePolicy === 'matched_external'"
            :model-value="aiRestartSubtitlePath"
            class="mt-3"
            :items="aiRestartSubtitleOptions"
            label="外挂字幕"
            density="comfortable"
            :hint="aiRestartSubtitleOptions.length ? '使用这条外挂 SRT 作为 AI 翻译来源' : '当前集没有可用于 AI 翻译的 SRT 外挂字幕'"
            persistent-hint
            :disabled="!aiRestartSubtitleOptions.length"
            @update:model-value="$emit('update:aiRestartSubtitlePath', $event)"
          />
        </div>
        <div v-if="aiDialogTasks.length" class="ai-task-list">
          <div
            v-for="task in aiDialogTasks"
            :key="task.task_id"
            class="ai-task-row"
            :class="`ai-${task.status}`"
          >
            <VCheckbox
              :model-value="aiSelectedTaskIds"
              :value="task.task_id"
              density="compact"
              hide-details
              :disabled="!isAiTaskAllowed(task)"
              @update:model-value="$emit('update:aiSelectedTaskIds', $event)"
            />
            <div class="ai-task-badge">
              <VIcon :icon="aiTaskIconForTask(task)" />
            </div>
            <div class="ai-task-main">
              <strong>{{ task.target_label || task.video_name }}</strong>
              <span>{{ task.source_asset_name || task.source_subtitle_name ? `字幕源：${task.source_asset_name || task.source_subtitle_name}` : (task.resolved_source_label || task.source_policy_label || task.video_name) }}</span>
              <span v-if="task.output_name">输出：{{ task.output_name }}</span>
              <p>{{ aiStatusText(task) }}</p>
            </div>
            <div class="ai-task-time">
              <VChip size="small" variant="tonal">{{ task.status_label }}</VChip>
              <span>{{ task.complete_time || task.add_time || '-' }}</span>
              <VBtn
                size="small"
                variant="tonal"
                color="warning"
                :disabled="!isAiTaskAllowed(task)"
                :loading="aiSubmitting"
                @click="$emit('regenerate-single-ai-task', task)"
              >
                重新生成
              </VBtn>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          当前资源还没有 AI 字幕生成任务。可以点击单集 AI 图标，或使用上方“AI 生成”批量提交。
        </div>
      </VCardText>
    </VCard>
  </VDialog>
</template>

<style scoped>
.ai-task-dialog {
  background:
    radial-gradient(circle at 8% 0%, rgba(219, 164, 71, 0.18), transparent 28%),
    radial-gradient(circle at 90% 20%, rgba(65, 116, 95, 0.14), transparent 32%),
    #fffaf2;
}

.dialog-title {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, auto) 40px;
  align-items: start;
  gap: 12px;
}

.dialog-title > div:first-child {
  min-width: 0;
}

.dialog-title > div:first-child span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dialog-title p {
  margin: 4px 0 0;
  color: #687873;
  font-size: 12px;
  font-weight: 400;
}

.online-title-actions {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.dialog-close-btn {
  justify-self: end;
}

.ai-task-list {
  display: grid;
  gap: 10px;
}

.ai-restart-options {
  margin-bottom: 14px;
}

.ai-task-row {
  display: grid;
  grid-template-columns: auto 42px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
}

.ai-task-row.ai-in_progress,
.ai-task-row.ai-pending {
  border-color: rgba(180, 122, 53, 0.3);
  background: #fff4da;
}

.ai-task-row.ai-completed {
  border-color: rgba(77, 143, 100, 0.26);
  background: rgba(230, 247, 235, 0.78);
}

.ai-task-row.ai-failed {
  border-color: rgba(185, 78, 70, 0.3);
  background: rgba(255, 234, 232, 0.8);
}

.ai-task-row.ai-cancelled {
  border-color: rgba(109, 123, 117, 0.24);
  background: rgba(239, 242, 240, 0.84);
}

.ai-task-badge {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 999px;
  background: #31463f;
  color: #fff8e8;
}

.ai-task-main {
  min-width: 0;
}

.ai-task-main strong,
.ai-task-main span,
.ai-task-main p {
  display: block;
}

.ai-task-main strong {
  font-weight: 900;
  word-break: break-word;
}

.ai-task-main span,
.ai-task-main p,
.ai-task-time span {
  color: #687873;
  font-size: 12px;
}

.ai-task-main p {
  margin: 4px 0 0;
}

.ai-task-time {
  display: grid;
  justify-items: end;
  gap: 6px;
}

.empty-state {
  padding: 28px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.58);
  color: #687873;
  text-align: center;
}

@media (max-width: 900px) {
  .dialog-title {
    grid-template-columns: minmax(0, 1fr) 40px;
  }

  .online-title-actions {
    grid-column: 1 / -1;
    grid-row: 2;
    width: 100%;
    justify-content: flex-end;
  }

  .dialog-close-btn {
    grid-column: 2;
    grid-row: 1;
  }
}

@media (max-width: 720px) {
  .ai-task-row {
    grid-template-columns: auto 42px minmax(0, 1fr);
  }

  .ai-task-time {
    grid-column: 1 / -1;
    justify-items: start;
  }
}
</style>
