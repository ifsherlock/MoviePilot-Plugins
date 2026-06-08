<script setup>
import { computed, onMounted, ref } from 'vue'
import { groupLabel, targetLabel, unwrapResponse } from '../provider'

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
  libraries: [],
  index: { ready: false, updated_at: '', entry_count: 0 },
})
const loading = ref(false)
const searching = ref(false)
const refreshing = ref(false)
const preparing = ref(false)
const applying = ref(false)
const message = ref('')
const error = ref('')
const searchKeyword = ref('')
const mediaType = ref('all')
const groups = ref([])
const selectedGroup = ref(null)
const selectedTargetIds = ref([])
const files = ref([])
const preview = ref(null)
const fileInputRef = ref(null)

const selectedTargets = computed(() => {
  if (!selectedGroup.value) return []
  const allTargets = selectedGroup.value.targets || []
  const picked = new Set(selectedTargetIds.value || [])
  return allTargets.filter(item => picked.has(item.id))
})

const canPrepare = computed(() => selectedTargetIds.value.length > 0 && files.value.length > 0)
const canApply = computed(() => {
  const items = preview.value?.items || []
  return items.length > 0 && items.every(item => item.target_id)
})

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
    const data = unwrapResponse(response) || {}
    message.value = `索引已刷新，共 ${data.entry_count || 0} 个媒体文件`
    await loadStatus()
    await runSearch()
  } catch (err) {
    error.value = err?.message || '刷新索引失败'
  } finally {
    refreshing.value = false
  }
}

function resetSelection() {
  selectedGroup.value = null
  selectedTargetIds.value = []
  preview.value = null
}

async function runSearch() {
  searching.value = true
  error.value = ''
  preview.value = null
  try {
    const params = new URLSearchParams()
    params.set('keyword', searchKeyword.value || '')
    params.set('media_type', mediaType.value)
    params.set('limit', '50')
    const response = await props.api.get(`${pluginBase.value}/search?${params.toString()}`)
    const data = unwrapResponse(response) || {}
    groups.value = data.groups || []
    if (groups.value.length === 1) {
      selectGroup(groups.value[0])
    }
  } catch (err) {
    error.value = err?.message || '搜索失败'
  } finally {
    searching.value = false
  }
}

function selectGroup(group) {
  selectedGroup.value = group
  selectedTargetIds.value = (group?.targets || []).map(item => item.id)
  preview.value = null
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

onMounted(async () => {
  await loadStatus()
  if (status.value.index?.ready) {
    await runSearch()
  }
})

defineExpose({
  loadStatus,
  refreshIndex,
  runSearch,
  loading,
  searching,
  refreshing,
  preparing,
  applying,
})
</script>

<template>
  <div class="subtitle-upload-page">
    <div v-if="!hideTitle" class="hero-shell">
      <div class="hero-copy">
        <div class="hero-eyebrow">MoviePilot 插件</div>
        <h1 class="hero-title">字幕手传匹配</h1>
        <p class="hero-text">
          先选电影或剧集，再拖拽字幕或 ZIP 上传。插件会尽量自动匹配季集，并按目标视频文件名直接落盘。
        </p>
      </div>
      <div class="hero-meta">
        <div class="meta-card">
          <div class="meta-label">媒体索引</div>
          <div class="meta-value">{{ status.index?.entry_count || 0 }}</div>
          <div class="meta-hint">{{ status.index?.updated_at || '尚未建立索引' }}</div>
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
        <VCardTitle class="panel-title">1. 选择目标媒体</VCardTitle>
        <VCardText>
          <div class="toolbar-row">
            <VTextField
              v-model="searchKeyword"
              label="搜索电影名、剧名或文件名"
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
            <VBtn color="primary" :loading="searching" @click="runSearch">搜索</VBtn>
            <VBtn variant="tonal" :loading="refreshing" @click="refreshIndex">刷新索引</VBtn>
          </div>

          <div class="library-hint">
            <span
              v-for="library in status.libraries || []"
              :key="library.name"
              class="library-chip"
            >
              {{ library.name }}
            </span>
          </div>

          <div v-if="groups.length" class="group-list">
            <button
              v-for="group in groups"
              :key="group.group_id"
              class="group-item"
              :class="{ active: selectedGroup?.group_id === group.group_id }"
              @click="selectGroup(group)"
            >
              <div class="group-head">
                <span class="group-type">{{ group.media_type === 'movie' ? '电影' : '剧集' }}</span>
                <span class="group-count">{{ group.summary }}</span>
              </div>
              <div class="group-title">{{ groupLabel(group) }}</div>
              <div class="group-subtitle">{{ (group.library_names || []).join(' / ') }}</div>
            </button>
          </div>
          <div v-else class="empty-state">
            先搜索目标电影或剧集。若结果为空，可以先刷新索引。
          </div>

          <div v-if="selectedGroup" class="target-shell">
            <div class="target-header">
              <div class="target-title">已选：{{ groupLabel(selectedGroup) }}</div>
              <div class="target-caption">默认全选，可取消无关集数。</div>
            </div>
            <div class="target-list">
              <label
                v-for="target in selectedGroup.targets || []"
                :key="target.id"
                class="target-item"
              >
                <input
                  v-model="selectedTargetIds"
                  type="checkbox"
                  :value="target.id"
                >
                <span>{{ targetLabel(target) }}</span>
              </label>
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
            <div class="dropzone-text">也可以点按钮选择多个文件。ZIP 会自动解包，只保留字幕文件。</div>
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
            <VBtn variant="tonal" @click="resetSelection">清空选择</VBtn>
          </div>

          <div v-if="preview?.items?.length" class="preview-shell">
            <div class="preview-header">
              <div class="target-title">3. 检查并写入</div>
              <div class="target-caption">每个字幕都需要对应一个目标视频。</div>
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
    radial-gradient(circle at top right, rgba(194, 219, 255, 0.4), transparent 30%),
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
  background: rgba(255, 255, 255, 0.82);
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
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #587196;
  margin-bottom: 8px;
}

.hero-title {
  margin: 0;
  font-size: 34px;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.hero-text {
  margin: 14px 0 0;
  max-width: 720px;
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
  grid-template-columns: minmax(320px, 0.95fr) minmax(380px, 1.05fr);
  gap: 20px;
}

.panel-card {
  border-radius: 28px;
}

.panel-title {
  font-size: 18px;
  font-weight: 700;
  padding: 22px 24px 8px;
}

.toolbar-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px;
  gap: 12px;
}

.toolbar-actions {
  display: flex;
  gap: 12px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.library-hint {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.library-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  background: #edf3fb;
  color: #47607f;
  font-size: 12px;
}

.group-list {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.group-item {
  border: 1px solid rgba(115, 146, 188, 0.2);
  border-radius: 18px;
  padding: 14px 16px;
  text-align: left;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(247, 250, 255, 0.92));
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.group-item:hover,
.group-item.active {
  transform: translateY(-1px);
  border-color: rgba(39, 88, 153, 0.45);
  box-shadow: 0 12px 30px rgba(41, 77, 126, 0.08);
}

.group-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 12px;
}

.group-type,
.group-count {
  color: #5a6d88;
}

.group-title {
  font-size: 16px;
  font-weight: 700;
}

.group-subtitle {
  margin-top: 6px;
  color: #67788f;
  font-size: 13px;
}

.empty-state {
  padding: 22px 14px;
  margin-top: 18px;
  border-radius: 18px;
  background: #f4f7fb;
  color: #6c7f97;
  text-align: center;
}

.target-shell,
.preview-shell {
  margin-top: 20px;
  border-top: 1px solid rgba(126, 151, 183, 0.18);
  padding-top: 18px;
}

.target-header,
.preview-header {
  margin-bottom: 12px;
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
}

.target-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f4f8fc;
  color: #34485f;
}

.dropzone {
  position: relative;
  overflow: hidden;
  border: 1px dashed rgba(55, 100, 165, 0.36);
  border-radius: 24px;
  padding: 26px 20px;
  background:
    linear-gradient(180deg, rgba(250, 252, 255, 0.95), rgba(239, 245, 252, 0.95));
  text-align: center;
}

.dropzone::before {
  content: '';
  position: absolute;
  inset: auto -20px -40px auto;
  width: 150px;
  height: 150px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(131, 176, 255, 0.28), transparent 70%);
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
  margin: 10px auto 18px;
  max-width: 520px;
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
  border: 1px solid rgba(124, 152, 186, 0.18);
  border-radius: 18px;
  padding: 12px 14px;
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

  .panel-card {
    border-radius: 22px;
  }
}
</style>
