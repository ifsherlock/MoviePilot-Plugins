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
const rarHelpDialog = ref(false)
const copyMessage = ref('')
const copyError = ref('')
const localConfig = ref({
  enabled: false,
  show_sidebar_nav: true,
  online_providers: ['assrt', 'opensubtitles'],
  online_use_proxy: false,
  traditional_to_simplified: false,
  auto_search_on_transfer: false,
  auto_skip_chinese_media_on_transfer: true,
  auto_transfer_subtitle_strategy: 'online_then_ai_source',
  trust_transfer_history_paths: false,
  auto_multi_subtitle_mode: 'best',
  auto_subtitle_language_priority: ['bilingual', 'chi', 'cht', 'eng'],
  auto_subtitle_format_priority: ['.ass', '.srt', '.ssa', '.vtt'],
  auto_ass_to_srt_for_ai: true,
  timeline_max_offset_seconds: 120,
  timeline_min_offset_seconds: 0.2,
  timeline_vad_mode: 'webrtc',
  timeline_allow_risky_offset: false,
  subhd_url: 'https://subhd.tv',
  zimuku_url: 'https://zmk.pw',
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
  { title: '在线匹配优先，AI 来源兜底', value: 'online_then_ai_source' },
  { title: '只用在线匹配来源', value: 'online_source_only' },
  { title: '只用 AI 来源生成', value: 'ai_source_only' },
]

const autoMultiSubtitleModes = [
  { title: '按偏好选择最佳', value: 'best' },
  { title: '中文/双语全部入库', value: 'chinese_all' },
  { title: '全部入库', value: 'all' },
]

const autoLanguageItems = [
  { title: '双语', value: 'bilingual' },
  { title: '简中', value: 'chi' },
  { title: '繁中', value: 'cht' },
  { title: '英文', value: 'eng' },
  { title: '日文', value: 'jpn' },
  { title: '韩文', value: 'kor' },
]

const autoFormatItems = [
  { title: 'ASS', value: '.ass' },
  { title: 'SRT', value: '.srt' },
  { title: 'SSA', value: '.ssa' },
  { title: 'VTT', value: '.vtt' },
  { title: 'WebVTT', value: '.webvtt' },
  { title: 'SBV', value: '.sbv' },
  { title: 'SUB', value: '.sub' },
]

const timelineVadItems = [
  { title: 'WebRTC VAD（推荐）', value: 'webrtc' },
  { title: 'RMS 能量阈值（降级）', value: 'rms' },
]

const rarContainerInstallCommand = `docker exec -it moviepilot bash
apt-get update
apt-get install -y p7zip-full unrar-free`
const rarStaticInstallCommand = `curl -fsSLo /tmp/mp-7zz.sh \\
  https://raw.githubusercontent.com/ifsherlock/MoviePilot-Plugins/main/plugins.v2/subtitlemanualupload/scripts/install-static-7zz.sh
sudo bash /tmp/mp-7zz.sh

# 脚本默认优先使用清华/中科大 Gentoo distfiles 镜像下载 7zz。
# 如果自动检测不准，可直接指定 MoviePilot 宿主机映射目录：
sudo env MP_HOST_ROOT=/volume1/docker/moviepilot bash /tmp/mp-7zz.sh

# 如果需要指定下载源，可覆盖 DOWNLOAD_URL：
sudo env DOWNLOAD_URL=https://example.com/7zz.tar.xz bash /tmp/mp-7zz.sh

# 按脚本输出的实际路径添加到 MoviePilot volumes：
volumes:
  - /volume1/docker/moviepilot/tools/7zz:/usr/local/bin/7z:ro

# 重建或重启 MoviePilot 容器后验证：
docker exec moviepilot which 7z
docker exec moviepilot 7z i`
const rarHelpItems = [
  {
    badge: '方案一',
    title: '容器内临时安装',
    description: '适合临时测试，容器重建后可能失效。',
    button: '复制命令',
    copyLabel: '容器安装命令',
    command: rarContainerInstallCommand,
  },
  {
    badge: '方案二',
    title: '静态 7zz 下载并映射',
    description: '推荐长期使用。脚本默认优先使用清华/中科大镜像下载，会检测或提示输入 MoviePilot 宿主机目录，并设置 0755 执行权限。',
    button: '复制方案',
    copyLabel: '静态 7zz 安装映射方案',
    command: rarStaticInstallCommand,
  },
]

async function copyHelpText(text, label) {
  copyMessage.value = ''
  copyError.value = ''
  try {
    await navigator.clipboard.writeText(text)
    copyMessage.value = `${label}已复制`
  } catch (error) {
    copyError.value = `复制失败，请手动选择命令文本。${error?.message || ''}`.trim()
  }
}

function normalizeProviders(value) {
  const allowed = ['subhd', 'zimuku', 'assrt', 'opensubtitles']
  const providers = Array.isArray(value) ? value.filter(item => allowed.includes(item)) : []
  return providers.length ? Array.from(new Set(providers)) : ['assrt', 'opensubtitles']
}

function normalizeRootUrl(value, fallback) {
  const text = String(value || '').trim().replace(/\/+$/, '')
  return /^https?:\/\//i.test(text) ? text : fallback
}

function normalizeZimukuRootUrl(value) {
  const normalized = normalizeRootUrl(value, 'https://zmk.pw')
  return normalized === 'https://zimuku.org' ? 'https://zmk.pw' : normalized
}

function normalizePositiveNumber(value, fallback) {
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? number : fallback
}

function normalizeAutoStrategy(value) {
  const aliases = {
    search_first: 'online_then_ai_source',
    search_only: 'online_source_only',
    ai_only: 'ai_source_only',
    ai_first: 'ai_source_only',
  }
  const normalized = aliases[value] || value
  return autoStrategyItems.some(item => item.value === normalized)
    ? normalized
    : 'online_then_ai_source'
}

function normalizeList(value, allowed, fallback) {
  const raw = Array.isArray(value) ? value : String(value || '').split(/[\s,，/|]+/)
  const result = []
  raw.forEach(item => {
    const normalized = String(item || '').trim().toLowerCase()
    if (allowed.includes(normalized) && !result.includes(normalized)) {
      result.push(normalized)
    }
  })
  fallback.forEach(item => {
    if (!result.includes(item)) result.push(item)
  })
  return result
}

function normalizeConfig(input) {
  const assrtApiKey = String(input?.assrt_api_key || '').trim()
  const opensubtitlesApiKey = String(input?.opensubtitles_api_key || '').trim()
  const opensubtitlesUsername = String(input?.opensubtitles_username || '').trim()
  const opensubtitlesPassword = String(input?.opensubtitles_password || '').trim()
  const providers = normalizeProviders(input?.online_providers)
  const autoStrategy = normalizeAutoStrategy(input?.auto_transfer_subtitle_strategy)
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
    trust_transfer_history_paths: Boolean(input?.trust_transfer_history_paths),
    auto_multi_subtitle_mode: autoMultiSubtitleModes.some(item => item.value === input?.auto_multi_subtitle_mode)
      ? input.auto_multi_subtitle_mode
      : 'best',
    auto_subtitle_language_priority: normalizeList(
      input?.auto_subtitle_language_priority,
      autoLanguageItems.map(item => item.value),
      ['bilingual', 'chi', 'cht', 'eng'],
    ),
    auto_subtitle_format_priority: normalizeList(
      input?.auto_subtitle_format_priority,
      autoFormatItems.map(item => item.value),
      ['.ass', '.srt', '.ssa', '.vtt'],
    ),
    auto_ass_to_srt_for_ai: input?.auto_ass_to_srt_for_ai !== false,
    timeline_max_offset_seconds: Math.min(300, Math.max(1, Math.round(normalizePositiveNumber(input?.timeline_max_offset_seconds, 120)))),
    timeline_min_offset_seconds: normalizePositiveNumber(input?.timeline_min_offset_seconds, 0.2),
    timeline_vad_mode: timelineVadItems.some(item => item.value === input?.timeline_vad_mode) ? input.timeline_vad_mode : 'webrtc',
    timeline_allow_risky_offset: Boolean(input?.timeline_allow_risky_offset),
    subhd_url: normalizeRootUrl(input?.subhd_url, 'https://subhd.tv'),
    zimuku_url: normalizeZimukuRootUrl(input?.zimuku_url),
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
            <VSwitch
              v-model="localConfig.trust_transfer_history_paths"
              label="信任整理历史路径"
              color="warning"
              hint="CD2、网盘挂载、SMB 等慢路径可开启，刷新资源清单时不逐条访问文件。"
              persistent-hint
            />
            <VSelect
              v-model="localConfig.auto_transfer_subtitle_strategy"
              :items="autoStrategyItems"
              label="入库后字幕处理策略"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VSelect
              v-model="localConfig.auto_multi_subtitle_mode"
              :items="autoMultiSubtitleModes"
              label="自动多字幕处理"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VSelect
              v-model="localConfig.auto_subtitle_language_priority"
              :items="autoLanguageItems"
              label="语言优先级"
              variant="outlined"
              density="comfortable"
              multiple
              chips
              hint="默认：双语、简中、繁中、英文"
              persistent-hint
            />
            <VSelect
              v-model="localConfig.auto_subtitle_format_priority"
              :items="autoFormatItems"
              label="格式优先级"
              variant="outlined"
              density="comfortable"
              multiple
              chips
              hint="默认：ASS、SRT、SSA、VTT"
              persistent-hint
            />
            <VSwitch
              v-model="localConfig.auto_ass_to_srt_for_ai"
              label="英文 ASS 转临时 SRT 后提交 AI"
              color="info"
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
              placeholder="https://zmk.pw"
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
            <div>
              <div class="config-section-title">智能调轴</div>
              <p>控制写入前可接受的全局偏移范围；超过 120 秒通常意味着错集、错版本或整季包映射错误。</p>
            </div>
          </div>

          <div class="config-grid two-column">
            <VTextField
              v-model.number="localConfig.timeline_max_offset_seconds"
              label="智能调轴最大偏移秒数"
              type="number"
              min="1"
              max="300"
              suffix="秒"
              hint="默认 120；不建议超过 120 秒。超过 120 秒的手动操作会再次确认，自动入库不放行高风险结果。"
              persistent-hint
              variant="outlined"
              density="comfortable"
            />
            <VTextField
              v-model.number="localConfig.timeline_min_offset_seconds"
              label="最小应用阈值"
              type="number"
              min="0.1"
              step="0.1"
              suffix="秒"
              hint="低于该阈值时仅复制字幕，不做时间轴改写。"
              persistent-hint
              variant="outlined"
              density="comfortable"
            />
            <VSelect
              v-model="localConfig.timeline_vad_mode"
              :items="timelineVadItems"
              label="音频 VAD 模式"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VSwitch
              v-model="localConfig.timeline_allow_risky_offset"
              label="全局允许高风险偏移"
              color="warning"
              hint="不建议开启。开启后后端会允许 120 秒以上结果；手动操作仍会显示风险确认。"
              persistent-hint
            />
          </div>

          <VDivider class="my-5" />

          <div class="config-section">
            <div>
              <div class="config-section-title">RAR / 7Z 解压器</div>
              <p>RAR 和 7Z 都依赖容器内可执行解压器；宿主机静态 7zz 映射更适合长期使用。</p>
            </div>
            <VBtn
              color="primary"
              variant="tonal"
              prepend-icon="mdi-tools"
              @click="rarHelpDialog = true"
            >
              查看安装教程
            </VBtn>
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
            text="自动安装只适合临时测试；长期建议在宿主机把静态 7zz 放到 MoviePilot 部署目录的 tools/7zz，并映射为容器内 /usr/local/bin/7z。插件不会主动重启 Docker 容器。"
          />
        </VCardText>
      </VCard>
    </div>

    <VDialog v-model="rarHelpDialog" max-width="820">
      <VCard class="rar-help-dialog" rounded="xl">
        <VCardTitle class="dialog-title">
          <span>RAR / 7Z 解压器说明</span>
          <VBtn icon="mdi-close" variant="text" @click="rarHelpDialog = false" />
        </VCardTitle>
        <VDivider />
        <VCardText>
          <div class="rar-help-summary">
            <p><strong>说明：</strong><code>rarfile</code> 只是 Python 调用封装，不是独立解压器。</p>
            <p><strong>要求：</strong>MoviePilot 容器内需要能执行 <code>unrar</code>、<code>7z</code>、<code>7za</code>、<code>7zz</code> 或 <code>bsdtar</code>。</p>
            <p><strong>方案：</strong>临时测试可在容器内安装；长期使用推荐通过国内镜像下载宿主机静态 <code>7zz</code>，设置执行权限后映射到容器内 <code>/usr/local/bin/7z</code>。</p>
          </div>

          <div class="rar-help-list">
            <section
              v-for="item in rarHelpItems"
              :key="item.title"
              class="rar-help-row"
            >
              <div class="rar-help-row-head">
                <div class="rar-help-row-title">
                  <span class="rar-help-step">{{ item.badge }}</span>
                  <strong>{{ item.title }}</strong>
                </div>
                <VBtn
                  color="primary"
                  variant="flat"
                  size="small"
                  @click="copyHelpText(item.command, item.copyLabel)"
                >
                  {{ item.button }}
                </VBtn>
              </div>
              <p>{{ item.description }}</p>
              <div class="command-block">
                <pre>{{ item.command }}</pre>
              </div>
            </section>
          </div>

          <VAlert
            v-if="copyMessage"
            class="mt-4"
            type="success"
            variant="tonal"
            :text="copyMessage"
          />
          <VAlert
            v-else-if="copyError"
            class="mt-4"
            type="warning"
            variant="tonal"
            :text="copyError"
          />

          <VAlert
            class="mt-4"
            type="info"
            variant="tonal"
            text="插件不会主动重启 Docker 容器。映射文件后需要按你的部署方式重建或重启 MoviePilot 容器；安装或映射完成后，刷新插件状态即可重新检测。"
          />
        </VCardText>
      </VCard>
    </VDialog>
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

.dialog-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.rar-help-dialog {
  background: #fffaf2;
}

.rar-help-summary {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid rgba(91, 109, 100, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.64);
  color: #52635d;
  line-height: 1.7;
}

.rar-help-summary p {
  margin: 0;
}

.rar-help-summary code {
  padding: 1px 5px;
  border-radius: 6px;
  background: #efe6d8;
}

.rar-help-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.rar-help-row {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
}

.rar-help-row-head {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}

.rar-help-row-title {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.rar-help-step {
  padding: 3px 8px;
  border-radius: 999px;
  background: #efe6d8;
  color: #8a6b3f;
  font-size: 12px;
  font-weight: 900;
}

.command-block {
  min-width: 0;
}

.command-block pre {
  padding: 10px;
  margin: 0;
  overflow-x: auto;
  border-radius: 12px;
  background: #2f443d;
  color: #fff6e8;
  font-size: 12px;
  line-height: 1.5;
}

.rar-help-row p {
  margin: 0;
  color: #687873;
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 760px) {
  .config-grid.two-column {
    grid-template-columns: 1fr;
  }

  .config-section {
    align-items: stretch;
    flex-direction: column;
  }

  .rar-help-row-head {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
