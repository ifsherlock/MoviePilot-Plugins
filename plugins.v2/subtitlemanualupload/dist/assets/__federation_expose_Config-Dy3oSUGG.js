import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString} = await importShared('vue');


const _hoisted_1 = { class: "subtitlemanualupload-config" };
const _hoisted_2 = { class: "config-shell" };
const _hoisted_3 = { class: "config-grid" };
const _hoisted_4 = { class: "config-grid two-column" };
const _hoisted_5 = { class: "config-grid two-column" };
const _hoisted_6 = { class: "config-section" };
const _hoisted_7 = { class: "config-grid" };
const _hoisted_8 = { class: "rar-help-list" };
const _hoisted_9 = { class: "rar-help-row-head" };
const _hoisted_10 = { class: "rar-help-row-title" };
const _hoisted_11 = { class: "rar-help-step" };
const _hoisted_12 = { class: "command-block" };

const {onMounted,ref} = await importShared('vue');


const rarContainerInstallCommand = `docker exec -it moviepilot bash
apt-get update
apt-get install -y p7zip-full unrar-free`;
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
docker exec moviepilot 7z i`;

const _sfc_main = {
  __name: 'Config',
  props: {
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
},
  emits: ['save', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;
const configError = ref('');
const rarHelpDialog = ref(false);
const copyMessage = ref('');
const copyError = ref('');
const localConfig = ref({
  enabled: false,
  show_sidebar_nav: true,
  online_providers: ['assrt', 'opensubtitles'],
  online_use_proxy: false,
  traditional_to_simplified: false,
  auto_search_on_transfer: false,
  auto_skip_chinese_media_on_transfer: true,
  auto_transfer_subtitle_strategy: 'online_then_ai_source',
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
});

const onlineProviderItems = [
  { title: 'SubHD 中文字幕', value: 'subhd' },
  { title: 'Zimuku 中文字幕', value: 'zimuku' },
  { title: '射手网(伪，需 API Key)', value: 'assrt' },
  { title: 'OpenSubtitles 多语言字幕', value: 'opensubtitles' },
];

const rarDependencyModes = [
  { title: '不处理，仅检测', value: 'none' },
  { title: '加载插件时尝试容器内安装', value: 'container_install' },
  { title: '使用宿主机映射文件', value: 'mapped_binary' },
];

const autoStrategyItems = [
  { title: '在线匹配优先，AI 来源兜底', value: 'online_then_ai_source' },
  { title: '只用在线匹配来源', value: 'online_source_only' },
  { title: '只用 AI 来源生成', value: 'ai_source_only' },
];

const autoMultiSubtitleModes = [
  { title: '按偏好选择最佳', value: 'best' },
  { title: '中文/双语全部入库', value: 'chinese_all' },
  { title: '全部入库', value: 'all' },
];

const autoLanguageItems = [
  { title: '双语', value: 'bilingual' },
  { title: '简中', value: 'chi' },
  { title: '繁中', value: 'cht' },
  { title: '英文', value: 'eng' },
  { title: '日文', value: 'jpn' },
  { title: '韩文', value: 'kor' },
];

const autoFormatItems = [
  { title: 'ASS', value: '.ass' },
  { title: 'SRT', value: '.srt' },
  { title: 'SSA', value: '.ssa' },
  { title: 'VTT', value: '.vtt' },
  { title: 'WebVTT', value: '.webvtt' },
  { title: 'SBV', value: '.sbv' },
  { title: 'SUB', value: '.sub' },
];

const timelineVadItems = [
  { title: 'WebRTC VAD（推荐）', value: 'webrtc' },
  { title: 'RMS 能量阈值（降级）', value: 'rms' },
];

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
];

async function copyHelpText(text, label) {
  copyMessage.value = '';
  copyError.value = '';
  try {
    await navigator.clipboard.writeText(text);
    copyMessage.value = `${label}已复制`;
  } catch (error) {
    copyError.value = `复制失败，请手动选择命令文本。${error?.message || ''}`.trim();
  }
}

function normalizeProviders(value) {
  const allowed = ['subhd', 'zimuku', 'assrt', 'opensubtitles'];
  const providers = Array.isArray(value) ? value.filter(item => allowed.includes(item)) : [];
  return providers.length ? Array.from(new Set(providers)) : ['assrt', 'opensubtitles']
}

function normalizeRootUrl(value, fallback) {
  const text = String(value || '').trim().replace(/\/+$/, '');
  return /^https?:\/\//i.test(text) ? text : fallback
}

function normalizeZimukuRootUrl(value) {
  const normalized = normalizeRootUrl(value, 'https://zmk.pw');
  return normalized === 'https://zimuku.org' ? 'https://zmk.pw' : normalized
}

function normalizePositiveNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : fallback
}

function normalizeAutoStrategy(value) {
  const aliases = {
    search_first: 'online_then_ai_source',
    search_only: 'online_source_only',
    ai_only: 'ai_source_only',
    ai_first: 'ai_source_only',
  };
  const normalized = aliases[value] || value;
  return autoStrategyItems.some(item => item.value === normalized)
    ? normalized
    : 'online_then_ai_source'
}

function normalizeList(value, allowed, fallback) {
  const raw = Array.isArray(value) ? value : String(value || '').split(/[\s,，/|]+/);
  const result = [];
  raw.forEach(item => {
    const normalized = String(item || '').trim().toLowerCase();
    if (allowed.includes(normalized) && !result.includes(normalized)) {
      result.push(normalized);
    }
  });
  fallback.forEach(item => {
    if (!result.includes(item)) result.push(item);
  });
  return result
}

function normalizeConfig(input) {
  const assrtApiKey = String(input?.assrt_api_key || '').trim();
  const opensubtitlesApiKey = String(input?.opensubtitles_api_key || '').trim();
  const opensubtitlesUsername = String(input?.opensubtitles_username || '').trim();
  const opensubtitlesPassword = String(input?.opensubtitles_password || '').trim();
  const providers = normalizeProviders(input?.online_providers);
  const autoStrategy = normalizeAutoStrategy(input?.auto_transfer_subtitle_strategy);
  if (assrtApiKey && !providers.includes('assrt')) {
    providers.push('assrt');
  }
  if (opensubtitlesApiKey && !providers.includes('opensubtitles')) {
    providers.push('opensubtitles');
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
  const normalized = normalizeConfig(localConfig.value);
  if (normalized.opensubtitles_username.includes('@')) {
    configError.value = '请输入用户名而非邮箱！';
    return
  }
  configError.value = '';
  emit('save', normalized);
}

onMounted(() => {
  localConfig.value = normalizeConfig(props.initialConfig);
});

return (_ctx, _cache) => {
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      color: "transparent"
    }, {
      default: _withCtx(() => [
        _cache[33] || (_cache[33] = _createElementVNode("div", { class: "text-h6 ms-3" }, "字幕匹配配置", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          icon: "mdi-content-save",
          variant: "text",
          color: "primary",
          onClick: saveConfig
        }),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          onClick: _cache[0] || (_cache[0] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_2, [
      _createVNode(_component_VCard, {
        rounded: "xl",
        elevation: "0",
        class: "config-card"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardText, null, {
            default: _withCtx(() => [
              (configError.value)
                ? (_openBlock(), _createBlock(_component_VAlert, {
                    key: 0,
                    class: "mb-4",
                    type: "error",
                    variant: "tonal",
                    density: "compact",
                    text: configError.value
                  }, null, 8, ["text"]))
                : _createCommentVNode("", true),
              _cache[36] || (_cache[36] = _createElementVNode("div", { class: "config-section" }, [
                _createElementVNode("div", { class: "config-section-title" }, "基础设置")
              ], -1)),
              _createElementVNode("div", _hoisted_3, [
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.enabled,
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((localConfig.value.enabled) = $event)),
                  label: "启用插件",
                  color: "primary",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.show_sidebar_nav,
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((localConfig.value.show_sidebar_nav) = $event)),
                  label: "显示侧边栏入口",
                  color: "primary",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.ai_link_enabled,
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((localConfig.value.ai_link_enabled) = $event)),
                  label: "启用 AI 字幕联动",
                  color: "warning",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.traditional_to_simplified,
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((localConfig.value.traditional_to_simplified) = $event)),
                  label: "写入前繁体转简体",
                  color: "success",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.auto_search_on_transfer,
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((localConfig.value.auto_search_on_transfer) = $event)),
                  label: "入库后自动搜索匹配字幕",
                  color: "info",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.auto_skip_chinese_media_on_transfer,
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((localConfig.value.auto_skip_chinese_media_on_transfer) = $event)),
                  label: "入库自动处理跳过中文资源",
                  color: "success",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.auto_transfer_subtitle_strategy,
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((localConfig.value.auto_transfer_subtitle_strategy) = $event)),
                  items: autoStrategyItems,
                  label: "入库后字幕处理策略",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.auto_multi_subtitle_mode,
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((localConfig.value.auto_multi_subtitle_mode) = $event)),
                  items: autoMultiSubtitleModes,
                  label: "自动多字幕处理",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.auto_subtitle_language_priority,
                  "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((localConfig.value.auto_subtitle_language_priority) = $event)),
                  items: autoLanguageItems,
                  label: "语言优先级",
                  variant: "outlined",
                  density: "comfortable",
                  multiple: "",
                  chips: "",
                  hint: "默认：双语、简中、繁中、英文",
                  "persistent-hint": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.auto_subtitle_format_priority,
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((localConfig.value.auto_subtitle_format_priority) = $event)),
                  items: autoFormatItems,
                  label: "格式优先级",
                  variant: "outlined",
                  density: "comfortable",
                  multiple: "",
                  chips: "",
                  hint: "默认：ASS、SRT、SSA、VTT",
                  "persistent-hint": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.auto_ass_to_srt_for_ai,
                  "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((localConfig.value.auto_ass_to_srt_for_ai) = $event)),
                  label: "英文 ASS 转临时 SRT 后提交 AI",
                  color: "info",
                  "hide-details": ""
                }, null, 8, ["modelValue"])
              ]),
              _createVNode(_component_VDivider, { class: "my-5" }),
              _cache[37] || (_cache[37] = _createElementVNode("div", { class: "config-section" }, [
                _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "config-section-title" }, "在线字幕搜索"),
                  _createElementVNode("p", null, "自动搜索支持 SubHD、Zimuku、射手网(伪) 和 OpenSubtitles；站点波动时仍可使用右侧手动搜索跳转。")
                ])
              ], -1)),
              _createElementVNode("div", _hoisted_4, [
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.online_providers,
                  "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((localConfig.value.online_providers) = $event)),
                  items: onlineProviderItems,
                  label: "启用字幕源",
                  variant: "outlined",
                  density: "comfortable",
                  multiple: "",
                  chips: "",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.online_use_proxy,
                  "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((localConfig.value.online_use_proxy) = $event)),
                  items: [
                { title: '不使用系统代理', value: false },
                { title: '使用 MoviePilot 系统代理', value: true },
              ],
                  label: "API 请求代理",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.subhd_url,
                  "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((localConfig.value.subhd_url) = $event)),
                  label: "SubHD 站点地址",
                  placeholder: "https://subhd.tv",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.zimuku_url,
                  "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((localConfig.value.zimuku_url) = $event)),
                  label: "Zimuku 站点地址",
                  placeholder: "https://zmk.pw",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.assrt_url,
                  "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((localConfig.value.assrt_url) = $event)),
                  label: "射手网(伪) 手动搜索地址",
                  placeholder: "https://2.assrt.net",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.assrt_api_url,
                  "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((localConfig.value.assrt_api_url) = $event)),
                  label: "射手网(伪) API 地址",
                  placeholder: "https://api.assrt.net",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.assrt_api_key,
                  "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((localConfig.value.assrt_api_key) = $event)),
                  label: "射手网(伪) API Key",
                  placeholder: "未填写时默认不启用伪射手自动搜索",
                  variant: "outlined",
                  density: "comfortable",
                  type: "password",
                  autocomplete: "new-password",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.opensubtitles_url,
                  "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((localConfig.value.opensubtitles_url) = $event)),
                  label: "OpenSubtitles 手动搜索地址",
                  placeholder: "https://www.opensubtitles.com",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.opensubtitles_api_url,
                  "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((localConfig.value.opensubtitles_api_url) = $event)),
                  label: "OpenSubtitles API 地址",
                  placeholder: "https://api.opensubtitles.com/api/v1",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.opensubtitles_api_key,
                  "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((localConfig.value.opensubtitles_api_key) = $event)),
                  label: "OpenSubtitles API Key",
                  placeholder: "用于搜索多语言字幕",
                  variant: "outlined",
                  density: "comfortable",
                  type: "password",
                  autocomplete: "new-password",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.opensubtitles_username,
                  "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((localConfig.value.opensubtitles_username) = $event)),
                  label: "OpenSubtitles 用户名（可选）",
                  placeholder: "下载时用于后台登录换取 token",
                  variant: "outlined",
                  density: "comfortable",
                  autocomplete: "username",
                  error: localConfig.value.opensubtitles_username.includes('@'),
                  "error-messages": localConfig.value.opensubtitles_username.includes('@') ? '请输入用户名而非邮箱！' : ''
                }, null, 8, ["modelValue", "error", "error-messages"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.opensubtitles_password,
                  "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((localConfig.value.opensubtitles_password) = $event)),
                  label: "OpenSubtitles 密码（可选）",
                  placeholder: "下载时用于后台登录换取 token",
                  variant: "outlined",
                  density: "comfortable",
                  type: "password",
                  autocomplete: "new-password",
                  "hide-details": ""
                }, null, 8, ["modelValue"])
              ]),
              _createVNode(_component_VAlert, {
                class: "mt-4",
                type: "info",
                variant: "tonal",
                density: "compact",
                text: "OpenSubtitles 搜索需要 API Key；下载由插件使用用户名和密码后台登录换取 token。英文字幕结果可下载后提交给 AI 字幕生成翻译。"
              }),
              _createVNode(_component_VDivider, { class: "my-5" }),
              _cache[38] || (_cache[38] = _createElementVNode("div", { class: "config-section" }, [
                _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "config-section-title" }, "智能调轴"),
                  _createElementVNode("p", null, "控制写入前可接受的全局偏移范围；超过 120 秒通常意味着错集、错版本或整季包映射错误。")
                ])
              ], -1)),
              _createElementVNode("div", _hoisted_5, [
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.timeline_max_offset_seconds,
                  "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((localConfig.value.timeline_max_offset_seconds) = $event)),
                  modelModifiers: { number: true },
                  label: "智能调轴最大偏移秒数",
                  type: "number",
                  min: "1",
                  max: "300",
                  suffix: "秒",
                  hint: "默认 120；不建议超过 120 秒。超过 120 秒的手动操作会再次确认，自动入库不放行高风险结果。",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable"
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.timeline_min_offset_seconds,
                  "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((localConfig.value.timeline_min_offset_seconds) = $event)),
                  modelModifiers: { number: true },
                  label: "最小应用阈值",
                  type: "number",
                  min: "0.1",
                  step: "0.1",
                  suffix: "秒",
                  hint: "低于该阈值时仅复制字幕，不做时间轴改写。",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable"
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.timeline_vad_mode,
                  "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((localConfig.value.timeline_vad_mode) = $event)),
                  items: timelineVadItems,
                  label: "音频 VAD 模式",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.timeline_allow_risky_offset,
                  "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((localConfig.value.timeline_allow_risky_offset) = $event)),
                  label: "全局允许高风险偏移",
                  color: "warning",
                  hint: "不建议开启。开启后后端会允许 120 秒以上结果；手动操作仍会显示风险确认。",
                  "persistent-hint": ""
                }, null, 8, ["modelValue"])
              ]),
              _createVNode(_component_VDivider, { class: "my-5" }),
              _createElementVNode("div", _hoisted_6, [
                _cache[35] || (_cache[35] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "config-section-title" }, "RAR / 7Z 解压器"),
                  _createElementVNode("p", null, "RAR 和 7Z 都依赖容器内可执行解压器；宿主机静态 7zz 映射更适合长期使用。")
                ], -1)),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "tonal",
                  "prepend-icon": "mdi-tools",
                  onClick: _cache[28] || (_cache[28] = $event => (rarHelpDialog.value = true))
                }, {
                  default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                    _createTextVNode(" 查看安装教程 ", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _createElementVNode("div", _hoisted_7, [
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.rar_dependency_mode,
                  "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((localConfig.value.rar_dependency_mode) = $event)),
                  items: rarDependencyModes,
                  label: "RAR 解压器处理方式",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.rar_tool_path,
                  "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((localConfig.value.rar_tool_path) = $event)),
                  label: "容器内映射路径",
                  placeholder: "/usr/local/bin/7z",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"])
              ]),
              _createVNode(_component_VAlert, {
                class: "mt-4",
                type: "info",
                variant: "tonal",
                text: "自动安装只适合临时测试；长期建议在宿主机把静态 7zz 放到 MoviePilot 部署目录的 tools/7zz，并映射为容器内 /usr/local/bin/7z。插件不会主动重启 Docker 容器。"
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _createVNode(_component_VDialog, {
      modelValue: rarHelpDialog.value,
      "onUpdate:modelValue": _cache[32] || (_cache[32] = $event => ((rarHelpDialog).value = $event)),
      "max-width": "820"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, {
          class: "rar-help-dialog",
          rounded: "xl"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dialog-title" }, {
              default: _withCtx(() => [
                _cache[39] || (_cache[39] = _createElementVNode("span", null, "RAR / 7Z 解压器说明", -1)),
                _createVNode(_component_VBtn, {
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[31] || (_cache[31] = $event => (rarHelpDialog.value = false))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _cache[40] || (_cache[40] = _createElementVNode("div", { class: "rar-help-summary" }, [
                  _createElementVNode("p", null, [
                    _createElementVNode("strong", null, "说明："),
                    _createElementVNode("code", null, "rarfile"),
                    _createTextVNode(" 只是 Python 调用封装，不是独立解压器。")
                  ]),
                  _createElementVNode("p", null, [
                    _createElementVNode("strong", null, "要求："),
                    _createTextVNode("MoviePilot 容器内需要能执行 "),
                    _createElementVNode("code", null, "unrar"),
                    _createTextVNode("、"),
                    _createElementVNode("code", null, "7z"),
                    _createTextVNode("、"),
                    _createElementVNode("code", null, "7za"),
                    _createTextVNode("、"),
                    _createElementVNode("code", null, "7zz"),
                    _createTextVNode(" 或 "),
                    _createElementVNode("code", null, "bsdtar"),
                    _createTextVNode("。")
                  ]),
                  _createElementVNode("p", null, [
                    _createElementVNode("strong", null, "方案："),
                    _createTextVNode("临时测试可在容器内安装；长期使用推荐通过国内镜像下载宿主机静态 "),
                    _createElementVNode("code", null, "7zz"),
                    _createTextVNode("，设置执行权限后映射到容器内 "),
                    _createElementVNode("code", null, "/usr/local/bin/7z"),
                    _createTextVNode("。")
                  ])
                ], -1)),
                _createElementVNode("div", _hoisted_8, [
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(rarHelpItems, (item) => {
                    return _createElementVNode("section", {
                      key: item.title,
                      class: "rar-help-row"
                    }, [
                      _createElementVNode("div", _hoisted_9, [
                        _createElementVNode("div", _hoisted_10, [
                          _createElementVNode("span", _hoisted_11, _toDisplayString(item.badge), 1),
                          _createElementVNode("strong", null, _toDisplayString(item.title), 1)
                        ]),
                        _createVNode(_component_VBtn, {
                          color: "primary",
                          variant: "flat",
                          size: "small",
                          onClick: $event => (copyHelpText(item.command, item.copyLabel))
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(item.button), 1)
                          ]),
                          _: 2
                        }, 1032, ["onClick"])
                      ]),
                      _createElementVNode("p", null, _toDisplayString(item.description), 1),
                      _createElementVNode("div", _hoisted_12, [
                        _createElementVNode("pre", null, _toDisplayString(item.command), 1)
                      ])
                    ])
                  }), 64))
                ]),
                (copyMessage.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      class: "mt-4",
                      type: "success",
                      variant: "tonal",
                      text: copyMessage.value
                    }, null, 8, ["text"]))
                  : (copyError.value)
                    ? (_openBlock(), _createBlock(_component_VAlert, {
                        key: 1,
                        class: "mt-4",
                        type: "warning",
                        variant: "tonal",
                        text: copyError.value
                      }, null, 8, ["text"]))
                    : _createCommentVNode("", true),
                _createVNode(_component_VAlert, {
                  class: "mt-4",
                  type: "info",
                  variant: "tonal",
                  text: "插件不会主动重启 Docker 容器。映射文件后需要按你的部署方式重建或重启 MoviePilot 容器；安装或映射完成后，刷新插件状态即可重新检测。"
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-cee4039b"]]);

export { Config as default };
