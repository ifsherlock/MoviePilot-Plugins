<script setup>
import { ref } from 'vue'
import AiStatusStrip from './AiStatusStrip.vue'
import EpisodeMobileCard from './EpisodeMobileCard.vue'

defineProps({
  selectedMedia: { type: Object, required: true },
  selectedSeason: { type: [String, Number], default: 'all' },
  selectedTargets: { type: Array, default: () => [] },
  selectedTargetIds: { type: Array, default: () => [] },
  lockedTargetIds: { type: Array, default: () => [] },
  visibleTargets: { type: Array, default: () => [] },
  seasonCards: { type: Array, default: () => [] },
  resolving: { type: Boolean, default: false },
  aiEnabled: { type: Boolean, default: false },
  aiAvailable: { type: Boolean, default: false },
  aiHasActiveTasks: { type: Boolean, default: false },
  aiTasksLoading: { type: Boolean, default: false },
  aiSummaryText: { type: String, default: '' },
  aiStatus: { type: Object, default: () => ({}) },
  allVisibleSelected: { type: Boolean, default: false },
  unlockedVisibleTargets: { type: Array, default: () => [] },
  aiCapableBatchTargets: { type: Array, default: () => [] },
  aiSubmitting: { type: Boolean, default: false },
  aiBatchLabel: { type: String, default: '' },
  aiBatchCancelTargets: { type: Array, default: () => [] },
  aiCancelling: { type: Boolean, default: false },
  onlineSearching: { type: Boolean, default: false },
  onlineBatchLabel: { type: String, default: '' },
  batchUploadTargets: { type: Array, default: () => [] },
  clearing: { type: Boolean, default: false },
  selectedTimelineTargets: { type: Array, default: () => [] },
  timelineFixing: { type: Boolean, default: false },
  timelineAvailable: { type: Boolean, default: false },
  selectedRestorableTargets: { type: Array, default: () => [] },
  lastWritten: { type: Array, default: () => [] },
  posterImageSrc: { type: Function, required: true },
  mediaLabel: { type: Function, required: true },
  formatMediaType: { type: Function, required: true },
  compactTargetName: { type: Function, required: true },
  formatBytes: { type: Function, required: true },
  isLocked: { type: Function, required: true },
  isTargetActionDisabled: { type: Function, required: true },
  isStreamTarget: { type: Function, required: true },
  detailExpanded: { type: Function, required: true },
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
  timelineResultText: { type: Function, required: true },
})

defineEmits([
  'reset-selection',
  'mark-poster-failed',
  'load-targets',
  'change-season',
  'open-ai-task-dialog',
  'toggle-select-all',
  'open-batch-upload',
  'open-batch-ai-generate',
  'cancel-batch-ai-generate',
  'open-batch-online-search',
  'clear-selected-subtitles',
  'fix-selected-detail-timeline',
  'restore-selected-backups',
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

const aiStatusStripRef = ref(null)

defineExpose({
  scrollIntoView(options) {
    aiStatusStripRef.value?.scrollIntoView?.(options)
  },
  focus(options) {
    aiStatusStripRef.value?.focus?.(options)
  },
})
</script>

<template>
  <VCard class="glass-card detail-card" rounded="xl" elevation="0">
    <VCardText>
      <div class="detail-head">
        <div class="selected-media">
          <button
            class="back-btn"
            type="button"
            aria-label="返回资源列表"
            @click="$emit('reset-selection')"
          >
            <VIcon icon="mdi-arrow-left" />
          </button>
          <div class="mini-poster">
            <img
              v-if="posterImageSrc(selectedMedia)"
              :src="posterImageSrc(selectedMedia)"
              :alt="mediaLabel(selectedMedia)"
              loading="eager"
              fetchpriority="high"
              decoding="async"
              draggable="false"
              @error="$emit('mark-poster-failed', selectedMedia)"
            >
            <span v-else>{{ formatMediaType(selectedMedia.media_type) }}</span>
          </div>
          <div>
            <div class="section-kicker">{{ formatMediaType(selectedMedia.media_type) }}</div>
            <h2>{{ mediaLabel(selectedMedia) }}</h2>
            <p>{{ visibleTargets.length }} 个本地目标 · {{ selectedTargets.length }} 个已选 · {{ lockedTargetIds.length }} 个锁定</p>
          </div>
        </div>
        <VBtn class="mobile-touch-target" variant="tonal" :loading="resolving" @click="$emit('load-targets', selectedMedia, selectedSeason)">
          刷新列表
        </VBtn>
      </div>

      <div v-if="selectedMedia.media_type === 'tv'" class="season-strip">
        <button
          v-for="season in seasonCards"
          :key="season.value"
          class="season-card"
          :class="{ active: selectedSeason === season.value }"
          @click="$emit('change-season', season.value)"
        >
          <span>{{ season.title }}</span>
          <strong>{{ season.subtitle }}</strong>
        </button>
      </div>

      <AiStatusStrip
        ref="aiStatusStripRef"
        :ai-enabled="aiEnabled"
        :ai-available="aiAvailable"
        :ai-has-active-tasks="aiHasActiveTasks"
        :ai-tasks-loading="aiTasksLoading"
        :ai-summary-text="aiSummaryText"
        :ai-status="aiStatus"
        @open="$emit('open-ai-task-dialog')"
      />

      <div class="match-panel">
        <div class="toolbar-row">
          <VBtn class="mobile-touch-target" variant="tonal" @click="$emit('toggle-select-all')">
            {{ allVisibleSelected ? '取消全选' : '全选当前列表' }}
          </VBtn>
          <VBtn
            class="mobile-touch-target"
            color="primary"
            :disabled="!unlockedVisibleTargets.length"
            @click="$emit('open-batch-upload')"
          >
            {{ selectedTargets.length ? '上传选中字幕' : '批量上传整季字幕' }}
          </VBtn>
          <VBtn
            v-if="aiEnabled"
            class="mobile-touch-target"
            color="warning"
            variant="tonal"
            prepend-icon="mdi-robot-outline"
            :disabled="!aiCapableBatchTargets.length || !aiAvailable"
            :loading="aiSubmitting"
            @click="$emit('open-batch-ai-generate')"
          >
            {{ aiBatchLabel }}
          </VBtn>
          <VBtn
            v-if="aiEnabled && aiBatchCancelTargets.length"
            class="mobile-touch-target"
            color="error"
            variant="tonal"
            prepend-icon="mdi-cancel"
            :loading="aiCancelling"
            @click="$emit('cancel-batch-ai-generate')"
          >
            取消 AI
          </VBtn>
          <VBtn
            class="online-batch-btn mobile-touch-target"
            color="success"
            variant="flat"
            prepend-icon="mdi-cloud-search-outline"
            :disabled="!batchUploadTargets.length"
            :loading="onlineSearching"
            @click="$emit('open-batch-online-search')"
          >
            {{ onlineBatchLabel }}
          </VBtn>
          <VBtn
            class="mobile-touch-target"
            color="error"
            variant="tonal"
            :disabled="!selectedTargetIds.length"
            :loading="clearing"
            @click="$emit('clear-selected-subtitles')"
          >
            清空选中外挂字幕
          </VBtn>
          <VBtn
            class="mobile-touch-target"
            color="warning"
            variant="tonal"
            prepend-icon="mdi-timeline-clock"
            :disabled="!selectedTimelineTargets.length || timelineFixing || !timelineAvailable"
            :loading="timelineFixing"
            @click="$emit('fix-selected-detail-timeline')"
          >
            批量调轴
          </VBtn>
          <VBtn
            class="mobile-touch-target"
            color="secondary"
            variant="tonal"
            prepend-icon="mdi-restore"
            :disabled="!selectedRestorableTargets.length || clearing"
            :loading="clearing"
            @click="$emit('restore-selected-backups')"
          >
            批量恢复
          </VBtn>
        </div>

        <div v-if="visibleTargets.length" class="episode-list">
          <div
            v-for="target in visibleTargets"
            :key="target.id"
            class="episode-row"
            :class="{ locked: isLocked(target.id) }"
          >
            <EpisodeMobileCard
              :target="target"
              :selected="selectedTargetIds.includes(target.id)"
              :locked="isLocked(target.id)"
              :disabled="isTargetActionDisabled(target)"
              :expanded="detailExpanded(target)"
              :ai-enabled="aiEnabled"
              :ai-available="aiAvailable"
              :timeline-available="timelineAvailable"
              :timeline-fixing="timelineFixing"
              :clearing="clearing"
              :compact-target-name="compactTargetName"
              :format-bytes="formatBytes"
              :is-stream-target="isStreamTarget"
              :detail-row-for-target="detailRowForTarget"
              :ai-task-for-target="aiTaskForTarget"
              :ai-task-status-class="aiTaskStatusClass"
              :ai-task-icon="aiTaskIcon"
              :ai-task-color="aiTaskColor"
              :ai-task-title="aiTaskTitle"
              :ai-status-text="aiStatusText"
              :timeline-result-for-target="timelineResultForTarget"
              :timeline-meta-items="timelineMetaItems"
              :timeline-task-for-target="timelineTaskForTarget"
              @toggle-target="(targetId, value) => $emit('toggle-target', targetId, value)"
              @toggle-detail-expanded="item => $emit('toggle-detail-expanded', item)"
              @open-single-ai-generate="item => $emit('open-single-ai-generate', item)"
              @open-single-online-search="item => $emit('open-single-online-search', item)"
              @toggle-lock="targetId => $emit('toggle-lock', targetId)"
              @open-single-upload="item => $emit('open-single-upload', item)"
              @fix-history-subtitle-timeline="(item, subtitle) => $emit('fix-history-subtitle-timeline', item, subtitle)"
              @restore-subtitle-backup="(item, subtitle) => $emit('restore-subtitle-backup', item, subtitle)"
              @delete-subtitle="(item, subtitle) => $emit('delete-subtitle', item, subtitle)"
            />
            <VCheckbox
              class="episode-desktop-check"
              :model-value="selectedTargetIds.includes(target.id)"
              density="compact"
              hide-details
              @update:model-value="value => $emit('toggle-target', target.id, value)"
            />
            <VBtn
              class="episode-expand-btn"
              variant="tonal"
              density="comfortable"
              :icon="detailExpanded(target) ? 'mdi-chevron-down' : 'mdi-chevron-right'"
              :title="detailExpanded(target) ? '收起外挂字幕' : '展开外挂字幕'"
              @click="$emit('toggle-detail-expanded', target)"
            />
            <div class="episode-index">
              {{ target.media_type === 'tv' ? `E${String(target.episode || 0).padStart(2, '0')}` : 'MOV' }}
            </div>
            <div class="episode-copy">
              <div class="episode-title">{{ compactTargetName(target) }}</div>
              <div class="episode-path">{{ target.relative_path }}</div>
            </div>
            <VMenu v-if="target.has_subtitle" location="bottom end">
              <template #activator="{ props: menuProps }">
                <VBtn
                  v-bind="menuProps"
                  class="cc-btn has-sub"
                  variant="text"
                  icon="mdi-closed-caption"
                  :title="`已有 ${target.subtitle_count} 个外挂字幕`"
                />
              </template>
              <VCard min-width="280" rounded="lg">
                <VList density="compact">
                  <VListSubheader>已有外挂字幕</VListSubheader>
                  <VListItem
                    v-for="subtitle in target.subtitles"
                    :key="subtitle.path"
                    :title="subtitle.name"
                    :subtitle="formatBytes(subtitle.size)"
                  />
                </VList>
              </VCard>
            </VMenu>
            <VBtn
              v-else
              class="cc-btn"
              variant="text"
              icon="mdi-closed-caption-outline"
              title="暂无外挂字幕"
            />
            <VBtn
              v-if="aiEnabled"
              class="ai-row-btn"
              :class="aiTaskStatusClass(target)"
              variant="text"
              :icon="aiTaskIcon(target)"
              :color="aiTaskColor(target)"
              :title="aiTaskTitle(target)"
              :disabled="isTargetActionDisabled(target) || isStreamTarget(target) || (!aiAvailable && !aiTaskForTarget(target))"
              @click="$emit('open-single-ai-generate', target)"
            />
            <VBtn
              variant="text"
              icon="mdi-magnify"
              title="搜索此集在线字幕"
              :disabled="isTargetActionDisabled(target)"
              @click="$emit('open-single-online-search', target)"
            />
            <VBtn
              variant="text"
              :icon="isLocked(target.id) ? 'mdi-lock' : 'mdi-lock-open-variant'"
              :color="isLocked(target.id) ? 'warning' : undefined"
              :title="isLocked(target.id) ? '解锁此集' : '锁定此集，批量上传跳过'"
              @click="$emit('toggle-lock', target.id)"
            />
            <VBtn
              class="mobile-touch-target"
              color="primary"
              variant="tonal"
              size="small"
              :disabled="isTargetActionDisabled(target)"
              @click="$emit('open-single-upload', target)"
            >
              单集上传
            </VBtn>
            <div v-if="detailExpanded(target)" class="episode-expanded">
              <div class="history-status compact-status">
                <span>{{ (target.subtitles || []).length ? `${target.subtitles.length} 个外挂字幕` : '暂无外挂字幕' }}</span>
                <span v-if="detailRowForTarget(target).task">AI：{{ aiStatusText(detailRowForTarget(target).task) }}</span>
                <span>{{ timelineResultForTarget(detailRowForTarget(target)) }}</span>
                <span
                  v-for="meta in timelineMetaItems(timelineTaskForTarget(target)?.timeline)"
                  :key="`${target.id}-detail-${meta}`"
                  class="timeline-meta"
                >
                  {{ meta }}
                </span>
                <span v-if="isStreamTarget(target)">STRM 资源不启用 AI 生成和智能调轴</span>
              </div>
              <div v-if="(target.subtitles || []).length" class="subtitle-history-list compact-subtitles">
                <div
                  v-for="subtitle in target.subtitles"
                  :key="subtitle.path"
                  class="subtitle-history-item"
                >
                  <div class="subtitle-history-copy">
                    <strong>{{ subtitle.name }}</strong>
                    <span>{{ formatBytes(subtitle.size) }} · {{ subtitle.modified_at || '未知时间' }}</span>
                  </div>
                  <div class="subtitle-history-actions">
                    <VBtn
                      size="small"
                      variant="tonal"
                      color="warning"
                      :loading="timelineFixing"
                      :disabled="timelineFixing || !timelineAvailable || isTargetActionDisabled(target) || isStreamTarget(target)"
                      @click.stop="$emit('fix-history-subtitle-timeline', target, subtitle)"
                    >
                      调轴
                    </VBtn>
                    <VBtn
                      size="small"
                      variant="tonal"
                      color="secondary"
                      :loading="clearing"
                      :disabled="!subtitle.backup_available || isTargetActionDisabled(target)"
                      @click.stop="$emit('restore-subtitle-backup', target, subtitle)"
                    >
                      恢复
                    </VBtn>
                    <VBtn
                      size="small"
                      variant="tonal"
                      color="error"
                      :loading="clearing"
                      :disabled="isTargetActionDisabled(target)"
                      @click.stop="$emit('delete-subtitle', target, subtitle)"
                    >
                      删除
                    </VBtn>
                  </div>
                </div>
              </div>
              <div v-else class="empty-state compact-empty">
                当前集暂无外挂字幕。
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          {{ resolving ? '正在读取本地视频目标...' : '这个资源没有本地视频文件。' }}
        </div>

        <div v-if="lastWritten.length" class="result-panel">
          <div class="section-kicker">写入结果</div>
          <div v-for="item in lastWritten" :key="item.output_path" class="result-row">
            <div>
              <strong>{{ item.output_name }}</strong>
              <span>{{ item.target_label }}</span>
            </div>
            <em>{{ timelineResultText(item) }}</em>
            <div v-if="timelineMetaItems(item).length" class="timeline-meta-list">
              <span
                v-for="meta in timelineMetaItems(item)"
                :key="`${item.output_path}-${meta}`"
                class="timeline-meta"
              >
                {{ meta }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </VCardText>
  </VCard>
</template>

<style scoped>
.glass-card {
  border: 1px solid var(--smu-border);
  background: var(--smu-card-bg-strong);
  box-shadow: var(--smu-shadow);
  backdrop-filter: blur(14px);
}

.detail-card {
  border-radius: 28px;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.detail-head h2 {
  margin: 0;
  letter-spacing: -0.04em;
}

.detail-head p {
  margin: 8px 0 0;
  color: var(--smu-text-muted);
  line-height: 1.7;
}

.selected-media {
  display: grid;
  grid-template-columns: auto 58px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.back-btn {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border: 0;
  border-radius: 999px;
  background: var(--smu-card-bg-soft);
  color: var(--smu-text);
}

.mini-poster {
  display: grid;
  width: 58px;
  height: 78px;
  place-items: center;
  overflow: hidden;
  border-radius: 14px;
  background: var(--smu-poster-bg);
  color: var(--smu-accent);
  font-size: 12px;
}

.mini-poster img {
  display: block;
  width: 100%;
  height: 100%;
  background: var(--smu-poster-bg);
  object-fit: cover;
}

.section-kicker {
  color: var(--smu-accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.season-strip {
  display: flex;
  gap: 10px;
  max-width: 100%;
  padding-bottom: 12px;
  margin-bottom: 14px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  -webkit-overflow-scrolling: touch;
}

.season-card {
  display: inline-flex;
  flex: 0 0 auto;
  gap: 8px;
  align-items: center;
  min-width: max-content;
  padding: 10px 16px;
  border: 1px solid var(--smu-border);
  border-radius: 999px;
  background: var(--smu-card-bg);
  color: inherit;
  text-align: left;
  white-space: nowrap;
}

.season-card.active {
  border-color: var(--smu-border-active);
  background: var(--smu-card-bg-active);
  box-shadow: inset 0 -3px 0 var(--smu-accent);
}

.season-card span {
  font-weight: 800;
}

.season-card strong {
  color: var(--smu-text-muted);
  font-size: 13px;
}

.match-panel {
  min-width: 0;
}

.toolbar-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 12px;
  border-radius: 20px;
  background: var(--smu-card-bg-soft);
}

.online-batch-btn {
  box-shadow: 0 12px 28px rgba(var(--v-theme-primary), 0.22);
  font-weight: 900;
}

.episode-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.episode-row {
  display: grid;
  grid-template-columns: auto auto 58px minmax(0, 1fr) repeat(5, auto);
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--smu-border);
  border-radius: 20px;
  background: var(--smu-card-bg);
}

.episode-row.locked {
  background: var(--smu-card-bg-disabled);
}

.episode-expand-btn {
  min-width: 34px;
  width: 34px;
  height: 34px;
  border: 1px solid var(--smu-border);
  background: var(--smu-card-bg-soft);
  color: var(--smu-text-muted);
}

.episode-expanded {
  display: grid;
  grid-column: 1 / -1;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 16px;
  background: var(--smu-card-bg-soft);
}

.episode-index {
  display: grid;
  min-width: 48px;
  min-height: 34px;
  place-items: center;
  border-radius: 999px;
  background: var(--smu-card-bg-soft);
  color: var(--smu-text-muted);
  font-size: 12px;
  font-weight: 900;
}

.episode-copy {
  min-width: 0;
}

.episode-title {
  font-weight: 900;
  word-break: break-word;
}

.episode-path {
  margin-top: 4px;
  color: var(--smu-text-muted);
  font-size: 12px;
  word-break: break-all;
}

.cc-btn {
  color: var(--smu-text-soft);
}

.cc-btn.has-sub {
  color: var(--smu-success-text);
}

.ai-row-btn {
  border-radius: 999px;
}

.ai-row-btn.ai-pending,
.ai-row-btn.ai-in_progress {
  background: var(--smu-warning-soft);
}

.ai-row-btn.ai-completed {
  background: var(--smu-success-soft);
}

.ai-row-btn.ai-failed {
  background: var(--smu-error-soft);
}

.ai-row-btn.ai-cancelled {
  background: var(--smu-card-bg-disabled);
}

.history-status {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.history-status span {
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--smu-card-bg-soft);
  color: var(--smu-text-muted);
  font-size: 12px;
}

.compact-status {
  margin-top: 0;
}

.subtitle-history-list {
  display: grid;
  grid-column: 1 / -1;
  gap: 8px;
}

.compact-subtitles {
  grid-column: 1 / -1;
  margin-top: 8px;
}

.subtitle-history-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--smu-card-bg-soft);
}

.subtitle-history-copy {
  min-width: 0;
  flex: 1 1 auto;
}

.subtitle-history-item strong,
.subtitle-history-item span {
  display: block;
  overflow-wrap: anywhere;
}

.subtitle-history-item span {
  color: var(--smu-text-muted);
  font-size: 12px;
}

.subtitle-history-actions {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--smu-border);
  border-radius: 12px;
  background: var(--smu-card-bg);
}

.subtitle-history-actions .v-btn {
  min-width: 52px;
}

.timeline-meta-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
  min-width: 160px;
}

.timeline-meta {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid rgba(var(--v-theme-outline), 0.24);
  background: rgba(var(--v-theme-surface), 0.78);
  color: rgba(var(--v-theme-on-surface), 0.74);
  font-size: 12px;
  line-height: 1.35;
}

.empty-state {
  padding: 28px 18px;
  border-radius: 22px;
  background: var(--smu-card-bg-soft);
  color: var(--smu-text-muted);
  text-align: center;
}

.compact-empty {
  padding: 12px;
  border-radius: 14px;
}

.result-panel {
  display: grid;
  gap: 10px;
  padding-top: 18px;
  margin-top: 18px;
  border-top: 1px solid var(--smu-border);
}

.result-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 16px;
  background: var(--smu-card-bg);
}

.result-row div {
  display: grid;
  gap: 3px;
}

.result-row .timeline-meta-list {
  display: flex;
  gap: 6px;
}

.result-row span,
.result-row em {
  color: var(--smu-text-muted);
  font-size: 12px;
  font-style: normal;
}

@media (max-width: 900px) {
  .detail-head {
    display: grid;
    grid-template-columns: 1fr;
  }

  .subtitle-history-item {
    grid-template-columns: 1fr;
    align-items: flex-start;
    flex-direction: column;
  }

  .subtitle-history-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .episode-row {
    grid-template-columns: auto auto 48px minmax(0, 1fr);
    align-items: start;
  }

  .episode-row > .cc-btn,
  .episode-row > .v-btn:not(.episode-expand-btn) {
    justify-self: start;
  }
}

@media (max-width: 600px) {
  .detail-card {
    border-radius: 20px;
  }

  .detail-card :deep(.v-card-text) {
    padding: 14px;
  }

  .detail-head {
    gap: 12px;
  }

  .detail-head > .v-btn {
    width: 100%;
  }

  .selected-media {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .mini-poster {
    display: none;
  }

  .toolbar-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    padding: 10px;
    border-radius: 16px;
  }

  .toolbar-row .v-btn {
    width: 100%;
  }

  .episode-row {
    display: block;
    border: 0;
    background: transparent;
    padding: 0;
  }

  .episode-desktop-check,
  .episode-expand-btn,
  .episode-index,
  .episode-copy,
  .episode-row > .cc-btn,
  .episode-row > .ai-row-btn,
  .episode-row > .v-btn:not(.episode-expand-btn),
  .episode-expanded {
    display: none;
  }
}
</style>

<style>
@media (max-width: 900px) {
  .detail-card .mobile-touch-target {
    --v-btn-height: 44px;
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
