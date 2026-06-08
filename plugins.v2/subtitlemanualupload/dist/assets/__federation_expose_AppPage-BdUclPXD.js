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

const {createElementVNode:_createElementVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,resolveComponent:_resolveComponent,createBlock:_createBlock,createTextVNode:_createTextVNode,withCtx:_withCtx,createVNode:_createVNode,withKeys:_withKeys,renderList:_renderList,Fragment:_Fragment,unref:_unref,toDisplayString:_toDisplayString,normalizeClass:_normalizeClass,mergeProps:_mergeProps} = await importShared('vue');


const _hoisted_1 = { class: "subtitle-upload-page" };
const _hoisted_2 = {
  key: 0,
  class: "hero-card"
};
const _hoisted_3 = {
  key: 3,
  class: "media-stage"
};
const _hoisted_4 = { class: "search-head" };
const _hoisted_5 = { class: "search-bar" };
const _hoisted_6 = {
  key: 0,
  class: "media-list"
};
const _hoisted_7 = ["onClick"];
const _hoisted_8 = { class: "poster-frame" };
const _hoisted_9 = ["src", "alt"];
const _hoisted_10 = { key: 1 };
const _hoisted_11 = { class: "media-copy" };
const _hoisted_12 = { class: "media-type" };
const _hoisted_13 = {
  key: 1,
  class: "empty-state"
};
const _hoisted_14 = {
  key: 4,
  class: "episode-stage"
};
const _hoisted_15 = { class: "detail-head" };
const _hoisted_16 = { class: "selected-media" };
const _hoisted_17 = { class: "mini-poster" };
const _hoisted_18 = ["src", "alt"];
const _hoisted_19 = { key: 1 };
const _hoisted_20 = { class: "section-kicker" };
const _hoisted_21 = {
  key: 0,
  class: "season-strip"
};
const _hoisted_22 = ["onClick"];
const _hoisted_23 = { class: "toolbar-row" };
const _hoisted_24 = {
  key: 1,
  class: "episode-list"
};
const _hoisted_25 = { class: "episode-index" };
const _hoisted_26 = { class: "episode-copy" };
const _hoisted_27 = { class: "episode-title" };
const _hoisted_28 = { class: "episode-path" };
const _hoisted_29 = {
  key: 2,
  class: "empty-state"
};
const _hoisted_30 = {
  key: 3,
  class: "result-panel"
};
const _hoisted_31 = {
  key: 1,
  class: "support-row"
};
const _hoisted_32 = {
  key: 2,
  class: "file-list"
};
const _hoisted_33 = {
  key: 3,
  class: "preview-list"
};
const _hoisted_34 = { class: "preview-head" };
const _hoisted_35 = { class: "batch-language" };
const _hoisted_36 = { class: "subtitle-source" };
const _hoisted_37 = { class: "output-name" };
const _hoisted_38 = { class: "rar-help-list" };
const _hoisted_39 = { class: "rar-help-row-head" };
const _hoisted_40 = { class: "rar-help-row-title" };
const _hoisted_41 = { class: "rar-help-step" };
const _hoisted_42 = ["onClick"];
const _hoisted_43 = { class: "command-block" };

const {computed,onMounted,ref} = await importShared('vue');

const rarContainerInstallCommand = `docker exec -it moviepilot bash
apt-get update
apt-get install -y p7zip-full unrar-free`;
const rarStaticInstallCommand = `curl -fsSLo /tmp/mp-7zz.sh \\
  https://raw.githubusercontent.com/ifsherlock/MoviePilot-Plugins/main/plugins.v2/subtitlemanualupload/scripts/install-static-7zz.sh
sudo bash /tmp/mp-7zz.sh`;
const rarComposeMountCommand = `volumes:
  - /volume1/docker/moviepilot/tools/7zz:/usr/local/bin/7z:ro

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
});

const loading = ref(false);
const searching = ref(false);
const resolving = ref(false);
const refreshing = ref(false);
const preparing = ref(false);
const applying = ref(false);
const clearing = ref(false);
const dragging = ref(false);
const message = ref('');
const error = ref('');
const searchKeyword = ref('');
const mediaType = ref('all');
const medias = ref([]);
const selectedMedia = ref(null);
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

const rarHelpItems = [
  {
    badge: '临时安装',
    title: '容器内临时安装',
    description: '适合临时测试，容器重建后可能失效。',
    button: '复制命令',
    copyLabel: '容器安装命令',
    command: rarContainerInstallCommand,
  },
  {
    badge: '静态文件',
    title: '下载静态 7zz',
    description: '在宿主机执行，默认安装到 MoviePilot 部署目录的 tools/7zz。',
    button: '复制脚本',
    copyLabel: '7zz 安装脚本',
    command: rarStaticInstallCommand,
  },
  {
    badge: '容器映射',
    title: '映射到 MoviePilot 容器',
    description: '把宿主机二进制映射为容器内 /usr/local/bin/7z。',
    button: '复制映射',
    copyLabel: '映射配置',
    command: rarComposeMountCommand,
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
  const items = preview.value?.items || [];
  return items.length > 0 && items.every(item => item.target_id)
});
const hasPreviewItems = computed(() => (preview.value?.items || []).length > 0);
const timelineStatus = computed(() => status.value?.timeline_fixer || { available: false, modules: {} });
const timelineAvailable = computed(() => timelineStatus.value.available === true);
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

function clearTargetState() {
  seasons.value = [];
  selectedSeason.value = 'all';
  targets.value = [];
  selectedTargetIds.value = [];
  preview.value = null;
  lastWritten.value = [];
}

async function loadStatus() {
  loading.value = true;
  error.value = '';
  try {
    const response = await props.api.get(`${pluginBase.value}/status`);
    status.value = unwrapResponse(response) || status.value;
  } catch (err) {
    error.value = errorMessage(err, '加载插件状态失败');
  } finally {
    loading.value = false;
  }
}

async function refreshIndex() {
  refreshing.value = true;
  error.value = '';
  try {
    const response = await props.api.post(`${pluginBase.value}/refresh_index`, {});
    message.value = response?.message || 'MoviePilot 本地整理记录为实时读取，无需重建索引';
  } catch (err) {
    error.value = errorMessage(err, '刷新状态失败');
  } finally {
    refreshing.value = false;
  }
}

async function runSearch() {
  const keyword = searchKeyword.value.trim();
  searching.value = true;
  error.value = '';
  message.value = '';
  selectedMedia.value = null;
  clearTargetState();
  try {
    const params = new URLSearchParams();
    params.set('keyword', keyword);
    params.set('media_type', mediaType.value);
    params.set('limit', '48');
    const response = await props.api.get(`${pluginBase.value}/search?${params.toString()}`);
    const data = unwrapResponse(response) || {};
    medias.value = data.medias || [];
    if (!medias.value.length) {
      message.value = keyword
        ? '本地资源库里没有匹配的视频目标，请换个关键词试试'
        : '本地整理记录里暂时没有可用的视频目标';
    }
  } catch (err) {
    error.value = errorMessage(err, '搜索本地资源失败');
  } finally {
    searching.value = false;
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

function openUploadDialog(scopeTargets, title) {
  const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false);
  if (!usableTargets.length) {
    error.value = '没有可上传的目标：选中的集数可能都已锁定';
    return
  }
  uploadScopeTargets.value = usableTargets;
  uploadTitle.value = title;
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

function onPickFiles(event) {
  const pickedFiles = Array.from(event?.target?.files || []);
  mergeFiles(pickedFiles);
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
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

function handleDrop(event) {
  event.preventDefault();
  dragging.value = false;
  const dropped = Array.from(event.dataTransfer?.files || []);
  mergeFiles(dropped);
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
  if (!canPrepare.value) return
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
      preview.value.items.forEach(item => {
        const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id);
        item.output_name = item.output_name || buildOutputName(target, item);
      });
    }
    message.value = response?.message || '已生成匹配预览';
  } catch (err) {
    error.value = errorMessage(err, '上传预解析失败');
  } finally {
    preparing.value = false;
  }
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

function applyBatchLanguageSuffix() {
  const suffix = batchLanguageSuffix.value.trim();
  if (!suffix || !preview.value?.items?.length) return
  preview.value.items.forEach(item => {
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
      fix_timeline: fixTimeline.value,
      items: preview.value.items.map(item => ({
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

onMounted(async () => {
  await loadStatus();
  await runSearch();
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
  const _component_VListSubheader = _resolveComponent("VListSubheader");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VMenu = _resolveComponent("VMenu");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VTooltip = _resolveComponent("VTooltip");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [...(_cache[10] || (_cache[10] = [
          _createElementVNode("div", null, [
            _createElementVNode("h1", null, "字幕匹配"),
            _createElementVNode("p", null, "从 MoviePilot 本地库选择资源，上传字幕后确认匹配与改名结果。")
          ], -1)
        ]))]))
      : _createCommentVNode("", true),
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          class: "mb-4",
          type: "error",
          variant: "tonal",
          text: error.value
        }, null, 8, ["text"]))
      : (message.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 2,
            class: "mb-4",
            type: "success",
            variant: "tonal",
            text: message.value
          }, null, 8, ["text"]))
        : _createCommentVNode("", true),
    (!selectedMedia.value)
      ? (_openBlock(), _createElementBlock("section", _hoisted_3, [
          _createVNode(_component_VCard, {
            class: "glass-card search-card",
            rounded: "xl",
            elevation: "0"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardText, null, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_4, [
                    _cache[12] || (_cache[12] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "section-kicker" }, "资源选择"),
                      _createElementVNode("h2", null, "选择本地已有资源"),
                      _createElementVNode("p", null, "仅展示 MoviePilot 已整理到本地库的视频资源。")
                    ], -1)),
                    _createVNode(_component_VBtn, {
                      variant: "text",
                      loading: refreshing.value,
                      onClick: refreshIndex
                    }, {
                      default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
                        _createTextVNode("接口状态", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _createElementVNode("div", _hoisted_5, [
                    _createVNode(_component_VTextField, {
                      modelValue: searchKeyword.value,
                      "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((searchKeyword).value = $event)),
                      label: "片名、剧名或文件关键词",
                      variant: "outlined",
                      density: "comfortable",
                      "hide-details": "",
                      clearable: "",
                      onKeyup: _withKeys(runSearch, ["enter"])
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSelect, {
                      modelValue: mediaType.value,
                      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((mediaType).value = $event)),
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
                      loading: searching.value,
                      onClick: runSearch
                    }, {
                      default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                        _createTextVNode("搜索", -1)
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
          (medias.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_6, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(medias.value, (media) => {
                  return (_openBlock(), _createElementBlock("button", {
                    key: media.id,
                    class: "media-card",
                    onClick: $event => (selectMedia(media))
                  }, [
                    _createElementVNode("div", _hoisted_8, [
                      (media.poster_url)
                        ? (_openBlock(), _createElementBlock("img", {
                            key: 0,
                            src: media.poster_url,
                            alt: _unref(mediaLabel)(media)
                          }, null, 8, _hoisted_9))
                        : (_openBlock(), _createElementBlock("span", _hoisted_10, _toDisplayString(formatMediaType(media.media_type)), 1))
                    ]),
                    _createElementVNode("div", _hoisted_11, [
                      _createElementVNode("div", _hoisted_12, _toDisplayString(formatMediaType(media.media_type)), 1),
                      _createElementVNode("h3", null, _toDisplayString(_unref(mediaLabel)(media)), 1),
                      _createElementVNode("p", null, _toDisplayString(mediaStat(media)), 1)
                    ]),
                    _createVNode(_component_VIcon, { icon: "mdi-chevron-right" })
                  ], 8, _hoisted_7))
                }), 128))
              ]))
            : (_openBlock(), _createElementBlock("div", _hoisted_13, _toDisplayString(searching.value ? '正在读取本地资源...' : '输入关键词搜索；留空搜索会显示最近整理的视频。'), 1))
        ]))
      : (_openBlock(), _createElementBlock("section", _hoisted_14, [
          _createVNode(_component_VCard, {
            class: "glass-card detail-card",
            rounded: "xl",
            elevation: "0"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardText, null, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_15, [
                    _createElementVNode("div", _hoisted_16, [
                      _createElementVNode("button", {
                        class: "back-btn",
                        onClick: resetSelection
                      }, [
                        _createVNode(_component_VIcon, { icon: "mdi-arrow-left" })
                      ]),
                      _createElementVNode("div", _hoisted_17, [
                        (selectedMedia.value.poster_url)
                          ? (_openBlock(), _createElementBlock("img", {
                              key: 0,
                              src: selectedMedia.value.poster_url,
                              alt: _unref(mediaLabel)(selectedMedia.value)
                            }, null, 8, _hoisted_18))
                          : (_openBlock(), _createElementBlock("span", _hoisted_19, _toDisplayString(formatMediaType(selectedMedia.value.media_type)), 1))
                      ]),
                      _createElementVNode("div", null, [
                        _createElementVNode("div", _hoisted_20, _toDisplayString(formatMediaType(selectedMedia.value.media_type)), 1),
                        _createElementVNode("h2", null, _toDisplayString(_unref(mediaLabel)(selectedMedia.value)), 1),
                        _createElementVNode("p", null, _toDisplayString(visibleTargets.value.length) + " 个本地目标 · " + _toDisplayString(selectedTargets.value.length) + " 个已选 · " + _toDisplayString(lockedTargetIds.value.length) + " 个锁定", 1)
                      ])
                    ]),
                    _createVNode(_component_VBtn, {
                      variant: "tonal",
                      loading: resolving.value,
                      onClick: _cache[2] || (_cache[2] = $event => (loadTargets(selectedMedia.value, selectedSeason.value)))
                    }, {
                      default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
                        _createTextVNode(" 刷新列表 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  (selectedMedia.value.media_type === 'tv')
                    ? (_openBlock(), _createElementBlock("div", _hoisted_21, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(seasonCards.value, (season) => {
                          return (_openBlock(), _createElementBlock("button", {
                            key: season.value,
                            class: _normalizeClass(["season-card", { active: selectedSeason.value === season.value }]),
                            onClick: $event => (changeSeason(season.value))
                          }, [
                            _createElementVNode("span", null, _toDisplayString(season.title), 1),
                            _createElementVNode("strong", null, _toDisplayString(season.subtitle), 1)
                          ], 10, _hoisted_22))
                        }), 128))
                      ]))
                    : _createCommentVNode("", true),
                  _createElementVNode("div", _hoisted_23, [
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
                    _createVNode(_component_VBtn, {
                      color: "error",
                      variant: "tonal",
                      disabled: !selectedTargetIds.value.length,
                      loading: clearing.value,
                      onClick: clearSelectedSubtitles
                    }, {
                      default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                        _createTextVNode(" 清空选中外挂字幕 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled", "loading"]),
                    _cache[16] || (_cache[16] = _createElementVNode("div", { class: "toolbar-hint" }, " 锁定项不参与批量上传；清空仅删除选中项外挂字幕。 ", -1))
                  ]),
                  (visibleTargets.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_24, [
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
                            _createElementVNode("div", _hoisted_25, _toDisplayString(target.media_type === 'tv' ? `E${String(target.episode || 0).padStart(2, '0')}` : 'MOV'), 1),
                            _createElementVNode("div", _hoisted_26, [
                              _createElementVNode("div", _hoisted_27, _toDisplayString(compactTargetName(target)), 1),
                              _createElementVNode("div", _hoisted_28, _toDisplayString(target.relative_path), 1)
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
                                              default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
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
                              disabled: isLocked(target.id),
                              onClick: $event => (openSingleUpload(target))
                            }, {
                              default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
                                _createTextVNode(" 单集上传 ", -1)
                              ]))]),
                              _: 1
                            }, 8, ["disabled", "onClick"])
                          ], 2))
                        }), 128))
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_29, _toDisplayString(resolving.value ? '正在读取本地视频目标...' : '这个资源没有本地视频文件。'), 1)),
                  (lastWritten.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_30, [
                        _cache[19] || (_cache[19] = _createElementVNode("div", { class: "section-kicker" }, "写入结果", -1)),
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
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ])),
    _createVNode(_component_VDialog, {
      modelValue: uploadDialog.value,
      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((uploadDialog).value = $event)),
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
                  onClick: _cache[3] || (_cache[3] = $event => (uploadDialog.value = false))
                })
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
                      _cache[21] || (_cache[21] = _createElementVNode("div", { class: "dropzone-icon" }, "SRT / ASS / ZIP / RAR", -1)),
                      _cache[22] || (_cache[22] = _createElementVNode("div", { class: "dropzone-title" }, "把字幕或压缩包拖到这里", -1)),
                      _cache[23] || (_cache[23] = _createElementVNode("div", { class: "dropzone-text" }, " 支持字幕文件、ZIP、RAR；RAR 需容器内解压器支持。 ", -1)),
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        variant: "flat",
                        onClick: openFileDialog
                      }, {
                        default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                          _createTextVNode("选择文件", -1)
                        ]))]),
                        _: 1
                      }),
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
                  ? (_openBlock(), _createElementBlock("div", _hoisted_31, [
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
                  ? (_openBlock(), _createElementBlock("div", _hoisted_32, [
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
                            default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                              _createTextVNode("移除", -1)
                            ]))]),
                            _: 1
                          }, 8, ["onClick"])
                        ]))
                      }), 128))
                    ]))
                  : _createCommentVNode("", true),
                (hasPreviewItems.value)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_33, [
                      _createElementVNode("div", _hoisted_34, [
                        _cache[26] || (_cache[26] = _createElementVNode("div", null, [
                          _createElementVNode("div", { class: "section-kicker" }, "字幕匹配"),
                          _createElementVNode("h3", null, "确认集数与输出文件名")
                        ], -1)),
                        _createElementVNode("div", _hoisted_35, [
                          _createVNode(_component_VTextField, {
                            modelValue: batchLanguageSuffix.value,
                            "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((batchLanguageSuffix).value = $event)),
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
                            default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                              _createTextVNode(" 应用到全部 ", -1)
                            ]))]),
                            _: 1
                          }, 8, ["disabled"])
                        ])
                      ]),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(preview.value.items, (item) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: item.upload_id,
                          class: "preview-row"
                        }, [
                          _createElementVNode("div", _hoisted_36, [
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
                            "onUpdate:modelValue": value => updatePreviewTarget(item.upload_id, value)
                          }, null, 8, ["model-value", "items", "onUpdate:modelValue"]),
                          _createVNode(_component_VTextField, {
                            "model-value": item.language_suffix,
                            label: "语言后缀",
                            variant: "outlined",
                            density: "comfortable",
                            "hide-details": "",
                            "onUpdate:modelValue": value => updateLanguageSuffix(item.upload_id, value)
                          }, null, 8, ["model-value", "onUpdate:modelValue"]),
                          _createElementVNode("div", _hoisted_37, [
                            _cache[27] || (_cache[27] = _createElementVNode("span", null, "改名为", -1)),
                            _createElementVNode("strong", null, _toDisplayString(item.output_name || buildOutputName(uploadTargets.value.find(target => target.id === item.target_id), item) || '待选择目标'), 1)
                          ])
                        ]))
                      }), 128))
                    ]))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, { class: "dialog-actions" }, {
              default: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[5] || (_cache[5] = $event => (uploadDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
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
                      default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                        _createTextVNode(" 重新选择文件 ", -1)
                      ]))]),
                      _: 1
                    }))
                  : _createCommentVNode("", true),
                (!hasPreviewItems.value)
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 1,
                      color: "primary",
                      variant: "tonal",
                      disabled: !canPrepare.value,
                      loading: preparing.value,
                      onClick: prepareUpload
                    }, {
                      default: _withCtx(() => [...(_cache[30] || (_cache[30] = [
                        _createTextVNode(" 生成匹配预览 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled", "loading"]))
                  : _createCommentVNode("", true),
                (hasPreviewItems.value)
                  ? (_openBlock(), _createBlock(_component_VTooltip, {
                      key: 2,
                      location: "top",
                      text: "写入前会分析视频/字幕时间轴，可能占用 CPU 并造成短暂卡顿。"
                    }, {
                      activator: _withCtx(({ props: tooltipProps }) => [
                        _createElementVNode("div", _mergeProps(tooltipProps, { class: "timeline-action" }), [
                          _createVNode(_component_VSwitch, {
                            modelValue: fixTimeline.value,
                            "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((fixTimeline).value = $event)),
                            color: "primary",
                            density: "comfortable",
                            "hide-details": "",
                            disabled: !timelineAvailable.value,
                            label: "智能调轴"
                          }, null, 8, ["modelValue", "disabled"])
                        ], 16)
                      ]),
                      _: 1
                    }))
                  : _createCommentVNode("", true),
                (hasPreviewItems.value)
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 3,
                      color: "success",
                      disabled: !canApply.value,
                      loading: applying.value,
                      onClick: applyUpload
                    }, {
                      default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                        _createTextVNode(" 写入字幕 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled", "loading"]))
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
      "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((rarHelpDialog).value = $event)),
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
                _cache[32] || (_cache[32] = _createElementVNode("span", null, "RAR 解压器说明", -1)),
                _createVNode(_component_VBtn, {
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[8] || (_cache[8] = $event => (rarHelpDialog.value = false))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _cache[33] || (_cache[33] = _createElementVNode("div", { class: "rar-help-summary" }, [
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
                    _createElementVNode("strong", null, "建议："),
                    _createTextVNode("长期使用推荐把宿主机静态 "),
                    _createElementVNode("code", null, "7zz"),
                    _createTextVNode(" 映射到容器内 "),
                    _createElementVNode("code", null, "/usr/local/bin/7z"),
                    _createTextVNode("。")
                  ])
                ], -1)),
                _createElementVNode("div", _hoisted_38, [
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(rarHelpItems, (item) => {
                    return _createElementVNode("section", {
                      key: item.title,
                      class: "rar-help-row"
                    }, [
                      _createElementVNode("div", _hoisted_39, [
                        _createElementVNode("div", _hoisted_40, [
                          _createElementVNode("span", _hoisted_41, _toDisplayString(item.badge), 1),
                          _createElementVNode("strong", null, _toDisplayString(item.title), 1)
                        ]),
                        _createElementVNode("button", {
                          type: "button",
                          class: "rar-help-copy",
                          onClick: $event => (copyHelpText(item.command, item.copyLabel))
                        }, _toDisplayString(item.button), 9, _hoisted_42)
                      ]),
                      _createElementVNode("p", null, _toDisplayString(item.description), 1),
                      _createElementVNode("div", _hoisted_43, [
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
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-2d71fca5"]]);

export { AppPage as default };
