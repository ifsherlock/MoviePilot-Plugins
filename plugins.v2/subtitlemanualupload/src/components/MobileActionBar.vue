<script setup>
defineProps({
  selectedCount: { type: Number, default: 0 },
  visibleCount: { type: Number, default: 0 },
  unlockedCount: { type: Number, default: 0 },
  batchUploadCount: { type: Number, default: 0 },
  aiEnabled: { type: Boolean, default: false },
  aiAvailable: { type: Boolean, default: false },
  aiCapableCount: { type: Number, default: 0 },
  aiCancelCount: { type: Number, default: 0 },
  aiSubmitting: { type: Boolean, default: false },
  aiCancelling: { type: Boolean, default: false },
  aiBatchLabel: { type: String, default: '' },
  onlineSearching: { type: Boolean, default: false },
  onlineBatchLabel: { type: String, default: '' },
  clearing: { type: Boolean, default: false },
  timelineCount: { type: Number, default: 0 },
  timelineFixing: { type: Boolean, default: false },
  timelineAvailable: { type: Boolean, default: false },
  restorableCount: { type: Number, default: 0 },
})

defineEmits([
  'open-batch-upload',
  'open-batch-ai-generate',
  'cancel-batch-ai-generate',
  'open-batch-online-search',
  'clear-selected-subtitles',
  'fix-selected-detail-timeline',
  'restore-selected-backups',
])
</script>

<template>
  <nav class="subtitle-mobile-action-bar" aria-label="字幕匹配批量操作">
    <div class="subtitle-mobile-action-summary">
      <span>{{ selectedCount ? `${selectedCount} 个已选` : `${visibleCount} 个目标` }}</span>
      <strong>{{ selectedCount ? '批量处理' : '选择剧集后批量处理' }}</strong>
    </div>
    <div class="subtitle-mobile-action-primary">
      <VBtn
        class="subtitle-mobile-action-btn"
        color="success"
        variant="flat"
        :disabled="!batchUploadCount"
        :loading="onlineSearching"
        @click="$emit('open-batch-online-search')"
      >
        {{ onlineBatchLabel || '在线搜索' }}
      </VBtn>
      <VBtn
        class="subtitle-mobile-action-btn"
        color="primary"
        variant="flat"
        :disabled="!unlockedCount"
        @click="$emit('open-batch-upload')"
      >
        上传
      </VBtn>
      <VBtn
        v-if="aiEnabled"
        class="subtitle-mobile-action-btn subtitle-mobile-ai-btn"
        color="warning"
        variant="tonal"
        prepend-icon="mdi-robot-outline"
        :disabled="!aiCapableCount || !aiAvailable"
        :loading="aiSubmitting"
        @click="$emit('open-batch-ai-generate')"
      >
        {{ aiBatchLabel || 'AI 生成' }}
      </VBtn>
    </div>
    <div class="subtitle-mobile-action-secondary">
      <VBtn
        v-if="aiEnabled && aiCancelCount"
        class="subtitle-mobile-action-btn"
        color="error"
        variant="tonal"
        :loading="aiCancelling"
        @click="$emit('cancel-batch-ai-generate')"
      >
        取消 AI
      </VBtn>
      <VBtn
        class="subtitle-mobile-action-btn"
        color="warning"
        variant="tonal"
        :disabled="!timelineCount || timelineFixing || !timelineAvailable"
        :loading="timelineFixing"
        @click="$emit('fix-selected-detail-timeline')"
      >
        调轴
      </VBtn>
      <VBtn
        class="subtitle-mobile-action-btn"
        color="secondary"
        variant="tonal"
        :disabled="!restorableCount || clearing"
        :loading="clearing"
        @click="$emit('restore-selected-backups')"
      >
        恢复
      </VBtn>
      <VBtn
        class="subtitle-mobile-action-btn"
        color="error"
        variant="tonal"
        :disabled="!selectedCount"
        :loading="clearing"
        @click="$emit('clear-selected-subtitles')"
      >
        清空
      </VBtn>
    </div>
  </nav>
</template>

<style scoped>
.subtitle-mobile-action-bar {
  display: none;
}

@media (max-width: 600px) {
  .subtitle-mobile-action-bar {
    position: sticky;
    z-index: 12;
    bottom: calc(72px + env(safe-area-inset-bottom, 0px));
    display: grid;
    gap: 10px;
    width: 100%;
    min-width: 0;
    padding: 10px;
    border: 1px solid var(--smu-border);
    border-radius: 18px;
    margin: 12px 0;
    background: var(--smu-card-bg-strong);
    box-shadow: var(--smu-shadow);
    backdrop-filter: blur(14px);
  }

  .subtitle-mobile-action-summary {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    align-items: center;
    min-width: 0;
    color: var(--smu-text-muted);
    font-size: 12px;
    line-height: 1.4;
  }

  .subtitle-mobile-action-summary strong {
    min-width: 0;
    color: var(--smu-text);
    font-size: 13px;
    overflow-wrap: anywhere;
  }

  .subtitle-mobile-action-primary,
  .subtitle-mobile-action-secondary {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .subtitle-mobile-ai-btn {
    grid-column: 1 / -1;
  }

  .subtitle-mobile-action-btn {
    min-width: 44px;
    min-height: 44px;
    touch-action: manipulation;
  }
}
</style>
