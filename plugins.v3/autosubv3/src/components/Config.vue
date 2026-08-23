<script setup>
import { computed, reactive, ref, watch } from 'vue'
import ApiEndpointSettings from './config/ApiEndpointSettings.vue'

const props = defineProps({
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'AutoSubv3',
  },
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['save', 'close', 'switch'])

const defaultConfig = {
  enabled: false,
  clear_history: false,
  send_notify: false,
  listen_transfer_event: true,
  generation_mode: 'monitor',
  process_new_only: true,
  path_whitelist: '',
  run_now: false,
  path_list: '',
  file_size: '10',
  translate_preference: 'english_first',
  translate_zh: true,
  enable_asr: true,
  auto_detect_language: false,
  skip_chinese: false,
  max_segment_duration: 8,
  max_segment_chars: 50,
  faster_whisper_model: 'base',
  proxy: true,
  openai_proxy: false,
  compatible: false,
  openai_url: 'https://api.siliconflow.cn',
  openai_key: '',
  openai_model: 'inclusionAI/Ling-flash-2.0',
  openai_endpoints: [],
  openai_active_endpoint: '',
  openai_fallback_enabled: true,
  context_window: 5,
  max_retries: 3,
  enable_merge: false,
  subtitle_output_mode: 'bilingual',
  enable_batch: true,
  batch_size: 20,
  parallel_workers: 10,
}

function normalizeModelValue(value) {
  if (typeof value === 'string') {
    const text = value.trim()
    if (text === '[object Object]') return ''
    if (text.startsWith('{') || text.startsWith('[')) {
      try {
        return normalizeModelValue(JSON.parse(text))
      } catch {
        const match = text.match(/['"](?:value|id|model|title)['"]\s*:\s*['"]([^'"]+)['"]/);
        if (match) return match[1].trim()
      }
    }
    return text
  }
  if (!value || typeof value !== 'object') return ''
  return String(value.value || value.id || value.model || value.title || '').trim()
}

function normalizeInitialConfig(value = {}) {
  const merged = { ...defaultConfig, ...(value || {}) }
  merged.generation_mode = merged.generation_mode === 'fallback' ? 'fallback' : 'monitor'
  const rawEndpoints = Array.isArray(merged.openai_endpoints) ? merged.openai_endpoints : []
  merged.openai_endpoints = rawEndpoints.length
    ? rawEndpoints.map((item, index) => ({
        id: item.id || `endpoint-${index + 1}`,
        name: item.name || `API 线路 ${index + 1}`,
        api_url: item.api_url || item.openai_url || 'https://api.openai.com',
        api_key: item.api_key || item.openai_key || '',
        model: normalizeModelValue(item.model || item.openai_model),
        use_proxy: Boolean(item.use_proxy ?? item.openai_proxy),
        compatible: Boolean(item.compatible),
        enabled: item.enabled !== false,
      }))
    : [{
        id: 'default',
        name: '默认线路',
        api_url: merged.openai_url,
        api_key: merged.openai_key,
        model: normalizeModelValue(merged.openai_model),
        use_proxy: Boolean(merged.openai_proxy),
        compatible: Boolean(merged.compatible),
        enabled: true,
      }]
  const activeExists = merged.openai_endpoints.some(item => (
    item.id === merged.openai_active_endpoint && item.enabled
  ))
  if (!activeExists) {
    merged.openai_active_endpoint = merged.openai_endpoints.find(item => item.enabled)?.id || merged.openai_endpoints[0]?.id || ''
  }
  return merged
}

const config = reactive(normalizeInitialConfig(props.initialConfig))
const saving = ref(false)
const error = ref('')
const activeTab = ref('basic')
const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoSubv3'}`)

const whisperModels = [
  { title: 'tiny', value: 'tiny' },
  { title: 'base', value: 'base' },
  { title: 'small', value: 'small' },
  { title: 'medium', value: 'medium' },
  { title: 'large-v3', value: 'large-v3' },
  { title: 'large-v3-turbo', value: 'deepdml/faster-whisper-large-v3-turbo-ct2' },
]
const outputModes = [
  { title: '双语字幕（翻译+原文）', value: 'bilingual' },
  { title: '纯中文字幕', value: 'chinese_only' },
]
const preferences = [
  { title: '仅英文', value: 'english_only' },
  { title: '英文优先', value: 'english_first' },
  { title: '原音优先', value: 'origin_first' },
]
watch(
  () => props.initialConfig,
  (value) => {
    Object.assign(config, normalizeInitialConfig(value))
  },
)

function updateEndpoints(value) {
  config.openai_endpoints = Array.isArray(value)
    ? value.map(item => ({ ...item, model: normalizeModelValue(item.model) }))
    : []
  const active = config.openai_endpoints.find(item => item.id === config.openai_active_endpoint && item.enabled)
  if (!active) {
    config.openai_active_endpoint = config.openai_endpoints.find(item => item.enabled)?.id || ''
  }
}

function syncLegacyApiFields() {
  const active = config.openai_endpoints.find(item => item.id === config.openai_active_endpoint && item.enabled)
    || config.openai_endpoints.find(item => item.enabled)
  if (!active) return
  active.model = normalizeModelValue(active.model)
  config.openai_active_endpoint = active.id
  config.openai_url = active.api_url
  config.openai_key = active.api_key
  config.openai_model = active.model
  config.openai_proxy = Boolean(active.use_proxy)
  config.compatible = Boolean(active.compatible)
}

function save() {
  saving.value = true
  error.value = ''
  try {
    syncLegacyApiFields()
    emit('save', {
      ...config,
      openai_endpoints: config.openai_endpoints.map(item => ({ ...item })),
    })
  } catch (err) {
    error.value = err?.message || '保存配置失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="autosub-config">
    <VToolbar density="comfortable" color="transparent">
      <div class="text-h6 ms-3">AI字幕生成配置</div>
      <VSpacer />
      <VBtn variant="text" prepend-icon="mdi-format-list-bulleted" @click="emit('switch')">查看任务</VBtn>
      <VBtn color="primary" variant="tonal" prepend-icon="mdi-content-save" :loading="saving" @click="save">保存</VBtn>
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <VTabs v-model="activeTab" class="config-tabs" color="primary" density="comfortable">
      <VTab value="basic" prepend-icon="mdi-tune-variant">基础设置</VTab>
      <VTab value="api" prepend-icon="mdi-api">AI API</VTab>
    </VTabs>
    <VDivider />

    <div class="config-shell">
      <VAlert v-if="error" class="mb-4" type="error" variant="tonal" density="compact" :text="error" />

      <VWindow v-model="activeTab">
        <VWindowItem value="basic">
          <section class="config-section">
        <div class="section-title">基础设置</div>
        <VRow>
          <VCol cols="12" md="6">
            <VSwitch
              v-model="config.generation_mode"
              label="启用独立入库监控"
              true-value="monitor"
              false-value="fallback"
              hint="关闭后仍可接收字幕匹配联动任务和手动任务"
              persistent-hint
            />
          </VCol>
          <VCol cols="12" md="3">
            <VSwitch v-model="config.enabled" label="启用插件" color="primary" hide-details />
          </VCol>
          <VCol cols="12" md="3">
            <VSwitch v-model="config.send_notify" label="发送通知" hide-details />
          </VCol>
        </VRow>

        <VRow>
          <VCol cols="12" md="3">
            <VSwitch v-model="config.clear_history" label="清理历史记录" hide-details />
          </VCol>
          <VCol cols="12" md="3">
            <VSwitch v-model="config.process_new_only" label="仅处理新增视频" hide-details />
          </VCol>
          <VCol cols="12" md="3">
            <VSwitch v-model="config.run_now" label="手动执行一次" color="secondary" hide-details />
          </VCol>
          <VCol cols="12" md="3">
            <VSwitch v-model="config.translate_zh" label="外语翻译成中文" hide-details />
          </VCol>
          <VCol cols="12" md="3">
            <VSwitch v-model="config.skip_chinese" label="中文视频不翻译" hide-details />
          </VCol>
          <VCol cols="12" md="3">
            <VSwitch v-model="config.enable_asr" label="允许 ASR 生成字幕" hide-details />
          </VCol>
        </VRow>
          </section>

      <section class="config-section">
        <div class="section-title">翻译参数</div>
        <VRow>
          <VCol cols="12" md="4">
            <VTextField v-model="config.context_window" label="上下文窗口大小" placeholder="5" />
          </VCol>
          <VCol cols="12" md="4">
            <VTextField v-model="config.max_retries" label="LLM 请求重试次数" placeholder="3" />
          </VCol>
          <VCol cols="12" md="4">
            <VSwitch v-model="config.enable_batch" label="启用批量翻译" hide-details />
          </VCol>
        </VRow>

        <VRow>
          <VCol cols="12" md="6">
            <VTextField v-model="config.batch_size" label="每批翻译行数" placeholder="20（建议不超过30）" />
          </VCol>
          <VCol cols="12" md="6">
            <VTextField v-model="config.parallel_workers" label="并发线程数" placeholder="10" />
          </VCol>
        </VRow>
          </section>

      <section class="config-section">
        <div class="section-title">Whisper 与输出</div>
        <VRow>
          <VCol cols="12" md="6">
            <VSelect
              v-model="config.faster_whisper_model"
              :items="whisperModels"
              label="Whisper 模型"
              hint="模型越大效果越好，耗时越久"
              persistent-hint
            />
          </VCol>
          <VCol cols="12" md="6">
            <VSelect v-model="config.subtitle_output_mode" :items="outputModes" label="字幕输出模式" />
          </VCol>
        </VRow>

        <VRow>
          <VCol cols="12" md="4">
            <VTextField v-model="config.max_segment_duration" label="每段字幕最大时长（秒）" placeholder="8" />
          </VCol>
          <VCol cols="12" md="4">
            <VTextField v-model="config.max_segment_chars" label="每段字幕最大字符数" placeholder="50" />
          </VCol>
          <VCol cols="12" md="4">
            <VTextField v-model="config.file_size" label="文件最小大小（MB）" placeholder="10" />
          </VCol>
        </VRow>

        <VRow>
          <VCol cols="12" md="6">
            <VSelect v-model="config.translate_preference" :items="preferences" label="字幕源语言偏好" />
          </VCol>
          <VCol cols="12" md="3">
            <VSwitch v-model="config.auto_detect_language" label="自动检测语言" hide-details />
          </VCol>
          <VCol cols="12" md="3">
            <VSwitch v-model="config.proxy" label="使用代理下载模型" hide-details />
          </VCol>
        </VRow>
          </section>

      <section class="config-section">
        <div class="section-title">路径</div>
        <VRow>
          <VCol cols="12">
            <VTextarea
              v-model="config.path_whitelist"
              label="监控路径（每行一个）"
              :rows="3"
              placeholder="/mnt/media/movies&#10;/downloads"
              hint="目录变化时自动触发字幕生成"
              persistent-hint
            />
          </VCol>
          <VCol cols="12">
            <VTextarea
              v-model="config.path_list"
              label="媒体路径（手动执行时使用）"
              :rows="3"
              placeholder="绝对路径，每行一个，支持文件和文件夹"
            />
          </VCol>
        </VRow>
          </section>
        </VWindowItem>

        <VWindowItem value="api">
          <ApiEndpointSettings
            :api="api"
            :plugin-base="pluginBase"
            :endpoints="config.openai_endpoints"
            :active-endpoint="config.openai_active_endpoint"
            :fallback-enabled="config.openai_fallback_enabled"
            @update:endpoints="updateEndpoints"
            @update:active-endpoint="config.openai_active_endpoint = $event"
            @update:fallback-enabled="config.openai_fallback_enabled = $event"
          />
        </VWindowItem>
      </VWindow>

      <div class="config-footer">
        <VBtn variant="text" prepend-icon="mdi-format-list-bulleted" @click="emit('switch')">查看任务</VBtn>
        <VSpacer />
        <VBtn variant="text" @click="emit('close')">关闭</VBtn>
        <VBtn color="primary" prepend-icon="mdi-content-save" :loading="saving" @click="save">保存</VBtn>
      </div>
    </div>

  </div>
</template>

<style scoped>
.autosub-config {
  background: rgb(var(--v-theme-background));
}

.config-shell {
  padding: 18px;
}

.config-tabs {
  padding-inline: 10px;
}

.config-section {
  margin-bottom: 20px;
}

.section-title {
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}

.config-footer {
  align-items: center;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  display: flex;
  gap: 10px;
  padding-top: 16px;
}
</style>
