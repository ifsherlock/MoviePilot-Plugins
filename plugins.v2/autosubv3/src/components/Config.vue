<script setup>
import { reactive, ref, watch } from 'vue'

const props = defineProps({
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
  context_window: 5,
  max_retries: 3,
  enable_merge: false,
  subtitle_output_mode: 'bilingual',
  enable_batch: true,
  batch_size: 20,
  parallel_workers: 10,
}

function normalizeInitialConfig(value = {}) {
  const merged = { ...defaultConfig, ...(value || {}) }
  merged.generation_mode = merged.generation_mode === 'fallback' ? 'fallback' : 'monitor'
  return merged
}

const config = reactive(normalizeInitialConfig(props.initialConfig))
const saving = ref(false)
const error = ref('')

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

function save() {
  saving.value = true
  error.value = ''
  try {
    emit('save', { ...config })
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

    <div class="config-shell">
      <VAlert v-if="error" class="mb-4" type="error" variant="tonal" density="compact" :text="error" />

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
        <div class="section-title">API 配置</div>
        <VRow>
          <VCol cols="12" md="6">
            <VSwitch v-model="config.openai_proxy" label="使用代理服务器" hide-details />
          </VCol>
          <VCol cols="12" md="6">
            <VSwitch v-model="config.compatible" label="兼容模式" hide-details />
          </VCol>
        </VRow>

        <VRow>
          <VCol cols="12" md="4">
            <VTextField v-model="config.openai_url" label="API URL" placeholder="https://api.siliconflow.cn" />
          </VCol>
          <VCol cols="12" md="4">
            <VTextField v-model="config.openai_key" label="API 密钥" type="password" placeholder="sk-xxx" />
          </VCol>
          <VCol cols="12" md="4">
            <VTextField v-model="config.openai_model" label="自定义模型" placeholder="inclusionAI/Ling-flash-2.0" />
          </VCol>
        </VRow>
      </section>
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

.config-section {
  margin-bottom: 20px;
}

.section-title {
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
</style>
