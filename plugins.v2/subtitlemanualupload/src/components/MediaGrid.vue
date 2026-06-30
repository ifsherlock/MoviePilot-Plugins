<script setup>
defineProps({
  rootTab: { type: String, required: true },
  medias: { type: Array, default: () => [] },
  mediaTotal: { type: Number, default: 0 },
  mediaHasMore: { type: Boolean, default: false },
  searching: { type: Boolean, default: false },
  formatMediaType: { type: Function, required: true },
  mediaLabel: { type: Function, required: true },
  mediaStat: { type: Function, required: true },
  posterImageSrc: { type: Function, required: true },
  posterLoading: { type: Function, required: true },
  posterFetchPriority: { type: Function, required: true },
})

defineEmits([
  'select-media',
  'mark-poster-failed',
  'load-more',
])
</script>

<template>
  <div v-if="rootTab === 'match' && medias.length" class="media-list">
    <button
      v-for="(media, index) in medias"
      :key="media.id"
      class="media-card"
      @click="$emit('select-media', media)"
    >
      <div class="poster-frame">
        <img
          v-if="posterImageSrc(media)"
          :src="posterImageSrc(media)"
          :alt="mediaLabel(media)"
          :loading="posterLoading(index)"
          :fetchpriority="posterFetchPriority(index)"
          decoding="async"
          draggable="false"
          @error="$emit('mark-poster-failed', media)"
        >
        <span v-else>{{ formatMediaType(media.media_type) }}</span>
      </div>
      <div class="media-copy">
        <div class="media-type">{{ formatMediaType(media.media_type) }}</div>
        <h3>{{ mediaLabel(media) }}</h3>
        <p>{{ mediaStat(media) }}</p>
      </div>
      <VIcon icon="mdi-chevron-right" />
    </button>
  </div>
  <div v-if="rootTab === 'match' && medias.length" class="pager-row">
    <span>{{ medias.length }}/{{ mediaTotal || medias.length }} 个资源</span>
    <VBtn
      v-if="mediaHasMore"
      variant="tonal"
      :loading="searching"
      @click="$emit('load-more')"
    >
      加载下一页
    </VBtn>
  </div>
  <div v-else-if="rootTab === 'match'" class="empty-state">
    {{ searching ? '正在读取本地资源...' : '输入关键词搜索；留空搜索会显示最近整理的视频。' }}
  </div>
</template>

<style scoped>
.media-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.media-card {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  width: 100%;
  min-height: 112px;
  padding: 12px;
  border: 1px solid rgba(83, 103, 94, 0.16);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.76);
  color: inherit;
  text-align: left;
  content-visibility: auto;
  contain-intrinsic-size: 112px;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.media-card:hover {
  transform: translateY(-2px);
  border-color: rgba(159, 107, 45, 0.45);
  background: #fff8ea;
}

.poster-frame {
  display: grid;
  width: 72px;
  height: 96px;
  place-items: center;
  overflow: hidden;
  border-radius: 16px;
  background: #30463f;
  color: #fffaf0;
}

.poster-frame img {
  display: block;
  width: 100%;
  height: 100%;
  background: #30463f;
  object-fit: cover;
}

.media-copy {
  min-width: 0;
}

.media-copy h3 {
  margin: 4px 0 6px;
  font-size: 17px;
  word-break: break-word;
}

.media-copy p {
  margin: 0;
  color: #687873;
  font-size: 13px;
}

.media-type {
  color: #8a6b3f;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
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

.empty-state {
  padding: 28px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.58);
  color: #687873;
  text-align: center;
}
</style>
