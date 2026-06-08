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
const status = ref({
  enabled: false,
  source: 'MoviePilot 本地整理记录',
  archive_support: { zip: true, rar: false, rar_tool: '', rar_python: false, rar_python_package: 'rarfile' },
  timeline_fixer: { available: false, modules: {} },
})

const loading = ref(false)
const searching = ref(false)
const resolving = ref(false)
const refreshing = ref(false)
const preparing = ref(false)
const applying = ref(false)
const clearing = ref(false)
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
const lockedTargetIds = ref([])
const uploadDialog = ref(false)
const rarHelpDialog = ref(false)
const uploadTitle = ref('')
const uploadScopeTargets = ref([])
const files = ref([])
const preview = ref(null)
const fileInputRef = ref(null)
const fixTimeline = ref(false)
const lastWritten = ref([])

const visibleTargets = computed(() => targets.value || [])
const selectedTargets = computed(() => {
  const picked = new Set(selectedTargetIds.value || [])
  return visibleTargets.value.filter(item => picked.has(item.id))
})
const unlockedVisibleTargets = computed(() => visibleTargets.value.filter(item => !isLocked(item.id) && item.writable !== false))
const uploadTargets = computed(() => uploadScopeTargets.value.filter(item => !isLocked(item.id) && item.writable !== false))
const batchUploadTargets = computed(() => {
  const base = selectedTargets.value.length ? selectedTargets.value : visibleTargets.value
  return base.filter(item => !isLocked(item.id) && item.writable !== false)
})
const targetSelectItems = computed(() => uploadTargets.value.map(target => ({
  title: compactTargetName(target),
  value: target.id,
})))
const canPrepare = computed(() => uploadTargets.value.length > 0 && files.value.length > 0)
const canApply = computed(() => {
  const items = preview.value?.items || []
  return items.length > 0 && items.every(item => item.target_id)
})
const timelineStatus = computed(() => status.value?.timeline_fixer || { available: false, modules: {} })
const timelineAvailable = computed(() => timelineStatus.value.available === true)
const archiveStatus = computed(() => status.value?.archive_support || { zip: true, rar: false, rar_tool: '', rar_python: false })
const rarAvailable = computed(() => archiveStatus.value.rar === true)
const rarPythonAvailable = computed(() => archiveStatus.value.rar_python === true)
const seasonCards = computed(() => {
  if (selectedMedia.value?.media_type !== 'tv') return []
  const total = seasons.value.reduce((sum, item) => sum + Number(item.local_count || 0), 0)
  return [
    { title: '全部季', subtitle: `${total} 集`, value: 'all', count: total },
    ...seasons.value
      .filter(item => item.available)
      .map(item => ({
        title: seasonLabel(item.season),
        subtitle: `${item.local_count || 0} 集`,
        value: item.season,
        count: item.local_count || 0,
      })),
  ]
})
const allVisibleSelected = computed(() => {
  if (!visibleTargets.value.length) return false
  const picked = new Set(selectedTargetIds.value || [])
  return visibleTargets.value.every(item => picked.has(item.id))
})
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
  if (season && episode) {
    return `S${String(season).padStart(2, '0')}E${String(episode).padStart(2, '0')} · ${target.basename || targetLabel(target)}`
  }
  return target.basename || targetLabel(target)
}

function mediaStat(media) {
  const count = Number(media?.local_count || 0)
  if (media?.media_type === 'tv') {
    const seasonCount = Number(media?.season_count || 0)
    return `${seasonCount || '-'} 季 · ${count} 集本地资源`
  }
  return `${count || 1} 个本地资源`
}

function formatBytes(value) {
  const size = Number(value || 0)
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size >= 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${size} B`
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
    return `已调轴 ${formatOffset(timeline.offset_seconds)} · ${base}`
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

function isLocked(targetId) {
  return lockedTargetIds.value.includes(targetId)
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
    message.value = response?.message || 'MoviePilot 本地整理记录为实时读取，无需重建索引'
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
    params.set('limit', '48')
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
  try {
    const params = buildMediaParams(media, season || 'all')
    const response = await props.api.get(`${pluginBase.value}/targets?${params.toString()}`)
    const data = unwrapResponse(response) || {}
    selectedMedia.value = data.media || media
    seasons.value = data.seasons || []
    selectedSeason.value = data.selected_season ?? 'all'
    targets.value = data.targets || []
    selectedTargetIds.value = []

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
  selectedTargetIds.value = []
  await loadTargets(selectedMedia.value, season)
}

function resetSelection() {
  selectedMedia.value = null
  clearTargetState()
  runSearch()
}

function toggleSelectAll() {
  if (allVisibleSelected.value) {
    selectedTargetIds.value = []
    return
  }
  selectedTargetIds.value = visibleTargets.value.map(item => item.id)
}

function toggleTarget(targetId, checked) {
  const set = new Set(selectedTargetIds.value)
  if (checked) {
    set.add(targetId)
  } else {
    set.delete(targetId)
  }
  selectedTargetIds.value = Array.from(set)
}

function toggleLock(targetId) {
  if (isLocked(targetId)) {
    lockedTargetIds.value = lockedTargetIds.value.filter(item => item !== targetId)
    return
  }
  lockedTargetIds.value = [...lockedTargetIds.value, targetId]
}

function openUploadDialog(scopeTargets, title) {
  const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false)
  if (!usableTargets.length) {
    error.value = '没有可上传的目标：选中的集数可能都已锁定'
    return
  }
  uploadScopeTargets.value = usableTargets
  uploadTitle.value = title
  files.value = []
  preview.value = null
  lastWritten.value = []
  error.value = ''
  message.value = ''
  uploadDialog.value = true
}

function openBatchUpload() {
  const title = selectedTargets.value.length
    ? `批量上传选中 ${batchUploadTargets.value.length} 集`
    : `批量上传 ${selectedSeason.value === 'all' ? '全部季' : seasonLabel(selectedSeason.value)}`
  openUploadDialog(batchUploadTargets.value, title)
}

function openSingleUpload(target) {
  openUploadDialog([target], `上传 ${compactTargetName(target)}`)
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
    const targetIds = uploadTargets.value.map(item => item.id)
    const formData = new FormData()
    formData.append('target_ids', JSON.stringify(targetIds))
    files.value.forEach(file => {
      formData.append('files', file)
    })
    const response = await props.api.post(`${pluginBase.value}/prepare_upload`, formData)
    preview.value = unwrapResponse(response)
    if (preview.value?.items) {
      preview.value.items.forEach(item => {
        const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
        item.output_name = item.output_name || buildOutputName(target, item)
      })
    }
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
  const target = uploadTargets.value.find(targetItem => targetItem.id === targetId)
  item.target_id = targetId
  item.output_name = buildOutputName(target, item)
}

function updateLanguageSuffix(uploadId, value) {
  const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId)
  if (!item) return
  item.language_suffix = String(value || '').trim() || 'und'
  const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
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
    const written = data.written || []
    const successMessage = response?.message || `已写入 ${data.count || 0} 个字幕文件`
    files.value = []
    preview.value = null
    uploadDialog.value = false
    await loadTargets(selectedMedia.value, selectedSeason.value)
    message.value = successMessage
    lastWritten.value = written
  } catch (err) {
    error.value = errorMessage(err, '写入字幕失败')
  } finally {
    applying.value = false
  }
}

async function clearSelectedSubtitles() {
  if (!selectedTargetIds.value.length) return
  clearing.value = true
  error.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/clear_subtitles`, {
      target_ids: selectedTargetIds.value,
    })
    const data = unwrapResponse(response) || {}
    const successMessage = response?.message || `已删除 ${data.count || 0} 个外挂字幕`
    await loadTargets(selectedMedia.value, selectedSeason.value)
    message.value = successMessage
  } catch (err) {
    error.value = errorMessage(err, '清空外挂字幕失败')
  } finally {
    clearing.value = false
  }
}

onMounted(async () => {
  await loadStatus()
  await runSearch()
})

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
  clearing,
})
</script>

<template>
  <div class="subtitle-upload-page">
    <div v-if="!hideTitle" class="hero-card">
      <div>
        <div class="hero-eyebrow">MoviePilot Local Subtitle Desk</div>
        <h1>字幕手传匹配</h1>
        <p>只读取本地媒体库已有资源。先选择电影或剧集，再按季度/集数上传字幕、ZIP 或 RAR，并在写入前确认自动改名结果。</p>
      </div>
      <div class="hero-status">
        <span>RAR</span>
        <strong>{{ rarAvailable ? archiveStatus.rar_tool || '可用' : '需解压器' }}</strong>
        <small>{{ rarPythonAvailable ? '已声明 rarfile' : '等待安装 rarfile' }}</small>
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

    <section v-if="!selectedMedia" class="media-stage">
      <VCard class="glass-card search-card" rounded="xl" elevation="0">
        <VCardText>
          <div class="search-head">
            <div>
              <div class="section-kicker">第一步</div>
              <h2>选择本地已有资源</h2>
              <p>搜索结果只来自 MoviePilot 本地整理记录，不再展示库里没有的视频。</p>
            </div>
            <VBtn variant="text" :loading="refreshing" @click="refreshIndex">接口状态</VBtn>
          </div>
          <div class="search-bar">
            <VTextField
              v-model="searchKeyword"
              label="片名、剧名或文件关键词"
              variant="outlined"
              density="comfortable"
              hide-details
              clearable
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
            <VBtn color="primary" :loading="searching" @click="runSearch">搜索</VBtn>
          </div>
        </VCardText>
      </VCard>

      <div v-if="medias.length" class="media-list">
        <button
          v-for="media in medias"
          :key="media.id"
          class="media-card"
          @click="selectMedia(media)"
        >
          <div class="poster-frame">
            <img
              v-if="media.poster_url"
              :src="media.poster_url"
              :alt="mediaLabel(media)"
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
      <div v-else class="empty-state">
        {{ searching ? '正在读取本地资源...' : '输入关键词搜索；留空搜索会显示最近整理的视频。' }}
      </div>
    </section>

    <section v-else class="episode-stage">
      <VCard class="glass-card detail-card" rounded="xl" elevation="0">
        <VCardText>
          <div class="detail-head">
            <div class="selected-media">
              <button class="back-btn" @click="resetSelection">
                <VIcon icon="mdi-arrow-left" />
              </button>
              <div class="mini-poster">
                <img
                  v-if="selectedMedia.poster_url"
                  :src="selectedMedia.poster_url"
                  :alt="mediaLabel(selectedMedia)"
                >
                <span v-else>{{ formatMediaType(selectedMedia.media_type) }}</span>
              </div>
              <div>
                <div class="section-kicker">{{ formatMediaType(selectedMedia.media_type) }}</div>
                <h2>{{ mediaLabel(selectedMedia) }}</h2>
                <p>{{ visibleTargets.length }} 个本地目标 · {{ selectedTargets.length }} 个已选 · {{ lockedTargetIds.length }} 个锁定</p>
              </div>
            </div>
            <VBtn variant="tonal" :loading="resolving" @click="loadTargets(selectedMedia, selectedSeason)">
              刷新列表
            </VBtn>
          </div>

          <div v-if="selectedMedia.media_type === 'tv'" class="season-strip">
            <button
              v-for="season in seasonCards"
              :key="season.value"
              class="season-card"
              :class="{ active: selectedSeason === season.value }"
              @click="changeSeason(season.value)"
            >
              <span>{{ season.title }}</span>
              <strong>{{ season.subtitle }}</strong>
            </button>
          </div>

          <div class="toolbar-row">
            <VBtn variant="tonal" @click="toggleSelectAll">
              {{ allVisibleSelected ? '取消全选' : '全选当前列表' }}
            </VBtn>
            <VBtn
              color="primary"
              :disabled="!unlockedVisibleTargets.length"
              @click="openBatchUpload"
            >
              {{ selectedTargets.length ? '上传选中字幕' : '批量上传整季字幕' }}
            </VBtn>
            <VBtn
              color="error"
              variant="tonal"
              :disabled="!selectedTargetIds.length"
              :loading="clearing"
              @click="clearSelectedSubtitles"
            >
              清空选中外挂字幕
            </VBtn>
            <div class="toolbar-hint">
              锁定的集数会在批量上传时自动跳过；清空字幕只作用于你勾选的集。
            </div>
          </div>

          <div v-if="visibleTargets.length" class="episode-list">
            <div
              v-for="target in visibleTargets"
              :key="target.id"
              class="episode-row"
              :class="{ locked: isLocked(target.id) }"
            >
              <VCheckbox
                :model-value="selectedTargetIds.includes(target.id)"
                density="compact"
                hide-details
                @update:model-value="value => toggleTarget(target.id, value)"
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
                variant="text"
                :icon="isLocked(target.id) ? 'mdi-lock' : 'mdi-lock-open-variant'"
                :color="isLocked(target.id) ? 'warning' : undefined"
                :title="isLocked(target.id) ? '解锁此集' : '锁定此集，批量上传跳过'"
                @click="toggleLock(target.id)"
              />
              <VBtn
                color="primary"
                variant="tonal"
                size="small"
                :disabled="isLocked(target.id)"
                @click="openSingleUpload(target)"
              >
                单集上传
              </VBtn>
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
            </div>
          </div>
        </VCardText>
      </VCard>
    </section>

    <VDialog v-model="uploadDialog" max-width="980">
      <VCard class="upload-dialog" rounded="xl">
        <VCardTitle class="dialog-title">
          <span>{{ uploadTitle || '上传字幕' }}</span>
          <VBtn icon="mdi-close" variant="text" @click="uploadDialog = false" />
        </VCardTitle>
        <VDivider />
        <VCardText>
          <div
            class="dropzone"
            :class="{ dragging }"
            @drop="handleDrop"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
          >
            <div class="dropzone-icon">SRT / ASS / ZIP / RAR</div>
            <div class="dropzone-title">把字幕或压缩包拖到这里</div>
            <div class="dropzone-text">
              ZIP 会自动解包；RAR 已加入轻量 Python 依赖 rarfile，但仍需要容器内有 unrar、bsdtar、7z 或 7za。
            </div>
            <VBtn color="primary" variant="flat" @click="openFileDialog">选择文件</VBtn>
            <input
              ref="fileInputRef"
              class="hidden-input"
              type="file"
              multiple
              accept=".srt,.ass,.ssa,.sbv,.sub,.vtt,.webvtt,.zip,.rar"
              @change="onPickFiles"
            >
          </div>

          <div class="support-row">
            <span :class="{ ok: rarPythonAvailable }">rarfile：{{ rarPythonAvailable ? '已安装' : '将由 requirements.txt 安装' }}</span>
            <span :class="{ ok: rarAvailable }">RAR 解压器：{{ rarAvailable ? archiveStatus.rar_tool || '可用' : '未检测到' }}</span>
            <button class="support-help" type="button" @click="rarHelpDialog = true">
              RAR 不能解压？查看处理方式
            </button>
            <span :class="{ ok: timelineAvailable }">
              智能调轴：{{ timelineAvailable ? '可用' : `缺少 ${timelineMissing || '依赖'}` }}
            </span>
          </div>

          <div v-if="files.length" class="file-list">
            <div v-for="file in files" :key="`${file.name}-${file.size}`" class="file-row">
              <div>
                <strong>{{ file.name }}</strong>
                <span>{{ formatBytes(file.size) }}</span>
              </div>
              <VBtn size="small" variant="text" color="error" @click="removeFile(file)">移除</VBtn>
            </div>
          </div>

          <div v-if="preview?.items?.length" class="preview-list">
            <div class="preview-head">
              <div>
                <div class="section-kicker">匹配预览</div>
                <h3>确认字幕对应集数和落盘文件名</h3>
              </div>
              <VSwitch
                v-model="fixTimeline"
                color="primary"
                density="comfortable"
                hide-details
                :disabled="!timelineAvailable"
                label="写入前智能调轴"
              />
            </div>
            <div
              v-for="item in preview.items"
              :key="item.upload_id"
              class="preview-row"
            >
              <div class="subtitle-source">
                <strong>{{ item.source_name }}</strong>
                <span>
                  {{ item.archive_name ? `来自 ${item.archive_name} · ` : '' }}{{ item.detected_label || '未知语言' }}
                </span>
              </div>
              <VSelect
                :model-value="item.target_id"
                :items="targetSelectItems"
                label="对应集数"
                variant="outlined"
                density="comfortable"
                hide-details
                @update:model-value="value => updatePreviewTarget(item.upload_id, value)"
              />
              <VTextField
                :model-value="item.language_suffix"
                label="语言后缀"
                variant="outlined"
                density="comfortable"
                hide-details
                @update:model-value="value => updateLanguageSuffix(item.upload_id, value)"
              />
              <div class="output-name">
                <span>改名为</span>
                <strong>{{ item.output_name || buildOutputName(uploadTargets.find(target => target.id === item.target_id), item) || '待选择目标' }}</strong>
              </div>
            </div>
          </div>
        </VCardText>
        <VDivider />
        <VCardActions class="dialog-actions">
          <VBtn variant="text" @click="uploadDialog = false">关闭</VBtn>
          <VSpacer />
          <VBtn
            color="primary"
            variant="tonal"
            :disabled="!canPrepare"
            :loading="preparing"
            @click="prepareUpload"
          >
            生成匹配预览
          </VBtn>
          <VBtn
            color="success"
            :disabled="!canApply"
            :loading="applying"
            @click="applyUpload"
          >
            写入字幕
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="rarHelpDialog" max-width="760">
      <VCard class="rar-help-dialog" rounded="xl">
        <VCardTitle class="dialog-title">
          <span>RAR 解压器说明</span>
          <VBtn icon="mdi-close" variant="text" @click="rarHelpDialog = false" />
        </VCardTitle>
        <VDivider />
        <VCardText>
          <div class="help-intro">
            插件已经声明了最轻的 Python 依赖 <code>rarfile</code>，但它不是纯 Python 解压器。
            真正读取 RAR 内容时，容器里还必须能执行 <code>unrar</code>、<code>7z</code>、<code>7za</code> 或 <code>bsdtar</code>。
          </div>

          <div class="help-grid">
            <div class="help-card">
              <strong>临时安装到当前容器</strong>
              <p>适合马上测试。容器删除或重建后可能丢失。</p>
              <pre>docker exec -it moviepilot bash
apt-get update
apt-get install -y p7zip-full unrar-free</pre>
            </div>
            <div class="help-card">
              <strong>宿主机安装 + 映射进容器</strong>
              <p>只在宿主机安装还不够，容器看不到宿主机命令；需要把可执行文件 bind mount 到容器 PATH 下。</p>
              <pre>volumes:
  - /path/to/7zz:/usr/local/bin/7z:ro</pre>
            </div>
            <div class="help-card">
              <strong>推荐映射静态二进制</strong>
              <p><code>/usr/bin/7z</code> 这类系统命令可能依赖额外动态库；如果要映射，优先用静态 <code>7zz</code> 或一并映射依赖库。</p>
              <pre>docker exec moviepilot which unrar 7z 7za bsdtar</pre>
            </div>
          </div>

          <VAlert
            class="mt-4"
            type="info"
            variant="tonal"
            text="安装或映射完成后，重新打开上传弹窗或刷新插件状态即可重新检测。检测逻辑只看容器内 PATH 是否能找到 unrar、bsdtar、7z 或 7za。"
          />
        </VCardText>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.subtitle-upload-page {
  min-height: 100%;
  padding: 24px;
  background:
    radial-gradient(circle at 12% 12%, rgba(210, 154, 79, 0.18), transparent 28%),
    radial-gradient(circle at 88% 0%, rgba(48, 90, 82, 0.16), transparent 32%),
    linear-gradient(180deg, #f5f0e7 0%, #edf1ec 100%);
  color: #263238;
  font-family: "LXGW WenKai Screen", "Noto Serif SC", "PingFang SC", sans-serif;
}

.hero-card,
.glass-card {
  border: 1px solid rgba(83, 103, 94, 0.16);
  background: rgba(255, 252, 245, 0.88);
  box-shadow: 0 24px 70px rgba(43, 62, 58, 0.1);
  backdrop-filter: blur(14px);
}

.hero-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 18px;
  padding: 26px;
  margin-bottom: 18px;
  border-radius: 28px;
}

.hero-card h1,
.search-head h2,
.detail-head h2,
.preview-head h3 {
  margin: 0;
  letter-spacing: -0.04em;
}

.hero-card p,
.search-head p,
.detail-head p {
  margin: 8px 0 0;
  color: #64746f;
  line-height: 1.7;
}

.hero-eyebrow,
.section-kicker,
.media-type {
  color: #8a6b3f;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.hero-status {
  display: grid;
  align-content: center;
  gap: 6px;
  padding: 18px;
  border-radius: 22px;
  background: linear-gradient(145deg, #2d463f, #7d6845);
  color: #fffaf0;
}

.hero-status span,
.hero-status small {
  opacity: 0.78;
}

.hero-status strong {
  font-size: 24px;
}

.media-stage,
.episode-stage {
  display: grid;
  gap: 16px;
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

.search-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px auto;
  gap: 12px;
  align-items: center;
}

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
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.media-card:hover {
  transform: translateY(-2px);
  border-color: rgba(159, 107, 45, 0.45);
  background: #fff8ea;
}

.poster-frame,
.mini-poster {
  display: grid;
  place-items: center;
  overflow: hidden;
  background: #30463f;
  color: #fffaf0;
}

.poster-frame {
  width: 72px;
  height: 96px;
  border-radius: 16px;
}

.poster-frame img,
.mini-poster img {
  width: 100%;
  height: 100%;
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

.detail-card {
  border-radius: 28px;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
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
  background: #e8ded0;
  color: #30443f;
}

.mini-poster {
  width: 58px;
  height: 78px;
  border-radius: 14px;
  font-size: 12px;
}

.season-strip {
  display: flex;
  gap: 10px;
  padding-bottom: 12px;
  margin-bottom: 14px;
  overflow-x: auto;
}

.season-card {
  display: grid;
  min-width: 126px;
  gap: 5px;
  padding: 12px 14px;
  border: 1px solid rgba(91, 109, 100, 0.16);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
  color: inherit;
  text-align: left;
}

.season-card.active {
  border-color: rgba(150, 99, 40, 0.58);
  background: #fff4da;
  box-shadow: inset 0 -3px 0 #b47a35;
}

.season-card span {
  font-weight: 800;
}

.season-card strong {
  color: #6d7b76;
  font-size: 12px;
}

.toolbar-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 12px;
  border-radius: 20px;
  background: rgba(238, 232, 219, 0.58);
}

.toolbar-hint {
  flex: 1 1 260px;
  color: #687873;
  font-size: 12px;
}

.episode-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.episode-row {
  display: grid;
  grid-template-columns: auto 58px minmax(0, 1fr) auto auto auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.76);
}

.episode-row.locked {
  background: rgba(238, 228, 207, 0.68);
}

.episode-index {
  display: grid;
  min-width: 48px;
  min-height: 34px;
  place-items: center;
  border-radius: 999px;
  background: #e8edf0;
  color: #53655f;
  font-size: 12px;
  font-weight: 900;
}

.episode-title {
  font-weight: 900;
  word-break: break-word;
}

.episode-path {
  margin-top: 4px;
  color: #6f7f79;
  font-size: 12px;
  word-break: break-all;
}

.cc-btn {
  color: #97a09c;
}

.cc-btn.has-sub {
  color: #2f7d62;
}

.empty-state {
  padding: 28px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.58);
  color: #687873;
  text-align: center;
}

.result-panel {
  display: grid;
  gap: 10px;
  padding-top: 18px;
  margin-top: 18px;
  border-top: 1px solid rgba(91, 109, 100, 0.14);
}

.result-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.7);
}

.result-row div {
  display: grid;
  gap: 3px;
}

.result-row span,
.result-row em {
  color: #687873;
  font-size: 12px;
  font-style: normal;
}

.upload-dialog {
  background:
    radial-gradient(circle at 10% 0%, rgba(215, 167, 98, 0.2), transparent 28%),
    #fffaf2;
}

.dialog-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dropzone {
  position: relative;
  display: grid;
  gap: 10px;
  justify-items: center;
  padding: 30px 18px;
  border: 1px dashed rgba(151, 101, 42, 0.48);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 250, 239, 0.95), rgba(241, 236, 225, 0.9));
  text-align: center;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.dropzone.dragging {
  transform: translateY(-1px);
  border-color: rgba(169, 105, 26, 0.9);
  background: #fff1d3;
}

.dropzone-icon {
  padding: 6px 10px;
  border-radius: 999px;
  background: #314840;
  color: #fff9ed;
  font-size: 12px;
  font-weight: 900;
}

.dropzone-title {
  font-size: 18px;
  font-weight: 900;
}

.dropzone-text,
.support-row,
.file-row span,
.subtitle-source span,
.output-name span {
  color: #687873;
  font-size: 12px;
}

.hidden-input {
  display: none;
}

.support-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.support-row span {
  padding: 5px 9px;
  border-radius: 999px;
  background: #ece8df;
}

.support-row span.ok {
  background: #e2f1e9;
  color: #2f7d62;
}

.support-help {
  padding: 5px 10px;
  border: 0;
  border-radius: 999px;
  background: #fff0d6;
  color: #9a611d;
  font-size: 12px;
  font-weight: 800;
}

.rar-help-dialog {
  background: #fffaf2;
}

.help-intro {
  color: #52635d;
  line-height: 1.7;
}

.help-intro code,
.help-card code {
  padding: 1px 5px;
  border-radius: 6px;
  background: #efe6d8;
}

.help-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.help-card {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
}

.help-card strong {
  color: #2f443d;
}

.help-card p {
  margin: 0;
  color: #687873;
  font-size: 12px;
  line-height: 1.6;
}

.help-card pre {
  padding: 10px;
  margin: 0;
  overflow-x: auto;
  border-radius: 12px;
  background: #2f443d;
  color: #fff6e8;
  font-size: 12px;
  line-height: 1.5;
}

.file-list,
.preview-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.file-row,
.preview-row {
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
}

.file-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
}

.file-row div,
.subtitle-source,
.output-name {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.preview-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.preview-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) minmax(210px, 1fr) 116px minmax(180px, 1fr);
  gap: 10px;
  align-items: center;
  padding: 12px;
}

.subtitle-source strong,
.output-name strong {
  word-break: break-word;
}

.dialog-actions {
  padding: 12px 18px;
}

@media (max-width: 900px) {
  .subtitle-upload-page {
    padding: 14px;
  }

  .hero-card,
  .search-bar,
  .detail-head,
  .help-grid,
  .preview-row {
    grid-template-columns: 1fr;
  }

  .detail-head,
  .search-head,
  .preview-head {
    display: grid;
  }

  .episode-row {
    grid-template-columns: auto 48px minmax(0, 1fr);
  }

  .episode-row > .cc-btn,
  .episode-row > .v-btn {
    justify-self: start;
  }
}
</style>
