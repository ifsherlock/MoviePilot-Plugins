<script setup>
import { ref } from 'vue'
import MobileTargetCard from './MobileTargetCard.vue'

defineProps({
  detail: { type: Object, required: true },
  actions: { type: Object, required: true },
})

const bulkActionsOpen = ref(false)
</script>

<template>
  <section class="mobile-detail">
    <header class="mobile-detail-header">
      <VBtn
        icon="mdi-arrow-left"
        variant="text"
        title="返回资源列表"
        @click="actions.resetSelection()"
      />
      <span>海拉鲁字幕大师</span>
      <VBtn
        icon="mdi-refresh"
        variant="text"
        :loading="detail.resolving"
        title="刷新视频目标"
        @click="actions.loadTargets(detail.selectedMedia, detail.selectedSeason)"
      />
    </header>

    <section class="mobile-selected-media">
      <div class="mobile-detail-poster">
        <img
          v-if="detail.posterImageSrc(detail.selectedMedia)"
          :src="detail.posterImageSrc(detail.selectedMedia)"
          :alt="detail.mediaLabel(detail.selectedMedia)"
          @error="actions.markPosterFailed(detail.selectedMedia)"
        >
        <span v-else>{{ detail.formatMediaType(detail.selectedMedia.media_type) }}</span>
      </div>
      <div>
        <div class="mobile-media-kind">{{ detail.formatMediaType(detail.selectedMedia.media_type) }}</div>
        <h1>{{ detail.mediaLabel(detail.selectedMedia) }}</h1>
        <p>{{ detail.selectedTargets.length ? `已选择 ${detail.selectedTargets.length} / ${detail.visibleTargets.length}` : `${detail.visibleTargets.length} 个视频目标` }}</p>
      </div>
    </section>

    <div v-if="detail.seasonCards.length" class="mobile-season-strip" aria-label="选择季">
      <button
        v-for="season in detail.seasonCards"
        :key="season.value"
        type="button"
        :class="{ active: detail.selectedSeason === season.value }"
        @click="actions.changeSeason(season.value)"
      >
        <span>{{ season.title }}</span>
        <strong>{{ season.count }}</strong>
      </button>
    </div>

    <section class="mobile-target-actions" aria-label="批量操作">
      <VBtn
        variant="tonal"
        :disabled="!detail.visibleTargets.length"
        @click="actions.toggleSelectAll()"
      >
        {{ detail.allVisibleSelected ? '取消全选' : '全选' }}
      </VBtn>
      <VBtn
        color="primary"
        :disabled="!detail.batchUploadTargets.length"
        :loading="detail.onlineSearching"
        prepend-icon="mdi-cloud-search-outline"
        @click="actions.openBatchOnlineSearch()"
      >
        搜索
      </VBtn>
      <VBtn
        color="primary"
        variant="tonal"
        :disabled="!detail.unlockedVisibleTargets.length"
        @click="actions.openBatchUpload()"
      >
        <VIcon start icon="mdi-upload-file" />
        上传
      </VBtn>
      <VBtn
        icon="mdi-dots-horizontal"
        variant="tonal"
        title="更多批量操作"
        @click="bulkActionsOpen = true"
      />
    </section>

    <section class="mobile-target-list" aria-label="视频目标">
      <div class="mobile-target-list-head">
        <h2>视频目标</h2>
        <span>{{ detail.visibleTargets.length }}</span>
      </div>

      <div v-if="detail.resolving && !detail.visibleTargets.length" class="mobile-detail-empty">
        <VProgressCircular indeterminate size="22" width="2" />
        正在读取本地视频目标
      </div>
      <div v-else-if="!detail.visibleTargets.length" class="mobile-detail-empty">
        当前资源没有本地可写入的视频文件。
      </div>
      <template v-else>
        <MobileTargetCard
          v-for="target in detail.visibleTargets"
          :key="target.id"
          :target="target"
          :detail="detail"
          :actions="actions"
        />
      </template>
    </section>

    <section v-if="detail.lastWritten.length" class="mobile-written-results">
      <div class="mobile-target-list-head">
        <h2>写入结果</h2>
      </div>
      <div v-for="item in detail.lastWritten" :key="item.output_path" class="mobile-written-row">
        <strong>{{ item.output_name }}</strong>
        <span>{{ item.target_label }}</span>
        <small>{{ detail.timelineResultText(item) }}</small>
      </div>
    </section>

    <VBottomSheet v-model="bulkActionsOpen" inset>
      <VCard class="mobile-bulk-sheet" rounded="t-xl">
        <VCardTitle>更多批量操作</VCardTitle>
        <VCardText class="mobile-bulk-actions">
          <VBtn
            v-if="detail.aiEnabled"
            block
            color="warning"
            variant="tonal"
            :disabled="!detail.aiCapableBatchTargets.length || !detail.aiAvailable"
            :loading="detail.aiSubmitting"
            @click="actions.openBatchAiGenerate(); bulkActionsOpen = false"
          >
            {{ detail.aiBatchLabel }}
          </VBtn>
          <VBtn
            v-if="detail.aiEnabled && detail.aiBatchCancelTargets.length"
            block
            color="error"
            variant="tonal"
            :loading="detail.aiCancelling"
            @click="actions.cancelBatchAiGenerate(); bulkActionsOpen = false"
          >
            取消 AI 任务
          </VBtn>
          <VBtn
            block
            color="error"
            variant="tonal"
            :disabled="!detail.selectedTargetIds.length"
            :loading="detail.clearing"
            @click="actions.clearSelectedSubtitles(); bulkActionsOpen = false"
          >
            清空选中外挂字幕
          </VBtn>
          <VBtn
            block
            color="warning"
            variant="tonal"
            :disabled="!detail.selectedTimelineTargets.length || detail.timelineFixing || !detail.timelineAvailable"
            :loading="detail.timelineFixing"
            @click="actions.fixSelectedDetailTimeline(); bulkActionsOpen = false"
          >
            批量调轴
          </VBtn>
          <VBtn
            block
            color="secondary"
            variant="tonal"
            :disabled="!detail.selectedRestorableTargets.length || detail.clearing"
            :loading="detail.clearing"
            @click="actions.restoreSelectedBackups(); bulkActionsOpen = false"
          >
            恢复调轴前备份
          </VBtn>
        </VCardText>
      </VCard>
    </VBottomSheet>
  </section>
</template>

<style scoped>
.mobile-detail,
.mobile-target-list,
.mobile-written-results {
  display: grid;
  gap: var(--smu-mobile-gap);
}

.mobile-detail-header,
.mobile-selected-media,
.mobile-target-actions,
.mobile-target-list-head,
.mobile-written-row {
  display: flex;
  align-items: center;
}

.mobile-detail-header {
  justify-content: space-between;
  min-height: 42px;
}

.mobile-detail-header > span {
  font-size: 16px;
  font-weight: 700;
}

.mobile-selected-media {
  gap: 12px;
  min-width: 0;
}

.mobile-detail-poster {
  display: grid;
  flex: 0 0 58px;
  width: 58px;
  height: 78px;
  overflow: hidden;
  place-items: center;
  border-radius: 10px;
  background: var(--smu-poster-bg);
  color: var(--smu-accent);
  font-size: 11px;
}

.mobile-detail-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mobile-selected-media h1 {
  margin: 3px 0 0;
  font-size: 18px;
  line-height: 1.28;
}

.mobile-selected-media p,
.mobile-media-kind {
  margin: 3px 0 0;
  color: var(--smu-text-muted);
  font-size: 12px;
}

.mobile-media-kind {
  color: var(--smu-accent);
  font-weight: 700;
}

.mobile-season-strip {
  display: flex;
  gap: 8px;
  padding-bottom: 2px;
  overflow-x: auto;
  scrollbar-width: none;
}

.mobile-season-strip::-webkit-scrollbar {
  display: none;
}

.mobile-season-strip button {
  display: inline-flex;
  flex: 0 0 auto;
  gap: 6px;
  align-items: center;
  min-height: 34px;
  padding: 7px 11px;
  border: 1px solid var(--smu-border);
  border-radius: 999px;
  background: var(--smu-card-bg);
  color: var(--smu-text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.mobile-season-strip button.active {
  border-color: var(--smu-border-active);
  background: var(--smu-card-bg-active);
  color: var(--smu-accent);
}

.mobile-season-strip strong {
  color: inherit;
}

.mobile-target-actions {
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.mobile-target-actions :deep(.v-btn) {
  flex: 0 0 auto;
}

.mobile-target-list-head {
  justify-content: space-between;
}

.mobile-target-list-head h2 {
  margin: 0;
  font-size: 16px;
}

.mobile-target-list-head > span {
  color: var(--smu-text-muted);
  font-size: 12px;
}

.mobile-detail-empty,
.mobile-written-row {
  border: 1px solid var(--smu-border);
  border-radius: var(--smu-mobile-radius);
  background: var(--smu-card-bg-strong);
}

.mobile-detail-empty {
  display: flex;
  justify-content: center;
  gap: 10px;
  min-height: 120px;
  align-items: center;
  padding: 16px;
  color: var(--smu-text-muted);
  text-align: center;
}

.mobile-written-row {
  display: grid;
  gap: 3px;
  padding: 11px 12px;
}

.mobile-written-row span,
.mobile-written-row small {
  color: var(--smu-text-muted);
  font-size: 12px;
}

.mobile-bulk-sheet {
  padding-bottom: max(12px, env(safe-area-inset-bottom));
}

.mobile-bulk-actions {
  display: grid;
  gap: 8px;
}
</style>
