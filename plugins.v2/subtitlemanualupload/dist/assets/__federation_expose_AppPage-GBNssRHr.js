import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'data') && response.success !== undefined) {
    return response.data
  }
  return response?.data ?? response
}

function mediaLabel(media) {
  if (!media) return ''
  return media.year ? `${media.title} (${media.year})` : `${media.title || ''}`
}

function targetLabel(target) {
  return target?.label || target?.target_label || ''
}

const {normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,resolveComponent:_resolveComponent,createBlock:_createBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,createVNode:_createVNode,withKeys:_withKeys,renderList:_renderList,Fragment:_Fragment,unref:_unref,withModifiers:_withModifiers,mergeProps:_mergeProps} = await importShared('vue');


const _hoisted_1 = { class: "subtitle-upload-page" };
const _hoisted_2 = {
  key: 0,
  class: "root-tabs"
};
const _hoisted_3 = {
  key: 1,
  class: "hero-card"
};
const _hoisted_4 = {
  key: 4,
  class: "media-stage"
};
const _hoisted_5 = { class: "search-head" };
const _hoisted_6 = { class: "section-kicker" };
const _hoisted_7 = { class: "search-bar" };
const _hoisted_8 = {
  key: 0,
  class: "media-list"
};
const _hoisted_9 = ["onClick"];
const _hoisted_10 = { class: "poster-frame" };
const _hoisted_11 = ["src", "alt"];
const _hoisted_12 = { key: 1 };
const _hoisted_13 = { class: "media-copy" };
const _hoisted_14 = { class: "media-type" };
const _hoisted_15 = {
  key: 1,
  class: "pager-row"
};
const _hoisted_16 = {
  key: 2,
  class: "empty-state"
};
const _hoisted_17 = {
  key: 3,
  class: "global-history-list"
};
const _hoisted_18 = ["onClick"];
const _hoisted_19 = { class: "poster-frame compact" };
const _hoisted_20 = ["src", "alt"];
const _hoisted_21 = { key: 1 };
const _hoisted_22 = { class: "media-copy" };
const _hoisted_23 = { class: "media-type" };
const _hoisted_24 = {
  key: 0,
  class: "global-history-targets"
};
const _hoisted_25 = { class: "history-bulk-toolbar" };
const _hoisted_26 = { class: "history-bulk-copy" };
const _hoisted_27 = { class: "history-bulk-actions" };
const _hoisted_28 = { class: "history-main" };
const _hoisted_29 = { class: "episode-title" };
const _hoisted_30 = { class: "episode-path" };
const _hoisted_31 = { class: "subtitle-history-list compact-subtitles" };
const _hoisted_32 = { class: "history-actions" };
const _hoisted_33 = {
  key: 4,
  class: "pager-row"
};
const _hoisted_34 = {
  key: 5,
  class: "empty-state"
};
const _hoisted_35 = {
  key: 5,
  class: "episode-stage"
};
const _hoisted_36 = { class: "detail-head" };
const _hoisted_37 = { class: "selected-media" };
const _hoisted_38 = { class: "mini-poster" };
const _hoisted_39 = ["src", "alt"];
const _hoisted_40 = { key: 1 };
const _hoisted_41 = { class: "section-kicker" };
const _hoisted_42 = {
  key: 0,
  class: "season-strip"
};
const _hoisted_43 = ["onClick"];
const _hoisted_44 = { class: "ai-status-orb" };
const _hoisted_45 = { class: "detail-tabs" };
const _hoisted_46 = {
  key: 2,
  class: "match-panel"
};
const _hoisted_47 = { class: "toolbar-row" };
const _hoisted_48 = {
  key: 0,
  class: "episode-list"
};
const _hoisted_49 = { class: "episode-index" };
const _hoisted_50 = { class: "episode-copy" };
const _hoisted_51 = { class: "episode-title" };
const _hoisted_52 = { class: "episode-path" };
const _hoisted_53 = {
  key: 1,
  class: "empty-state"
};
const _hoisted_54 = {
  key: 2,
  class: "result-panel"
};
const _hoisted_55 = {
  key: 3,
  class: "history-panel"
};
const _hoisted_56 = {
  key: 0,
  class: "history-list"
};
const _hoisted_57 = { class: "history-main" };
const _hoisted_58 = { class: "episode-title" };
const _hoisted_59 = { class: "episode-path" };
const _hoisted_60 = { class: "history-status" };
const _hoisted_61 = { key: 0 };
const _hoisted_62 = { key: 1 };
const _hoisted_63 = { class: "history-actions" };
const _hoisted_64 = {
  key: 0,
  class: "subtitle-history-list"
};
const _hoisted_65 = {
  key: 1,
  class: "empty-state"
};
const _hoisted_66 = { class: "online-title-actions" };
const _hoisted_67 = {
  key: 1,
  class: "ai-task-list"
};
const _hoisted_68 = { class: "ai-task-badge" };
const _hoisted_69 = { class: "ai-task-main" };
const _hoisted_70 = { class: "ai-task-time" };
const _hoisted_71 = {
  key: 2,
  class: "empty-state"
};
const _hoisted_72 = { class: "online-title-actions" };
const _hoisted_73 = { class: "online-message-summary-content" };
const _hoisted_74 = { class: "online-layout" };
const _hoisted_75 = { class: "online-results-panel" };
const _hoisted_76 = { class: "online-panel-head" };
const _hoisted_77 = {
  key: 2,
  class: "online-provider-progress"
};
const _hoisted_78 = {
  key: 3,
  class: "online-loading"
};
const _hoisted_79 = {
  key: 4,
  class: "online-result-list"
};
const _hoisted_80 = { class: "online-result-main" };
const _hoisted_81 = { class: "online-result-title" };
const _hoisted_82 = { class: "online-result-meta" };
const _hoisted_83 = {
  key: 0,
  class: "online-manual-badge"
};
const _hoisted_84 = { key: 0 };
const _hoisted_85 = {
  key: 1,
  class: "online-match-detail"
};
const _hoisted_86 = ["href"];
const _hoisted_87 = {
  key: 5,
  class: "empty-state"
};
const _hoisted_88 = { class: "manual-links-panel" };
const _hoisted_89 = { class: "manual-provider-head" };
const _hoisted_90 = { class: "manual-keywords" };
const _hoisted_91 = ["href"];
const _hoisted_92 = {
  key: 1,
  class: "support-row"
};
const _hoisted_93 = {
  key: 2,
  class: "file-list"
};
const _hoisted_94 = {
  key: 3,
  class: "preview-list"
};
const _hoisted_95 = { class: "preview-head" };
const _hoisted_96 = { class: "batch-language" };
const _hoisted_97 = { class: "subtitle-source" };
const _hoisted_98 = { class: "output-name" };
const _hoisted_99 = { class: "rar-help-list" };
const _hoisted_100 = { class: "rar-help-row-head" };
const _hoisted_101 = { class: "rar-help-row-title" };
const _hoisted_102 = { class: "rar-help-step" };
const _hoisted_103 = ["onClick"];
const _hoisted_104 = { class: "command-block" };

const {computed,nextTick,onBeforeUnmount,onMounted,ref} = await importShared('vue');

const mediaPageSize = 24;
const matchHistoryPageSize = 20;
const ONLINE_PROVIDER_TIMEOUT_MS = 25000;
const ONLINE_DOWNLOAD_TIMEOUT_MS = 35000;

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
  __name: 'AppPage',
  props: {
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
},
  setup(__props, { expose: __expose }) {

const props = __props;

const pluginBase = computed(() => `plugin/${props.pluginId || 'SubtitleManualUpload'}`);
const status = ref({
  enabled: false,
  source: 'MoviePilot 本地整理记录',
  index: {
    ready: false,
    updated_at: '',
    entry_count: 0,
    media_count: 0,
    expires_in: 0,
  },
  archive_support: {
    zip: true,
    rar: false,
    rar_tool: '',
    rar_tool_path: '/usr/local/bin/7z',
    rar_python: false,
    rar_python_package: 'rarfile',
    dependency_mode: 'none',
    dependency_status: {},
  },
  timeline_fixer: { available: false, modules: {} },
  ai_subtitle: {
    enabled: true,
    installed: false,
    available: false,
    running: false,
    queue_ready: false,
    plugin_name: 'AI字幕生成(联动版)',
    plugin_version: '',
    message: '请先安装并启用 AI字幕生成(联动版)',
    counts: {},
    updated_at: '',
  },
});

const loading = ref(false);
const searching = ref(false);
const resolving = ref(false);
const refreshing = ref(false);
const preparing = ref(false);
const applying = ref(false);
const clearing = ref(false);
const aiSubmitting = ref(false);
const aiCancelling = ref(false);
const aiTasksLoading = ref(false);
const onlineSearching = ref(false);
const onlineDownloading = ref(false);
const onlinePreviewDownloading = ref(false);
const onlineAiDownloading = ref(false);
const dragging = ref(false);
const message = ref('');
const error = ref('');
const onlineError = ref('');
const searchKeyword = ref('');
const mediaType = ref('all');
const medias = ref([]);
const mediaPage = ref(1);
const mediaTotal = ref(0);
const mediaHasMore = ref(false);
const mediaPrefetchPages = ref({});
let mediaSearchToken = 0;
const rootTab = ref('match');
const matchHistoryLoading = ref(false);
const matchHistoryItems = ref([]);
const matchHistoryPage = ref(1);
const matchHistoryTotal = ref(0);
const matchHistoryHasMore = ref(false);
const expandedHistoryIds = ref([]);
const selectedHistoryTargetIds = ref({});
const selectedMedia = ref(null);
const detailTab = ref('match');
const seasons = ref([]);
const selectedSeason = ref('all');
const targets = ref([]);
const selectedTargetIds = ref([]);
const lockedTargetIds = ref([]);
const uploadDialog = ref(false);
const rarHelpDialog = ref(false);
const uploadTitle = ref('');
const uploadScopeTargets = ref([]);
const files = ref([]);
const preview = ref(null);
const fileInputRef = ref(null);
const fixTimeline = ref(false);
const batchLanguageSuffix = ref('');
const copyMessage = ref('');
const copyError = ref('');
const lastWritten = ref([]);
const onlineDialog = ref(false);
const onlineAiConfirmDialog = ref(false);
const onlineTitle = ref('');
const onlineScope = ref('auto');
const onlineKeyword = ref('');
const onlineTargets = ref([]);
const onlineStatus = ref({ providers: [], capabilities: {} });
const onlineSelectedProviders = ref(['assrt', 'opensubtitles']);
const onlineResults = ref([]);
const onlineLanguageFilter = ref('all');
const onlineProviderFilter = ref('all');
const onlineMessages = ref([]);
const onlineMessagesCollapsed = ref(false);
const onlineManualLinks = ref([]);
const onlineProviderProgress = ref({});
const selectedOnlineResultIds = ref([]);
const aiTaskDialog = ref(false);
const aiTaskDialogTarget = ref(null);
const aiTaskData = ref({
  status: null,
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, ignored: 0, no_audio: 0, failed: 0, cancelled: 0 },
  tasks: [],
  task_by_target: {},
});
let aiTaskTimer = null;
let onlineSearchSeq = 0;
let onlineDownloadSeq = 0;
const onlineProviderItems = [
  { title: '射手网(伪)', value: 'assrt' },
  { title: 'OpenSubtitles', value: 'opensubtitles' },
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

const visibleTargets = computed(() => targets.value || []);
const selectedTargets = computed(() => {
  const picked = new Set(selectedTargetIds.value || []);
  return visibleTargets.value.filter(item => picked.has(item.id))
});
const unlockedVisibleTargets = computed(() => visibleTargets.value.filter(item => !isLocked(item.id) && item.writable !== false));
const uploadTargets = computed(() => uploadScopeTargets.value.filter(item => !isLocked(item.id) && item.writable !== false));
const batchUploadTargets = computed(() => {
  const base = selectedTargets.value.length ? selectedTargets.value : visibleTargets.value;
  return base.filter(item => !isLocked(item.id) && item.writable !== false)
});
const targetSelectItems = computed(() => uploadTargets.value.map(target => ({
  title: compactTargetName(target),
  value: target.id,
})));
const canPrepare = computed(() => uploadTargets.value.length > 0 && files.value.length > 0);
const canApply = computed(() => {
  const items = selectedPreviewItems.value;
  return items.length > 0 && items.every(item => item.target_id)
});
const hasPreviewItems = computed(() => (preview.value?.items || []).length > 0);
const selectedPreviewItems = computed(() => (preview.value?.items || []).filter(item => item.selected !== false));
const hasOnlineResults = computed(() => onlineResults.value.length > 0);
const filteredOnlineResults = computed(() => {
  return onlineResults.value.filter(item => {
    const languageMatched = onlineLanguageFilter.value === 'all' || onlineResultLanguageFilterCategory(item) === onlineLanguageFilter.value;
    const providerMatched = onlineProviderFilter.value === 'all' || item.provider === onlineProviderFilter.value;
    return languageMatched && providerMatched
  })
});
const onlineLanguageFilterItems = computed(() => {
  const languageItems = [
    { title: '中文', value: 'chinese' },
    { title: '英文', value: 'english' },
    { title: '日文', value: 'japanese' },
    { title: '其他', value: 'other' },
  ];
  const counts = onlineResults.value.reduce((acc, item) => {
    const category = onlineResultLanguageFilterCategory(item);
    acc[category] = (acc[category] || 0) + 1;
    return acc
  }, {});
  return [
    { title: `全部 ${onlineResults.value.length}`, value: 'all' },
    ...languageItems.map(item => ({ title: `${item.title} ${counts[item.value] || 0}`, value: item.value })),
  ]
});
const onlineProviderFilterItems = computed(() => {
  const counts = onlineResults.value.reduce((acc, item) => {
    const provider = item.provider || 'unknown';
    acc[provider] = (acc[provider] || 0) + 1;
    return acc
  }, {});
  return [
    { title: `全部 ${onlineResults.value.length}`, value: 'all' },
    ...onlineProviderItems.map(item => ({ title: `${item.title} ${counts[item.value] || 0}`, value: item.value })),
  ]
});
const selectedOnlineResults = computed(() => {
  const picked = new Set(selectedOnlineResultIds.value);
  return onlineResults.value.filter(item => picked.has(onlineResultKey(item)) && isOnlineResultDownloadable(item))
});
const canSubmitOnlineAiTranslate = computed(() => {
  return aiAvailable.value && selectedOnlineResults.value.length > 0 && selectedOnlineResults.value.every(isForeignOnlineResult)
});
const onlineMessageSummary = computed(() => {
  const messages = onlineMessages.value || [];
  if (!messages.length) return ''
  const warnings = messages.filter(item => item.level !== 'info');
  const infos = messages.filter(item => item.level === 'info');
  const source = warnings.length ? warnings : infos;
  const text = source
    .slice(0, 3)
    .map(item => item.provider ? `${providerName(item.provider)}：${item.message}` : item.message)
    .join('；');
  const extra = source.length > 3 ? `；另有 ${source.length - 3} 条提示` : '';
  return `${text}${extra}`
});
const onlineMessageType = computed(() => {
  return (onlineMessages.value || []).some(item => item.level !== 'info') ? 'warning' : 'info'
});
const onlineProviderProgressItems = computed(() => onlineSelectedProviders.value.map(provider => ({
  provider,
  state: onlineProviderProgress.value[provider] || 'idle',
})));
const onlineAiConfirmText = computed(() => {
  const count = selectedOnlineResults.value.length;
  const targetCount = onlineTargets.value.length;
  return `将下载 ${count} 个外语字幕结果，并提交给 AI字幕生成(联动版) 翻译；当前范围包含 ${targetCount} 个目标。`
});
const onlineBatchLabel = computed(() => {
  if (selectedMedia.value?.media_type !== 'tv') return '搜索在线字幕'
  if (selectedTargets.value.length) return `搜索选中 ${selectedTargets.value.length} 集`
  return selectedSeason.value === 'all' ? '搜索全部季字幕包' : '搜索本季字幕包'
});
const aiStatus = computed(() => aiTaskData.value.status || status.value?.ai_subtitle || {});
const aiEnabled = computed(() => aiStatus.value.enabled !== false);
const aiAvailable = computed(() => aiEnabled.value && aiStatus.value.available === true);
const aiSummary = computed(() => aiTaskData.value.summary || {});
const aiHasActiveTasks = computed(() => Number(aiSummary.value.active || 0) > 0);
const aiBatchCancelTargets = computed(() => batchUploadTargets.value.filter(target => isAiTaskActive(aiTaskForTarget(target))));
const aiCapableBatchTargets = computed(() => batchUploadTargets.value.filter(target => !isStreamTarget(target)));
const aiBatchLabel = computed(() => {
  if (selectedMedia.value?.media_type !== 'tv') return 'AI 生成字幕'
  if (selectedTargets.value.length) return `AI 生成选中 ${selectedTargets.value.length} 集`
  return selectedSeason.value === 'all' ? 'AI 生成全部季' : 'AI 生成本季'
});
const aiSummaryText = computed(() => {
  if (!aiEnabled.value) return 'AI 联动已关闭'
  if (!aiStatus.value.installed && !aiStatus.value.available) return aiStatus.value.message || '请先安装并启用 AI字幕生成(联动版)'
  const parts = [];
  if (aiSummary.value.in_progress) parts.push(`${aiSummary.value.in_progress} 个生成中`);
  if (aiSummary.value.pending) parts.push(`${aiSummary.value.pending} 个排队`);
  if (aiSummary.value.failed) parts.push(`${aiSummary.value.failed} 个失败`);
  if (aiSummary.value.completed) parts.push(`${aiSummary.value.completed} 个完成`);
  if (aiSummary.value.ignored) parts.push(`${aiSummary.value.ignored} 个忽略`);
  if (aiSummary.value.no_audio) parts.push(`${aiSummary.value.no_audio} 个无音轨`);
  if (aiSummary.value.cancelled) parts.push(`${aiSummary.value.cancelled} 个取消`);
  return parts.length ? `AI：${parts.join(' / ')}` : (aiStatus.value.message || 'AI：暂无当前资源任务')
});
const aiDialogTasks = computed(() => {
  const targetId = aiTaskDialogTarget.value?.id;
  const tasks = aiTaskData.value.tasks || [];
  return targetId ? tasks.filter(item => item.target_id === targetId) : tasks
});
const aiDialogHasActiveTasks = computed(() => aiDialogTasks.value.some(task => isAiTaskActive(task)));
const timelineStatus = computed(() => status.value?.timeline_fixer || { available: false, modules: {} });
const timelineAvailable = computed(() => timelineStatus.value.available === true);
const selectedPreviewTargets = computed(() => {
  const targetMap = new Map(uploadTargets.value.map(target => [target.id, target]));
  return selectedPreviewItems.value
    .map(item => targetMap.get(item.target_id))
    .filter(Boolean)
});
const allSelectedPreviewTargetsAreStream = computed(() => {
  const items = selectedPreviewTargets.value;
  return items.length > 0 && items.every(isStreamTarget)
});
const hasSelectedPreviewStreamTargets = computed(() => selectedPreviewTargets.value.some(isStreamTarget));
const timelineEnabledForApply = computed(() => fixTimeline.value && timelineAvailable.value && !allSelectedPreviewTargetsAreStream.value);
const indexStatus = computed(() => status.value?.index || {});
const indexSummary = computed(() => {
  if (!indexStatus.value.ready) return '媒体库清单尚未缓存'
  const parts = [
    `${indexStatus.value.media_count || 0} 个媒体`,
    `${indexStatus.value.entry_count || 0} 个视频`,
  ];
  if (indexStatus.value.updated_at) parts.push(`更新于 ${indexStatus.value.updated_at}`);
  return parts.join(' · ')
});
const archiveStatus = computed(() => status.value?.archive_support || { zip: true, rar: false, rar_tool: '', rar_python: false });
const rarAvailable = computed(() => archiveStatus.value.rar === true);
const rarPythonAvailable = computed(() => archiveStatus.value.rar_python === true);
const rarDependencyStatus = computed(() => archiveStatus.value.dependency_status || {});
const seasonCards = computed(() => {
  if (selectedMedia.value?.media_type !== 'tv') return []
  const total = seasons.value.reduce((sum, item) => sum + Number(item.local_count || 0), 0);
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
});
const allVisibleSelected = computed(() => {
  if (!visibleTargets.value.length) return false
  const picked = new Set(selectedTargetIds.value || []);
  return visibleTargets.value.every(item => picked.has(item.id))
});
const matchHistoryRows = computed(() => visibleTargets.value.map(target => {
  const subtitles = target.subtitles || [];
  const task = aiTaskForTarget(target);
  const written = (lastWritten.value || []).filter(item => (
    item.target_label === target.label
    || subtitles.some(subtitle => subtitle.path === item.output_path || subtitle.name === item.output_name)
  ));
  return {
    target,
    subtitles,
    task,
    written,
    hasTimelineRunning: applying.value && selectedPreviewTargets.value.some(item => item.id === target.id) && timelineEnabledForApply.value,
  }
}));
const matchHistorySummary = computed(() => {
  if (!matchHistoryTotal.value) return '暂无已匹配字幕记录'
  return `${matchHistoryTotal.value} 部资源有外挂字幕记录`
});
const timelineMissing = computed(() => {
  const missing = [];
  if (timelineStatus.value.ffmpeg === false) missing.push('ffmpeg');
  if (timelineStatus.value.ffprobe === false) missing.push('ffprobe');
  const modules = timelineStatus.value.modules || {};
  Object.entries(modules).forEach(([name, ok]) => {
    if (!ok) missing.push(name);
  });
  return missing.join('、')
});

function formatMediaType(type) {
  return type === 'tv' ? '剧集' : '电影'
}

function rarDependencyModeLabel(mode) {
  if (mode === 'container_install') return '容器内自动安装'
  if (mode === 'mapped_binary') return '宿主机映射文件'
  return '仅检测'
}

function seasonLabel(season) {
  const value = Number(season || 0);
  return value === 0 ? '特别篇' : `第 ${value} 季`
}

function compactTargetName(target) {
  if (!target) return ''
  if (target.media_type !== 'tv') return target.basename || targetLabel(target)
  const season = Number(target.season || 0);
  const episode = Number(target.episode || 0);
  if (season && episode) {
    return `S${String(season).padStart(2, '0')}E${String(episode).padStart(2, '0')} · ${target.basename || targetLabel(target)}`
  }
  return target.basename || targetLabel(target)
}

function mediaStat(media) {
  const count = Number(media?.local_count || 0);
  if (media?.media_type === 'tv') {
    const seasonCount = Number(media?.season_count || 0);
    return `${seasonCount || '-'} 季 · ${count} 集本地资源`
  }
  return `${count || 1} 个本地资源`
}

function historyMediaStat(item) {
  const subtitleCount = Number(item?.subtitle_count || 0);
  const targetCount = Number(item?.target_count || 0);
  if (item?.media_type === 'tv') return `${targetCount} 集 · ${subtitleCount} 个外挂字幕`
  return `${subtitleCount} 个外挂字幕`
}

function historyExpanded(item) {
  return expandedHistoryIds.value.includes(item?.id)
}

function toggleHistoryExpanded(item) {
  const id = item?.id;
  if (!id) return
  if (expandedHistoryIds.value.includes(id)) {
    expandedHistoryIds.value = expandedHistoryIds.value.filter(value => value !== id);
    return
  }
  expandedHistoryIds.value = [...expandedHistoryIds.value, id];
}

function historyDeletableTargets(item) {
  return (item?.targets || []).filter(target => target?.id && (target.subtitles || []).length)
}

function historySelectedIds(item) {
  const id = item?.id;
  return id ? (selectedHistoryTargetIds.value[id] || []) : []
}

function historySelectedCount(item) {
  const selected = new Set(historySelectedIds(item));
  return historyDeletableTargets(item).filter(target => selected.has(target.id)).length
}

function allHistoryTargetsSelected(item) {
  const targets = historyDeletableTargets(item);
  if (!targets.length) return false
  const selected = new Set(historySelectedIds(item));
  return targets.every(target => selected.has(target.id))
}

function setHistorySelection(item, ids) {
  const itemId = item?.id;
  if (!itemId) return
  selectedHistoryTargetIds.value = {
    ...selectedHistoryTargetIds.value,
    [itemId]: Array.from(new Set(ids)),
  };
}

function toggleHistoryTarget(item, targetId, checked) {
  if (!item?.id || !targetId) return
  const selected = new Set(historySelectedIds(item));
  if (checked) {
    selected.add(targetId);
  } else {
    selected.delete(targetId);
  }
  setHistorySelection(item, Array.from(selected));
}

function toggleHistoryItemTargets(item) {
  if (allHistoryTargetsSelected(item)) {
    setHistorySelection(item, []);
    return
  }
  setHistorySelection(item, historyDeletableTargets(item).map(target => target.id));
}

function historySeasonGroups(item) {
  const groups = new Map();
  historyDeletableTargets(item).forEach(target => {
    const season = Number(target.season || 0);
    if (!groups.has(season)) {
      groups.set(season, {
        season,
        label: seasonLabel(season),
        targets: [],
        subtitleCount: 0,
      });
    }
    const group = groups.get(season);
    group.targets.push(target);
    group.subtitleCount += (target.subtitles || []).length;
  });
  return Array.from(groups.values()).sort((a, b) => a.season - b.season)
}

async function clearHistoryTargets(item, targetsToClear, label) {
  const targetIds = (targetsToClear || []).map(target => target.id).filter(Boolean);
  if (!targetIds.length || clearing.value) return
  const subtitleCount = (targetsToClear || []).reduce((sum, target) => sum + (target.subtitles || []).length, 0);
  const confirmed = window.confirm(`确认删除${label}的 ${subtitleCount} 个外挂字幕？`);
  if (!confirmed) return
  clearing.value = true;
  error.value = '';
  message.value = '';
  try {
    const response = await props.api.post(`${pluginBase.value}/clear_subtitles`, {
      target_ids: targetIds,
    });
    const data = unwrapResponse(response) || {};
    message.value = response?.message || `已删除 ${data.count || 0} 个外挂字幕`;
    setHistorySelection(item, []);
    await loadMatchHistory();
  } catch (err) {
    error.value = errorMessage(err, '批量删除外挂字幕失败');
  } finally {
    clearing.value = false;
  }
}

function clearHistorySelectedSubtitles(item) {
  const selected = new Set(historySelectedIds(item));
  const targetsToClear = historyDeletableTargets(item).filter(target => selected.has(target.id));
  clearHistoryTargets(item, targetsToClear, '选中集数');
}

function clearHistorySeasonSubtitles(item, season) {
  const targetsToClear = historyDeletableTargets(item).filter(target => Number(target.season || 0) === Number(season || 0));
  clearHistoryTargets(item, targetsToClear, seasonLabel(season));
}

function clearHistoryAllSubtitles(item) {
  const label = item?.media_type === 'tv' ? '全季' : '全部';
  clearHistoryTargets(item, historyDeletableTargets(item), label);
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size >= 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${size} B`
}

function formatOffset(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? '+' : ''}${number.toFixed(3)}s`
}

function timelineResultText(item) {
  const timeline = item?.timeline || {};
  if (!timeline.enabled) return '未启用智能调轴'
  const base = timeline.base === 'audio' ? '音频基准' : '内置字幕基准';
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
  const basename = target.basename || 'subtitle';
  const suffix = item?.language_suffix || 'und';
  let ext = item?.ext || '.srt';
  if (!ext.startsWith('.')) ext = `.${ext}`;
  return `${basename}.${suffix}${ext.toLowerCase()}`
}

function isLocked(targetId) {
  return lockedTargetIds.value.includes(targetId)
}

function isStreamTarget(target) {
  if (!target) return false
  if (target.is_stream === true) return true
  const text = `${target.path || ''} ${target.relative_path || ''} ${target.basename || ''}`.toLowerCase();
  return /\.strm(?:$|[\s?#])/.test(text)
}

function isTargetActionDisabled(target) {
  return isLocked(target.id) || target.writable === false
}

function onlineResultKey(item) {
  return `${item?.provider || 'unknown'}:${item?.result_id || item?.page_url || item?.title || ''}`
}

function providerName(providerId) {
  const known = onlineProviderItems.find(item => item.value === providerId);
  return known?.title || providerId || '未知来源'
}

function providerPriority(providerId) {
  if (providerId === 'assrt') return 30
  if (providerId === 'opensubtitles') return 20
  return 0
}

function onlineResultMeta(item) {
  const parts = [];
  if (item.language) parts.push(item.language);
  if (item.format) parts.push(item.format);
  if (item.season || item.episode) {
    parts.push(`S${String(item.season || 0).padStart(2, '0')}E${String(item.episode || 0).padStart(2, '0')}`);
  }
  if (item.score) parts.push(`匹配 ${item.score}`);
  return parts.join(' · ') || '等待下载后自动匹配'
}

function isOnlineResultDownloadable(item) {
  return item?.downloadable !== false
}

function onlineResultLanguageCategory(item) {
  const category = String(item?.language_category || '').toLowerCase();
  if (['chinese', 'english', 'japanese', 'korean', 'other'].includes(category)) return category
  const text = `${item?.language || ''} ${item?.title || ''} ${item?.note || ''}`.toLowerCase();
  if (
    text.includes('中文')
    || text.includes('简体')
    || text.includes('繁体')
    || text.includes('双语')
    || text.includes('chinese')
    || /(^|[\s._()\[\]-])(zh|ze|chi|chs|cht|zho)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'chinese'
  if (
    text.includes('英文')
    || text.includes('english')
    || /(^|[\s._()\[\]-])(en|eng)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'english'
  if (
    text.includes('日文')
    || text.includes('日语')
    || text.includes('japanese')
    || /(^|[\s._()\[\]-])(ja|jpn)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'japanese'
  if (
    text.includes('korean')
    || /(^|[\s._()\[\]-])(ko|kor)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'korean'
  return 'other'
}

function onlineResultLanguageFilterCategory(item) {
  const category = onlineResultLanguageCategory(item);
  return category === 'korean' ? 'other' : category
}

function onlineResultLanguagePriority(item) {
  const category = onlineResultLanguageCategory(item);
  if (category === 'chinese') return 40
  if (category === 'english') return 30
  if (category === 'japanese' || category === 'korean') return 20
  return 10
}

function onlineResultIdentityPriority(item) {
  const status = String(item?.identity_status || '').toLowerCase();
  if (status === 'strong') return 30
  if (status === 'weak') return 10
  return 0
}

function isForeignOnlineResult(item) {
  return onlineResultLanguageCategory(item) !== 'chinese'
}

function providerProgressText(state) {
  if (state === 'searching') return '搜索中'
  if (state === 'done') return '已完成'
  if (state === 'timeout') return '超时'
  if (state === 'cancelled') return '已停止'
  if (state === 'error') return '失败'
  return '等待'
}

function providerProgressColor(state) {
  if (state === 'searching') return 'info'
  if (state === 'done') return 'success'
  if (state === 'timeout') return 'warning'
  if (state === 'cancelled') return 'default'
  if (state === 'error') return 'warning'
  return 'default'
}

function ensureConfiguredApiProvidersSelected() {
  const configured = [];
  if (onlineStatus.value?.assrt_api_configured) configured.push('assrt');
  if (onlineStatus.value?.opensubtitles_api_configured) configured.push('opensubtitles');
  if (!configured.length) return
  onlineSelectedProviders.value = configured;
}

function stopAiPolling() {
  if (aiTaskTimer) {
    clearTimeout(aiTaskTimer);
    aiTaskTimer = null;
  }
}

function scheduleAiPolling() {
  stopAiPolling();
  if (!aiHasActiveTasks.value || !visibleTargets.value.length) return
  aiTaskTimer = setTimeout(() => {
    loadAiTasks({ silent: true });
  }, 5000);
}

async function loadAiTasks(options = {}) {
  if (!visibleTargets.value.length) {
    aiTaskData.value = {
      ...aiTaskData.value,
      summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, ignored: 0, no_audio: 0, failed: 0, cancelled: 0 },
      tasks: [],
      task_by_target: {},
    };
    stopAiPolling();
    return
  }
  if (!options.silent) aiTasksLoading.value = true;
  try {
    const response = await props.api.post(`${pluginBase.value}/ai_tasks`, {
      target_ids: visibleTargets.value.map(item => item.id),
    });
    aiTaskData.value = unwrapResponse(response) || aiTaskData.value;
    if (aiTaskData.value.status) {
      status.value = { ...status.value, ai_subtitle: aiTaskData.value.status };
    }
  } catch (err) {
    if (!options.silent) {
      error.value = errorMessage(err, '读取 AI 字幕任务失败');
    }
  } finally {
    if (!options.silent) aiTasksLoading.value = false;
    scheduleAiPolling();
  }
}

function aiTaskForTarget(target) {
  return (aiTaskData.value.task_by_target || {})[target?.id] || null
}

function isAiTaskActive(task) {
  return Boolean(task && (task.active || ['pending', 'in_progress'].includes(task.status)))
}

function aiTaskColor(target) {
  const task = aiTaskForTarget(target);
  if (!aiAvailable.value) return undefined
  if (!task) return 'primary'
  if (task.status === 'pending') return 'info'
  if (task.status === 'in_progress') return 'warning'
  if (task.status === 'completed') return 'success'
  if (task.status === 'failed') return 'error'
  if (task.status === 'no_audio') return 'grey'
  if (task.status === 'cancelled') return 'grey'
  return 'secondary'
}

function aiTaskIcon(target) {
  const task = aiTaskForTarget(target);
  if (!task) return 'mdi-robot-outline'
  if (task.status === 'pending') return 'mdi-clock-outline'
  if (task.status === 'in_progress') return 'mdi-robot-happy-outline'
  if (task.status === 'completed') return 'mdi-check-decagram-outline'
  if (task.status === 'failed') return 'mdi-alert-circle-outline'
  if (task.status === 'no_audio') return 'mdi-volume-off'
  if (task.status === 'cancelled') return 'mdi-cancel'
  return 'mdi-robot-confused-outline'
}

function aiTaskTitle(target) {
  const task = aiTaskForTarget(target);
  if (isStreamTarget(target)) return 'STRM 资源暂不支持 AI 生成字幕'
  if (!aiEnabled.value) return 'AI 字幕联动已关闭'
  if (!aiAvailable.value) return aiStatus.value.message || '请先安装并启用 AI字幕生成(联动版)'
  if (!task) return '调用 AI 字幕生成'
  return task.message || task.status_label || '查看 AI 任务状态'
}

function aiTaskStatusClass(target) {
  const task = aiTaskForTarget(target);
  return task ? `ai-${task.status}` : 'ai-idle'
}

function aiStatusText(task) {
  if (!task) return '未提交'
  return task.message || task.status_label || task.status
}

function openAiTaskDialog(target = null) {
  aiTaskDialogTarget.value = target;
  aiTaskDialog.value = true;
  loadAiTasks({ silent: true });
}

async function submitAiForTargets(scopeTargets) {
  const streamCount = scopeTargets.filter(isStreamTarget).length;
  const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false);
  const capableTargets = usableTargets.filter(item => !isStreamTarget(item));
  if (!usableTargets.length || !capableTargets.length) {
    error.value = streamCount
      ? 'STRM 资源暂不支持 AI 生成字幕，请选择本地视频文件'
      : '没有可生成 AI 字幕的目标：选中的集数可能都已锁定';
    return
  }
  if (!aiAvailable.value) {
    error.value = aiStatus.value.message || '请先安装并启用 AI字幕生成(联动版)';
    return
  }
  aiSubmitting.value = true;
  error.value = '';
  message.value = '';
  try {
    const response = await props.api.post(`${pluginBase.value}/ai_submit`, {
      target_ids: usableTargets.map(item => item.id),
    });
    const data = unwrapResponse(response) || {};
    if (data.tasks) {
      aiTaskData.value = data.tasks;
    }
    message.value = response?.message || '已提交 AI 字幕生成任务';
    await loadAiTasks({ silent: true });
  } catch (err) {
    error.value = errorMessage(err, '提交 AI 字幕任务失败');
  } finally {
    aiSubmitting.value = false;
  }
}

async function cancelAiForTargets(scopeTargets) {
  const activeTargets = scopeTargets.filter(target => isAiTaskActive(aiTaskForTarget(target)));
  if (!activeTargets.length) {
    message.value = '当前范围没有可取消的 AI 字幕任务';
    return
  }
  aiCancelling.value = true;
  error.value = '';
  message.value = '';
  try {
    const response = await props.api.post(`${pluginBase.value}/ai_cancel`, {
      target_ids: activeTargets.map(item => item.id),
    });
    const data = unwrapResponse(response) || {};
    if (data.tasks) {
      aiTaskData.value = data.tasks;
    }
    message.value = response?.message || '已取消 AI 字幕任务';
    await loadAiTasks({ silent: true });
  } catch (err) {
    error.value = errorMessage(err, '取消 AI 字幕任务失败');
  } finally {
    aiCancelling.value = false;
  }
}

function openBatchAiGenerate() {
  submitAiForTargets(batchUploadTargets.value);
}

function cancelBatchAiGenerate() {
  cancelAiForTargets(batchUploadTargets.value);
}

function cancelDialogAiTasks() {
  const scopeTargets = aiTaskDialogTarget.value ? [aiTaskDialogTarget.value] : visibleTargets.value;
  cancelAiForTargets(scopeTargets);
}

function openSingleAiGenerate(target) {
  const task = aiTaskForTarget(target);
  if (task) {
    openAiTaskDialog(target);
    return
  }
  submitAiForTargets([target]);
}

function clearTargetState() {
  seasons.value = [];
  detailTab.value = 'match';
  selectedSeason.value = 'all';
  targets.value = [];
  selectedTargetIds.value = [];
  preview.value = null;
  lastWritten.value = [];
  aiTaskDialogTarget.value = null;
  aiTaskData.value = {
    ...aiTaskData.value,
    summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, ignored: 0, no_audio: 0, failed: 0, cancelled: 0 },
    tasks: [],
    task_by_target: {},
  };
  stopAiPolling();
}

async function loadStatus() {
  loading.value = true;
  error.value = '';
  try {
    const response = await props.api.get(`${pluginBase.value}/status`);
    status.value = unwrapResponse(response) || status.value;
    if (status.value.ai_subtitle) {
      aiTaskData.value = { ...aiTaskData.value, status: status.value.ai_subtitle };
    }
  } catch (err) {
    error.value = errorMessage(err, '加载插件状态失败');
  } finally {
    loading.value = false;
  }
}

async function loadOnlineStatus() {
  try {
    const response = await props.api.get(`${pluginBase.value}/online_status`);
    onlineStatus.value = unwrapResponse(response) || onlineStatus.value;
    const enabled = onlineStatus.value.enabled_providers || [];
    if (enabled.length) {
      onlineSelectedProviders.value = enabled;
    }
    ensureConfiguredApiProvidersSelected();
  } catch (err) {
    onlineError.value = errorMessage(err, '加载在线字幕源状态失败');
  }
}

async function refreshIndex() {
  refreshing.value = true;
  error.value = '';
  try {
    const response = await props.api.post(`${pluginBase.value}/refresh_index`, {});
    const data = unwrapResponse(response) || {};
    if (data.index) {
      status.value = { ...status.value, index: data.index };
    }
    if (selectedMedia.value) {
      await loadTargets(selectedMedia.value, selectedSeason.value || 'all');
    } else if (rootTab.value === 'history') {
      await loadMatchHistory();
    } else {
      await runSearch();
    }
    message.value = response?.message || '已刷新媒体库资源清单';
  } catch (err) {
    error.value = errorMessage(err, '刷新媒体库清单失败');
  } finally {
    refreshing.value = false;
  }
}

function mediaRequestKey(keyword, type, page) {
  return `${type || 'all'}\u0000${keyword || ''}\u0000${page}`
}

function clearMediaPrefetch() {
  mediaPrefetchPages.value = {};
}

async function fetchMediaPage(keyword, type, page) {
  const params = new URLSearchParams();
  params.set('keyword', keyword);
  params.set('media_type', type);
  params.set('page', String(page));
  params.set('page_size', String(mediaPageSize));
  const response = await props.api.get(`${pluginBase.value}/search?${params.toString()}`);
  return unwrapResponse(response) || {}
}

function applyMediaPage(data, page, append) {
  mediaPage.value = Number(data.page || page);
  mediaTotal.value = Number(data.total || 0);
  mediaHasMore.value = Boolean(data.has_more);
  medias.value = append ? [...medias.value, ...(data.medias || [])] : (data.medias || []);
  if (!medias.value.length) {
    const keyword = searchKeyword.value.trim();
    message.value = keyword
      ? '本地资源库里没有匹配的视频目标，请换个关键词试试'
      : '本地整理记录里暂时没有可用的视频目标';
  }
}

async function prefetchMediaPage(page, token) {
  if (!mediaHasMore.value || page <= mediaPage.value) return
  const keyword = searchKeyword.value.trim();
  const type = mediaType.value;
  const key = mediaRequestKey(keyword, type, page);
  if (mediaPrefetchPages.value[key]?.loading || mediaPrefetchPages.value[key]?.data) return
  mediaPrefetchPages.value = {
    ...mediaPrefetchPages.value,
    [key]: { loading: true },
  };
  try {
    const data = await fetchMediaPage(keyword, type, page);
    if (token !== mediaSearchToken) return
    mediaPrefetchPages.value = {
      ...mediaPrefetchPages.value,
      [key]: { data },
    };
  } catch (err) {
    if (token !== mediaSearchToken) return
    const nextCache = { ...mediaPrefetchPages.value };
    delete nextCache[key];
    mediaPrefetchPages.value = nextCache;
  }
}

async function runSearch(options = {}) {
  const keyword = searchKeyword.value.trim();
  const append = Boolean(options.append);
  const page = append ? mediaPage.value + 1 : 1;
  if (!append) {
    mediaSearchToken += 1;
    clearMediaPrefetch();
  }
  const token = mediaSearchToken;
  const cacheKey = mediaRequestKey(keyword, mediaType.value, page);
  const cachedPage = append ? mediaPrefetchPages.value[cacheKey]?.data : null;
  if (cachedPage) {
    const nextCache = { ...mediaPrefetchPages.value };
    delete nextCache[cacheKey];
    mediaPrefetchPages.value = nextCache;
    applyMediaPage(cachedPage, page, true);
    prefetchMediaPage(page + 1, token);
    return
  }
  searching.value = true;
  error.value = '';
  message.value = '';
  if (!append) {
    selectedMedia.value = null;
    clearTargetState();
  }
  try {
    const data = await fetchMediaPage(keyword, mediaType.value, page);
    if (token !== mediaSearchToken) return
    applyMediaPage(data, page, append);
    prefetchMediaPage(page + 1, token);
  } catch (err) {
    error.value = errorMessage(err, '搜索本地资源失败');
  } finally {
    if (token === mediaSearchToken) {
      searching.value = false;
    }
  }
}

function submitRootSearch() {
  if (rootTab.value === 'history') {
    loadMatchHistory();
    return
  }
  runSearch();
}

function loadMoreMedia() {
  if (searching.value || !mediaHasMore.value) return
  runSearch({ append: true });
}

async function loadMatchHistory(options = {}) {
  const append = Boolean(options.append);
  const page = append ? matchHistoryPage.value + 1 : 1;
  matchHistoryLoading.value = true;
  error.value = '';
  try {
    const params = new URLSearchParams();
    params.set('keyword', searchKeyword.value.trim());
    params.set('media_type', mediaType.value);
    params.set('page', String(page));
    params.set('page_size', String(matchHistoryPageSize));
    const response = await props.api.get(`${pluginBase.value}/match_history?${params.toString()}`);
    const data = unwrapResponse(response) || {};
    matchHistoryPage.value = Number(data.page || page);
    matchHistoryTotal.value = Number(data.total || 0);
    matchHistoryHasMore.value = Boolean(data.has_more);
    matchHistoryItems.value = append ? [...matchHistoryItems.value, ...(data.items || [])] : (data.items || []);
  } catch (err) {
    error.value = errorMessage(err, '读取匹配历史失败');
  } finally {
    matchHistoryLoading.value = false;
  }
}

function loadMoreMatchHistory() {
  if (matchHistoryLoading.value || !matchHistoryHasMore.value) return
  loadMatchHistory({ append: true });
}

function setRootTab(tab) {
  rootTab.value = tab;
  selectedMedia.value = null;
  clearTargetState();
  if (tab === 'history' && !matchHistoryItems.value.length) {
    loadMatchHistory();
  }
}

function buildMediaParams(media, season) {
  const params = new URLSearchParams();
  params.set('media_type', media.media_type || '');
  if (media.tmdb_id) params.set('tmdb_id', String(media.tmdb_id));
  if (media.douban_id) params.set('douban_id', String(media.douban_id));
  if (media.title) params.set('title', media.title);
  if (media.year) params.set('year', media.year);
  if (season !== null && season !== undefined && season !== '') {
    params.set('season', String(season));
  }
  return params
}

async function loadTargets(media = selectedMedia.value, season = selectedSeason.value) {
  if (!media) return
  resolving.value = true;
  error.value = '';
  message.value = '';
  preview.value = null;
  try {
    const params = buildMediaParams(media, season || 'all');
    const response = await props.api.get(`${pluginBase.value}/targets?${params.toString()}`);
    const data = unwrapResponse(response) || {};
    selectedMedia.value = data.media || media;
    seasons.value = data.seasons || [];
    selectedSeason.value = data.selected_season ?? 'all';
    targets.value = data.targets || [];
    selectedTargetIds.value = [];
    await loadAiTasks({ silent: true });

    if (!targets.value.length) {
      message.value = `${mediaLabel(selectedMedia.value)} 没有找到本地可写入的视频文件`;
    }
  } catch (err) {
    error.value = errorMessage(err, '读取本地视频目标失败');
  } finally {
    resolving.value = false;
  }
}

async function selectMedia(media) {
  selectedMedia.value = media;
  clearTargetState();
  await loadTargets(media, 'all');
}

async function changeSeason(season) {
  selectedSeason.value = season;
  detailTab.value = 'match';
  selectedTargetIds.value = [];
  await loadTargets(selectedMedia.value, season);
}

function resetSelection() {
  selectedMedia.value = null;
  clearTargetState();
  runSearch();
}

function toggleSelectAll() {
  if (allVisibleSelected.value) {
    selectedTargetIds.value = [];
    return
  }
  selectedTargetIds.value = visibleTargets.value.map(item => item.id);
}

function toggleTarget(targetId, checked) {
  const set = new Set(selectedTargetIds.value);
  if (checked) {
    set.add(targetId);
  } else {
    set.delete(targetId);
  }
  selectedTargetIds.value = Array.from(set);
}

function toggleLock(targetId) {
  if (isLocked(targetId)) {
    lockedTargetIds.value = lockedTargetIds.value.filter(item => item !== targetId);
    return
  }
  lockedTargetIds.value = [...lockedTargetIds.value, targetId];
}

function timelineResultForTarget(row) {
  if (row.hasTimelineRunning) return '智能调轴处理中'
  const latest = [...(row.written || [])].reverse().find(item => item.timeline);
  if (latest) return timelineResultText(latest)
  if (isStreamTarget(row.target)) return 'STRM 资源不启用智能调轴'
  return '暂无调轴记录'
}

async function deleteSubtitle(target, subtitle) {
  if (!target || !subtitle) return
  clearing.value = true;
  error.value = '';
  message.value = '';
  try {
    const response = await props.api.post(`${pluginBase.value}/delete_subtitle`, {
      target_id: target.id,
      subtitle_path: subtitle.path,
      subtitle_name: subtitle.name,
    });
    message.value = response?.message || `已删除外挂字幕：${subtitle.name}`;
    if (selectedMedia.value) {
      await loadTargets(selectedMedia.value, selectedSeason.value);
    } else {
      await loadMatchHistory();
    }
  } catch (err) {
    error.value = errorMessage(err, '删除外挂字幕失败');
  } finally {
    clearing.value = false;
  }
}

function openUploadDialog(scopeTargets, title) {
  const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false);
  if (!usableTargets.length) {
    error.value = '没有可上传的目标：选中的集数可能都已锁定';
    return
  }
  uploadScopeTargets.value = usableTargets;
  uploadTitle.value = title;
  if (usableTargets.every(isStreamTarget)) {
    fixTimeline.value = false;
  }
  files.value = [];
  preview.value = null;
  batchLanguageSuffix.value = '';
  lastWritten.value = [];
  error.value = '';
  message.value = '';
  uploadDialog.value = true;
}

function openBatchUpload() {
  const title = selectedTargets.value.length
    ? `批量上传选中 ${batchUploadTargets.value.length} 集`
    : `批量上传 ${selectedSeason.value === 'all' ? '全部季' : seasonLabel(selectedSeason.value)}`;
  openUploadDialog(batchUploadTargets.value, title);
}

function openSingleUpload(target) {
  openUploadDialog([target], `上传 ${compactTargetName(target)}`);
}

async function openOnlineDialog(scopeTargets, title, scope) {
  const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false);
  if (!usableTargets.length) {
    error.value = '没有可搜索的目标：选中的集数可能都已锁定';
    return
  }
  onlineTitle.value = title;
  onlineScope.value = scope;
  onlineTargets.value = usableTargets;
  uploadScopeTargets.value = usableTargets;
  uploadTitle.value = `${title} · 在线字幕`;
  onlineKeyword.value = '';
  onlineResults.value = [];
  onlineLanguageFilter.value = 'all';
  onlineProviderFilter.value = 'all';
  onlineMessages.value = [];
  onlineMessagesCollapsed.value = false;
  onlineManualLinks.value = [];
  onlineProviderProgress.value = {};
  selectedOnlineResultIds.value = [];
  onlineError.value = '';
  error.value = '';
  message.value = '';
  lastWritten.value = [];
  preview.value = null;
  files.value = [];
  onlineDialog.value = true;
  await loadOnlineStatus();
  await loadOnlineManualLinks();
  await runOnlineSearch();
}

function openBatchOnlineSearch() {
  const title = selectedMedia.value?.media_type === 'tv'
    ? onlineBatchLabel.value
    : '搜索在线字幕';
  const scope = selectedMedia.value?.media_type === 'tv'
    ? (selectedTargets.value.length ? 'batch' : 'season')
    : 'movie';
  openOnlineDialog(batchUploadTargets.value, title, scope);
}

function openSingleOnlineSearch(target) {
  openOnlineDialog([target], `搜索 ${compactTargetName(target)}`, 'episode');
}

function onlinePayload() {
  return {
    target_ids: onlineTargets.value.map(item => item.id),
    media: selectedMedia.value,
    scope: onlineScope.value,
    keyword: onlineKeyword.value.trim(),
    providers: onlineSelectedProviders.value,
  }
}

async function loadOnlineManualLinks() {
  if (!onlineTargets.value.length) return
  try {
    const response = await props.api.post(`${pluginBase.value}/online_manual_links`, onlinePayload());
    const data = unwrapResponse(response) || {};
    onlineManualLinks.value = data.links || [];
  } catch (err) {
    onlineError.value = errorMessage(err, '生成手动搜索链接失败');
  }
}

async function runOnlineSearch() {
  if (!onlineTargets.value.length || onlineSearching.value) return
  if (!onlineSelectedProviders.value.length) {
    onlineError.value = '请至少选择一个在线字幕源';
    return
  }
  const searchSeq = ++onlineSearchSeq;
  const providers = [...onlineSelectedProviders.value];
  const payload = onlinePayload();
  onlineSearching.value = true;
  onlineError.value = '';
  onlineResults.value = [];
  onlineLanguageFilter.value = 'all';
  onlineProviderFilter.value = 'all';
  onlineMessages.value = [];
  onlineMessagesCollapsed.value = false;
  selectedOnlineResultIds.value = [];
  onlineProviderProgress.value = Object.fromEntries(providers.map(provider => [provider, 'searching']));
  const finishSearch = () => {
    if (searchSeq !== onlineSearchSeq) return
    if (!onlineResults.value.length && !onlineMessages.value.length) {
      onlineMessages.value = [{ level: 'info', message: '没有搜索到可自动下载的字幕，可使用右侧手动搜索链接。' }];
    }
    onlineSearching.value = false;
  };
  const searchProvider = async (provider) => {
    try {
      const response = await withTimeout(
        props.api.post(`${pluginBase.value}/online_search_provider`, {
          ...payload,
          provider,
          providers: [provider],
        }),
        ONLINE_PROVIDER_TIMEOUT_MS,
        `${providerName(provider)} 搜索超时，已保留其它字幕源结果。`,
      );
      if (searchSeq !== onlineSearchSeq) return
      const data = unwrapResponse(response) || {};
      mergeOnlineResults(data.results || []);
      appendOnlineMessages(data.messages || []);
      await nextTick();
      onlineProviderProgress.value = { ...onlineProviderProgress.value, [provider]: 'done' };
    } catch (err) {
      if (searchSeq !== onlineSearchSeq) return
      onlineProviderProgress.value = {
        ...onlineProviderProgress.value,
        [provider]: err?.name === 'TimeoutError' ? 'timeout' : 'error',
      };
      appendOnlineMessages([{
        provider,
        level: err?.name === 'TimeoutError' ? 'info' : 'warning',
        message: errorMessage(err, `${providerName(provider)} 在线字幕搜索失败`),
      }]);
    }
  };
  Promise.allSettled(providers.map(provider => searchProvider(provider))).then(finishSearch);
}

function stopOnlineSearch() {
  if (!onlineSearching.value) return
  onlineSearchSeq += 1;
  onlineSearching.value = false;
  onlineProviderProgress.value = Object.fromEntries(
    Object.entries(onlineProviderProgress.value).map(([provider, state]) => [
      provider,
      state === 'searching' ? 'cancelled' : state,
    ]),
  );
  appendOnlineMessages([{ level: 'info', message: '已停止等待未返回的字幕源，已显示的结果会保留。' }]);
}

function withTimeout(promise, timeoutMs, message) {
  let timer = null;
  const timeout = new Promise((resolve, reject) => {
    timer = window.setTimeout(() => {
      const err = new Error(message);
      err.name = 'TimeoutError';
      reject(err);
    }, timeoutMs);
  });
  return Promise.race([promise, timeout]).finally(() => {
    if (timer) window.clearTimeout(timer);
  })
}

function mergeOnlineResults(items) {
  const merged = new Map(onlineResults.value.map(item => [onlineResultKey(item), item]))
  ;(items || []).forEach(item => {
    if (item) merged.set(onlineResultKey(item), item);
  });
  onlineResults.value = Array.from(merged.values()).sort((a, b) => {
    const provider = providerPriority(b.provider) - providerPriority(a.provider);
    if (provider) return provider
    const language = onlineResultLanguagePriority(b) - onlineResultLanguagePriority(a);
    if (language) return language
    const identity = onlineResultIdentityPriority(b) - onlineResultIdentityPriority(a);
    if (identity) return identity
    const score = Number(b.score || 0) - Number(a.score || 0);
    if (score) return score
    return providerName(a.provider).localeCompare(providerName(b.provider), 'zh-Hans-CN')
  });
}

function appendOnlineMessages(items) {
  const merged = new Map((onlineMessages.value || []).map(item => [`${item.provider || ''}:${item.level || ''}:${item.message || ''}`, item]))
  ;(items || []).forEach(item => {
    if (item?.message) {
      merged.set(`${item.provider || ''}:${item.level || ''}:${item.message || ''}`, item);
    }
  });
  onlineMessages.value = Array.from(merged.values());
}

function toggleOnlineResult(item, checked) {
  if (!isOnlineResultDownloadable(item)) return
  const key = onlineResultKey(item);
  const set = new Set(selectedOnlineResultIds.value);
  if (checked) {
    set.add(key);
  } else {
    set.delete(key);
  }
  selectedOnlineResultIds.value = Array.from(set);
}

function requestOnlineAiTranslate() {
  if (!selectedOnlineResults.value.length || onlineDownloading.value) return
  if (!canSubmitOnlineAiTranslate.value) {
    onlineError.value = aiAvailable.value
      ? '请只选择外语字幕结果后再提交 AI 翻译。'
      : 'AI 字幕生成联动当前不可用，无法提交翻译任务。';
    return
  }
  onlineError.value = '';
  onlineAiConfirmDialog.value = true;
}

function confirmOnlineAiTranslate() {
  onlineAiConfirmDialog.value = false;
  downloadOnlinePreview(true);
}

async function downloadOnlinePreview(submitAiTranslate = false) {
  if (!selectedOnlineResults.value.length || onlineDownloading.value) return
  if (submitAiTranslate && !canSubmitOnlineAiTranslate.value) {
    onlineError.value = aiAvailable.value
      ? '请只选择外语字幕结果后再提交 AI 翻译。'
      : 'AI 字幕生成联动当前不可用，无法提交翻译任务。';
    return
  }
  const downloadSeq = ++onlineDownloadSeq;
  onlineDownloading.value = true;
  if (submitAiTranslate) {
    onlineAiDownloading.value = true;
  } else {
    onlinePreviewDownloading.value = true;
  }
  onlineError.value = '';
  try {
    const response = await withTimeout(
      props.api.post(`${pluginBase.value}/online_download_preview`, {
        ...onlinePayload(),
        results: selectedOnlineResults.value,
        submit_ai_translate: submitAiTranslate,
      }),
      ONLINE_DOWNLOAD_TIMEOUT_MS,
      '在线字幕下载仍在源站验证中，已停止等待；可换一个结果重试，或打开手动链接下载后上传。',
    );
    if (downloadSeq !== onlineDownloadSeq) return
    preview.value = unwrapResponse(response);
    batchLanguageSuffix.value = '';
    if (preview.value?.items) {
      const preferSingleCandidate = preview.value.source === 'online' && preview.value.items.length > 1;
      preview.value.items.forEach((item, index) => {
        const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id);
        item.output_name = item.output_name || buildOutputName(target, item);
        item.selected = item.selected !== false && (!preferSingleCandidate || index === 0);
      });
    }
    onlineDialog.value = false;
    uploadDialog.value = true;
    message.value = response?.message || (submitAiTranslate ? '已下载英文字幕并提交 AI 翻译' : '已下载在线字幕并生成匹配预览');
  } catch (err) {
    if (downloadSeq !== onlineDownloadSeq) return
    onlineError.value = errorMessage(err, '在线字幕下载预览失败');
  } finally {
    if (downloadSeq === onlineDownloadSeq) {
      onlineDownloading.value = false;
      onlinePreviewDownloading.value = false;
      onlineAiDownloading.value = false;
    }
  }
}

function stopOnlineDownload() {
  if (!onlineDownloading.value) return
  onlineDownloadSeq += 1;
  onlineDownloading.value = false;
  onlinePreviewDownloading.value = false;
  onlineAiDownloading.value = false;
  onlineError.value = '已停止等待在线字幕下载，当前搜索结果仍可继续选择。';
}

async function onPickFiles(event) {
  const pickedFiles = Array.from(event?.target?.files || []);
  mergeFiles(pickedFiles);
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
  await prepareUploadAfterFiles(pickedFiles);
}

function mergeFiles(inputFiles) {
  const existing = new Map(files.value.map(item => [`${item.name}-${item.size}`, item]));
  for (const file of inputFiles) {
    const key = `${file.name}-${file.size}`;
    if (!existing.has(key)) {
      existing.set(key, file);
    }
  }
  files.value = Array.from(existing.values());
  lastWritten.value = [];
}

function removeFile(file) {
  files.value = files.value.filter(item => !(item.name === file.name && item.size === file.size));
}

function openFileDialog() {
  fileInputRef.value?.click();
}

async function handleDrop(event) {
  event.preventDefault();
  dragging.value = false;
  const dropped = Array.from(event.dataTransfer?.files || []);
  mergeFiles(dropped);
  await prepareUploadAfterFiles(dropped);
}

function handleDragOver(event) {
  event.preventDefault();
  dragging.value = true;
}

function handleDragLeave(event) {
  event.preventDefault();
  dragging.value = false;
}

async function prepareUpload() {
  if (!canPrepare.value || preparing.value) return
  preparing.value = true;
  error.value = '';
  try {
    const targetIds = uploadTargets.value.map(item => item.id);
    const formData = new FormData();
    formData.append('target_ids', JSON.stringify(targetIds));
    files.value.forEach(file => {
      formData.append('files', file);
    });
    const response = await props.api.post(`${pluginBase.value}/prepare_upload`, formData);
    preview.value = unwrapResponse(response);
    batchLanguageSuffix.value = '';
    if (preview.value?.items) {
      const preferSingleCandidate = preview.value.source === 'online' && preview.value.items.length > 1;
      preview.value.items.forEach((item, index) => {
        const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id);
        item.output_name = item.output_name || buildOutputName(target, item);
        item.selected = item.selected !== false && (!preferSingleCandidate || index === 0);
      });
    }
    message.value = response?.message || '已生成匹配预览';
  } catch (err) {
    error.value = errorMessage(err, '上传预解析失败');
  } finally {
    preparing.value = false;
  }
}

async function prepareUploadAfterFiles(inputFiles) {
  if (!inputFiles.length || hasPreviewItems.value || !canPrepare.value) return
  await prepareUpload();
}

function updatePreviewTarget(uploadId, targetId) {
  const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId);
  if (!item) return
  const target = uploadTargets.value.find(targetItem => targetItem.id === targetId);
  item.target_id = targetId;
  item.output_name = buildOutputName(target, item);
}

function updateLanguageSuffix(uploadId, value) {
  const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId);
  if (!item) return
  item.language_suffix = String(value || '').trim() || 'und';
  const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id);
  item.output_name = buildOutputName(target, item);
}

function togglePreviewItem(uploadId, checked) {
  const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId);
  if (!item) return
  item.selected = Boolean(checked);
}

function applyBatchLanguageSuffix() {
  const suffix = batchLanguageSuffix.value.trim();
  if (!suffix || !preview.value?.items?.length) return
  selectedPreviewItems.value.forEach(item => {
    item.language_suffix = suffix;
    const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id);
    item.output_name = buildOutputName(target, item);
  });
}

function resetUploadPreview() {
  files.value = [];
  preview.value = null;
  batchLanguageSuffix.value = '';
  lastWritten.value = [];
  error.value = '';
  message.value = '';
}

function openRarHelp() {
  copyMessage.value = '';
  copyError.value = '';
  rarHelpDialog.value = true;
}

async function copyHelpText(text, label) {
  copyMessage.value = '';
  copyError.value = '';
  try {
    await navigator.clipboard.writeText(text);
    copyMessage.value = `${label} 已复制`;
  } catch (err) {
    copyError.value = '复制失败，请手动选择命令文本复制';
  }
}

async function applyUpload() {
  if (!canApply.value || !preview.value) return
  applying.value = true;
  error.value = '';
  try {
    const payload = {
      session_id: preview.value.session_id,
      fix_timeline: timelineEnabledForApply.value,
      items: selectedPreviewItems.value.map(item => ({
        upload_id: item.upload_id,
        target_id: item.target_id,
        ext: item.ext,
        language_suffix: item.language_suffix,
      })),
    };
    const response = await props.api.post(`${pluginBase.value}/apply_upload`, payload);
    const data = unwrapResponse(response) || {};
    const written = data.written || [];
    const successMessage = response?.message || `已写入 ${data.count || 0} 个字幕文件`;
    files.value = [];
    preview.value = null;
    uploadDialog.value = false;
    await loadTargets(selectedMedia.value, selectedSeason.value);
    message.value = successMessage;
    lastWritten.value = written;
  } catch (err) {
    error.value = errorMessage(err, '写入字幕失败');
  } finally {
    applying.value = false;
  }
}

async function clearSelectedSubtitles() {
  if (!selectedTargetIds.value.length) return
  clearing.value = true;
  error.value = '';
  try {
    const response = await props.api.post(`${pluginBase.value}/clear_subtitles`, {
      target_ids: selectedTargetIds.value,
    });
    const data = unwrapResponse(response) || {};
    const successMessage = response?.message || `已删除 ${data.count || 0} 个外挂字幕`;
    await loadTargets(selectedMedia.value, selectedSeason.value);
    message.value = successMessage;
  } catch (err) {
    error.value = errorMessage(err, '清空外挂字幕失败');
  } finally {
    clearing.value = false;
  }
}

onMounted(() => {
  loadStatus();
  runSearch();
});

onBeforeUnmount(() => {
  stopAiPolling();
});

__expose({
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
  aiSubmitting,
  aiCancelling,
  aiTasksLoading,
  onlineSearching,
  onlineDownloading,
});

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VCheckbox = _resolveComponent("VCheckbox");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VListSubheader = _resolveComponent("VListSubheader");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VMenu = _resolveComponent("VMenu");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VChipGroup = _resolveComponent("VChipGroup");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VTooltip = _resolveComponent("VTooltip");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!selectedMedia.value)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _createElementVNode("button", {
            type: "button",
            class: _normalizeClass({ active: rootTab.value === 'match' }),
            onClick: _cache[0] || (_cache[0] = $event => (setRootTab('match')))
          }, " 字幕匹配 ", 2),
          _createElementVNode("button", {
            type: "button",
            class: _normalizeClass({ active: rootTab.value === 'history' }),
            onClick: _cache[1] || (_cache[1] = $event => (setRootTab('history')))
          }, " 匹配历史 ", 2)
        ]))
      : _createCommentVNode("", true),
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_3, [...(_cache[28] || (_cache[28] = [
          _createElementVNode("div", null, [
            _createElementVNode("h1", null, "字幕匹配"),
            _createElementVNode("p", null, "从 MoviePilot 本地库选择资源，上传字幕后确认匹配与改名结果。")
          ], -1)
        ]))]))
      : _createCommentVNode("", true),
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 2,
          class: "mb-4",
          type: "error",
          variant: "tonal",
          text: error.value
        }, null, 8, ["text"]))
      : (message.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 3,
            class: "mb-4",
            type: "success",
            variant: "tonal",
            text: message.value
          }, null, 8, ["text"]))
        : _createCommentVNode("", true),
    (!selectedMedia.value)
      ? (_openBlock(), _createElementBlock("section", _hoisted_4, [
          _createVNode(_component_VCard, {
            class: "glass-card search-card",
            rounded: "xl",
            elevation: "0"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardText, null, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_5, [
                    _createElementVNode("div", null, [
                      _createElementVNode("div", _hoisted_6, _toDisplayString(rootTab.value === 'history' ? '历史记录' : '资源选择'), 1),
                      _createElementVNode("h2", null, _toDisplayString(rootTab.value === 'history' ? '查看已匹配字幕' : '选择本地已有资源'), 1),
                      _createElementVNode("p", null, _toDisplayString(rootTab.value === 'history' ? matchHistorySummary.value : `仅展示 MoviePilot 已整理到本地库的视频资源。${indexSummary.value}`), 1)
                    ]),
                    _createVNode(_component_VBtn, {
                      variant: "tonal",
                      color: "primary",
                      "prepend-icon": "mdi-refresh",
                      loading: refreshing.value,
                      onClick: refreshIndex
                    }, {
                      default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                        _createTextVNode(" 刷新媒体库清单 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _createElementVNode("div", _hoisted_7, [
                    _createVNode(_component_VTextField, {
                      modelValue: searchKeyword.value,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((searchKeyword).value = $event)),
                      label: "片名、剧名或文件关键词",
                      variant: "outlined",
                      density: "comfortable",
                      "hide-details": "",
                      clearable: "",
                      onKeyup: _withKeys(submitRootSearch, ["enter"])
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSelect, {
                      modelValue: mediaType.value,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((mediaType).value = $event)),
                      items: [
                { title: '全部', value: 'all' },
                { title: '电影', value: 'movie' },
                { title: '剧集', value: 'tv' },
              ],
                      label: "类型",
                      variant: "outlined",
                      density: "comfortable",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      loading: rootTab.value === 'history' ? matchHistoryLoading.value : searching.value,
                      onClick: submitRootSearch
                    }, {
                      default: _withCtx(() => [...(_cache[30] || (_cache[30] = [
                        _createTextVNode(" 搜索 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ])
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          (rootTab.value === 'match' && medias.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(medias.value, (media) => {
                  return (_openBlock(), _createElementBlock("button", {
                    key: media.id,
                    class: "media-card",
                    onClick: $event => (selectMedia(media))
                  }, [
                    _createElementVNode("div", _hoisted_10, [
                      (media.poster_url)
                        ? (_openBlock(), _createElementBlock("img", {
                            key: 0,
                            src: media.poster_url,
                            alt: _unref(mediaLabel)(media)
                          }, null, 8, _hoisted_11))
                        : (_openBlock(), _createElementBlock("span", _hoisted_12, _toDisplayString(formatMediaType(media.media_type)), 1))
                    ]),
                    _createElementVNode("div", _hoisted_13, [
                      _createElementVNode("div", _hoisted_14, _toDisplayString(formatMediaType(media.media_type)), 1),
                      _createElementVNode("h3", null, _toDisplayString(_unref(mediaLabel)(media)), 1),
                      _createElementVNode("p", null, _toDisplayString(mediaStat(media)), 1)
                    ]),
                    _createVNode(_component_VIcon, { icon: "mdi-chevron-right" })
                  ], 8, _hoisted_9))
                }), 128))
              ]))
            : _createCommentVNode("", true),
          (rootTab.value === 'match' && medias.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_15, [
                _createElementVNode("span", null, _toDisplayString(medias.value.length) + "/" + _toDisplayString(mediaTotal.value || medias.value.length) + " 个资源", 1),
                (mediaHasMore.value)
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 0,
                      variant: "tonal",
                      loading: searching.value,
                      onClick: loadMoreMedia
                    }, {
                      default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                        _createTextVNode(" 加载下一页 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]))
                  : _createCommentVNode("", true)
              ]))
            : (rootTab.value === 'match')
              ? (_openBlock(), _createElementBlock("div", _hoisted_16, _toDisplayString(searching.value ? '正在读取本地资源...' : '输入关键词搜索；留空搜索会显示最近整理的视频。'), 1))
              : _createCommentVNode("", true),
          (rootTab.value === 'history' && matchHistoryItems.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_17, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(matchHistoryItems.value, (item) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: item.id,
                    class: "global-history-card"
                  }, [
                    _createElementVNode("button", {
                      type: "button",
                      class: "global-history-head",
                      onClick: $event => (toggleHistoryExpanded(item))
                    }, [
                      _createElementVNode("div", _hoisted_19, [
                        (item.poster_url)
                          ? (_openBlock(), _createElementBlock("img", {
                              key: 0,
                              src: item.poster_url,
                              alt: _unref(mediaLabel)(item)
                            }, null, 8, _hoisted_20))
                          : (_openBlock(), _createElementBlock("span", _hoisted_21, _toDisplayString(formatMediaType(item.media_type)), 1))
                      ]),
                      _createElementVNode("div", _hoisted_22, [
                        _createElementVNode("div", _hoisted_23, _toDisplayString(formatMediaType(item.media_type)), 1),
                        _createElementVNode("h3", null, _toDisplayString(_unref(mediaLabel)(item)), 1),
                        _createElementVNode("p", null, _toDisplayString(historyMediaStat(item)) + " · " + _toDisplayString(item.latest_at || '未知时间'), 1)
                      ]),
                      _createVNode(_component_VIcon, {
                        icon: historyExpanded(item) ? 'mdi-chevron-up' : 'mdi-chevron-down'
                      }, null, 8, ["icon"])
                    ], 8, _hoisted_18),
                    (historyExpanded(item))
                      ? (_openBlock(), _createElementBlock("div", _hoisted_24, [
                          _createElementVNode("div", _hoisted_25, [
                            _createElementVNode("div", _hoisted_26, [
                              _createElementVNode("strong", null, "已选 " + _toDisplayString(historySelectedCount(item)) + "/" + _toDisplayString(historyDeletableTargets(item).length) + " 集", 1),
                              _createElementVNode("span", null, _toDisplayString(item.subtitle_count) + " 个外挂字幕", 1)
                            ]),
                            _createElementVNode("div", _hoisted_27, [
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "tonal",
                                "prepend-icon": "mdi-checkbox-multiple-marked-outline",
                                disabled: !historyDeletableTargets(item).length || clearing.value,
                                onClick: _withModifiers($event => (toggleHistoryItemTargets(item)), ["stop"])
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(allHistoryTargetsSelected(item) ? '取消勾选' : '勾选全部'), 1)
                                ]),
                                _: 2
                              }, 1032, ["disabled", "onClick"]),
                              _createVNode(_component_VBtn, {
                                size: "small",
                                color: "error",
                                variant: "tonal",
                                "prepend-icon": "mdi-delete-sweep",
                                disabled: !historySelectedCount(item) || clearing.value,
                                loading: clearing.value,
                                onClick: _withModifiers($event => (clearHistorySelectedSubtitles(item)), ["stop"])
                              }, {
                                default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                                  _createTextVNode(" 删除选中 ", -1)
                                ]))]),
                                _: 1
                              }, 8, ["disabled", "loading", "onClick"]),
                              (item.media_type === 'tv')
                                ? (_openBlock(true), _createElementBlock(_Fragment, { key: 0 }, _renderList(historySeasonGroups(item), (season) => {
                                    return (_openBlock(), _createBlock(_component_VBtn, {
                                      key: `${item.id}-season-${season.season}`,
                                      size: "small",
                                      color: "error",
                                      variant: "text",
                                      "prepend-icon": "mdi-calendar-remove",
                                      disabled: clearing.value,
                                      onClick: _withModifiers($event => (clearHistorySeasonSubtitles(item, season.season)), ["stop"])
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(" 删" + _toDisplayString(season.label), 1)
                                      ]),
                                      _: 2
                                    }, 1032, ["disabled", "onClick"]))
                                  }), 128))
                                : _createCommentVNode("", true),
                              _createVNode(_component_VBtn, {
                                size: "small",
                                color: "error",
                                variant: "flat",
                                "prepend-icon": "mdi-delete-alert",
                                disabled: !historyDeletableTargets(item).length || clearing.value,
                                loading: clearing.value,
                                onClick: _withModifiers($event => (clearHistoryAllSubtitles(item)), ["stop"])
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.media_type === 'tv' ? '全季删除' : '删除全部'), 1)
                                ]),
                                _: 2
                              }, 1032, ["disabled", "loading", "onClick"])
                            ])
                          ]),
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(item.targets, (target) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: target.id,
                              class: "history-row compact-row selectable"
                            }, [
                              _createVNode(_component_VCheckbox, {
                                "model-value": historySelectedIds(item).includes(target.id),
                                density: "compact",
                                "hide-details": "",
                                disabled: !(target.subtitles || []).length || clearing.value,
                                onClick: _cache[4] || (_cache[4] = _withModifiers(() => {}, ["stop"])),
                                "onUpdate:modelValue": value => toggleHistoryTarget(item, target.id, value)
                              }, null, 8, ["model-value", "disabled", "onUpdate:modelValue"]),
                              _createElementVNode("div", _hoisted_28, [
                                _createElementVNode("div", _hoisted_29, _toDisplayString(compactTargetName(target)), 1),
                                _createElementVNode("div", _hoisted_30, _toDisplayString(target.relative_path), 1),
                                _createElementVNode("div", _hoisted_31, [
                                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(target.subtitles, (subtitle) => {
                                    return (_openBlock(), _createElementBlock("div", {
                                      key: subtitle.path,
                                      class: "subtitle-history-item"
                                    }, [
                                      _createElementVNode("div", null, [
                                        _createElementVNode("strong", null, _toDisplayString(subtitle.name), 1),
                                        _createElementVNode("span", null, _toDisplayString(formatBytes(subtitle.size)) + " · " + _toDisplayString(subtitle.modified_at || '未知时间'), 1)
                                      ]),
                                      _createVNode(_component_VBtn, {
                                        size: "small",
                                        variant: "text",
                                        color: "error",
                                        loading: clearing.value,
                                        onClick: _withModifiers($event => (deleteSubtitle(target, subtitle)), ["stop"])
                                      }, {
                                        default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
                                          _createTextVNode(" 删除 ", -1)
                                        ]))]),
                                        _: 1
                                      }, 8, ["loading", "onClick"])
                                    ]))
                                  }), 128))
                                ])
                              ]),
                              _createElementVNode("div", _hoisted_32, [
                                _createVNode(_component_VBtn, {
                                  size: "small",
                                  variant: "tonal",
                                  "prepend-icon": "mdi-magnify",
                                  disabled: isTargetActionDisabled(target),
                                  onClick: _withModifiers($event => (openSingleOnlineSearch(target)), ["stop"])
                                }, {
                                  default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                                    _createTextVNode(" 重新搜索 ", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["disabled", "onClick"])
                              ])
                            ]))
                          }), 128))
                        ]))
                      : _createCommentVNode("", true)
                  ]))
                }), 128))
              ]))
            : _createCommentVNode("", true),
          (rootTab.value === 'history' && matchHistoryItems.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_33, [
                _createElementVNode("span", null, _toDisplayString(matchHistoryItems.value.length) + "/" + _toDisplayString(matchHistoryTotal.value || matchHistoryItems.value.length) + " 部资源", 1),
                (matchHistoryHasMore.value)
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 0,
                      variant: "tonal",
                      loading: matchHistoryLoading.value,
                      onClick: loadMoreMatchHistory
                    }, {
                      default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                        _createTextVNode(" 加载下一页 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"]))
                  : _createCommentVNode("", true)
              ]))
            : (rootTab.value === 'history')
              ? (_openBlock(), _createElementBlock("div", _hoisted_34, _toDisplayString(matchHistoryLoading.value ? '正在读取匹配历史...' : '还没有找到已匹配字幕记录。'), 1))
              : _createCommentVNode("", true)
        ]))
      : (_openBlock(), _createElementBlock("section", _hoisted_35, [
          _createVNode(_component_VCard, {
            class: "glass-card detail-card",
            rounded: "xl",
            elevation: "0"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardText, null, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_36, [
                    _createElementVNode("div", _hoisted_37, [
                      _createElementVNode("button", {
                        class: "back-btn",
                        onClick: resetSelection
                      }, [
                        _createVNode(_component_VIcon, { icon: "mdi-arrow-left" })
                      ]),
                      _createElementVNode("div", _hoisted_38, [
                        (selectedMedia.value.poster_url)
                          ? (_openBlock(), _createElementBlock("img", {
                              key: 0,
                              src: selectedMedia.value.poster_url,
                              alt: _unref(mediaLabel)(selectedMedia.value)
                            }, null, 8, _hoisted_39))
                          : (_openBlock(), _createElementBlock("span", _hoisted_40, _toDisplayString(formatMediaType(selectedMedia.value.media_type)), 1))
                      ]),
                      _createElementVNode("div", null, [
                        _createElementVNode("div", _hoisted_41, _toDisplayString(formatMediaType(selectedMedia.value.media_type)), 1),
                        _createElementVNode("h2", null, _toDisplayString(_unref(mediaLabel)(selectedMedia.value)), 1),
                        _createElementVNode("p", null, _toDisplayString(visibleTargets.value.length) + " 个本地目标 · " + _toDisplayString(selectedTargets.value.length) + " 个已选 · " + _toDisplayString(lockedTargetIds.value.length) + " 个锁定", 1)
                      ])
                    ]),
                    _createVNode(_component_VBtn, {
                      variant: "tonal",
                      loading: resolving.value,
                      onClick: _cache[5] || (_cache[5] = $event => (loadTargets(selectedMedia.value, selectedSeason.value)))
                    }, {
                      default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
                        _createTextVNode(" 刷新列表 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  (selectedMedia.value.media_type === 'tv')
                    ? (_openBlock(), _createElementBlock("div", _hoisted_42, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(seasonCards.value, (season) => {
                          return (_openBlock(), _createElementBlock("button", {
                            key: season.value,
                            class: _normalizeClass(["season-card", { active: selectedSeason.value === season.value }]),
                            onClick: $event => (changeSeason(season.value))
                          }, [
                            _createElementVNode("span", null, _toDisplayString(season.title), 1),
                            _createElementVNode("strong", null, _toDisplayString(season.subtitle), 1)
                          ], 10, _hoisted_43))
                        }), 128))
                      ]))
                    : _createCommentVNode("", true),
                  (aiEnabled.value)
                    ? (_openBlock(), _createElementBlock("button", {
                        key: 1,
                        class: _normalizeClass(["ai-status-strip", { unavailable: !aiAvailable.value, active: aiHasActiveTasks.value }]),
                        type: "button",
                        onClick: _cache[6] || (_cache[6] = $event => (openAiTaskDialog()))
                      }, [
                        _createElementVNode("span", _hoisted_44, [
                          (aiTasksLoading.value || aiHasActiveTasks.value)
                            ? (_openBlock(), _createBlock(_component_VProgressCircular, {
                                key: 0,
                                size: "16",
                                width: "2",
                                indeterminate: ""
                              }))
                            : (_openBlock(), _createBlock(_component_VIcon, {
                                key: 1,
                                icon: "mdi-robot-outline",
                                size: "18"
                              }))
                        ]),
                        _createElementVNode("strong", null, _toDisplayString(aiSummaryText.value), 1),
                        _createElementVNode("em", null, _toDisplayString(aiAvailable.value ? '点击查看当前资源任务' : aiStatus.value.message), 1)
                      ], 2))
                    : _createCommentVNode("", true),
                  _createElementVNode("div", _hoisted_45, [
                    _createElementVNode("button", {
                      type: "button",
                      class: _normalizeClass({ active: detailTab.value === 'match' }),
                      onClick: _cache[7] || (_cache[7] = $event => (detailTab.value = 'match'))
                    }, " 字幕匹配 ", 2),
                    _createElementVNode("button", {
                      type: "button",
                      class: _normalizeClass({ active: detailTab.value === 'history' }),
                      onClick: _cache[8] || (_cache[8] = $event => (detailTab.value = 'history'))
                    }, " 匹配历史 ", 2)
                  ]),
                  (detailTab.value === 'match')
                    ? (_openBlock(), _createElementBlock("div", _hoisted_46, [
                        _createElementVNode("div", _hoisted_47, [
                          _createVNode(_component_VBtn, {
                            variant: "tonal",
                            onClick: toggleSelectAll
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(allVisibleSelected.value ? '取消全选' : '全选当前列表'), 1)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_VBtn, {
                            color: "primary",
                            disabled: !unlockedVisibleTargets.value.length,
                            onClick: openBatchUpload
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(selectedTargets.value.length ? '上传选中字幕' : '批量上传整季字幕'), 1)
                            ]),
                            _: 1
                          }, 8, ["disabled"]),
                          (aiEnabled.value)
                            ? (_openBlock(), _createBlock(_component_VBtn, {
                                key: 0,
                                color: "warning",
                                variant: "tonal",
                                "prepend-icon": "mdi-robot-outline",
                                disabled: !aiCapableBatchTargets.value.length || !aiAvailable.value,
                                loading: aiSubmitting.value,
                                onClick: openBatchAiGenerate
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(aiBatchLabel.value), 1)
                                ]),
                                _: 1
                              }, 8, ["disabled", "loading"]))
                            : _createCommentVNode("", true),
                          (aiEnabled.value && aiBatchCancelTargets.value.length)
                            ? (_openBlock(), _createBlock(_component_VBtn, {
                                key: 1,
                                color: "error",
                                variant: "tonal",
                                "prepend-icon": "mdi-cancel",
                                loading: aiCancelling.value,
                                onClick: cancelBatchAiGenerate
                              }, {
                                default: _withCtx(() => [...(_cache[37] || (_cache[37] = [
                                  _createTextVNode(" 取消 AI ", -1)
                                ]))]),
                                _: 1
                              }, 8, ["loading"]))
                            : _createCommentVNode("", true),
                          _createVNode(_component_VBtn, {
                            class: "online-batch-btn",
                            color: "success",
                            variant: "flat",
                            "prepend-icon": "mdi-cloud-search-outline",
                            disabled: !batchUploadTargets.value.length,
                            loading: onlineSearching.value,
                            onClick: openBatchOnlineSearch
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(onlineBatchLabel.value), 1)
                            ]),
                            _: 1
                          }, 8, ["disabled", "loading"]),
                          _createVNode(_component_VBtn, {
                            color: "error",
                            variant: "tonal",
                            disabled: !selectedTargetIds.value.length,
                            loading: clearing.value,
                            onClick: clearSelectedSubtitles
                          }, {
                            default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                              _createTextVNode(" 清空选中外挂字幕 ", -1)
                            ]))]),
                            _: 1
                          }, 8, ["disabled", "loading"]),
                          _cache[39] || (_cache[39] = _createElementVNode("div", { class: "toolbar-hint" }, " 锁定项不参与批量上传；清空仅删除选中项外挂字幕。 ", -1))
                        ]),
                        (visibleTargets.value.length)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_48, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(visibleTargets.value, (target) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: target.id,
                                  class: _normalizeClass(["episode-row", { locked: isLocked(target.id) }])
                                }, [
                                  _createVNode(_component_VCheckbox, {
                                    "model-value": selectedTargetIds.value.includes(target.id),
                                    density: "compact",
                                    "hide-details": "",
                                    "onUpdate:modelValue": value => toggleTarget(target.id, value)
                                  }, null, 8, ["model-value", "onUpdate:modelValue"]),
                                  _createElementVNode("div", _hoisted_49, _toDisplayString(target.media_type === 'tv' ? `E${String(target.episode || 0).padStart(2, '0')}` : 'MOV'), 1),
                                  _createElementVNode("div", _hoisted_50, [
                                    _createElementVNode("div", _hoisted_51, _toDisplayString(compactTargetName(target)), 1),
                                    _createElementVNode("div", _hoisted_52, _toDisplayString(target.relative_path), 1)
                                  ]),
                                  (target.has_subtitle)
                                    ? (_openBlock(), _createBlock(_component_VMenu, {
                                        key: 0,
                                        location: "bottom end"
                                      }, {
                                        activator: _withCtx(({ props: menuProps }) => [
                                          _createVNode(_component_VBtn, _mergeProps({ ref_for: true }, menuProps, {
                                            class: "cc-btn has-sub",
                                            variant: "text",
                                            icon: "mdi-closed-caption",
                                            title: `已有 ${target.subtitle_count} 个外挂字幕`
                                          }), null, 16, ["title"])
                                        ]),
                                        default: _withCtx(() => [
                                          _createVNode(_component_VCard, {
                                            "min-width": "280",
                                            rounded: "lg"
                                          }, {
                                            default: _withCtx(() => [
                                              _createVNode(_component_VList, { density: "compact" }, {
                                                default: _withCtx(() => [
                                                  _createVNode(_component_VListSubheader, null, {
                                                    default: _withCtx(() => [...(_cache[40] || (_cache[40] = [
                                                      _createTextVNode("已有外挂字幕", -1)
                                                    ]))]),
                                                    _: 1
                                                  }),
                                                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(target.subtitles, (subtitle) => {
                                                    return (_openBlock(), _createBlock(_component_VListItem, {
                                                      key: subtitle.path,
                                                      title: subtitle.name,
                                                      subtitle: formatBytes(subtitle.size)
                                                    }, null, 8, ["title", "subtitle"]))
                                                  }), 128))
                                                ]),
                                                _: 2
                                              }, 1024)
                                            ]),
                                            _: 2
                                          }, 1024)
                                        ]),
                                        _: 2
                                      }, 1024))
                                    : (_openBlock(), _createBlock(_component_VBtn, {
                                        key: 1,
                                        class: "cc-btn",
                                        variant: "text",
                                        icon: "mdi-closed-caption-outline",
                                        title: "暂无外挂字幕"
                                      })),
                                  (aiEnabled.value)
                                    ? (_openBlock(), _createBlock(_component_VBtn, {
                                        key: 2,
                                        class: _normalizeClass(["ai-row-btn", aiTaskStatusClass(target)]),
                                        variant: "text",
                                        icon: aiTaskIcon(target),
                                        color: aiTaskColor(target),
                                        title: aiTaskTitle(target),
                                        disabled: isTargetActionDisabled(target) || isStreamTarget(target) || (!aiAvailable.value && !aiTaskForTarget(target)),
                                        onClick: $event => (openSingleAiGenerate(target))
                                      }, null, 8, ["class", "icon", "color", "title", "disabled", "onClick"]))
                                    : _createCommentVNode("", true),
                                  _createVNode(_component_VBtn, {
                                    variant: "text",
                                    icon: "mdi-magnify",
                                    title: "搜索此集在线字幕",
                                    disabled: isTargetActionDisabled(target),
                                    onClick: $event => (openSingleOnlineSearch(target))
                                  }, null, 8, ["disabled", "onClick"]),
                                  _createVNode(_component_VBtn, {
                                    variant: "text",
                                    icon: isLocked(target.id) ? 'mdi-lock' : 'mdi-lock-open-variant',
                                    color: isLocked(target.id) ? 'warning' : undefined,
                                    title: isLocked(target.id) ? '解锁此集' : '锁定此集，批量上传跳过',
                                    onClick: $event => (toggleLock(target.id))
                                  }, null, 8, ["icon", "color", "title", "onClick"]),
                                  _createVNode(_component_VBtn, {
                                    color: "primary",
                                    variant: "tonal",
                                    size: "small",
                                    disabled: isTargetActionDisabled(target),
                                    onClick: $event => (openSingleUpload(target))
                                  }, {
                                    default: _withCtx(() => [...(_cache[41] || (_cache[41] = [
                                      _createTextVNode(" 单集上传 ", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["disabled", "onClick"])
                                ], 2))
                              }), 128))
                            ]))
                          : (_openBlock(), _createElementBlock("div", _hoisted_53, _toDisplayString(resolving.value ? '正在读取本地视频目标...' : '这个资源没有本地视频文件。'), 1)),
                        (lastWritten.value.length)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_54, [
                              _cache[42] || (_cache[42] = _createElementVNode("div", { class: "section-kicker" }, "写入结果", -1)),
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(lastWritten.value, (item) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: item.output_path,
                                  class: "result-row"
                                }, [
                                  _createElementVNode("div", null, [
                                    _createElementVNode("strong", null, _toDisplayString(item.output_name), 1),
                                    _createElementVNode("span", null, _toDisplayString(item.target_label), 1)
                                  ]),
                                  _createElementVNode("em", null, _toDisplayString(timelineResultText(item)), 1)
                                ]))
                              }), 128))
                            ]))
                          : _createCommentVNode("", true)
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_55, [
                        (matchHistoryRows.value.length)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_56, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(matchHistoryRows.value, (row) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: row.target.id,
                                  class: "history-row"
                                }, [
                                  _createElementVNode("div", _hoisted_57, [
                                    _createElementVNode("div", _hoisted_58, _toDisplayString(compactTargetName(row.target)), 1),
                                    _createElementVNode("div", _hoisted_59, _toDisplayString(row.target.relative_path), 1),
                                    _createElementVNode("div", _hoisted_60, [
                                      _createElementVNode("span", null, _toDisplayString(row.subtitles.length ? `${row.subtitles.length} 个外挂字幕` : '暂无外挂字幕'), 1),
                                      (row.task)
                                        ? (_openBlock(), _createElementBlock("span", _hoisted_61, "AI：" + _toDisplayString(aiStatusText(row.task)), 1))
                                        : _createCommentVNode("", true),
                                      _createElementVNode("span", null, _toDisplayString(timelineResultForTarget(row)), 1),
                                      (isStreamTarget(row.target))
                                        ? (_openBlock(), _createElementBlock("span", _hoisted_62, "STRM 资源不启用 AI 生成和智能调轴"))
                                        : _createCommentVNode("", true)
                                    ])
                                  ]),
                                  _createElementVNode("div", _hoisted_63, [
                                    _createVNode(_component_VBtn, {
                                      size: "small",
                                      variant: "tonal",
                                      "prepend-icon": "mdi-magnify",
                                      disabled: isTargetActionDisabled(row.target),
                                      onClick: $event => (openSingleOnlineSearch(row.target))
                                    }, {
                                      default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
                                        _createTextVNode(" 重新搜索 ", -1)
                                      ]))]),
                                      _: 1
                                    }, 8, ["disabled", "onClick"]),
                                    (aiEnabled.value && row.task)
                                      ? (_openBlock(), _createBlock(_component_VBtn, {
                                          key: 0,
                                          size: "small",
                                          variant: "text",
                                          "prepend-icon": "mdi-robot-outline",
                                          onClick: $event => (openAiTaskDialog(row.target))
                                        }, {
                                          default: _withCtx(() => [...(_cache[44] || (_cache[44] = [
                                            _createTextVNode(" AI 状态 ", -1)
                                          ]))]),
                                          _: 1
                                        }, 8, ["onClick"]))
                                      : _createCommentVNode("", true)
                                  ]),
                                  (row.subtitles.length)
                                    ? (_openBlock(), _createElementBlock("div", _hoisted_64, [
                                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(row.subtitles, (subtitle) => {
                                          return (_openBlock(), _createElementBlock("div", {
                                            key: subtitle.path,
                                            class: "subtitle-history-item"
                                          }, [
                                            _createElementVNode("div", null, [
                                              _createElementVNode("strong", null, _toDisplayString(subtitle.name), 1),
                                              _createElementVNode("span", null, _toDisplayString(formatBytes(subtitle.size)) + " · " + _toDisplayString(subtitle.modified_at || '未知时间'), 1)
                                            ]),
                                            _createVNode(_component_VBtn, {
                                              size: "small",
                                              variant: "text",
                                              color: "error",
                                              loading: clearing.value,
                                              onClick: $event => (deleteSubtitle(row.target, subtitle))
                                            }, {
                                              default: _withCtx(() => [...(_cache[45] || (_cache[45] = [
                                                _createTextVNode(" 删除 ", -1)
                                              ]))]),
                                              _: 1
                                            }, 8, ["loading", "onClick"])
                                          ]))
                                        }), 128))
                                      ]))
                                    : _createCommentVNode("", true)
                                ]))
                              }), 128))
                            ]))
                          : (_openBlock(), _createElementBlock("div", _hoisted_65, " 当前列表暂无匹配历史。 "))
                      ]))
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ])),
    _createVNode(_component_VDialog, {
      modelValue: aiTaskDialog.value,
      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((aiTaskDialog).value = $event)),
      "max-width": "860"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, {
          class: "ai-task-dialog",
          rounded: "xl"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dialog-title" }, {
              default: _withCtx(() => [
                _createElementVNode("div", null, [
                  _createElementVNode("span", null, _toDisplayString(aiTaskDialogTarget.value ? `AI 状态 · ${compactTargetName(aiTaskDialogTarget.value)}` : 'AI 字幕生成状态'), 1),
                  _createElementVNode("p", null, _toDisplayString(aiSummaryText.value) + " · 状态来自 AI字幕生成(联动版) 队列", 1)
                ]),
                _createElementVNode("div", _hoisted_66, [
                  (aiDialogHasActiveTasks.value)
                    ? (_openBlock(), _createBlock(_component_VBtn, {
                        key: 0,
                        variant: "tonal",
                        color: "error",
                        "prepend-icon": "mdi-cancel",
                        loading: aiCancelling.value,
                        onClick: cancelDialogAiTasks
                      }, {
                        default: _withCtx(() => [...(_cache[46] || (_cache[46] = [
                          _createTextVNode(" 取消任务 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading"]))
                    : _createCommentVNode("", true),
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    color: "primary",
                    "prepend-icon": "mdi-refresh",
                    loading: aiTasksLoading.value,
                    onClick: loadAiTasks
                  }, {
                    default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                      _createTextVNode(" 刷新 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading"]),
                  _createVNode(_component_VBtn, {
                    icon: "mdi-close",
                    variant: "text",
                    onClick: _cache[9] || (_cache[9] = $event => (aiTaskDialog.value = false))
                  })
                ])
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                (!aiAvailable.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      class: "mb-4",
                      type: "warning",
                      variant: "tonal",
                      text: aiStatus.value.message || '请先安装并启用 AI字幕生成(联动版)'
                    }, null, 8, ["text"]))
                  : _createCommentVNode("", true),
                (aiDialogTasks.value.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_67, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(aiDialogTasks.value, (task) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: task.task_id,
                          class: _normalizeClass(["ai-task-row", `ai-${task.status}`])
                        }, [
                          _createElementVNode("div", _hoisted_68, [
                            _createVNode(_component_VIcon, {
                              icon: aiTaskIcon({ id: task.target_id })
                            }, null, 8, ["icon"])
                          ]),
                          _createElementVNode("div", _hoisted_69, [
                            _createElementVNode("strong", null, _toDisplayString(task.target_label || task.video_name), 1),
                            _createElementVNode("span", null, _toDisplayString(task.video_name), 1),
                            _createElementVNode("p", null, _toDisplayString(aiStatusText(task)), 1)
                          ]),
                          _createElementVNode("div", _hoisted_70, [
                            _createVNode(_component_VChip, {
                              size: "small",
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(task.status_label), 1)
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode("span", null, _toDisplayString(task.complete_time || task.add_time || '-'), 1)
                          ])
                        ], 2))
                      }), 128))
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_71, " 当前资源还没有 AI 字幕生成任务。可以点击单集 AI 图标，或使用上方“AI 生成”批量提交。 "))
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: onlineDialog.value,
      "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((onlineDialog).value = $event)),
      "max-width": "1080"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, {
          class: "online-dialog",
          rounded: "xl"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dialog-title" }, {
              default: _withCtx(() => [
                _createElementVNode("div", null, [
                  _createElementVNode("span", null, _toDisplayString(onlineTitle.value || '在线字幕搜索'), 1),
                  _createElementVNode("p", null, _toDisplayString(onlineTargets.value.length) + " 个目标 · 下载后进入匹配预览，不会直接写入", 1)
                ]),
                _createElementVNode("div", _hoisted_72, [
                  _createVNode(_component_VBtn, {
                    color: "success",
                    disabled: !selectedOnlineResults.value.length || onlineAiDownloading.value,
                    loading: onlinePreviewDownloading.value,
                    onClick: _cache[11] || (_cache[11] = $event => (downloadOnlinePreview(false)))
                  }, {
                    default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
                      _createTextVNode(" 下载并生成预览 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "loading"]),
                  _createVNode(_component_VBtn, {
                    color: "primary",
                    variant: "tonal",
                    disabled: !canSubmitOnlineAiTranslate.value || onlinePreviewDownloading.value,
                    loading: onlineAiDownloading.value,
                    onClick: requestOnlineAiTranslate
                  }, {
                    default: _withCtx(() => [...(_cache[49] || (_cache[49] = [
                      _createTextVNode(" 下载并提交 AI 翻译 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "loading"]),
                  (onlineDownloading.value)
                    ? (_openBlock(), _createBlock(_component_VBtn, {
                        key: 0,
                        color: "warning",
                        variant: "tonal",
                        onClick: stopOnlineDownload
                      }, {
                        default: _withCtx(() => [...(_cache[50] || (_cache[50] = [
                          _createTextVNode(" 停止等待 ", -1)
                        ]))]),
                        _: 1
                      }))
                    : _createCommentVNode("", true),
                  _createVNode(_component_VBtn, {
                    icon: "mdi-close",
                    variant: "text",
                    onClick: _cache[12] || (_cache[12] = $event => (onlineDialog.value = false))
                  })
                ])
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, { class: "online-search-actions" }, {
              default: _withCtx(() => [
                _createVNode(_component_VTextField, {
                  modelValue: onlineKeyword.value,
                  "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((onlineKeyword).value = $event)),
                  label: "手动关键词（可选）",
                  placeholder: "留空按资源名、季集号自动生成",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": "",
                  clearable: "",
                  onKeyup: _withKeys(runOnlineSearch, ["enter"])
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: onlineSelectedProviders.value,
                  "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((onlineSelectedProviders).value = $event)),
                  items: onlineProviderItems,
                  label: "字幕源",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": "",
                  multiple: "",
                  chips: ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  disabled: !onlineSelectedProviders.value.length,
                  loading: onlineSearching.value,
                  onClick: runOnlineSearch
                }, {
                  default: _withCtx(() => [...(_cache[51] || (_cache[51] = [
                    _createTextVNode(" 搜索 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"]),
                (onlineSearching.value)
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 0,
                      color: "warning",
                      variant: "tonal",
                      onClick: stopOnlineSearch
                    }, {
                      default: _withCtx(() => [...(_cache[52] || (_cache[52] = [
                        _createTextVNode(" 停止等待 ", -1)
                      ]))]),
                      _: 1
                    }))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                (onlineError.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      class: "mb-4",
                      type: "error",
                      variant: "tonal",
                      text: onlineError.value
                    }, null, 8, ["text"]))
                  : _createCommentVNode("", true),
                (onlineMessages.value.length && !onlineMessagesCollapsed.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 1,
                      class: "online-message-summary",
                      type: onlineMessageType.value,
                      variant: "tonal",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_73, [
                          _createElementVNode("span", null, _toDisplayString(onlineMessageSummary.value), 1),
                          _createVNode(_component_VBtn, {
                            size: "x-small",
                            variant: "text",
                            onClick: _cache[15] || (_cache[15] = $event => (onlineMessagesCollapsed.value = true))
                          }, {
                            default: _withCtx(() => [...(_cache[53] || (_cache[53] = [
                              _createTextVNode(" 收起 ", -1)
                            ]))]),
                            _: 1
                          })
                        ])
                      ]),
                      _: 1
                    }, 8, ["type"]))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_74, [
                  _createElementVNode("section", _hoisted_75, [
                    _createElementVNode("div", _hoisted_76, [
                      _cache[54] || (_cache[54] = _createElementVNode("div", null, [
                        _createElementVNode("div", { class: "section-kicker" }, "自动搜索"),
                        _createElementVNode("h3", null, "选择要下载的字幕")
                      ], -1)),
                      _createElementVNode("span", null, _toDisplayString(hasOnlineResults.value ? `${filteredOnlineResults.value.length}/${onlineResults.value.length} 条结果` : '暂无结果'), 1)
                    ]),
                    (hasOnlineResults.value)
                      ? (_openBlock(), _createBlock(_component_VChipGroup, {
                          key: 0,
                          modelValue: onlineLanguageFilter.value,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((onlineLanguageFilter).value = $event)),
                          class: "online-provider-filter",
                          mandatory: "",
                          "selected-class": "online-provider-filter-active"
                        }, {
                          default: _withCtx(() => [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(onlineLanguageFilterItems.value, (item) => {
                              return (_openBlock(), _createBlock(_component_VChip, {
                                key: item.value,
                                value: item.value,
                                size: "small",
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.title), 1)
                                ]),
                                _: 2
                              }, 1032, ["value"]))
                            }), 128))
                          ]),
                          _: 1
                        }, 8, ["modelValue"]))
                      : _createCommentVNode("", true),
                    (hasOnlineResults.value)
                      ? (_openBlock(), _createBlock(_component_VChipGroup, {
                          key: 1,
                          modelValue: onlineProviderFilter.value,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((onlineProviderFilter).value = $event)),
                          class: "online-provider-filter",
                          mandatory: "",
                          "selected-class": "online-provider-filter-active"
                        }, {
                          default: _withCtx(() => [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(onlineProviderFilterItems.value, (item) => {
                              return (_openBlock(), _createBlock(_component_VChip, {
                                key: item.value,
                                value: item.value,
                                size: "small",
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.title), 1)
                                ]),
                                _: 2
                              }, 1032, ["value"]))
                            }), 128))
                          ]),
                          _: 1
                        }, 8, ["modelValue"]))
                      : _createCommentVNode("", true),
                    (onlineProviderProgressItems.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_77, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(onlineProviderProgressItems.value, (item) => {
                            return (_openBlock(), _createBlock(_component_VChip, {
                              key: item.provider,
                              size: "small",
                              variant: "tonal",
                              color: providerProgressColor(item.state)
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(providerName(item.provider)) + " · " + _toDisplayString(providerProgressText(item.state)), 1)
                              ]),
                              _: 2
                            }, 1032, ["color"]))
                          }), 128))
                        ]))
                      : _createCommentVNode("", true),
                    (onlineSearching.value && !filteredOnlineResults.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_78, " 正在从 API 搜索字幕，先返回的结果会先显示... "))
                      : _createCommentVNode("", true),
                    (filteredOnlineResults.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_79, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(filteredOnlineResults.value, (item) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: onlineResultKey(item),
                              class: _normalizeClass(["online-result-card", {
                    active: selectedOnlineResultIds.value.includes(onlineResultKey(item)),
                    disabled: !isOnlineResultDownloadable(item),
                  }])
                            }, [
                              _createVNode(_component_VCheckbox, {
                                "model-value": selectedOnlineResultIds.value.includes(onlineResultKey(item)),
                                density: "compact",
                                "hide-details": "",
                                disabled: !isOnlineResultDownloadable(item),
                                "onUpdate:modelValue": value => toggleOnlineResult(item, value)
                              }, null, 8, ["model-value", "disabled", "onUpdate:modelValue"]),
                              _createElementVNode("div", _hoisted_80, [
                                _createElementVNode("div", _hoisted_81, _toDisplayString(item.title), 1),
                                _createElementVNode("div", _hoisted_82, [
                                  _createElementVNode("span", null, _toDisplayString(providerName(item.provider)), 1),
                                  _createElementVNode("span", null, _toDisplayString(onlineResultMeta(item)), 1),
                                  (!isOnlineResultDownloadable(item))
                                    ? (_openBlock(), _createElementBlock("span", _hoisted_83, " 需手动下载 "))
                                    : _createCommentVNode("", true)
                                ]),
                                (item.note)
                                  ? (_openBlock(), _createElementBlock("p", _hoisted_84, _toDisplayString(item.note), 1))
                                  : _createCommentVNode("", true),
                                (item.match_detail)
                                  ? (_openBlock(), _createElementBlock("p", _hoisted_85, _toDisplayString(item.match_detail), 1))
                                  : _createCommentVNode("", true)
                              ]),
                              (item.page_url)
                                ? (_openBlock(), _createElementBlock("a", {
                                    key: 0,
                                    class: "online-open-link",
                                    href: item.page_url,
                                    target: "_blank",
                                    rel: "noopener noreferrer"
                                  }, " 查看 ", 8, _hoisted_86))
                                : _createCommentVNode("", true)
                            ], 2))
                          }), 128))
                        ]))
                      : (!onlineSearching.value)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_87, _toDisplayString(hasOnlineResults.value ? '当前平台筛选下没有结果。' : '没有可自动下载的字幕结果。可以换关键词重试，或使用右侧手动搜索。'), 1))
                        : _createCommentVNode("", true)
                  ]),
                  _createElementVNode("aside", _hoisted_88, [
                    _cache[55] || (_cache[55] = _createElementVNode("div", { class: "section-kicker" }, "手动搜索", -1)),
                    _cache[56] || (_cache[56] = _createElementVNode("h3", null, "跳转字幕站", -1)),
                    _cache[57] || (_cache[57] = _createElementVNode("p", null, "自动搜索失败或源站需要验证时，可打开链接下载字幕包后回到本页上传。", -1)),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(onlineManualLinks.value, (provider) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: provider.provider,
                        class: "manual-provider"
                      }, [
                        _createElementVNode("div", _hoisted_89, [
                          _createElementVNode("strong", null, _toDisplayString(provider.name), 1)
                        ]),
                        _createElementVNode("div", _hoisted_90, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(provider.links, (link) => {
                            return (_openBlock(), _createElementBlock("a", {
                              key: `${provider.provider}-${link.keyword}`,
                              href: link.url,
                              target: "_blank",
                              rel: "noopener noreferrer"
                            }, _toDisplayString(link.keyword), 9, _hoisted_91))
                          }), 128))
                        ])
                      ]))
                    }), 128))
                  ])
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: onlineAiConfirmDialog.value,
      "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((onlineAiConfirmDialog).value = $event)),
      "max-width": "520"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { rounded: "lg" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dialog-title compact" }, {
              default: _withCtx(() => [
                _createElementVNode("div", null, [
                  _cache[58] || (_cache[58] = _createElementVNode("span", null, "确认提交 AI 翻译", -1)),
                  _createElementVNode("p", null, _toDisplayString(onlineAiConfirmText.value), 1)
                ])
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createVNode(_component_VAlert, {
                  type: "warning",
                  variant: "tonal",
                  text: "确认后会下载所选外语字幕并提交 AI 翻译任务；误触后可在 AI 状态里取消。"
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, { class: "justify-end" }, {
              default: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[19] || (_cache[19] = $event => (onlineAiConfirmDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[59] || (_cache[59] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  loading: onlineAiDownloading.value,
                  onClick: confirmOnlineAiTranslate
                }, {
                  default: _withCtx(() => [...(_cache[60] || (_cache[60] = [
                    _createTextVNode(" 确认提交 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: uploadDialog.value,
      "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((uploadDialog).value = $event)),
      "max-width": "980"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, {
          class: "upload-dialog",
          rounded: "xl"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dialog-title" }, {
              default: _withCtx(() => [
                _createElementVNode("span", null, _toDisplayString(uploadTitle.value || '上传字幕'), 1),
                _createVNode(_component_VBtn, {
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[21] || (_cache[21] = $event => (uploadDialog.value = false))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, { class: "dialog-actions dialog-actions-top" }, {
              default: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[22] || (_cache[22] = $event => (uploadDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[61] || (_cache[61] = [
                    _createTextVNode("关闭", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VSpacer),
                (hasPreviewItems.value)
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 0,
                      variant: "tonal",
                      onClick: resetUploadPreview
                    }, {
                      default: _withCtx(() => [...(_cache[62] || (_cache[62] = [
                        _createTextVNode(" 重新选择文件 ", -1)
                      ]))]),
                      _: 1
                    }))
                  : _createCommentVNode("", true),
                (hasPreviewItems.value)
                  ? (_openBlock(), _createBlock(_component_VTooltip, {
                      key: 1,
                      location: "top",
                      text: allSelectedPreviewTargetsAreStream.value ? 'STRM 资源暂不支持智能调轴。' : (hasSelectedPreviewStreamTargets.value ? 'STRM 目标会跳过调轴，其余本地视频正常处理。' : '写入前会分析视频/字幕时间轴，可能占用 CPU 并造成短暂卡顿。')
                    }, {
                      activator: _withCtx(({ props: tooltipProps }) => [
                        _createElementVNode("div", _mergeProps(tooltipProps, { class: "timeline-action" }), [
                          _createVNode(_component_VSwitch, {
                            modelValue: fixTimeline.value,
                            "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((fixTimeline).value = $event)),
                            color: "primary",
                            density: "comfortable",
                            "hide-details": "",
                            disabled: !timelineAvailable.value || allSelectedPreviewTargetsAreStream.value,
                            label: hasSelectedPreviewStreamTargets.value ? '智能调轴（STRM跳过）' : '智能调轴'
                          }, null, 8, ["modelValue", "disabled", "label"])
                        ], 16)
                      ]),
                      _: 1
                    }, 8, ["text"]))
                  : _createCommentVNode("", true),
                (hasPreviewItems.value)
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 2,
                      color: "success",
                      disabled: !canApply.value,
                      loading: applying.value,
                      onClick: applyUpload
                    }, {
                      default: _withCtx(() => [...(_cache[63] || (_cache[63] = [
                        _createTextVNode(" 写入字幕 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled", "loading"]))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                (!hasPreviewItems.value)
                  ? (_openBlock(), _createElementBlock("div", {
                      key: 0,
                      class: _normalizeClass(["dropzone", { dragging: dragging.value }]),
                      onDrop: handleDrop,
                      onDragover: handleDragOver,
                      onDragleave: handleDragLeave
                    }, [
                      _cache[65] || (_cache[65] = _createElementVNode("div", { class: "dropzone-icon" }, "SRT / ASS / ZIP / RAR", -1)),
                      _cache[66] || (_cache[66] = _createElementVNode("div", { class: "dropzone-title" }, "把字幕或压缩包拖到这里", -1)),
                      _cache[67] || (_cache[67] = _createElementVNode("div", { class: "dropzone-text" }, " 支持字幕文件、ZIP、RAR；RAR 需容器内解压器支持。 ", -1)),
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        variant: "flat",
                        disabled: preparing.value,
                        loading: preparing.value,
                        onClick: openFileDialog
                      }, {
                        default: _withCtx(() => [...(_cache[64] || (_cache[64] = [
                          _createTextVNode(" 选择文件 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled", "loading"]),
                      _createElementVNode("input", {
                        ref_key: "fileInputRef",
                        ref: fileInputRef,
                        class: "hidden-input",
                        type: "file",
                        multiple: "",
                        accept: ".srt,.ass,.ssa,.sbv,.sub,.vtt,.webvtt,.zip,.rar",
                        onChange: onPickFiles
                      }, null, 544)
                    ], 34))
                  : _createCommentVNode("", true),
                (!hasPreviewItems.value)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_92, [
                      _createElementVNode("span", {
                        class: _normalizeClass({ ok: rarPythonAvailable.value })
                      }, "rarfile：" + _toDisplayString(rarPythonAvailable.value ? '已安装' : '将由 requirements.txt 安装'), 3),
                      _createElementVNode("span", {
                        class: _normalizeClass({ ok: rarAvailable.value })
                      }, "RAR 解压器：" + _toDisplayString(rarAvailable.value ? archiveStatus.value.rar_tool || '可用' : '未检测到'), 3),
                      _createElementVNode("span", {
                        class: _normalizeClass({ ok: rarDependencyStatus.value.state === 'ready' })
                      }, " 处理方式：" + _toDisplayString(rarDependencyModeLabel(archiveStatus.value.dependency_mode)), 3),
                      _createElementVNode("button", {
                        class: "support-help",
                        type: "button",
                        onClick: openRarHelp
                      }, " RAR 不能解压？查看处理方式 "),
                      _createElementVNode("span", {
                        class: _normalizeClass({ ok: timelineAvailable.value })
                      }, " 智能调轴：" + _toDisplayString(timelineAvailable.value ? '可用' : `缺少 ${timelineMissing.value || '依赖'}`), 3)
                    ]))
                  : _createCommentVNode("", true),
                (!hasPreviewItems.value && files.value.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_93, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(files.value, (file) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: `${file.name}-${file.size}`,
                          class: "file-row"
                        }, [
                          _createElementVNode("div", null, [
                            _createElementVNode("strong", null, _toDisplayString(file.name), 1),
                            _createElementVNode("span", null, _toDisplayString(formatBytes(file.size)), 1)
                          ]),
                          _createVNode(_component_VBtn, {
                            size: "small",
                            variant: "text",
                            color: "error",
                            onClick: $event => (removeFile(file))
                          }, {
                            default: _withCtx(() => [...(_cache[68] || (_cache[68] = [
                              _createTextVNode("移除", -1)
                            ]))]),
                            _: 1
                          }, 8, ["onClick"])
                        ]))
                      }), 128))
                    ]))
                  : _createCommentVNode("", true),
                (hasPreviewItems.value)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_94, [
                      _createElementVNode("div", _hoisted_95, [
                        _cache[70] || (_cache[70] = _createElementVNode("div", null, [
                          _createElementVNode("div", { class: "section-kicker" }, "字幕匹配"),
                          _createElementVNode("h3", null, "确认集数与输出文件名")
                        ], -1)),
                        _createElementVNode("div", _hoisted_96, [
                          _createVNode(_component_VTextField, {
                            modelValue: batchLanguageSuffix.value,
                            "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((batchLanguageSuffix).value = $event)),
                            label: "批量语言后缀",
                            placeholder: "chi / eng / jpn",
                            variant: "outlined",
                            density: "comfortable",
                            "hide-details": "",
                            onKeyup: _withKeys(applyBatchLanguageSuffix, ["enter"])
                          }, null, 8, ["modelValue"]),
                          _createVNode(_component_VBtn, {
                            variant: "tonal",
                            color: "primary",
                            disabled: !batchLanguageSuffix.value.trim(),
                            onClick: applyBatchLanguageSuffix
                          }, {
                            default: _withCtx(() => [...(_cache[69] || (_cache[69] = [
                              _createTextVNode(" 应用到全部 ", -1)
                            ]))]),
                            _: 1
                          }, 8, ["disabled"])
                        ])
                      ]),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(preview.value.items, (item) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: item.upload_id,
                          class: _normalizeClass(["preview-row", { disabled: item.selected === false }])
                        }, [
                          _createVNode(_component_VCheckbox, {
                            "model-value": item.selected !== false,
                            density: "compact",
                            "hide-details": "",
                            "onUpdate:modelValue": value => togglePreviewItem(item.upload_id, value)
                          }, null, 8, ["model-value", "onUpdate:modelValue"]),
                          _createElementVNode("div", _hoisted_97, [
                            _createElementVNode("strong", null, _toDisplayString(item.source_name), 1),
                            _createElementVNode("span", null, _toDisplayString(item.archive_name ? `来自 ${item.archive_name} · ` : '') + _toDisplayString(item.detected_label || '未知语言'), 1)
                          ]),
                          _createVNode(_component_VSelect, {
                            "model-value": item.target_id,
                            items: targetSelectItems.value,
                            label: "对应集数",
                            variant: "outlined",
                            density: "comfortable",
                            "hide-details": "",
                            disabled: item.selected === false,
                            "onUpdate:modelValue": value => updatePreviewTarget(item.upload_id, value)
                          }, null, 8, ["model-value", "items", "disabled", "onUpdate:modelValue"]),
                          _createVNode(_component_VTextField, {
                            "model-value": item.language_suffix,
                            label: "语言后缀",
                            variant: "outlined",
                            density: "comfortable",
                            "hide-details": "",
                            disabled: item.selected === false,
                            "onUpdate:modelValue": value => updateLanguageSuffix(item.upload_id, value)
                          }, null, 8, ["model-value", "disabled", "onUpdate:modelValue"]),
                          _createElementVNode("div", _hoisted_98, [
                            _cache[71] || (_cache[71] = _createElementVNode("span", null, "改名为", -1)),
                            _createElementVNode("strong", null, _toDisplayString(item.output_name || buildOutputName(uploadTargets.value.find(target => target.id === item.target_id), item) || '待选择目标'), 1)
                          ])
                        ], 2))
                      }), 128))
                    ]))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: rarHelpDialog.value,
      "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((rarHelpDialog).value = $event)),
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
                _cache[72] || (_cache[72] = _createElementVNode("span", null, "RAR 解压器说明", -1)),
                _createVNode(_component_VBtn, {
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[26] || (_cache[26] = $event => (rarHelpDialog.value = false))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _cache[73] || (_cache[73] = _createElementVNode("div", { class: "rar-help-summary" }, [
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
                _createElementVNode("div", _hoisted_99, [
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(rarHelpItems, (item) => {
                    return _createElementVNode("section", {
                      key: item.title,
                      class: "rar-help-row"
                    }, [
                      _createElementVNode("div", _hoisted_100, [
                        _createElementVNode("div", _hoisted_101, [
                          _createElementVNode("span", _hoisted_102, _toDisplayString(item.badge), 1),
                          _createElementVNode("strong", null, _toDisplayString(item.title), 1)
                        ]),
                        _createElementVNode("button", {
                          type: "button",
                          class: "rar-help-copy",
                          onClick: $event => (copyHelpText(item.command, item.copyLabel))
                        }, _toDisplayString(item.button), 9, _hoisted_103)
                      ]),
                      _createElementVNode("p", null, _toDisplayString(item.description), 1),
                      _createElementVNode("div", _hoisted_104, [
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
                (rarDependencyStatus.value.message)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 2,
                      class: "mt-4",
                      type: rarDependencyStatus.value.state === 'ready' ? 'success' : 'warning',
                      variant: "tonal",
                      text: rarDependencyStatus.value.message
                    }, null, 8, ["type", "text"]))
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
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-1397e546"]]);

export { AppPage as default };
