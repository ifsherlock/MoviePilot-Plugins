<script setup>
import { computed } from 'vue'

const props = defineProps({
  rootTab: { type: String, required: true },
  matchHistorySummary: { type: String, required: true },
  indexSummary: { type: String, required: true },
  autoQueueVisible: { type: Boolean, default: false },
  autoQueueSummaryText: { type: String, default: '' },
  refreshing: { type: Boolean, default: false },
  matchHistoryLoading: { type: Boolean, default: false },
  searching: { type: Boolean, default: false },
  searchKeyword: { type: String, default: '' },
  mediaType: { type: String, default: 'all' },
})

const emit = defineEmits([
  'update:searchKeyword',
  'update:mediaType',
  'open-auto-queue',
  'refresh-index',
  'submit',
])

const searchKeywordModel = computed({
  get: () => props.searchKeyword,
  set: value => emit('update:searchKeyword', value || ''),
})
const mediaTypeModel = computed({
  get: () => props.mediaType,
  set: value => emit('update:mediaType', value || 'all'),
})

const mediaTypeItems = [
  { title: '全部', value: 'all' },
  { title: '电影', value: 'movie' },
  { title: '剧集', value: 'tv' },
]
</script>

<template>
  <VCard class="glass-card search-card" rounded="xl" elevation="0">
    <VCardText>
      <div class="search-head">
        <div>
          <div class="section-kicker">{{ rootTab === 'history' ? '历史记录' : '资源选择' }}</div>
          <h2 v-if="rootTab === 'history'">查看已匹配字幕</h2>
          <p>{{ rootTab === 'history' ? matchHistorySummary : `仅展示 MoviePilot 已整理到本地库的视频资源。${indexSummary}` }}</p>
        </div>
        <div class="search-head-actions">
          <VBtn
            v-if="autoQueueVisible"
            variant="text"
            prepend-icon="mdi-tray-full"
            @click="$emit('open-auto-queue')"
          >
            自动入库队列 · {{ autoQueueSummaryText }}
          </VBtn>
          <VBtn
            variant="tonal"
            color="primary"
            prepend-icon="mdi-refresh"
            :loading="refreshing"
            @click="$emit('refresh-index')"
          >
            刷新媒体库清单
          </VBtn>
        </div>
      </div>
      <div class="search-bar">
        <VTextField
          v-model="searchKeywordModel"
          label="片名、剧名或文件关键词"
          variant="outlined"
          density="comfortable"
          hide-details
          clearable
          @keyup.enter="$emit('submit')"
        />
        <VSelect
          v-model="mediaTypeModel"
          :items="mediaTypeItems"
          label="类型"
          variant="outlined"
          density="comfortable"
          hide-details
        />
        <VBtn
          color="primary"
          :loading="rootTab === 'history' ? matchHistoryLoading : searching"
          @click="$emit('submit')"
        >
          搜索
        </VBtn>
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

.search-card {
  border-radius: 28px;
}

.search-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.search-head h2 {
  margin: 0;
  letter-spacing: -0.04em;
}

.search-head p {
  margin: 8px 0 0;
  color: var(--smu-text-muted);
  line-height: 1.7;
}

.search-head-actions {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}

.section-kicker {
  color: var(--smu-accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.search-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px auto;
  gap: 12px;
  align-items: center;
}

@media (max-width: 900px) {
  .search-bar {
    grid-template-columns: 1fr;
  }

  .search-head {
    display: grid;
  }

  .search-head-actions {
    justify-content: flex-start;
  }
}
</style>
