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
const status = ref({ enabled: false, source: 'MoviePilot 本地整理记录', timeline_fixer: { available: false, modules: {} } })
const loading = ref(false)
const searching = ref(false)
const resolving = ref(false)
const refreshing = ref(false)
const preparing = ref(false)
const applying = ref(false)
const dragging = ref(false)
const message = ref('')
const error = ref('')
const searchKeyword = ref('')
const mediaType = ref('all')
const medias = ref([])
const selectedMedia = ref(null)
const seasons = ref([])
const selectedSeason = ref('all')
const targets = ref([])
const selectedTargetIds = ref([])
const files = ref([])
const preview = ref(null)
const fileInputRef = ref(null)
const fixTimeline = ref(false)
const lastWritten = ref([])

const selectedTargets = computed(() => {
  const picked = new Set(selectedTargetIds.value || [])
  return targets.value.filter(item => picked.has(item.id))
})

const seasonItems = computed(() => {
  if (selectedMedia.value?.media_type !== 'tv') return []
  const total = seasons.value.reduce((sum, item) => sum + Number(item.local_count || 0), 0)
  return [
    { title: `全部季度 · 本地 ${total} 集`, value: 'all', count: total },
    ...seasons.value
      .filter(item => item.available)
      .map(item => ({
        title: `${seasonLabel(item.season)} · 本地 ${item.local_count || 0} 集`,
        value: item.season,
        count: item.local_count || 0,
      })),
  ]
})

const targetSelectItems = computed(() => {
  return selectedTargets.value.map(target => ({
    title: targetLabel(target),
    value: target.id,
  }))
})

const canPrepare = computed(() => selectedTargets.value.length > 0 && files.value.length > 0)
const canApply = computed(() => {
  const items = preview.value?.items || []
  return items.length > 0 && items.every(item => item.target_id)
})
const timelineStatus = computed(() => status.value?.timeline_fixer || { available: false, modules: {} })
const timelineAvailable = computed(() => timelineStatus.value.available === true)
const timelineMissing = computed(() => {
  const missing = []
  if (timelineStatus.value.ffmpeg === false) missing.push('ffmpeg')
  if (timelineStatus.value.ffprobe === false) missing.push('ffprobe')
  const modules = timelineStatus.value.modules || {}
  Object.entries(modules).forEach(([name, ok]) => {
    if (!ok) missing.push(name)
  })
  return missing.join('、')
})

function formatMediaType(type) {
  return type === 'tv' ? '剧集' : '电影'
}

function seasonLabel(season) {
  const value = Number(season || 0)
  return value === 0 ? '特别篇' : `第 ${value} 季`
}

function compactTargetName(target) {
  if (!target) return ''
  if (target.media_type !== 'tv') return target.basename || targetLabel(target)
  const season = Number(target.season || 0)
  const episode = Number(target.episode || 0)
  if (season && episode) return `S${String(season).padStart(2, '0')}E${String(episode).padStart(2, '0')} · ${target.basename}`
  return target.basename || targetLabel(target)
}

function mediaStat(media) {
  const count = Number(media?.local_count || 0)
  if (media?.media_type === 'tv') {
    const seasonCount = Number(media?.season_count || 0)
    return `${seasonCount || '-'} 季 · ${count} 集本地视频`
  }
  return `${count || 1} 个本地视频`
}

function formatOffset(value) {
  const number = Number(value || 0)
  return `${number >= 0 ? '+' : ''}${number.toFixed(3)}s`
}

function timelineResultText(item) {
  const timeline = item?.timeline || {}
  if (!timeline.enabled) return '未启用智能调轴'
  const base = timeline.base === 'audio' ? '音频基准' : '内置字幕基准'
  if (timeline.applied) {
    return `已调轴 ${formatOffset(timeline.offset_seconds)} · ${base} · 倍率 ${Number(timeline.scale_factor || 1).toFixed(4)}`
  }
  return `未调整：偏移 ${formatOffset(timeline.offset_seconds)} 小于阈值 · ${base}`
}

function errorMessage(err, fallback) {
  return err?.response?.data?.detail
    || err?.response?.data?.message
    || err?.data?.detail
    || err?.data?.message
    || err?.message
    || fallback
}

function buildOutputName(target, item) {
  if (!target) return ''
  const basename = target.basename || 'subtitle'
  const suffix = item?.language_suffix || 'und'
  let ext = item?.ext || '.srt'
  if (!ext.startsWith('.')) ext = `.${ext}`
  return `${basename}.${suffix}${ext.toLowerCase()}`
}

function clearTargetState() {
  seasons.value = []
  selectedSeason.value = 'all'
  targets.value = []
  selectedTargetIds.value = []
  preview.value = null
  lastWritten.value = []
}

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    const response = await props.api.get(`${pluginBase.value}/status`)
    status.value = unwrapResponse(response) || status.value
  } catch (err) {
    error.value = errorMessage(err, '加载插件状态失败')
  } finally {
    loading.value = false
  }
}

async function refreshIndex() {
  refreshing.value = true
  error.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/refresh_index`, {})
    message.value = response?.message || '已改用 MoviePilot 本地整理记录实时读取，无需刷新索引'
  } catch (err) {
    error.value = errorMessage(err, '刷新状态失败')
  } finally {
    refreshing.value = false
  }
}

async function runSearch() {
  const keyword = searchKeyword.value.trim()
  searching.value = true
  error.value = ''
  message.value = ''
  selectedMedia.value = null
  clearTargetState()
  try {
    const params = new URLSearchParams()
    params.set('keyword', keyword)
    params.set('media_type', mediaType.value)
    params.set('limit', '36')
    const response = await props.api.get(`${pluginBase.value}/search?${params.toString()}`)
    const data = unwrapResponse(response) || {}
    medias.value = data.medias || []
    if (!medias.value.length) {
      message.value = keyword
        ? '本地资源库里没有匹配的视频目标，请换个关键词试试'
        : '本地整理记录里暂时没有可用的视频目标'
    }
  } catch (err) {
    error.value = errorMessage(err, '搜索本地资源失败')
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
  lastWritten.value = []
  try {
    const params = buildMediaParams(media, season || 'all')
    const response = await props.api.get(`${pluginBase.value}/targets?${params.toString()}`)
    const data = unwrapResponse(response) || {}
    selectedMedia.value = data.media || media
    seasons.value = data.seasons || []
    selectedSeason.value = data.selected_season ?? 'all'
    targets.value = data.targets || []
    selectedTargetIds.value = targets.value.filter(item => item.writable !== false).map(item => item.id)

    if (!targets.value.length) {
      message.value = `${mediaLabel(selectedMedia.value)} 没有找到本地可写入的视频文件`
    }
  } catch (err) {
    error.value = errorMessage(err, '读取本地视频目标失败')
  } finally {
    resolving.value = false
  }
}

async function selectMedia(media) {
  selectedMedia.value = media
  clearTargetState()
  await loadTargets(media, 'all')
}

async function changeSeason(season) {
  selectedSeason.value = season
  await loadTargets(selectedMedia.value, season)
}

function resetSelection() {
  selectedMedia.value = null
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
  lastWritten.value = []
}

function removeFile(file) {
  files.value = files.value.filter(item => !(item.name === file.name && item.size === file.size))
}

function openFileDialog() {
  fileInputRef.value?.click()
}

function handleDrop(event) {
  event.preventDefault()
  dragging.value = false
  const dropped = Array.from(event.dataTransfer?.files || [])
  mergeFiles(dropped)
}

function handleDragOver(event) {
  event.preventDefault()
  dragging.value = true
}

function handleDragLeave(event) {
  event.preventDefault()
  dragging.value = false
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
    if (preview.value?.items) {
      preview.value.items.forEach(item => {
        const target = selectedTargets.value.find(targetItem => targetItem.id === item.target_id)
        item.output_name = item.output_name || buildOutputName(target, item)
      })
    }
    lastWritten.value = []
    message.value = response?.message || '已生成匹配预览'
  } catch (err) {
    error.value = errorMessage(err, '上传预解析失败')
  } finally {
    preparing.value = false
  }
}

function updatePreviewTarget(uploadId, targetId) {
  const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId)
  if (!item) return
  const target = selectedTargets.value.find(targetItem => targetItem.id === targetId)
  item.target_id = targetId
  item.output_name = buildOutputName(target, item)
}

async function applyUpload() {
  if (!canApply.value || !preview.value) return
  applying.value = true
  error.value = ''
  try {
    const payload = {
      session_id: preview.value.session_id,
      fix_timeline: fixTimeline.value,
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
    lastWritten.value = data.written || []
    files.value = []
    preview.value = null
  } catch (err) {
    error.value = errorMessage(err, '写入字幕失败')
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
        <div class="hero-eyebrow">MoviePilot 本地字幕工作台</div>
        <h1 class="hero-title">字幕手传匹配</h1>
        <p class="hero-text">
          只从 MoviePilot 本地资源库里找已有视频，左侧选资源和季度，中间确认目标与改名预览，右侧拖入字幕或 ZIP 后写入。
        </p>
      </div>
      <div class="hero-meta">
        <div class="meta-card">
          <div class="meta-label">数据来源</div>
          <div class="meta-value">LOCAL</div>
          <div class="meta-hint">{{ status.source || 'MoviePilot 本地整理记录' }}</div>
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
      <VCard class="panel-card resource-panel" rounded="xl" elevation="0">
        <VCardTitle class="panel-title">
          <span>选择本地资源</span>
          <VBtn size="small" variant="text" :loading="refreshing" @click="refreshIndex">接口状态</VBtn>
        </VCardTitle>
        <VCardText>
          <div class="search-stack">
            <VTextField
              v-model="searchKeyword"
              label="片名、剧名或文件路径关键词"
              variant="outlined"
              density="comfortable"
              hide-details
              clearable
              @keyup.enter="runSearch"
            />
            <div class="search-actions">
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
              <VBtn color="primary" :loading="searching" @click="runSearch">搜索本地</VBtn>
            </div>
          </div>

          <div v-if="medias.length" class="media-list">
            <button
              v-for="media in medias"
              :key="media.id"
              class="media-row"
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
                <div class="media-title">{{ mediaLabel(media) }}</div>
                <div class="media-meta">
                  <span>{{ formatMediaType(media.media_type) }}</span>
                  <span>{{ mediaStat(media) }}</span>
                </div>
              </div>
            </button>
          </div>
          <div v-else class="empty-state">
            输入关键词搜索本地已有资源；留空点击搜索会显示最近整理的视频。
          </div>

        </VCardText>
      </VCard>

      <VCard class="panel-card preview-panel" rounded="xl" elevation="0">
        <VCardTitle class="panel-title">
          <span>目标与预览</span>
          <span v-if="selectedTargets.length" class="panel-count">{{ selectedTargets.length }} 个目标</span>
        </VCardTitle>
        <VCardText>
          <div v-if="!selectedMedia" class="center-empty">
            <div class="empty-title">先从左侧选择一个本地资源</div>
            <div class="empty-text">这里会显示该电影或剧集季度下的真实视频文件，不再混入库里没有的视频目标。</div>
          </div>

          <template v-else>
            <div class="selected-header">
              <div class="selected-summary">
                <span class="selected-title">{{ mediaLabel(selectedMedia) }}</span>
                <span class="selected-subtitle">
                  {{ formatMediaType(selectedMedia.media_type) }} · {{ selectedTargets.length }} 个本地目标
                </span>
              </div>
              <VSelect
                v-if="selectedMedia.media_type === 'tv'"
                :model-value="selectedSeason"
                :items="seasonItems"
                label="季度范围"
                variant="outlined"
                density="compact"
                hide-details
                :loading="resolving"
                @update:model-value="changeSeason"
              />
              <VBtn size="small" variant="tonal" @click="resetSelection">重选</VBtn>
            </div>

            <div class="target-list">
              <div
                v-for="target in selectedTargets"
                :key="target.id"
                class="target-row"
              >
                <div class="target-index">{{ target.media_type === 'tv' ? `E${String(target.episode || 0).padStart(2, '0')}` : 'MOV' }}</div>
                <div class="target-copy">
                  <div class="target-name">{{ compactTargetName(target) }}</div>
                  <div class="target-path">{{ target.relative_path }}</div>
                </div>
              </div>
            </div>

            <div v-if="!selectedTargets.length" class="empty-state compact">
              {{ resolving ? '正在读取本地视频目标...' : '这个资源没有可写入的本地视频文件。' }}
            </div>

            <div v-if="preview?.items?.length" class="preview-section">
              <div class="section-head">
                <div>
                  <div class="section-title">匹配预览</div>
                  <div class="section-desc">检查每个字幕对应的视频目标和最终落盘文件名。</div>
                </div>
              </div>

              <div class="match-list">
                <div
                  v-for="item in preview.items"
                  :key="item.upload_id"
                  class="match-row"
                >
                  <div class="subtitle-source">
                    <div class="source-name">{{ item.source_name }}</div>
                    <div class="source-meta">
                      <span v-if="item.archive_name">来自 {{ item.archive_name }}</span>
                      <span>{{ item.detected_label || '未知语言' }}</span>
                      <span>{{ item.language_suffix }}</span>
                    </div>
                  </div>
                  <VSelect
                    :model-value="item.target_id"
                    :items="targetSelectItems"
                    label="匹配目标"
                    variant="outlined"
                    density="comfortable"
                    hide-details
                    @update:model-value="value => updatePreviewTarget(item.upload_id, value)"
                  />
                  <div class="output-name">
                    <span>改名为</span>
                    <strong>{{ item.output_name || buildOutputName(selectedTargets.find(target => target.id === item.target_id), item) || '待选择目标' }}</strong>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="lastWritten.length" class="result-section">
              <div class="section-title">写入结果</div>
              <div class="result-list">
                <div v-for="item in lastWritten" :key="item.output_path" class="result-row">
                  <div>
                    <div class="source-name">{{ item.output_name }}</div>
                    <div class="source-meta">{{ item.target_label }}</div>
                  </div>
                  <div class="result-badge" :class="{ active: item.timeline?.applied }">
                    {{ timelineResultText(item) }}
                  </div>
                </div>
              </div>
            </div>
          </template>
        </VCardText>
      </VCard>

      <VCard class="panel-card upload-panel" rounded="xl" elevation="0">
        <VCardTitle class="panel-title">上传字幕</VCardTitle>
        <VCardText>
          <div
            class="dropzone"
            :class="{ dragging }"
            @drop="handleDrop"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
          >
            <div class="dropzone-icon">SRT / ASS / ZIP</div>
            <div class="dropzone-title">拖入字幕或压缩包</div>
            <div class="dropzone-text">支持多文件上传；ZIP 会自动解包，只保留字幕文件参与匹配。</div>
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
            <div v-for="file in files" :key="`${file.name}-${file.size}`" class="file-row">
              <div>
                <div class="file-name">{{ file.name }}</div>
                <div class="file-size">{{ Math.max(1, Math.round(file.size / 1024)) }} KB</div>
              </div>
              <VBtn size="small" variant="text" color="error" @click="removeFile(file)">移除</VBtn>
            </div>
          </div>

          <div class="timeline-option">
            <VSwitch
              v-model="fixTimeline"
              color="primary"
              density="comfortable"
              hide-details
              :disabled="!timelineAvailable"
              label="写入前智能调轴"
            />
            <div class="timeline-hint">
              <span v-if="timelineAvailable">
                使用容器内 ffmpeg/ffprobe 与 Python 依赖计算整体偏移。
              </span>
              <span v-else>
                当前缺少调轴依赖{{ timelineMissing ? `：${timelineMissing}` : '' }}。
              </span>
            </div>
          </div>

          <div class="action-stack">
            <VBtn
              color="primary"
              block
              :disabled="!canPrepare"
              :loading="preparing"
              @click="prepareUpload"
            >
              生成匹配预览
            </VBtn>
            <VBtn
              color="success"
              block
              variant="tonal"
              :disabled="!canApply"
              :loading="applying"
              @click="applyUpload"
            >
              写入字幕
            </VBtn>
          </div>

          <div class="upload-note">
            先生成预览再写入。预览会出现在中间栏，确认改名结果后再点击写入。
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
    radial-gradient(circle at 92% 4%, rgba(245, 184, 94, 0.22), transparent 30%),
    radial-gradient(circle at 0% 0%, rgba(88, 126, 156, 0.18), transparent 34%),
    linear-gradient(180deg, #f6f4ee 0%, #edf1f4 100%);
  color: #1f2a32;
  font-family: "LXGW WenKai Screen", "Noto Serif SC", "PingFang SC", sans-serif;
}

.hero-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(220px, 0.7fr);
  gap: 18px;
  margin-bottom: 18px;
}

.hero-copy,
.hero-meta,
.panel-card {
  border: 1px solid rgba(93, 109, 119, 0.16);
  background: rgba(255, 252, 245, 0.88);
  backdrop-filter: blur(14px);
  box-shadow: 0 20px 50px rgba(47, 59, 68, 0.08);
}

.hero-copy {
  padding: 28px;
  border-radius: 28px;
}

.hero-meta {
  padding: 18px;
  border-radius: 28px;
}

.hero-eyebrow,
.meta-label,
.section-kicker {
  color: #7a694f;
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
  max-width: 820px;
  margin: 12px 0 0;
  color: #596870;
  line-height: 1.7;
}

.meta-card {
  height: 100%;
  padding: 18px;
  border-radius: 22px;
  background: linear-gradient(145deg, #25343d, #52616a);
  color: #fff9ed;
}

.meta-value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 800;
}

.meta-hint {
  margin-top: 8px;
  font-size: 13px;
  opacity: 0.82;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(420px, 1.45fr) minmax(300px, 0.85fr);
  gap: 18px;
  align-items: start;
}

.panel-card {
  border-radius: 28px;
}

.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 20px 22px 8px;
  font-size: 17px;
  font-weight: 800;
}

.panel-count {
  color: #7b8a92;
  font-size: 13px;
  font-weight: 500;
}

.search-stack,
.file-list,
.target-list,
.match-list,
.result-list,
.action-stack {
  display: grid;
  gap: 12px;
}

.search-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.media-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.media-row {
  width: 100%;
  border: 1px solid rgba(109, 126, 137, 0.18);
  background: rgba(255, 255, 255, 0.72);
  color: inherit;
  text-align: left;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.media-row {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 12px;
  min-height: 86px;
  padding: 10px;
  border-radius: 18px;
}

.media-row:hover,
.media-row.active {
  transform: translateY(-1px);
  border-color: rgba(161, 107, 39, 0.46);
  background: #fff8ea;
}

.poster-shell,
.poster,
.poster-fallback {
  width: 58px;
  height: 76px;
  border-radius: 12px;
}

.poster {
  display: block;
  object-fit: cover;
}

.poster-fallback {
  display: grid;
  place-items: center;
  background: #293942;
  color: #fff8ea;
  font-size: 13px;
}

.media-info {
  min-width: 0;
}

.media-title,
.selected-title,
.target-name,
.source-name,
.file-name,
.section-title {
  font-weight: 800;
  word-break: break-all;
}

.media-meta,
.selected-subtitle,
.target-path,
.source-meta,
.file-size,
.section-desc,
.empty-text,
.timeline-hint,
.upload-note {
  color: #65757d;
  font-size: 12px;
  line-height: 1.55;
}

.media-meta,
.source-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 5px;
}

.target-index {
  display: inline-grid;
  min-width: 34px;
  min-height: 26px;
  place-items: center;
  border-radius: 999px;
  background: #eef1f2;
  color: #53636b;
  font-size: 12px;
  font-weight: 700;
}

.empty-state,
.center-empty {
  padding: 22px 14px;
  margin-top: 16px;
  border-radius: 18px;
  background: rgba(238, 242, 244, 0.78);
  color: #687980;
  text-align: center;
}

.empty-state.compact {
  padding: 14px 12px;
}

.empty-title {
  color: #24343d;
  font-weight: 800;
}

.selected-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(180px, 220px) auto;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
}

.selected-summary {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
}

.target-list {
  max-height: 360px;
  overflow: auto;
  padding-right: 2px;
}

.target-row,
.match-row,
.result-row,
.file-row {
  border: 1px solid rgba(109, 126, 137, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
}

.target-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  padding: 11px 12px;
}

.preview-section,
.result-section {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid rgba(112, 128, 138, 0.16);
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.match-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(220px, 0.95fr) minmax(180px, 0.9fr);
  gap: 12px;
  align-items: center;
  padding: 12px;
}

.output-name {
  display: grid;
  gap: 4px;
  min-width: 0;
  color: #65757d;
  font-size: 12px;
}

.output-name strong {
  color: #293942;
  word-break: break-all;
}

.dropzone {
  position: relative;
  overflow: hidden;
  padding: 28px 18px;
  border: 1px dashed rgba(151, 101, 42, 0.42);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 250, 239, 0.95), rgba(242, 238, 229, 0.9));
  text-align: center;
  transition: border-color 0.18s ease, transform 0.18s ease, background 0.18s ease;
}

.dropzone.dragging {
  transform: translateY(-1px);
  border-color: rgba(169, 105, 26, 0.88);
  background: #fff3d8;
}

.dropzone-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 126px;
  padding: 8px 14px;
  border-radius: 999px;
  background: #293942;
  color: #fff8ea;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.dropzone-title {
  margin-top: 16px;
  font-size: 20px;
  font-weight: 800;
}

.dropzone-text {
  max-width: 420px;
  margin: 10px auto 18px;
  color: #65757d;
  line-height: 1.65;
}

.hidden-input {
  display: none;
}

.file-list {
  margin-top: 16px;
}

.file-row,
.result-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 11px 12px;
}

.timeline-option {
  display: grid;
  gap: 6px;
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 18px;
  background: rgba(238, 242, 244, 0.78);
}

.action-stack {
  margin-top: 16px;
}

.upload-note {
  margin-top: 12px;
}

.result-badge {
  max-width: 320px;
  padding: 8px 10px;
  border-radius: 999px;
  background: #eef1f2;
  color: #53636b;
  font-size: 12px;
  text-align: right;
}

.result-badge.active {
  background: #e7f3ea;
  color: #2b744d;
}

.mb-4 {
  margin-bottom: 16px;
}

@media (max-width: 1280px) {
  .workspace-grid {
    grid-template-columns: minmax(300px, 0.9fr) minmax(420px, 1.2fr);
  }

  .upload-panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 920px) {
  .hero-shell,
  .workspace-grid,
  .match-row,
  .selected-header {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
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

  .search-actions,
  .file-row,
  .result-row {
    grid-template-columns: 1fr;
  }
}
</style>
