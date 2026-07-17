<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  home: { type: Object, required: true },
  actions: { type: Object, required: true },
})

const filterOpen = ref(false)

const mediaTypeItems = [
  { title: '全部资源', value: 'all' },
  { title: '电影', value: 'movie' },
  { title: '剧集', value: 'tv' },
]

const mediaTypeTitle = computed(() => (
  mediaTypeItems.find(item => item.value === props.home.mediaType)?.title || '全部资源'
))

const status = computed(() => props.home.status || {})
const index = computed(() => status.value.index || {})
const archive = computed(() => status.value.archive_support || {})
const timeline = computed(() => status.value.timeline_fixer || {})
const ai = computed(() => status.value.ai_subtitle || {})

function chooseMediaType(value) {
  props.actions.setMediaType(value)
  filterOpen.value = false
  props.actions.submitSearch()
}
</script>

<template>
  <section class="mobile-home">
    <section class="mobile-overview" aria-label="运行概览">
      <div class="mobile-overview-head">
        <div>
          <div class="mobile-overview-label">海拉鲁字幕大师</div>
          <strong>{{ status.enabled ? '运行中' : '未启用' }}</strong>
        </div>
        <span class="mobile-status-dot" :class="{ active: status.enabled }" />
      </div>

      <div class="mobile-overview-stats">
        <span><strong>{{ index.media_count || 0 }}</strong> 媒体</span>
        <span><strong>{{ index.entry_count || 0 }}</strong> 视频</span>
        <span v-if="index.refreshing">索引刷新中</span>
        <span v-else>{{ home.indexSummary }}</span>
      </div>

      <div class="mobile-capabilities" aria-label="功能状态">
        <span :class="{ ready: archive.rar }"><VIcon :icon="archive.rar ? 'mdi-check' : 'mdi-close'" />RAR</span>
        <span :class="{ ready: timeline.available }"><VIcon :icon="timeline.available ? 'mdi-check' : 'mdi-close'" />调轴</span>
        <span :class="{ ready: ai.available }"><VIcon :icon="ai.available ? 'mdi-check' : 'mdi-close'" />AI</span>
      </div>
    </section>

    <div class="mobile-quick-actions">
      <button type="button" @click="actions.setRootTab('history')">
        <span class="mobile-action-icon"><VIcon icon="mdi-history" /></span>
        <span>匹配历史</span>
        <VIcon icon="mdi-chevron-right" />
      </button>
      <button type="button" @click="actions.openAutoQueue()">
        <span class="mobile-action-icon"><VIcon icon="mdi-tray-full" /></span>
        <span>自动入库队列</span>
        <VIcon icon="mdi-chevron-right" />
      </button>
    </div>

    <section class="mobile-media-section" aria-label="搜索资源">
      <header class="mobile-section-heading">
        <div>
          <h2>搜索资源</h2>
          <p>{{ home.searchKeyword ? `“${home.searchKeyword}” · ${mediaTypeTitle}` : `本地媒体库 · ${mediaTypeTitle}` }}</p>
        </div>
        <span v-if="home.medias.length">{{ home.medias.length }}/{{ home.mediaTotal || home.medias.length }}</span>
      </header>

      <div v-if="home.searching && !home.medias.length" class="mobile-loading-state">
        <VProgressCircular indeterminate size="22" width="2" />
        正在搜索本地资源
      </div>

      <div v-else-if="!home.medias.length" class="mobile-empty-state">
        暂无资源，刷新索引或输入片名后重试。
      </div>

      <div v-else class="mobile-media-list">
        <button
          v-for="(media, index) in home.medias"
          :key="media.id"
          type="button"
          class="mobile-media-row"
          @click="actions.selectMedia(media)"
        >
          <div class="mobile-poster">
            <img
              v-if="home.posterImageSrc(media)"
              :src="home.posterImageSrc(media)"
              :alt="home.mediaLabel(media)"
              :loading="home.posterLoading(index)"
              :fetchpriority="home.posterFetchPriority(index)"
              decoding="async"
              @error="actions.markPosterFailed(media)"
            >
            <span v-else>{{ home.formatMediaType(media.media_type) }}</span>
            <em>{{ home.formatMediaType(media.media_type) }}</em>
          </div>
          <span class="mobile-media-copy">
            <strong>{{ home.mediaLabel(media) }}</strong>
            <small>{{ media.year || '未知年份' }}</small>
            <i>{{ home.mediaStat(media) }}</i>
          </span>
          <VIcon icon="mdi-chevron-right" />
        </button>
      </div>

      <VBtn
        v-if="home.mediaHasMore"
        class="mobile-load-more"
        block
        variant="tonal"
        :loading="home.searching"
        @click="actions.loadMoreMedia()"
      >
        加载更多资源
      </VBtn>
    </section>

    <form class="mobile-search-dock" @submit.prevent="actions.submitSearch()">
      <VBtn
        icon="mdi-filter-variant"
        variant="text"
        :title="`筛选：${mediaTypeTitle}`"
        @click="filterOpen = true"
      />
      <VTextField
        :model-value="home.searchKeyword"
        density="compact"
        variant="plain"
        hide-details
        clearable
        placeholder="片名、剧名或文件名"
        @update:model-value="actions.setSearchKeyword($event)"
      />
      <VBtn
        icon="mdi-refresh"
        variant="text"
        :loading="home.refreshing"
        title="刷新媒体库索引"
        @click="actions.refreshIndex()"
      />
      <VBtn
        color="primary"
        icon="mdi-magnify"
        :loading="home.searching"
        title="搜索"
        type="submit"
      />
    </form>

    <VBottomSheet v-model="filterOpen" inset>
      <VCard class="mobile-filter-sheet" rounded="t-xl">
        <VCardTitle>资源筛选</VCardTitle>
        <VCardText class="mobile-filter-options">
          <VBtn
            v-for="item in mediaTypeItems"
            :key="item.value"
            :color="home.mediaType === item.value ? 'primary' : undefined"
            :variant="home.mediaType === item.value ? 'flat' : 'tonal'"
            block
            @click="chooseMediaType(item.value)"
          >
            {{ item.title }}
          </VBtn>
        </VCardText>
      </VCard>
    </VBottomSheet>
  </section>
</template>

<style scoped>
.mobile-home {
  display: grid;
  gap: var(--smu-mobile-gap);
}

.mobile-overview,
.mobile-quick-actions button,
.mobile-media-row,
.mobile-empty-state,
.mobile-loading-state {
  border: 1px solid var(--smu-border);
  border-radius: var(--smu-mobile-radius);
  background: var(--smu-card-bg-strong);
}

.mobile-overview {
  display: grid;
  gap: 12px;
  padding: 14px;
}

.mobile-overview-head,
.mobile-overview-stats,
.mobile-capabilities,
.mobile-section-heading,
.mobile-media-row,
.mobile-search-dock {
  display: flex;
  align-items: center;
}

.mobile-overview-head,
.mobile-section-heading {
  justify-content: space-between;
  gap: 12px;
}

.mobile-overview-label,
.mobile-section-heading p,
.mobile-media-copy small,
.mobile-media-copy i {
  color: var(--smu-text-muted);
  font-size: 12px;
}

.mobile-overview-head strong {
  font-size: 19px;
}

.mobile-status-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: rgba(var(--v-theme-on-surface), 0.28);
}

.mobile-status-dot.active {
  background: rgb(var(--v-theme-primary));
  box-shadow: 0 0 0 5px rgba(var(--v-theme-primary), 0.12);
}

.mobile-overview-stats {
  flex-wrap: wrap;
  gap: 8px;
  color: var(--smu-text-muted);
  font-size: 12px;
}

.mobile-overview-stats span:not(:last-child)::after {
  margin-left: 8px;
  color: var(--smu-border-strong);
  content: '·';
}

.mobile-overview-stats strong {
  color: var(--smu-text);
}

.mobile-capabilities {
  justify-content: space-between;
  padding-top: 10px;
  border-top: 1px solid var(--smu-border);
}

.mobile-capabilities span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--smu-text-soft);
  font-size: 12px;
}

.mobile-capabilities .ready {
  color: var(--smu-text);
}

.mobile-capabilities :deep(.v-icon) {
  color: var(--smu-text-soft);
  font-size: 15px;
}

.mobile-capabilities .ready :deep(.v-icon) {
  color: var(--smu-accent);
}

.mobile-quick-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.mobile-quick-actions button {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-height: 62px;
  padding: 10px;
  color: var(--smu-text);
  text-align: left;
}

.mobile-quick-actions button > span:not(.mobile-action-icon) {
  overflow: hidden;
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-action-icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 9px;
  background: var(--smu-accent-soft);
  color: var(--smu-accent);
}

.mobile-media-section {
  display: grid;
  gap: 8px;
}

.mobile-section-heading h2 {
  margin: 0;
  font-size: 16px;
}

.mobile-section-heading p {
  margin: 3px 0 0;
}

.mobile-section-heading > span {
  color: var(--smu-text-muted);
  font-size: 12px;
}

.mobile-media-list {
  display: grid;
  gap: 8px;
}

.mobile-media-row {
  width: 100%;
  gap: 12px;
  padding: 10px;
  color: var(--smu-text);
  text-align: left;
}

.mobile-poster {
  position: relative;
  flex: 0 0 72px;
  width: 72px;
  height: 102px;
  overflow: hidden;
  border-radius: 10px;
  background: var(--smu-poster-bg);
}

.mobile-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mobile-poster > span {
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
  color: var(--smu-accent);
  font-size: 11px;
}

.mobile-poster em {
  position: absolute;
  bottom: 5px;
  left: 5px;
  padding: 2px 5px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.64);
  color: #fff;
  font-size: 10px;
  font-style: normal;
}

.mobile-media-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 4px;
}

.mobile-media-copy strong {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  font-size: 15px;
  line-height: 1.3;
}

.mobile-media-copy i {
  width: max-content;
  max-width: 100%;
  overflow: hidden;
  padding: 3px 6px;
  border-radius: 6px;
  background: var(--smu-card-bg-soft);
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-media-row > :deep(.v-icon) {
  color: var(--smu-text-soft);
}

.mobile-empty-state,
.mobile-loading-state {
  display: flex;
  justify-content: center;
  gap: 10px;
  min-height: 132px;
  align-items: center;
  padding: 16px;
  color: var(--smu-text-muted);
  text-align: center;
}

.mobile-load-more {
  margin-top: 4px;
}

.mobile-search-dock {
  position: fixed;
  z-index: 8;
  right: max(var(--smu-mobile-edge), env(safe-area-inset-right));
  bottom: max(16px, env(safe-area-inset-bottom));
  left: max(var(--smu-mobile-edge), env(safe-area-inset-left));
  gap: 4px;
  min-height: 52px;
  padding: 4px 5px 4px 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 999px;
  background: rgba(var(--v-theme-surface), 0.88);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(28px);
}

.mobile-search-dock :deep(.v-field) {
  min-height: 40px;
}

.mobile-search-dock :deep(.v-field__input) {
  min-width: 0;
  padding-top: 0;
}

.mobile-filter-sheet {
  padding-bottom: max(12px, env(safe-area-inset-bottom));
}

.mobile-filter-options {
  display: grid;
  gap: 8px;
}

@supports not (backdrop-filter: blur(1px)) {
  .mobile-search-dock {
    background: rgb(var(--v-theme-surface));
  }
}
</style>
