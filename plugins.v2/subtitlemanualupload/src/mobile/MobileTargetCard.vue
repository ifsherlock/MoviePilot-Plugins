<script setup>
import { computed } from 'vue'

const props = defineProps({
  target: { type: Object, required: true },
  detail: { type: Object, required: true },
  actions: { type: Object, required: true },
})

const selected = computed(() => props.detail.selectedTargetIds.includes(props.target.id))
const expanded = computed(() => props.detail.detailExpanded(props.target))
const disabled = computed(() => props.detail.isTargetActionDisabled(props.target))
const subtitles = computed(() => props.target.subtitles || [])
const row = computed(() => props.detail.detailRowForTarget(props.target))
const timelineTask = computed(() => props.detail.timelineTaskForTarget(props.target))

function toggleSelection(value) {
  props.actions.toggleTarget(props.target.id, value)
}
</script>

<template>
  <article class="mobile-target-card" :class="{ selected, locked: detail.isLocked(target.id) }">
    <div class="mobile-target-main">
      <VCheckbox
        :model-value="selected"
        density="compact"
        hide-details
        :disabled="target.writable === false"
        @update:model-value="toggleSelection"
      />
      <button type="button" class="mobile-target-summary" @click="actions.toggleDetailExpanded(target)">
        <span class="mobile-target-index">{{ target.media_type === 'tv' ? `E${String(target.episode || 0).padStart(2, '0')}` : 'MOV' }}</span>
        <span class="mobile-target-copy">
          <strong>{{ detail.compactTargetName(target) }}</strong>
          <small>{{ target.relative_path || target.path || '未提供路径' }}</small>
          <i v-if="target.writable === false">不可写入</i>
        </span>
        <span v-if="subtitles.length" class="mobile-subtitle-count">{{ subtitles.length }}</span>
        <VIcon :icon="expanded ? 'mdi-chevron-up' : 'mdi-chevron-down'" />
      </button>
    </div>

    <div class="mobile-target-actions">
      <VBtn
        size="small"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-cloud-search-outline"
        :disabled="disabled"
        @click="actions.openSingleOnlineSearch(target)"
      >
        在线
      </VBtn>
      <VBtn
        size="small"
        variant="tonal"
        :disabled="disabled"
        @click="actions.openSingleUpload(target)"
      >
        <VIcon start icon="mdi-upload-file" />
        上传
      </VBtn>
      <VMenu location="bottom end">
        <template #activator="{ props: menuProps }">
          <VBtn
            v-bind="menuProps"
            size="small"
            icon="mdi-dots-vertical"
            variant="text"
            title="更多操作"
          />
        </template>
        <VList density="compact" min-width="200">
          <VListItem
            :prepend-icon="detail.isLocked(target.id) ? 'mdi-lock-open-variant' : 'mdi-lock'"
            :title="detail.isLocked(target.id) ? '解除锁定' : '锁定并跳过批量上传'"
            @click="actions.toggleLock(target.id)"
          />
          <VListItem
            v-if="detail.aiEnabled"
            prepend-icon="mdi-robot-outline"
            title="AI 字幕生成"
            :disabled="disabled || detail.isStreamTarget(target) || (!detail.aiAvailable && !detail.aiTaskForTarget(target))"
            @click="actions.openSingleAiGenerate(target)"
          />
        </VList>
      </VMenu>
    </div>

    <section v-if="expanded || subtitles.length" class="mobile-target-expanded">
      <div class="mobile-target-meta">
        <span>{{ subtitles.length ? `${subtitles.length} 个外挂字幕` : '暂无外挂字幕' }}</span>
        <span v-if="row.task">AI：{{ detail.aiStatusText(row.task) }}</span>
        <span>{{ detail.timelineResultForTarget(row) }}</span>
        <span v-for="meta in detail.timelineMetaItems(timelineTask?.timeline)" :key="meta">{{ meta }}</span>
      </div>

      <div v-if="subtitles.length" class="mobile-subtitle-list">
        <div v-for="subtitle in subtitles" :key="subtitle.path" class="mobile-subtitle-row">
          <div>
            <strong>{{ subtitle.name }}</strong>
            <span>{{ detail.formatBytes(subtitle.size) }} · {{ subtitle.modified_at || '未知时间' }}</span>
          </div>
          <div class="mobile-subtitle-buttons">
            <VBtn
              icon="mdi-timeline-clock-outline"
              size="small"
              variant="text"
              color="warning"
              title="调轴"
              :disabled="detail.timelineFixing || !detail.timelineAvailable || disabled || detail.isStreamTarget(target)"
              :loading="detail.timelineFixing"
              @click="actions.fixHistorySubtitleTimeline(target, subtitle)"
            />
            <VBtn
              icon="mdi-restore"
              size="small"
              variant="text"
              color="secondary"
              title="恢复调轴前备份"
              :disabled="!subtitle.backup_available || disabled"
              :loading="detail.clearing"
              @click="actions.restoreSubtitleBackup(target, subtitle)"
            />
            <VBtn
              icon="mdi-delete-outline"
              size="small"
              variant="text"
              color="error"
              title="删除字幕"
              :disabled="disabled"
              :loading="detail.clearing"
              @click="actions.deleteSubtitle(target, subtitle)"
            />
          </div>
        </div>
      </div>
    </section>
  </article>
</template>

<style scoped>
.mobile-target-card {
  display: grid;
  gap: 8px;
  padding: 9px 10px 10px;
  border: 1px solid var(--smu-border);
  border-radius: var(--smu-mobile-radius);
  background: var(--smu-card-bg-strong);
}

.mobile-target-card.selected {
  border-color: var(--smu-border-active);
  background: var(--smu-card-bg-active);
}

.mobile-target-card.locked {
  opacity: 0.72;
}

.mobile-target-main,
.mobile-target-summary,
.mobile-target-actions,
.mobile-target-meta,
.mobile-subtitle-row,
.mobile-subtitle-buttons {
  display: flex;
  align-items: center;
}

.mobile-target-main {
  align-items: flex-start;
}

.mobile-target-main :deep(.v-selection-control) {
  min-height: 30px;
}

.mobile-target-summary {
  width: 100%;
  min-width: 0;
  gap: 8px;
  padding: 2px 0 0;
  color: var(--smu-text);
  text-align: left;
}

.mobile-target-index {
  display: grid;
  min-width: 42px;
  min-height: 28px;
  place-items: center;
  border-radius: 7px;
  background: var(--smu-card-bg-soft);
  color: var(--smu-text-muted);
  font-size: 11px;
  font-weight: 700;
}

.mobile-target-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 3px;
}

.mobile-target-copy strong,
.mobile-target-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-target-copy strong {
  font-size: 14px;
}

.mobile-target-copy small {
  color: var(--smu-text-muted);
  font-size: 11px;
}

.mobile-target-copy i {
  color: var(--smu-error-text);
  font-size: 11px;
  font-style: normal;
}

.mobile-subtitle-count {
  color: var(--smu-accent);
  font-size: 12px;
  font-weight: 700;
}

.mobile-target-summary > :deep(.v-icon) {
  color: var(--smu-text-soft);
}

.mobile-target-actions {
  justify-content: flex-end;
  gap: 4px;
  padding-left: 38px;
}

.mobile-target-expanded {
  display: grid;
  gap: 8px;
  padding: 9px;
  border-radius: 8px;
  background: var(--smu-card-bg-soft);
}

.mobile-target-meta {
  flex-wrap: wrap;
  gap: 5px;
}

.mobile-target-meta span {
  padding: 3px 6px;
  border-radius: 5px;
  background: rgba(var(--v-theme-surface), 0.68);
  color: var(--smu-text-muted);
  font-size: 11px;
}

.mobile-subtitle-list {
  display: grid;
  gap: 6px;
}

.mobile-subtitle-row {
  justify-content: space-between;
  gap: 8px;
  padding: 8px;
  border: 1px solid var(--smu-border);
  border-radius: 8px;
  background: var(--smu-card-bg);
}

.mobile-subtitle-row > div:first-child {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.mobile-subtitle-row strong,
.mobile-subtitle-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-subtitle-row strong {
  font-size: 12px;
}

.mobile-subtitle-row span {
  color: var(--smu-text-muted);
  font-size: 11px;
}

.mobile-subtitle-buttons {
  flex: 0 0 auto;
  gap: 1px;
}
</style>
