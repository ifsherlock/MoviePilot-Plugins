<script setup>
import { ref } from 'vue'

defineProps({
  modelValue: { type: Boolean, default: false },
  uploadTitle: { type: String, default: '' },
  hasPreviewItems: { type: Boolean, default: false },
  allSelectedPreviewTargetsAreStream: { type: Boolean, default: false },
  hasSelectedPreviewStreamTargets: { type: Boolean, default: false },
  timelineAvailable: { type: Boolean, default: false },
  applying: { type: Boolean, default: false },
  canApply: { type: Boolean, default: false },
  dragging: { type: Boolean, default: false },
  preparing: { type: Boolean, default: false },
  rarPythonAvailable: { type: Boolean, default: false },
  rarAvailable: { type: Boolean, default: false },
  archiveStatus: { type: Object, default: () => ({}) },
  rarDependencyStatus: { type: Object, default: () => ({}) },
  timelineMissing: { type: String, default: '' },
  files: { type: Array, default: () => [] },
  preview: { type: Object, default: null },
  batchLanguageSuffix: { type: String, default: '' },
  targetSelectItems: { type: Array, default: () => [] },
  uploadTargets: { type: Array, default: () => [] },
  fixTimeline: { type: Boolean, default: false },
  formatBytes: { type: Function, required: true },
  rarDependencyModeLabel: { type: Function, required: true },
  buildOutputName: { type: Function, required: true },
})

const emit = defineEmits([
  'update:modelValue',
  'update:fixTimeline',
  'update:batchLanguageSuffix',
  'reset-upload-preview',
  'apply-upload',
  'pick-files',
  'drop',
  'dragover',
  'dragleave',
  'remove-file',
  'open-rar-help',
  'apply-batch-language-suffix',
  'toggle-preview-item',
  'update-preview-target',
  'update-language-suffix',
])

const fileInputRef = ref(null)

function openFileDialog() {
  fileInputRef.value?.click()
}

function onPickFiles(event) {
  emit('pick-files', event)
  if (event.target) {
    event.target.value = ''
  }
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="980"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <VCard class="upload-dialog" rounded="xl">
      <VCardTitle class="dialog-title">
        <span>{{ uploadTitle || '上传字幕' }}</span>
        <VBtn icon="mdi-close" variant="text" @click="$emit('update:modelValue', false)" />
      </VCardTitle>
      <VDivider />
      <VCardActions class="dialog-actions dialog-actions-top">
        <VBtn variant="text" @click="$emit('update:modelValue', false)">关闭</VBtn>
        <VSpacer />
        <VBtn
          v-if="hasPreviewItems"
          variant="tonal"
          @click="$emit('reset-upload-preview')"
        >
          重新选择文件
        </VBtn>
        <VTooltip
          v-if="hasPreviewItems"
          location="top"
          :text="allSelectedPreviewTargetsAreStream ? 'STRM 资源暂不支持智能调轴。' : (hasSelectedPreviewStreamTargets ? 'STRM 目标会跳过调轴，其余本地视频正常处理。' : '写入前会分析视频/字幕时间轴，可能占用 CPU 并造成短暂卡顿。')"
        >
          <template #activator="{ props: tooltipProps }">
            <div
              v-bind="tooltipProps"
              class="timeline-action"
            >
              <VSwitch
                :model-value="fixTimeline"
                color="primary"
                density="comfortable"
                hide-details
                :disabled="!timelineAvailable || allSelectedPreviewTargetsAreStream"
                :label="hasSelectedPreviewStreamTargets ? '智能调轴（STRM跳过）' : '智能调轴'"
                @update:model-value="$emit('update:fixTimeline', $event)"
              />
            </div>
          </template>
        </VTooltip>
        <VBtn
          v-if="hasPreviewItems"
          color="success"
          :disabled="!canApply"
          :loading="applying"
          @click="$emit('apply-upload')"
        >
          写入字幕
        </VBtn>
      </VCardActions>
      <VDivider />
      <VCardText>
        <div
          v-if="!hasPreviewItems"
          class="dropzone"
          :class="{ dragging }"
          @drop="$emit('drop', $event)"
          @dragover="$emit('dragover', $event)"
          @dragleave="$emit('dragleave', $event)"
        >
          <div class="dropzone-icon">SRT / ASS / ZIP / RAR / 7Z</div>
          <div class="dropzone-title">把字幕或压缩包拖到这里</div>
          <div class="dropzone-text">
            支持字幕文件、ZIP、RAR、7Z；RAR/7Z 需容器内解压器支持。
          </div>
          <VBtn
            color="primary"
            variant="flat"
            :disabled="preparing"
            :loading="preparing"
            @click="openFileDialog"
          >
            选择文件
          </VBtn>
          <input
            ref="fileInputRef"
            class="hidden-input"
            type="file"
            multiple
            accept=".srt,.ass,.ssa,.sbv,.sub,.vtt,.webvtt,.zip,.rar,.7z"
            @change="onPickFiles"
          >
        </div>

        <div v-if="!hasPreviewItems" class="support-row">
          <span :class="{ ok: rarPythonAvailable }">rarfile：{{ rarPythonAvailable ? '已安装' : '将由 requirements.txt 安装' }}</span>
          <span :class="{ ok: rarAvailable }">RAR 解压器：{{ rarAvailable ? archiveStatus.rar_tool || '可用' : '未检测到' }}</span>
          <span :class="{ ok: rarDependencyStatus.state === 'ready' }">
            处理方式：{{ rarDependencyModeLabel(archiveStatus.dependency_mode) }}
          </span>
          <button class="support-help" type="button" @click="$emit('open-rar-help')">
            RAR 不能解压？查看处理方式
          </button>
          <span :class="{ ok: timelineAvailable }">
            智能调轴：{{ timelineAvailable ? '可用' : `缺少 ${timelineMissing || '依赖'}` }}
          </span>
        </div>

        <div v-if="!hasPreviewItems && files.length" class="file-list">
          <div v-for="file in files" :key="`${file.name}-${file.size}`" class="file-row">
            <div>
              <strong>{{ file.name }}</strong>
              <span>{{ formatBytes(file.size) }}</span>
            </div>
            <VBtn size="small" variant="text" color="error" @click="$emit('remove-file', file)">移除</VBtn>
          </div>
        </div>

        <div v-if="hasPreviewItems" class="preview-list">
          <div class="preview-head">
            <div>
              <div class="section-kicker">字幕匹配</div>
              <h3>确认集数与输出文件名</h3>
            </div>
            <div class="batch-language">
              <VTextField
                :model-value="batchLanguageSuffix"
                label="批量语言后缀"
                placeholder="chi / eng / jpn"
                variant="outlined"
                density="comfortable"
                hide-details
                @update:model-value="$emit('update:batchLanguageSuffix', $event)"
                @keyup.enter="$emit('apply-batch-language-suffix')"
              />
              <VBtn
                variant="tonal"
                color="primary"
                :disabled="!batchLanguageSuffix.trim()"
                @click="$emit('apply-batch-language-suffix')"
              >
                应用到全部
              </VBtn>
            </div>
          </div>
          <div
            v-for="item in preview.items"
            :key="item.upload_id"
            class="preview-row"
            :class="{ disabled: item.selected === false }"
          >
            <VCheckbox
              :model-value="item.selected !== false"
              density="compact"
              hide-details
              @update:model-value="value => $emit('toggle-preview-item', item.upload_id, value)"
            />
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
              :disabled="item.selected === false"
              @update:model-value="value => $emit('update-preview-target', item.upload_id, value)"
            />
            <VTextField
              :model-value="item.language_suffix"
              label="语言后缀"
              variant="outlined"
              density="comfortable"
              hide-details
              :disabled="item.selected === false"
              @update:model-value="value => $emit('update-language-suffix', item.upload_id, value)"
            />
            <div class="output-name">
              <span>改名为</span>
              <strong>{{ item.output_name || buildOutputName(uploadTargets.find(target => target.id === item.target_id), item) || '待选择目标' }}</strong>
            </div>
          </div>
        </div>
      </VCardText>
    </VCard>
  </VDialog>
</template>

<style scoped>
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

.dialog-title p {
  margin: 4px 0 0;
  color: #687873;
  font-size: 12px;
  font-weight: 400;
}

.dialog-actions {
  padding: 12px 18px;
}

.dialog-actions-top {
  flex-wrap: wrap;
  gap: 8px;
  background: rgba(255, 250, 242, 0.96);
}

.timeline-action {
  display: flex;
  align-items: center;
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

.section-kicker {
  color: #8a6b3f;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.batch-language {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-width: min(100%, 360px);
}

.preview-row {
  display: grid;
  grid-template-columns: auto minmax(160px, 1fr) minmax(210px, 1fr) 116px minmax(180px, 1fr);
  gap: 10px;
  align-items: center;
  padding: 12px;
}

.preview-row.disabled {
  opacity: 0.58;
}

.subtitle-source strong,
.output-name strong {
  word-break: break-word;
}

@media (max-width: 900px) {
  .preview-row {
    grid-template-columns: 1fr;
  }

  .preview-head {
    display: grid;
  }

  .batch-language {
    grid-template-columns: 1fr;
  }

  .dialog-actions-top {
    align-items: stretch;
  }

  .dialog-actions-top .v-btn {
    flex: 1 1 auto;
  }
}
</style>
