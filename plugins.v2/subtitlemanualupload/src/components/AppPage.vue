<script setup>
import { computed, onMounted, ref } from 'vue'
import { mediaLabel, targetLabel, unwrapResponse } from '../provider'

const props = defineProps({
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'SubtitleManualUpload',
  },
  navKey: {
    type: String,
    default: 'main',
  },
  hideTitle: {
    type: Boolean,
    default: false,
  },
})

const pluginBase = computed(() => `plugin/${props.pluginId || 'SubtitleManualUpload'}`)
const status = ref({ enabled: false, source: 'MoviePilot MediaChain' })
const loading = ref(false)
const searching = ref(false)
const resolving = ref(false)
const refreshing = ref(false)
const preparing = ref(false)
const applying = ref(false)
const message = ref('')
const error = ref('')
const searchKeyword = ref('')
const mediaType = ref('all')
const medias = ref([])
const selectedMedia = ref(null)
const seasons = ref([])
const selectedSeason = ref(null)
const targets = ref([])
const selectedTargetIds = ref([])
const files = ref([])
const preview = ref(null)
const fileInputRef = ref(null)

const availableSeasonItems = computed(() => {
  return seasons.value
    .filter(item => item.available)
    .map(item => ({
      title: `${seasonLabel(item.season)} · 本地 ${item.local_count || 0} 集${item.episode_count ? ` / TMDB ${item.episode_count} 集` : ''}`,
      value: item.season,
    }))
})

const selectedTargets = computed(() => {
  const picked = new Set(selectedTargetIds.value || [])
  return targets.value.filter(item => picked.has(item.id))
})

const canPrepare = computed(() => selectedTargetIds.value.length > 0 && files.value.length > 0)
const canApply = computed(() => {
  const items = preview.value?.items || []
  return items.length > 0 && items.every(item => item.target_id)
})

function formatMediaType(type) {
  return type === 'tv' ? '剧集' : '电影'
}

function seasonLabel(season) {
  const value = Number(season || 0)
  return value === 0 ? '特别篇' : `第 ${value} 季`
}

function clearTargetState() {
  seasons.value = []
  selectedSeason.value = null
  targets.value = []
  selectedTargetIds.value = []
  preview.value = null
}

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    const response = await props.api.get(`${pluginBase.value}/status`)
    status.value = unwrapResponse(response) || status.value
  } catch (err) {
    error.value = err?.message || '加载插件状态失败'
  } finally {
    loading.value = false
  }
}

async function refreshIndex() {
  refreshing.value = true
  error.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/refresh_index`, {})
    message.value = response?.message || '已改用 MoviePilot 实时媒体搜索，无需刷新索引'
  } catch (err) {
    error.value = err?.message || '刷新状态失败'
  } finally {
    refreshing.value = false
  }
}

async function runSearch() {
  const keyword = searchKeyword.value.trim()
  if (!keyword) {
    error.value = '请输入电影名或剧名'
    return
  }

  searching.value = true
  error.value = ''
  message.value = ''
  selectedMedia.value = null
  clearTargetState()
  try {
    const params = new URLSearchParams()
    params.set('keyword', keyword)
    params.set('media_type', mediaType.value)
    params.set('limit', '24')
    const response = await props.api.get(`${pluginBase.value}/search?${params.toString()}`)
    const data = unwrapResponse(response) || {}
    medias.value = data.medias || []
    if (!medias.value.length) {
      message.value = '没有找到媒体候选，请换一个关键词试试'
    }
  } catch (err) {
    error.value = err?.message || '搜索媒体失败'
  } finally {
    searching.value = false
  }
}

function buildMediaParams(media, season) {
  const params = new URLSearchParams()
  params.set('media_type', media.media_type || '')
  if (media.tmdb_id) params.set('tmdb_id', String(media.tmdb_id))
  if (media.douban_id) params.set('douban_id', String(media.douban_id))
  if (media.title) params.set('title', media.title)
  if (media.year) params.set('year', media.year)
  if (season !== null && season !== undefined && season !== '') {
    params.set('season', String(season))
  }
  return params
}

async function loadTargets(media = selectedMedia.value, season = selectedSeason.value) {
  if (!media) return
  resolving.value = true
  error.value = ''
  message.value = ''
  preview.value = null
  try {
    const params = buildMediaParams(media, season)
    const response = await props.api.get(`${pluginBase.value}/targets?${params.toString()}`)
    const data = unwrapResponse(response) || {}
    selectedMedia.value = data.media || media
    seasons.value = data.seasons || []
    selectedSeason.value = data.selected_season ?? null
    targets.value = data.targets || []
    selectedTargetIds.value = targets.value.filter(item => item.writable !== false).map(item => item.id)

    if (!targets.value.length) {
      message.value = `${mediaLabel(selectedMedia.value)} 未在 MoviePilot 本地媒体库中找到可写入的视频文件`
    } else {
      message.value = `已读取 ${targets.value.length} 个本地目标文件`
    }
  } catch (err) {
    error.value = err?.message || '读取媒体库目标失败'
  } finally {
    resolving.value = false
  }
}

async function selectMedia(media) {
  selectedMedia.value = media
  clearTargetState()
  await loadTargets(media, null)
}

async function changeSeason(season) {
  selectedSeason.value = season
  await loadTargets(selectedMedia.value, season)
}

function resetSelection() {
  selectedMedia.value = null
  medias.value = []
  clearTargetState()
}

function onPickFiles(event) {
  const pickedFiles = Array.from(event?.target?.files || [])
  mergeFiles(pickedFiles)
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

function mergeFiles(inputFiles) {
  const existing = new Map(files.value.map(item => [`${item.name}-${item.size}`, item]))
  for (const file of inputFiles) {
    const key = `${file.name}-${file.size}`
    if (!existing.has(key)) {
      existing.set(key, file)
    }
  }
  files.value = Array.from(existing.values())
}

function removeFile(file) {
  files.value = files.value.filter(item => !(item.name === file.name && item.size === file.size))
}

function openFileDialog() {
  fileInputRef.value?.click()
}

function handleDrop(event) {
  event.preventDefault()
  const dropped = Array.from(event.dataTransfer?.files || [])
  mergeFiles(dropped)
}

function handleDragOver(event) {
  event.preventDefault()
}

async function prepareUpload() {
  if (!canPrepare.value) return
  preparing.value = true
  error.value = ''
  try {
    const formData = new FormData()
    formData.append('target_ids', JSON.stringify(selectedTargetIds.value))
    files.value.forEach(file => {
      formData.append('files', file)
    })
    const response = await props.api.post(`${pluginBase.value}/prepare_upload`, formData)
    preview.value = unwrapResponse(response)
    message.value = response?.message || '已生成匹配预览'
  } catch (err) {
    error.value = err?.message || '上传预解析失败'
  } finally {
    preparing.value = false
  }
}

function updatePreviewTarget(uploadId, targetId) {
  const items = preview.value?.items || []
  const target = items.find(item => item.upload_id === uploadId)
  if (target) {
    target.target_id = targetId
  }
}

async function applyUpload() {
  if (!canApply.value || !preview.value) return
  applying.value = true
  error.value = ''
  try {
    const payload = {
      session_id: preview.value.session_id,
      items: preview.value.items.map(item => ({
        upload_id: item.upload_id,
        target_id: item.target_id,
        ext: item.ext,
        language_suffix: item.language_suffix,
      })),
    }
    const response = await props.api.post(`${pluginBase.value}/apply_upload`, payload)
    const data = unwrapResponse(response) || {}
    message.value = response?.message || `已写入 ${data.count || 0} 个字幕文件`
    files.value = []
    preview.value = null
  } catch (err) {
    error.value = err?.message || '写入字幕失败'
  } finally {
    applying.value = false
  }
}

onMounted(loadStatus)

defineExpose({
  loadStatus,
  refreshIndex,
  runSearch,
  loading,
  searching,
  resolving,
  refreshing,
  preparing,
  applying,
})
</script>

<template>
  <div class="subtitle-upload-page">
    <div v-if="!hideTitle" class="hero-shell">
      <div class="hero-copy">
        <div class="hero-eyebrow">MoviePilot 媒体库字幕工具</div>
        <h1 class="hero-title">字幕手传匹配</h1>
        <p class="hero-text">
          像 CSB 一样先搜索媒体并确认封面，再读取 MoviePilot 已入库文件。剧集可按季度选择目标，然后拖入字幕或 ZIP 自动匹配写入。
        </p>
      </div>
      <div class="hero-meta">
        <div class="meta-card">
          <div class="meta-label">当前链路</div>
          <div class="meta-value">MP</div>
          <div class="meta-hint">{{ status.source || 'MoviePilot MediaChain' }}</div>
        </div>
      </div>
    </div>

    <VAlert
      v-if="error"
      class="mb-4"
      type="error"
      variant="tonal"
      :text="error"
    />
    <VAlert
      v-else-if="message"
      class="mb-4"
      type="success"
      variant="tonal"
      :text="message"
    />

    <div class="workspace-grid">
      <VCard class="panel-card" rounded="xl" elevation="0">
        <VCardTitle class="panel-title">1. 搜索并选择媒体</VCardTitle>
        <VCardText>
          <div class="toolbar-row">
            <VTextField
              v-model="searchKeyword"
              label="电影名、剧名或英文名"
              variant="outlined"
              density="comfortable"
              hide-details
              @keyup.enter="runSearch"
            />
            <VSelect
              v-model="mediaType"
              :items="[
                { title: '全部', value: 'all' },
                { title: '电影', value: 'movie' },
                { title: '剧集', value: 'tv' },
              ]"
              label="类型"
              variant="outlined"
              density="comfortable"
              hide-details
            />
          </div>
          <div class="toolbar-actions">
            <VBtn color="primary" :loading="searching" @click="runSearch">搜索媒体</VBtn>
            <VBtn variant="tonal" :loading="refreshing" @click="refreshIndex">接口状态</VBtn>
          </div>

          <div v-if="medias.length" class="media-grid">
            <button
              v-for="media in medias"
              :key="media.id"
              class="media-card"
              :class="{ active: selectedMedia?.id === media.id }"
              @click="selectMedia(media)"
            >
              <div class="poster-shell">
                <img
                  v-if="media.poster_url"
                  class="poster"
                  :src="media.poster_url"
                  :alt="mediaLabel(media)"
                >
                <div v-else class="poster-fallback">{{ formatMediaType(media.media_type) }}</div>
              </div>
              <div class="media-info">
                <div class="media-type">{{ formatMediaType(media.media_type) }}</div>
                <div class="media-title">{{ mediaLabel(media) }}</div>
                <div v-if="media.en_title" class="media-subtitle">{{ media.en_title }}</div>
                <div class="media-meta">
                  <span v-if="media.vote_average">TMDB {{ Number(media.vote_average).toFixed(1) }}</span>
                  <span v-if="media.tmdb_id">#{{ media.tmdb_id }}</span>
                </div>
              </div>
            </button>
          </div>
          <div v-else class="empty-state">
            输入关键词搜索媒体。结果会使用 MoviePilot 的媒体搜索能力，并直接展示封面。
          </div>

          <div v-if="selectedMedia" class="target-shell">
            <div class="selected-media">
              <img
                v-if="selectedMedia.poster_url"
                class="selected-poster"
                :src="selectedMedia.poster_url"
                :alt="mediaLabel(selectedMedia)"
              >
              <div class="selected-copy">
                <div class="target-title">已选：{{ mediaLabel(selectedMedia) }}</div>
                <div class="target-caption">
                  正在读取 MoviePilot 媒体库中这个条目的实际视频文件。
                </div>
              </div>
            </div>

            <VSelect
              v-if="selectedMedia.media_type === 'tv' && availableSeasonItems.length"
              class="season-select"
              :model-value="selectedSeason"
              :items="availableSeasonItems"
              label="选择季度"
              variant="outlined"
              density="comfortable"
              hide-details
              :loading="resolving"
              @update:model-value="changeSeason"
            />

            <div v-if="targets.length" class="target-list">
              <label
                v-for="target in targets"
                :key="target.id"
                class="target-item"
                :class="{ disabled: target.writable === false }"
              >
                <input
                  v-model="selectedTargetIds"
                  type="checkbox"
                  :value="target.id"
                  :disabled="target.writable === false"
                >
                <span>{{ targetLabel(target) }}</span>
              </label>
            </div>
            <div v-else class="empty-state compact">
              {{ resolving ? '正在读取媒体库目标...' : '这个媒体还没有可写入的本地视频目标。' }}
            </div>
          </div>
        </VCardText>
      </VCard>

      <VCard class="panel-card" rounded="xl" elevation="0">
        <VCardTitle class="panel-title">2. 上传并确认匹配</VCardTitle>
        <VCardText>
          <div
            class="dropzone"
            @drop="handleDrop"
            @dragover="handleDragOver"
          >
            <div class="dropzone-icon">SRT / ASS / ZIP</div>
            <div class="dropzone-title">拖拽字幕文件或 ZIP 到这里</div>
            <div class="dropzone-text">可以一次选择多个字幕。ZIP 会自动解包，只保留字幕文件参与匹配。</div>
            <VBtn color="primary" variant="flat" @click="openFileDialog">选择文件</VBtn>
            <input
              ref="fileInputRef"
              class="hidden-input"
              type="file"
              multiple
              accept=".srt,.ass,.ssa,.sbv,.sub,.vtt,.webvtt,.zip"
              @change="onPickFiles"
            >
          </div>

          <div v-if="files.length" class="file-list">
            <div v-for="file in files" :key="`${file.name}-${file.size}`" class="file-item">
              <div>
                <div class="file-name">{{ file.name }}</div>
                <div class="file-size">{{ Math.max(1, Math.round(file.size / 1024)) }} KB</div>
              </div>
              <VBtn size="small" variant="text" color="error" @click="removeFile(file)">移除</VBtn>
            </div>
          </div>

          <div class="toolbar-actions mt-4">
            <VBtn color="primary" :disabled="!canPrepare" :loading="preparing" @click="prepareUpload">
              生成匹配预览
            </VBtn>
            <VBtn variant="tonal" @click="resetSelection">重新选择媒体</VBtn>
          </div>

          <div v-if="preview?.items?.length" class="preview-shell">
            <div class="preview-header">
              <div class="target-title">3. 检查并写入</div>
              <div class="target-caption">每个字幕都需要对应一个目标视频；自动匹配不准时可以手动改。</div>
            </div>
            <div class="preview-list">
              <div
                v-for="item in preview.items"
                :key="item.upload_id"
                class="preview-item"
              >
                <div class="preview-main">
                  <div class="preview-name">{{ item.source_name }}</div>
                  <div class="preview-meta">
                    <span v-if="item.archive_name">来自 {{ item.archive_name }}</span>
                    <span>{{ item.detected_label || '未知语言' }}</span>
                    <span>{{ item.language_suffix }}</span>
                  </div>
                </div>
                <VSelect
                  :model-value="item.target_id"
                  :items="selectedTargets.map(target => ({ title: targetLabel(target), value: target.id }))"
                  label="目标视频"
                  variant="outlined"
                  density="comfortable"
                  hide-details
                  @update:model-value="value => updatePreviewTarget(item.upload_id, value)"
                />
              </div>
            </div>
            <div class="toolbar-actions mt-4">
              <VBtn color="primary" :disabled="!canApply" :loading="applying" @click="applyUpload">
                写入字幕
              </VBtn>
            </div>
          </div>
        </VCardText>
      </VCard>
    </div>
  </div>
</template>

<style scoped>
.subtitle-upload-page {
  min-height: 100%;
  padding: 24px;
  background:
    radial-gradient(circle at 95% 0%, rgba(184, 214, 255, 0.36), transparent 32%),
    linear-gradient(180deg, #f7f9fc 0%, #edf2f8 100%);
  color: #1c2635;
}

.hero-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(220px, 0.8fr);
  gap: 20px;
  margin-bottom: 20px;
}

.hero-copy,
.hero-meta,
.panel-card {
  border: 1px solid rgba(127, 151, 185, 0.18);
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(12px);
  box-shadow: 0 18px 50px rgba(30, 63, 108, 0.08);
}

.hero-copy {
  padding: 28px;
  border-radius: 28px;
}

.hero-meta {
  padding: 20px;
  border-radius: 28px;
}

.hero-eyebrow {
  margin-bottom: 8px;
  color: #587196;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.hero-title {
  margin: 0;
  font-size: 34px;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.hero-text {
  max-width: 760px;
  margin: 14px 0 0;
  color: #53637b;
  line-height: 1.7;
}

.meta-card {
  padding: 18px;
  border-radius: 22px;
  background: linear-gradient(145deg, #17375d, #315c94);
  color: #f8fbff;
}

.meta-label {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.78;
}

.meta-value {
  margin-top: 8px;
  font-size: 34px;
  font-weight: 700;
}

.meta-hint {
  margin-top: 8px;
  font-size: 13px;
  opacity: 0.82;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(380px, 0.95fr);
  gap: 20px;
}

.panel-card {
  border-radius: 28px;
}

.panel-title {
  padding: 22px 24px 8px;
  font-size: 18px;
  font-weight: 700;
}

.toolbar-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px;
  gap: 12px;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 14px;
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.media-card {
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr);
  gap: 12px;
  min-height: 118px;
  padding: 10px;
  border: 1px solid rgba(115, 146, 188, 0.2);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 250, 255, 0.92));
  text-align: left;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.media-card:hover,
.media-card.active {
  transform: translateY(-1px);
  border-color: rgba(39, 88, 153, 0.45);
  box-shadow: 0 12px 30px rgba(41, 77, 126, 0.08);
}

.poster-shell,
.poster,
.poster-fallback {
  width: 74px;
  height: 98px;
  border-radius: 12px;
}

.poster {
  display: block;
  object-fit: cover;
}

.poster-fallback {
  display: grid;
  place-items: center;
  background: #17375d;
  color: #eef6ff;
  font-size: 13px;
}

.media-info {
  min-width: 0;
}

.media-type {
  color: #5a6d88;
  font-size: 12px;
}

.media-title {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
}

.media-subtitle,
.media-meta {
  margin-top: 6px;
  color: #67788f;
  font-size: 12px;
}

.media-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.empty-state {
  padding: 22px 14px;
  margin-top: 18px;
  border-radius: 18px;
  background: #f4f7fb;
  color: #6c7f97;
  text-align: center;
}

.empty-state.compact {
  margin-top: 12px;
  padding: 16px 12px;
}

.target-shell,
.preview-shell {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid rgba(126, 151, 183, 0.18);
}

.selected-media {
  display: flex;
  gap: 14px;
  align-items: center;
}

.selected-poster {
  width: 54px;
  height: 76px;
  border-radius: 12px;
  object-fit: cover;
}

.selected-copy {
  min-width: 0;
}

.season-select {
  margin-top: 14px;
}

.target-title {
  font-size: 16px;
  font-weight: 700;
}

.target-caption {
  margin-top: 4px;
  color: #697b92;
  font-size: 13px;
}

.target-list {
  display: grid;
  gap: 8px;
  max-height: 360px;
  margin-top: 14px;
  overflow: auto;
}

.target-item {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f4f8fc;
  color: #34485f;
}

.target-item.disabled {
  opacity: 0.58;
}

.dropzone {
  position: relative;
  overflow: hidden;
  padding: 26px 20px;
  border: 1px dashed rgba(55, 100, 165, 0.36);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(250, 252, 255, 0.95), rgba(239, 245, 252, 0.95));
  text-align: center;
}

.dropzone::before {
  position: absolute;
  right: -20px;
  bottom: -40px;
  width: 150px;
  height: 150px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(131, 176, 255, 0.28), transparent 70%);
  content: '';
}

.dropzone-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 132px;
  padding: 8px 14px;
  border-radius: 999px;
  background: #17375d;
  color: #eef6ff;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.dropzone-title {
  margin-top: 16px;
  font-size: 20px;
  font-weight: 700;
}

.dropzone-text {
  max-width: 520px;
  margin: 10px auto 18px;
  color: #647790;
  line-height: 1.65;
}

.hidden-input {
  display: none;
}

.file-list,
.preview-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.file-item,
.preview-item {
  display: grid;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid rgba(124, 152, 186, 0.18);
  border-radius: 18px;
  background: rgba(249, 251, 255, 0.92);
}

.file-item {
  grid-template-columns: minmax(0, 1fr) auto;
}

.preview-item {
  grid-template-columns: minmax(0, 1fr) minmax(220px, 320px);
}

.file-name,
.preview-name {
  font-weight: 600;
  word-break: break-all;
}

.file-size,
.preview-meta {
  margin-top: 4px;
  color: #667890;
  font-size: 12px;
}

.preview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.mt-4 {
  margin-top: 16px;
}

.mb-4 {
  margin-bottom: 16px;
}

@media (max-width: 1120px) {
  .hero-shell,
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .subtitle-upload-page {
    padding: 16px;
  }

  .hero-copy,
  .hero-meta {
    padding: 20px;
    border-radius: 22px;
  }

  .hero-title {
    font-size: 28px;
  }

  .toolbar-row,
  .preview-item {
    grid-template-columns: 1fr;
  }

  .media-card {
    grid-template-columns: 64px minmax(0, 1fr);
  }

  .poster-shell,
  .poster,
  .poster-fallback {
    width: 64px;
    height: 88px;
  }

  .panel-card {
    border-radius: 22px;
  }
}
</style>
