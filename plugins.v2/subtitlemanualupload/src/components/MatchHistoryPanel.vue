<script setup>
defineProps({
  rootTab: { type: String, default: 'match' },
  autoQueueTasks: { type: Array, default: () => [] },
  autoQueueSummary: { type: Object, default: () => ({}) },
  autoQueueSummaryText: { type: String, default: '' },
  matchHistoryItems: { type: Array, default: () => [] },
  matchHistoryTotal: { type: Number, default: 0 },
  matchHistoryHasMore: { type: Boolean, default: false },
  matchHistoryLoading: { type: Boolean, default: false },
  clearing: { type: Boolean, default: false },
  timelineFixing: { type: Boolean, default: false },
  timelineAvailable: { type: Boolean, default: false },
  posterImageSrc: { type: Function, required: true },
  mediaLabel: { type: Function, required: true },
  posterLoading: { type: Function, required: true },
  posterFetchPriority: { type: Function, required: true },
  markPosterFailed: { type: Function, required: true },
  formatMediaType: { type: Function, required: true },
  historyMediaStat: { type: Function, required: true },
  historyExpanded: { type: Function, required: true },
  toggleHistoryExpanded: { type: Function, required: true },
  historySelectedCount: { type: Function, required: true },
  historyDeletableTargets: { type: Function, required: true },
  toggleHistoryItemTargets: { type: Function, required: true },
  allHistoryTargetsSelected: { type: Function, required: true },
  clearHistorySelectedSubtitles: { type: Function, required: true },
  historySelectedTimelineTargets: { type: Function, required: true },
  fixHistorySelectedTimeline: { type: Function, required: true },
  historySeasonGroups: { type: Function, required: true },
  historySeasonKey: { type: Function, required: true },
  allHistorySeasonTargetsSelected: { type: Function, required: true },
  historySeasonPartiallySelected: { type: Function, required: true },
  toggleHistorySeasonTargets: { type: Function, required: true },
  historySeasonExpanded: { type: Function, required: true },
  toggleHistorySeasonExpanded: { type: Function, required: true },
  historySeasonSelectedCount: { type: Function, required: true },
  historySelectedIds: { type: Function, required: true },
  toggleHistoryTarget: { type: Function, required: true },
  historyTargetExpanded: { type: Function, required: true },
  toggleHistoryTargetExpanded: { type: Function, required: true },
  compactTargetName: { type: Function, required: true },
  isTargetActionDisabled: { type: Function, required: true },
  openSingleOnlineSearch: { type: Function, required: true },
  timelineTaskText: { type: Function, required: true },
  timelineMetaItems: { type: Function, required: true },
  formatBytes: { type: Function, required: true },
  fixHistorySubtitleTimeline: { type: Function, required: true },
  isStreamTarget: { type: Function, required: true },
  deleteSubtitle: { type: Function, required: true },
})

defineEmits([
  'open-auto-queue',
  'load-more-match-history',
])
</script>

<template>
  <div
    v-if="rootTab === 'history' && (autoQueueTasks.length || autoQueueSummary.active)"
    class="auto-queue-entry"
  >
    <VBtn
      variant="tonal"
      color="primary"
      prepend-icon="mdi-tray-full"
      @click="$emit('open-auto-queue')"
    >
      入库自动字幕队列 · {{ autoQueueSummaryText }}
    </VBtn>
  </div>

  <div v-if="rootTab === 'history' && matchHistoryItems.length" class="global-history-list">
    <div
      v-for="(item, index) in matchHistoryItems"
      :key="item.id"
      class="global-history-card"
    >
      <button
        type="button"
        class="global-history-head"
        @click="toggleHistoryExpanded(item)"
      >
        <div class="poster-frame compact">
          <img
            v-if="posterImageSrc(item)"
            :src="posterImageSrc(item)"
            :alt="mediaLabel(item)"
            :loading="posterLoading(index)"
            :fetchpriority="posterFetchPriority(index)"
            decoding="async"
            draggable="false"
            @error="markPosterFailed(item)"
          >
          <span v-else>{{ formatMediaType(item.media_type) }}</span>
        </div>
        <div class="media-copy">
          <div class="media-type">{{ formatMediaType(item.media_type) }}</div>
          <h3>{{ mediaLabel(item) }}</h3>
          <p>{{ historyMediaStat(item) }} · {{ item.latest_at || '未知时间' }}</p>
        </div>
        <VIcon :icon="historyExpanded(item) ? 'mdi-chevron-up' : 'mdi-chevron-down'" />
      </button>
      <div v-if="historyExpanded(item)" class="global-history-targets">
        <div class="history-bulk-toolbar">
          <div class="history-bulk-copy">
            <strong>已选 {{ historySelectedCount(item) }}/{{ historyDeletableTargets(item).length }} 集</strong>
            <span>{{ item.subtitle_count }} 个外挂字幕</span>
          </div>
          <div class="history-bulk-actions">
            <VBtn
              size="small"
              variant="tonal"
              prepend-icon="mdi-checkbox-multiple-marked-outline"
              :disabled="!historyDeletableTargets(item).length || clearing"
              @click.stop="toggleHistoryItemTargets(item)"
            >
              {{ allHistoryTargetsSelected(item) ? '取消全选' : '全选' }}
            </VBtn>
            <VBtn
              size="small"
              color="error"
              variant="tonal"
              prepend-icon="mdi-delete-sweep"
              :disabled="!historySelectedCount(item) || clearing"
              :loading="clearing"
              @click.stop="clearHistorySelectedSubtitles(item)"
            >
              删除选中
            </VBtn>
            <VBtn
              size="small"
              color="warning"
              variant="tonal"
              prepend-icon="mdi-timeline-clock-outline"
              :disabled="!historySelectedTimelineTargets(item).length || timelineFixing || !timelineAvailable"
              :loading="timelineFixing"
              @click.stop="fixHistorySelectedTimeline(item)"
            >
              调轴选中
            </VBtn>
          </div>
        </div>
        <div class="history-season-tree">
          <div
            v-for="season in historySeasonGroups(item)"
            :key="historySeasonKey(item, season)"
            class="history-season-node"
          >
            <div v-if="!season.direct" class="history-season-row">
              <VCheckbox
                :model-value="allHistorySeasonTargetsSelected(item, season)"
                :indeterminate="historySeasonPartiallySelected(item, season)"
                density="compact"
                hide-details
                :disabled="!season.targets.length || clearing"
                @click.stop
                @update:model-value="value => toggleHistorySeasonTargets(item, season, value)"
              />
              <button
                type="button"
                class="history-season-toggle"
                @click.stop="toggleHistorySeasonExpanded(item, season)"
              >
                <VIcon :icon="historySeasonExpanded(item, season) ? 'mdi-chevron-down' : 'mdi-chevron-right'" />
                <strong>{{ season.label }}</strong>
                <span>{{ season.targets.length }} 集 · {{ season.subtitleCount }} 个外挂字幕</span>
                <em v-if="historySeasonSelectedCount(item, season)">已选 {{ historySeasonSelectedCount(item, season) }}</em>
              </button>
            </div>
            <div
              v-if="season.direct || historySeasonExpanded(item, season)"
              class="history-episode-list"
              :class="{ 'direct-targets': season.direct }"
            >
              <div
                v-for="target in season.targets"
                :key="`${historySeasonKey(item, season)}-${target.id}`"
                class="history-episode-node"
              >
                <div class="history-episode-row">
                  <VCheckbox
                    :model-value="historySelectedIds(item).includes(target.id)"
                    density="compact"
                    hide-details
                    :disabled="!(target.subtitles || []).length || clearing"
                    @click.stop
                    @update:model-value="value => toggleHistoryTarget(item, target.id, value)"
                  />
                  <button
                    type="button"
                    class="history-episode-toggle"
                    @click.stop="toggleHistoryTargetExpanded(target)"
                  >
                    <VIcon :icon="historyTargetExpanded(target) ? 'mdi-chevron-down' : 'mdi-chevron-right'" />
                    <span class="episode-title">{{ compactTargetName(target) }}</span>
                    <small>{{ (target.subtitles || []).length }} 个外挂字幕</small>
                  </button>
                  <VBtn
                    size="small"
                    variant="tonal"
                    prepend-icon="mdi-magnify"
                    :disabled="isTargetActionDisabled(target)"
                    @click.stop="openSingleOnlineSearch(target)"
                  >
                    重新搜索
                  </VBtn>
                </div>
                <div v-if="historyTargetExpanded(target)" class="history-subtitle-children">
                  <div class="episode-path">{{ target.relative_path }}</div>
                  <div v-if="target.timeline_task" class="history-status compact-status">
                    <span>调轴：{{ timelineTaskText(target.timeline_task) }}</span>
                    <span
                      v-for="meta in timelineMetaItems(target.timeline_task.timeline)"
                      :key="`${target.id}-${meta}`"
                      class="timeline-meta"
                    >
                      {{ meta }}
                    </span>
                  </div>
                  <div class="subtitle-history-list compact-subtitles">
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
                          :disabled="timelineFixing || !timelineAvailable || isStreamTarget(target)"
                          @click.stop="fixHistorySubtitleTimeline(target, subtitle)"
                        >
                          调轴
                        </VBtn>
                        <VBtn
                          size="small"
                          variant="tonal"
                          color="error"
                          :loading="clearing"
                          @click.stop="deleteSubtitle(target, subtitle)"
                        >
                          删除
                        </VBtn>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="!historySeasonGroups(item).length" class="empty-state compact-empty">
          暂无可管理的外挂字幕
        </div>
      </div>
    </div>
  </div>
  <div v-if="rootTab === 'history' && matchHistoryItems.length" class="pager-row">
    <span>{{ matchHistoryItems.length }}/{{ matchHistoryTotal || matchHistoryItems.length }} 部资源</span>
    <VBtn
      v-if="matchHistoryHasMore"
      variant="tonal"
      :loading="matchHistoryLoading"
      @click="$emit('load-more-match-history')"
    >
      加载下一页
    </VBtn>
  </div>
  <div v-else-if="rootTab === 'history'" class="empty-state">
    {{ matchHistoryLoading ? '正在读取匹配历史...' : '还没有找到已匹配字幕记录。' }}
  </div>
</template>

<style scoped>
.auto-queue-entry {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.global-history-list {
  display: grid;
  gap: 12px;
}

.global-history-card {
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 22px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.76);
}

.global-history-head {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  width: 100%;
  padding: 12px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
}

.poster-frame {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  background: linear-gradient(135deg, #2f463f, #6d887b);
  color: #fff8e8;
  font-weight: 900;
}

.poster-frame.compact {
  width: 54px;
  height: 74px;
  border-radius: 14px;
}

.poster-frame img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.poster-frame span {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 6px;
  text-align: center;
}

.media-copy {
  min-width: 0;
}

.media-type {
  color: #d79333;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0;
}

.media-copy h3 {
  margin: 3px 0;
  overflow: hidden;
  font-size: 17px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.media-copy p {
  margin: 0;
  color: #687873;
  font-size: 13px;
}

.global-history-targets {
  display: grid;
  gap: 10px;
  padding: 0 12px 12px;
}

.history-bulk-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border: 1px solid rgba(91, 109, 100, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.58);
}

.history-bulk-copy {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: #53655f;
  font-size: 12px;
}

.history-bulk-copy strong {
  color: #263a33;
  font-size: 13px;
}

.history-bulk-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.history-season-tree {
  display: grid;
  gap: 8px;
}

.history-season-node {
  overflow: hidden;
  border: 1px solid rgba(91, 109, 100, 0.13);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.62);
}

.history-season-row,
.history-episode-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-height: 46px;
  padding: 6px 10px;
}

.history-season-toggle,
.history-episode-toggle {
  display: flex;
  min-width: 0;
  gap: 8px;
  align-items: center;
  border: 0;
  background: transparent;
  color: #30443f;
  text-align: left;
}

.history-season-toggle strong,
.history-episode-toggle .episode-title {
  min-width: 0;
  overflow: hidden;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-season-toggle span,
.history-episode-toggle small {
  flex: 0 0 auto;
  color: #6f7f79;
  font-size: 12px;
}

.history-season-toggle em {
  flex: 0 0 auto;
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(255, 244, 218, 0.9);
  color: #8a5f23;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.history-episode-list {
  display: grid;
  gap: 6px;
  padding: 0 10px 10px 42px;
}

.history-episode-list.direct-targets {
  padding: 8px 10px 10px;
}

.history-episode-node {
  border-radius: 12px;
  background: rgba(245, 241, 232, 0.52);
}

.history-subtitle-children {
  display: grid;
  gap: 8px;
  padding: 0 10px 10px 42px;
}

.episode-path {
  overflow-wrap: anywhere;
  color: #53655f;
  font-size: 12px;
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
  background: rgba(232, 237, 240, 0.72);
  color: #53655f;
  font-size: 12px;
}

.subtitle-history-list {
  display: grid;
  grid-column: 1 / -1;
  gap: 8px;
}

.compact-subtitles {
  margin-top: 8px;
}

.subtitle-history-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(245, 241, 232, 0.68);
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
  color: #687873;
  font-size: 12px;
}

.subtitle-history-actions {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  padding: 4px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
}

.subtitle-history-actions .v-btn {
  min-width: 52px;
}

.empty-state {
  padding: 28px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.58);
  color: #687873;
  text-align: center;
}

.compact-empty {
  padding: 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.58);
}

.pager-row {
  display: flex;
  justify-content: center;
  gap: 12px;
  align-items: center;
  padding: 4px 0 8px;
  color: #687873;
  font-size: 13px;
}

@media (max-width: 720px) {
  .history-season-row,
  .history-episode-row {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .history-episode-row > .v-btn {
    grid-column: 2;
    justify-self: start;
  }

  .history-episode-list,
  .history-subtitle-children {
    padding-left: 16px;
  }

  .history-season-toggle,
  .history-episode-toggle {
    flex-wrap: wrap;
  }

  .subtitle-history-item {
    align-items: flex-start;
    flex-direction: column;
  }

  .subtitle-history-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
