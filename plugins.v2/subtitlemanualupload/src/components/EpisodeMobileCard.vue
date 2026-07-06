<script setup>
defineProps({
  target: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  locked: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  expanded: { type: Boolean, default: false },
  aiEnabled: { type: Boolean, default: false },
  aiAvailable: { type: Boolean, default: false },
  timelineAvailable: { type: Boolean, default: false },
  timelineFixing: { type: Boolean, default: false },
  clearing: { type: Boolean, default: false },
  compactTargetName: { type: Function, required: true },
  formatBytes: { type: Function, required: true },
  isStreamTarget: { type: Function, required: true },
  detailRowForTarget: { type: Function, required: true },
  aiTaskForTarget: { type: Function, required: true },
  aiTaskStatusClass: { type: Function, required: true },
  aiTaskIcon: { type: Function, required: true },
  aiTaskColor: { type: Function, required: true },
  aiTaskTitle: { type: Function, required: true },
  aiStatusText: { type: Function, required: true },
  timelineResultForTarget: { type: Function, required: true },
  timelineMetaItems: { type: Function, required: true },
  timelineTaskForTarget: { type: Function, required: true },
})

const emit = defineEmits([
  'toggle-target',
  'toggle-detail-expanded',
  'open-single-ai-generate',
  'open-single-online-search',
  'toggle-lock',
  'open-single-upload',
  'fix-history-subtitle-timeline',
  'restore-subtitle-backup',
  'delete-subtitle',
])

function episodeLabel(target) {
  return target.media_type === 'tv' ? `E${String(target.episode || 0).padStart(2, '0')}` : 'MOV'
}
</script>

<template>
  <article class="episode-mobile-card" :class="{ locked, selected }">
    <header class="episode-mobile-header">
      <VCheckbox
        class="episode-mobile-check mobile-touch-target"
        :model-value="selected"
        density="compact"
        hide-details
        :aria-label="`选择 ${compactTargetName(target)}`"
        @update:model-value="value => emit('toggle-target', target.id, value)"
      />
      <div class="episode-mobile-title-block">
        <div class="episode-mobile-title-line">
          <span class="episode-mobile-index">{{ episodeLabel(target) }}</span>
          <strong :title="compactTargetName(target)">{{ compactTargetName(target) }}</strong>
        </div>
        <div class="episode-mobile-chips">
          <span class="episode-mobile-chip" :class="{ positive: target.has_subtitle }">
            {{ (target.subtitles || []).length ? `${target.subtitles.length} 个外挂字幕` : '暂无外挂字幕' }}
          </span>
          <span v-if="aiEnabled" class="episode-mobile-chip" :class="aiTaskStatusClass(target)">
            AI：{{ aiTaskForTarget(target) ? aiStatusText(aiTaskForTarget(target)) : (aiAvailable ? '可生成' : '不可用') }}
          </span>
          <span v-if="locked" class="episode-mobile-chip warning">已锁定</span>
        </div>
      </div>
      <VBtn
        class="episode-mobile-expand mobile-touch-target"
        variant="tonal"
        :icon="expanded ? 'mdi-chevron-down' : 'mdi-chevron-right'"
        :title="expanded ? '收起详情' : '展开详情'"
        @click="emit('toggle-detail-expanded', target)"
      />
    </header>

    <section class="episode-mobile-summary" aria-label="剧集摘要">
      <div class="episode-mobile-meta-row">
        <span>文件</span>
        <strong :title="target.basename || compactTargetName(target)">{{ target.basename || compactTargetName(target) }}</strong>
      </div>
      <div class="episode-mobile-meta-row">
        <span>调轴</span>
        <strong>{{ timelineResultForTarget(detailRowForTarget(target)) }}</strong>
      </div>
      <p class="episode-mobile-path" :title="target.relative_path || target.path">
        {{ target.relative_path || target.path }}
      </p>
    </section>

    <div class="episode-mobile-actions">
      <VBtn
        class="episode-online-action mobile-touch-target"
        color="success"
        variant="tonal"
        :disabled="disabled"
        @click="emit('open-single-online-search', target)"
      >
        在线搜索
      </VBtn>
      <VBtn
        class="episode-upload-action mobile-touch-target"
        color="primary"
        variant="flat"
        :disabled="disabled"
        @click="emit('open-single-upload', target)"
      >
        上传
      </VBtn>
      <VBtn
        v-if="aiEnabled"
        class="episode-ai-action mobile-touch-target"
        variant="tonal"
        :icon="aiTaskIcon(target)"
        :color="aiTaskColor(target)"
        :title="aiTaskTitle(target)"
        :disabled="disabled || isStreamTarget(target) || (!aiAvailable && !aiTaskForTarget(target))"
        @click="emit('open-single-ai-generate', target)"
      />
    </div>

    <section v-if="expanded" class="episode-mobile-details" aria-label="剧集详情">
      <div class="episode-mobile-detail-block">
        <span>完整路径</span>
        <p>{{ target.path || target.relative_path }}</p>
      </div>
      <div class="episode-mobile-detail-tags">
        <span>{{ timelineResultForTarget(detailRowForTarget(target)) }}</span>
        <span v-if="detailRowForTarget(target).task">AI：{{ aiStatusText(detailRowForTarget(target).task) }}</span>
        <span
          v-for="meta in timelineMetaItems(timelineTaskForTarget(target)?.timeline)"
          :key="`${target.id}-mobile-${meta}`"
        >
          {{ meta }}
        </span>
        <span v-if="isStreamTarget(target)">STRM 资源不启用 AI 生成和智能调轴</span>
      </div>

      <div v-if="(target.subtitles || []).length" class="episode-mobile-subtitles">
        <div
          v-for="subtitle in target.subtitles"
          :key="subtitle.path"
          class="episode-mobile-subtitle"
        >
          <div class="episode-mobile-subtitle-copy">
            <strong :title="subtitle.name">{{ subtitle.name }}</strong>
            <span>{{ formatBytes(subtitle.size) }} · {{ subtitle.modified_at || '未知时间' }}</span>
          </div>
          <div class="episode-mobile-subtitle-actions">
            <VBtn
              class="mobile-touch-target"
              variant="tonal"
              color="warning"
              :loading="timelineFixing"
              :disabled="timelineFixing || !timelineAvailable || disabled || isStreamTarget(target)"
              @click.stop="emit('fix-history-subtitle-timeline', target, subtitle)"
            >
              调轴
            </VBtn>
            <VBtn
              class="mobile-touch-target"
              variant="tonal"
              color="secondary"
              :loading="clearing"
              :disabled="!subtitle.backup_available || disabled"
              @click.stop="emit('restore-subtitle-backup', target, subtitle)"
            >
              恢复
            </VBtn>
            <VBtn
              class="mobile-touch-target"
              variant="tonal"
              color="error"
              :loading="clearing"
              :disabled="disabled"
              @click.stop="emit('delete-subtitle', target, subtitle)"
            >
              删除
            </VBtn>
          </div>
        </div>
      </div>
      <div v-else class="episode-mobile-empty">当前集暂无外挂字幕。</div>

      <div class="episode-mobile-low-actions">
        <VBtn
          class="mobile-touch-target"
          variant="text"
          :color="locked ? 'warning' : undefined"
          @click="emit('toggle-lock', target.id)"
        >
          {{ locked ? '解除锁定' : '锁定此集' }}
        </VBtn>
      </div>
    </section>
  </article>
</template>

<style scoped>
.episode-mobile-card {
  display: none;
}

@media (max-width: 600px) {
  .episode-mobile-card {
    display: grid;
    gap: 12px;
    min-width: 0;
    border: 1px solid var(--smu-border);
    border-radius: 16px;
    background: var(--smu-card-bg);
    padding: 12px;
  }

  .episode-mobile-card.selected {
    border-color: var(--smu-border-active);
    background: var(--smu-card-bg-active);
  }

  .episode-mobile-card.locked {
    background: var(--smu-card-bg-disabled);
  }

  .episode-mobile-header {
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr) 44px;
    gap: 8px;
    align-items: start;
    min-width: 0;
  }

  .episode-mobile-title-block,
  .episode-mobile-summary,
  .episode-mobile-details {
    display: grid;
    gap: 8px;
    min-width: 0;
  }

  .episode-mobile-title-line {
    display: flex;
    gap: 8px;
    align-items: baseline;
    min-width: 0;
  }

  .episode-mobile-title-line strong {
    min-width: 0;
    color: var(--smu-text);
    font-size: 15px;
    line-height: 1.45;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .episode-mobile-index {
    flex: 0 0 auto;
    color: var(--smu-accent);
    font-size: 12px;
    font-weight: 900;
  }

  .episode-mobile-chips,
  .episode-mobile-detail-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .episode-mobile-chip,
  .episode-mobile-detail-tags span {
    min-height: 24px;
    padding: 3px 8px;
    border-radius: 999px;
    background: var(--smu-card-bg-soft);
    color: var(--smu-text-muted);
    font-size: 12px;
    line-height: 1.4;
  }

  .episode-mobile-chip.positive,
  .episode-mobile-chip.ai-completed {
    background: var(--smu-success-soft);
    color: var(--smu-success-text);
  }

  .episode-mobile-chip.ai-pending,
  .episode-mobile-chip.ai-in_progress,
  .episode-mobile-chip.warning {
    background: var(--smu-warning-soft);
  }

  .episode-mobile-chip.ai-failed {
    background: var(--smu-error-soft);
  }

  .episode-mobile-meta-row {
    display: grid;
    grid-template-columns: 42px minmax(0, 1fr);
    gap: 8px;
    color: var(--smu-text-muted);
    font-size: 13px;
    line-height: 1.45;
  }

  .episode-mobile-meta-row strong {
    min-width: 0;
    color: var(--smu-text);
    font-weight: 650;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .episode-mobile-path {
    display: -webkit-box;
    margin: 0;
    color: var(--smu-text-muted);
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px;
    line-height: 1.55;
    overflow: hidden;
    overflow-wrap: anywhere;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 1;
  }

  .episode-mobile-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 46px;
    gap: 8px;
  }

  .episode-mobile-actions .mobile-touch-target,
  .episode-mobile-subtitle-actions .mobile-touch-target,
  .episode-mobile-low-actions .mobile-touch-target,
  .episode-mobile-check,
  .episode-mobile-expand {
    min-width: 44px;
    min-height: 46px;
    touch-action: manipulation;
  }

  .episode-mobile-details {
    border-top: 1px solid var(--smu-border);
    padding-top: 10px;
  }

  .episode-mobile-detail-block {
    display: grid;
    gap: 4px;
    color: var(--smu-text-muted);
    font-size: 12px;
  }

  .episode-mobile-detail-block p {
    margin: 0;
    color: var(--smu-text);
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    line-height: 1.55;
    overflow-wrap: anywhere;
  }

  .episode-mobile-subtitles {
    display: grid;
    gap: 8px;
  }

  .episode-mobile-subtitle {
    display: grid;
    gap: 8px;
    border-radius: 12px;
    background: var(--smu-card-bg-soft);
    padding: 10px;
  }

  .episode-mobile-subtitle-copy {
    display: grid;
    gap: 3px;
    min-width: 0;
  }

  .episode-mobile-subtitle-copy strong,
  .episode-mobile-subtitle-copy span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .episode-mobile-subtitle-copy span {
    color: var(--smu-text-muted);
    font-size: 12px;
  }

  .episode-mobile-subtitle-actions {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .episode-mobile-empty {
    border-radius: 12px;
    background: var(--smu-card-bg-soft);
    color: var(--smu-text-muted);
    padding: 12px;
    text-align: center;
  }

  .episode-mobile-low-actions {
    display: flex;
    justify-content: flex-end;
  }
}
</style>
