<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['save', 'close'])
const configError = ref('')
const localConfig = ref({
  enabled: false,
  show_sidebar_nav: true,
  online_providers: ['assrt', 'opensubtitles'],
  online_use_proxy: false,
  traditional_to_simplified: false,
  auto_search_on_transfer: false,
  auto_skip_chinese_media_on_transfer: true,
  auto_transfer_subtitle_strategy: 'search_first',
  subhd_url: 'https://subhd.tv',
  zimuku_url: 'https://zimuku.org',
  assrt_url: 'https://2.assrt.net',
  assrt_api_key: '',
  assrt_api_url: 'https://api.assrt.net',
  opensubtitles_url: 'https://www.opensubtitles.com',
  opensubtitles_api_key: '',
  opensubtitles_api_url: 'https://api.opensubtitles.com/api/v1',
  opensubtitles_username: '',
  opensubtitles_password: '',
  ai_link_enabled: true,
  rar_dependency_mode: 'none',
  rar_tool_path: '/usr/local/bin/7z',
})

const onlineProviderItems = [
  { title: 'SubHD 中文字幕', value: 'subhd' },
  { title: 'Zimuku 中文字幕', value: 'zimuku' },
  { title: '射手网(伪，需 API Key)', value: 'assrt' },
  { title: 'OpenSubtitles 多语言字幕', value: 'opensubtitles' },
]

const rarDependencyModes = [
  { title: '不处理，仅检测', value: 'none' },
  { title: '加载插件时尝试容器内安装', value: 'container_install' },
  { title: '使用宿主机映射文件', value: 'mapped_binary' },
]

const autoStrategyItems = [
  { title: '搜索优先，AI 兜底', value: 'search_first' },
  { title: '只搜索匹配字幕', value: 'search_only' },
  { title: '只提交 AI 生成', value: 'ai_only' },
  { title: 'AI 优先，失败再搜索', value: 'ai_first' },
]

function normalizeProviders(value) {
  const allowed = ['subhd', 'zimuku', 'assrt', 'opensubtitles']
  const providers = Array.isArray(value) ? value.filter(item => allowed.includes(item)) : []
  return providers.length ? Array.from(new Set(providers)) : ['assrt', 'opensubtitles']
}

function normalizeRootUrl(value, fallback) {
  const text = String(value || '').trim().replace(/\/+$/, '')
  return /^https?:\/\//i.test(text) ? text : fallback
}

function normalizeConfig(input) {
  const assrtApiKey = String(input?.assrt_api_key || '').trim()
  const opensubtitlesApiKey = String(input?.opensubtitles_api_key || '').trim()
  const opensubtitlesUsername = String(input?.opensubtitles_username || '').trim()
  const opensubtitlesPassword = String(input?.opensubtitles_password || '').trim()
  const providers = normalizeProviders(input?.online_providers)
  const autoStrategy = autoStrategyItems.some(item => item.value === input?.auto_transfer_subtitle_strategy)
    ? input.auto_transfer_subtitle_strategy
    : 'search_first'
  if (assrtApiKey && !providers.includes('assrt')) {
    providers.push('assrt')
  }
  if (opensubtitlesApiKey && !providers.includes('opensubtitles')) {
    providers.push('opensubtitles')
  }
  return {
    enabled: Boolean(input?.enabled),
    show_sidebar_nav: input?.show_sidebar_nav !== false,
    online_providers: providers,
    online_use_proxy: Boolean(input?.online_use_proxy),
    online_proxy_migrated: true,
    traditional_to_simplified: Boolean(input?.traditional_to_simplified),
    auto_search_on_transfer: Boolean(input?.auto_search_on_transfer),
    auto_skip_chinese_media_on_transfer: input?.auto_skip_chinese_media_on_transfer !== false,
    auto_transfer_subtitle_strategy: autoStrategy,
    subhd_url: normalizeRootUrl(input?.subhd_url, 'https://subhd.tv'),
    zimuku_url: normalizeRootUrl(input?.zimuku_url, 'https://zimuku.org'),
    assrt_url: normalizeRootUrl(input?.assrt_url, 'https://2.assrt.net'),
    assrt_api_key: assrtApiKey,
    assrt_api_url: normalizeRootUrl(input?.assrt_api_url, 'https://api.assrt.net'),
    opensubtitles_url: normalizeRootUrl(input?.opensubtitles_url, 'https://www.opensubtitles.com'),
    opensubtitles_api_key: opensubtitlesApiKey,
    opensubtitles_api_url: normalizeRootUrl(input?.opensubtitles_api_url, 'https://api.opensubtitles.com/api/v1'),
    opensubtitles_username: opensubtitlesUsername,
    opensubtitles_password: opensubtitlesPassword,
    ai_link_enabled: input?.ai_link_enabled !== false,
    rar_dependency_mode: ['none', 'container_install', 'mapped_binary'].includes(input?.rar_dependency_mode)
      ? input.rar_dependency_mode
      : 'none',
    rar_tool_path: String(input?.rar_tool_path || '/usr/local/bin/7z').trim() || '/usr/local/bin/7z',
  }
}

function saveConfig() {
  const normalized = normalizeConfig(localConfig.value)
  if (normalized.opensubtitles_username.includes('@')) {
    configError.value = '请输入用户名而非邮箱！'
    return
  }
  configError.value = ''
  emit('save', normalized)
}

onMounted(() => {
  localConfig.value = normalizeConfig(props.initialConfig)
})
</script>

<template>
  <div class="subtitlemanualupload-config">
    <VToolbar density="comfortable" color="transparent">
      <div class="text-h6 ms-3">字幕匹配配置</div>
      <VSpacer />
      <VBtn icon="mdi-content-save" variant="text" color="primary" @click="saveConfig" />
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <div class="config-shell">
      <VCard rounded="xl" elevation="0" class="config-card">
        <VCardText>
          <VAlert
            v-if="configError"
            class="mb-4"
            type="error"
            variant="tonal"
            density="compact"
            :text="configError"
          />
          <div class="config-section">
            <div class="config-section-title">基础设置</div>
          </div>
          <div class="config-grid">
            <VSwitch
              v-model="localConfig.enabled"
              label="启用插件"
              color="primary"
              hide-details
            />
            <VSwitch
              v-model="localConfig.show_sidebar_nav"
              label="显示侧边栏入口"
              color="primary"
              hide-details
            />
            <VSwitch
              v-model="localConfig.ai_link_enabled"
              label="启用 AI 字幕联动"
              color="warning"
              hide-details
            />
            <VSwitch
              v-model="localConfig.traditional_to_simplified"
              label="写入前繁体转简体"
              color="success"
              hide-details
            />
            <VSwitch
              v-model="localConfig.auto_search_on_transfer"
              label="入库后自动搜索匹配字幕"
              color="info"
              hide-details
            />
            <VSwitch
              v-model="localConfig.auto_skip_chinese_media_on_transfer"
              label="入库自动处理跳过中文资源"
              color="success"
              hide-details
            />
            <VSelect
              v-model="localConfig.auto_transfer_subtitle_strategy"
              :items="autoStrategyItems"
              label="入库后字幕处理策略"
              variant="outlined"
              density="comfortable"
              hide-details
            />
          </div>

          <VDivider class="my-5" />

          <div class="config-section">
            <div>
              <div class="config-section-title">在线字幕搜索</div>
              <p>自动搜索支持 SubHD、Zimuku、射手网(伪) 和 OpenSubtitles；站点波动时仍可使用右侧手动搜索跳转。</p>
            </div>
          </div>

          <div class="config-grid two-column">
            <VSelect
              v-model="localConfig.online_providers"
              :items="onlineProviderItems"
              label="启用字幕源"
              variant="outlined"
              density="comfortable"
              multiple
              chips
              hide-details
            />
            <VSelect
              v-model="localConfig.online_use_proxy"
              :items="[
                { title: '不使用系统代理', value: false },
                { title: '使用 MoviePilot 系统代理', value: true },
              ]"
              label="API 请求代理"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VTextField
              v-model="localConfig.subhd_url"
              label="SubHD 站点地址"
              placeholder="https://subhd.tv"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VTextField
              v-model="localConfig.zimuku_url"
              label="Zimuku 站点地址"
              placeholder="https://zimuku.org"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VTextField
              v-model="localConfig.assrt_url"
              label="射手网(伪) 手动搜索地址"
              placeholder="https://2.assrt.net"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VTextField
              v-model="localConfig.assrt_api_url"
              label="射手网(伪) API 地址"
              placeholder="https://api.assrt.net"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VTextField
              v-model="localConfig.assrt_api_key"
              label="射手网(伪) API Key"
              placeholder="未填写时默认不启用伪射手自动搜索"
              variant="outlined"
              density="comfortable"
              type="password"
              autocomplete="new-password"
              hide-details
            />
            <VTextField
              v-model="localConfig.opensubtitles_url"
              label="OpenSubtitles 手动搜索地址"
              placeholder="https://www.opensubtitles.com"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VTextField
              v-model="localConfig.opensubtitles_api_url"
              label="OpenSubtitles API 地址"
              placeholder="https://api.opensubtitles.com/api/v1"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VTextField
              v-model="localConfig.opensubtitles_api_key"
              label="OpenSubtitles API Key"
              placeholder="用于搜索多语言字幕"
              variant="outlined"
              density="comfortable"
              type="password"
              autocomplete="new-password"
              hide-details
            />
            <VTextField
              v-model="localConfig.opensubtitles_username"
              label="OpenSubtitles 用户名（可选）"
              placeholder="下载时用于后台登录换取 token"
              variant="outlined"
              density="comfortable"
              autocomplete="username"
              :error="localConfig.opensubtitles_username.includes('@')"
              :error-messages="localConfig.opensubtitles_username.includes('@') ? '请输入用户名而非邮箱！' : ''"
            />
            <VTextField
              v-model="localConfig.opensubtitles_password"
              label="OpenSubtitles 密码（可选）"
              placeholder="下载时用于后台登录换取 token"
              variant="outlined"
              density="comfortable"
              type="password"
              autocomplete="new-password"
              hide-details
            />
          </div>

          <VAlert
            class="mt-4"
            type="info"
            variant="tonal"
            density="compact"
            text="OpenSubtitles 搜索需要 API Key；下载由插件使用用户名和密码后台登录换取 token。英文字幕结果可下载后提交给 AI 字幕生成翻译。"
          />

          <VDivider class="my-5" />

          <div class="config-section">
            <div class="config-section-title">RAR 解压器</div>
          </div>

          <div class="config-grid">
            <VSelect
              v-model="localConfig.rar_dependency_mode"
              :items="rarDependencyModes"
              label="RAR 解压器处理方式"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VTextField
              v-model="localConfig.rar_tool_path"
              label="容器内映射路径"
              placeholder="/usr/local/bin/7z"
              variant="outlined"
              density="comfortable"
              hide-details
            />
          </div>
          <VAlert
            class="mt-4"
            type="info"
            variant="tonal"
            text="RAR 自动安装只适合临时测试；长期建议在宿主机把静态 7zz 放到 MoviePilot 部署目录的 tools/7zz，并映射为容器内 /usr/local/bin/7z。插件不会主动重启 Docker 容器。"
          />
        </VCardText>
      </VCard>
    </div>
  </div>
</template>

<style scoped>
.config-shell {
  padding: 20px;
}

.config-card {
  border: 1px solid rgba(127, 151, 185, 0.18);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(12px);
  box-shadow: 0 18px 50px rgba(30, 63, 108, 0.08);
}

.config-grid {
  display: grid;
  gap: 16px;
}

.config-grid.two-column {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.config-section {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.config-section-title {
  color: #24362f;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.config-section p {
  margin: 4px 0 0;
  color: #687873;
  font-size: 12px;
}

.config-switch-line {
  min-height: 48px;
}

@media (max-width: 760px) {
  .config-grid.two-column {
    grid-template-columns: 1fr;
  }
}
</style>
