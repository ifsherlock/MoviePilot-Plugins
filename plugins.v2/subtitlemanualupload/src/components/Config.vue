<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['save', 'close'])
const localConfig = ref({
  enabled: false,
  show_sidebar_nav: true,
  online_providers: ['subhd', 'zimuku'],
  online_engine: 'cloakbrowser',
  online_use_proxy: false,
  subhd_url: 'https://subhd.tv',
  zimuku_url: 'https://zimuku.org',
  assrt_url: 'https://2.assrt.net',
  assrt_api_key: '',
  assrt_api_url: 'https://api.assrt.net',
  ai_link_enabled: true,
  rar_dependency_mode: 'none',
  rar_tool_path: '/usr/local/bin/7z',
})

const onlineProviderItems = [
  { title: 'SubHD', value: 'subhd' },
  { title: 'Zimuku', value: 'zimuku' },
  { title: '射手网(伪，需 API Key)', value: 'assrt' },
]

const onlineEngineItems = [
  { title: 'CloakBrowser（默认）', value: 'cloakbrowser' },
  { title: 'MoviePilot 浏览器仿真 / FlareSolverr', value: 'mp_browser' },
]

const rarDependencyModes = [
  { title: '不处理，仅检测', value: 'none' },
  { title: '加载插件时尝试容器内安装', value: 'container_install' },
  { title: '使用宿主机映射文件', value: 'mapped_binary' },
]

function normalizeProviders(value) {
  const allowed = ['subhd', 'zimuku', 'assrt']
  const providers = Array.isArray(value) ? value.filter(item => allowed.includes(item)) : []
  return providers.length ? Array.from(new Set(providers)) : ['subhd', 'zimuku']
}

function normalizeRootUrl(value, fallback) {
  const text = String(value || '').trim().replace(/\/+$/, '')
  return /^https?:\/\//i.test(text) ? text : fallback
}

function normalizeConfig(input) {
  return {
    enabled: Boolean(input?.enabled),
    show_sidebar_nav: input?.show_sidebar_nav !== false,
    online_providers: normalizeProviders(input?.online_providers),
    online_engine: ['cloakbrowser', 'mp_browser'].includes(input?.online_engine)
      ? input.online_engine
      : 'cloakbrowser',
    online_use_proxy: Boolean(input?.online_use_proxy),
    online_proxy_migrated: true,
    subhd_url: normalizeRootUrl(input?.subhd_url, 'https://subhd.tv'),
    zimuku_url: normalizeRootUrl(input?.zimuku_url, 'https://zimuku.org'),
    assrt_url: normalizeRootUrl(input?.assrt_url, 'https://2.assrt.net'),
    assrt_api_key: String(input?.assrt_api_key || '').trim(),
    assrt_api_url: normalizeRootUrl(input?.assrt_api_url, 'https://api.assrt.net'),
    ai_link_enabled: input?.ai_link_enabled !== false,
    rar_dependency_mode: ['none', 'container_install', 'mapped_binary'].includes(input?.rar_dependency_mode)
      ? input.rar_dependency_mode
      : 'none',
    rar_tool_path: String(input?.rar_tool_path || '/usr/local/bin/7z').trim() || '/usr/local/bin/7z',
  }
}

function saveConfig() {
  emit('save', normalizeConfig(localConfig.value))
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
          </div>

          <VDivider class="my-5" />

          <div class="config-section">
            <div>
              <div class="config-section-title">在线字幕搜索</div>
              <p>维护字幕站根地址；代理默认关闭，由容器当前网络环境决定。</p>
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
              v-model="localConfig.online_engine"
              :items="onlineEngineItems"
              label="在线搜索引擎"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VSwitch
              v-model="localConfig.online_use_proxy"
              class="config-switch-line"
              label="在线搜索使用 MoviePilot 系统代理（默认关闭）"
              color="primary"
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
              label="射手网(伪) 站点地址"
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
          </div>

          <VAlert
            class="mt-4"
            type="info"
            variant="tonal"
            density="compact"
            text="站点地址只填写根地址；射手网(伪) 默认不启用，填写 API Key 后可勾选并优先使用官方 API。"
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
