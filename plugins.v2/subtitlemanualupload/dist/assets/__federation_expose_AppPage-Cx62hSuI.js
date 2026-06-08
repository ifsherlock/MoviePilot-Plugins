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
const _hoisted_31 = { class: "support-row" };
const _hoisted_32 = {
  key: 0,
  class: "file-list"
};
const _hoisted_33 = {
  key: 1,
  class: "preview-list"
};
const _hoisted_34 = { class: "preview-head" };
const _hoisted_35 = { class: "subtitle-source" };
const _hoisted_36 = { class: "output-name" };

const {computed,onMounted,ref} = await importShared('vue');


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
const lastWritten = ref([]);

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
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [...(_cache[10] || (_cache[10] = [
          _createElementVNode("div", null, [
            _createElementVNode("div", { class: "hero-eyebrow" }, "MoviePilot Local Subtitle Desk"),
            _createElementVNode("h1", null, "字幕手传匹配"),
            _createElementVNode("p", null, "只读取本地媒体库已有资源。先选择电影或剧集，再按季度/集数上传字幕、ZIP 或 RAR，并在写入前确认自动改名结果。")
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
                      _createElementVNode("div", { class: "section-kicker" }, "第一步"),
                      _createElementVNode("h2", null, "选择本地已有资源"),
                      _createElementVNode("p", null, "搜索结果只来自 MoviePilot 本地整理记录，不再展示库里没有的视频。")
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
                    _cache[16] || (_cache[16] = _createElementVNode("div", { class: "toolbar-hint" }, " 锁定的集数会在批量上传时自动跳过；清空字幕只作用于你勾选的集。 ", -1))
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
                _createElementVNode("div", {
                  class: _normalizeClass(["dropzone", { dragging: dragging.value }]),
                  onDrop: handleDrop,
                  onDragover: handleDragOver,
                  onDragleave: handleDragLeave
                }, [
                  _cache[21] || (_cache[21] = _createElementVNode("div", { class: "dropzone-icon" }, "SRT / ASS / ZIP / RAR", -1)),
                  _cache[22] || (_cache[22] = _createElementVNode("div", { class: "dropzone-title" }, "把字幕或压缩包拖到这里", -1)),
                  _cache[23] || (_cache[23] = _createElementVNode("div", { class: "dropzone-text" }, " ZIP 会自动解包；RAR 已加入轻量 Python 依赖 rarfile，但仍需要容器内有 unrar、bsdtar、7z、7za 或 7zz。 ", -1)),
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
                ], 34),
                _createElementVNode("div", _hoisted_31, [
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
                    onClick: _cache[4] || (_cache[4] = $event => (rarHelpDialog.value = true))
                  }, " RAR 不能解压？查看处理方式 "),
                  _createElementVNode("span", {
                    class: _normalizeClass({ ok: timelineAvailable.value })
                  }, " 智能调轴：" + _toDisplayString(timelineAvailable.value ? '可用' : `缺少 ${timelineMissing.value || '依赖'}`), 3)
                ]),
                (files.value.length)
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
                (preview.value?.items?.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_33, [
                      _createElementVNode("div", _hoisted_34, [
                        _cache[25] || (_cache[25] = _createElementVNode("div", null, [
                          _createElementVNode("div", { class: "section-kicker" }, "匹配预览"),
                          _createElementVNode("h3", null, "确认字幕对应集数和落盘文件名")
                        ], -1)),
                        _createVNode(_component_VSwitch, {
                          modelValue: fixTimeline.value,
                          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((fixTimeline).value = $event)),
                          color: "primary",
                          density: "comfortable",
                          "hide-details": "",
                          disabled: !timelineAvailable.value,
                          label: "写入前智能调轴"
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(preview.value.items, (item) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: item.upload_id,
                          class: "preview-row"
                        }, [
                          _createElementVNode("div", _hoisted_35, [
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
                          _createElementVNode("div", _hoisted_36, [
                            _cache[26] || (_cache[26] = _createElementVNode("span", null, "改名为", -1)),
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
                  onClick: _cache[6] || (_cache[6] = $event => (uploadDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                    _createTextVNode("关闭", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "tonal",
                  disabled: !canPrepare.value,
                  loading: preparing.value,
                  onClick: prepareUpload
                }, {
                  default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
                    _createTextVNode(" 生成匹配预览 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"]),
                _createVNode(_component_VBtn, {
                  color: "success",
                  disabled: !canApply.value,
                  loading: applying.value,
                  onClick: applyUpload
                }, {
                  default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                    _createTextVNode(" 写入字幕 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"])
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
      "max-width": "760"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, {
          class: "rar-help-dialog",
          rounded: "xl"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dialog-title" }, {
              default: _withCtx(() => [
                _cache[30] || (_cache[30] = _createElementVNode("span", null, "RAR 解压器说明", -1)),
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
                _cache[31] || (_cache[31] = _createElementVNode("div", { class: "help-intro" }, [
                  _createTextVNode(" 插件已经声明了最轻的 Python 依赖 "),
                  _createElementVNode("code", null, "rarfile"),
                  _createTextVNode("，但它不是纯 Python 解压器。 真正读取 RAR 内容时，容器里还必须能执行 "),
                  _createElementVNode("code", null, "unrar"),
                  _createTextVNode("、"),
                  _createElementVNode("code", null, "7z"),
                  _createTextVNode("、"),
                  _createElementVNode("code", null, "7za"),
                  _createTextVNode("、"),
                  _createElementVNode("code", null, "7zz"),
                  _createTextVNode(" 或 "),
                  _createElementVNode("code", null, "bsdtar"),
                  _createTextVNode("。 ")
                ], -1)),
                _cache[32] || (_cache[32] = _createElementVNode("div", { class: "help-grid" }, [
                  _createElementVNode("div", { class: "help-card" }, [
                    _createElementVNode("strong", null, "插件设置：容器内安装"),
                    _createElementVNode("p", null, "适合马上测试。保存设置后插件加载时会尝试安装，容器删除或重建后可能丢失。"),
                    _createElementVNode("pre", null, "docker exec -it moviepilot bash\napt-get update\napt-get install -y p7zip-full unrar-free")
                  ]),
                  _createElementVNode("div", { class: "help-card" }, [
                    _createElementVNode("strong", null, "一键下载静态 7zz"),
                    _createElementVNode("p", null, [
                      _createTextVNode("在宿主机执行脚本，它会下载官方 Linux 版 7zz，优先安装到 MoviePilot 宿主机部署目录下的 "),
                      _createElementVNode("code", null, "tools/7zz"),
                      _createTextVNode(" 并打印映射片段。")
                    ]),
                    _createElementVNode("pre", null, "curl -fsSLo /tmp/mp-7zz.sh \\\n  https://raw.githubusercontent.com/ifsherlock/MoviePilot-Plugins/main/plugins.v2/subtitlemanualupload/scripts/install-static-7zz.sh\nsudo bash /tmp/mp-7zz.sh")
                  ]),
                  _createElementVNode("div", { class: "help-card" }, [
                    _createElementVNode("strong", null, "推荐映射静态二进制"),
                    _createElementVNode("p", null, [
                      _createTextVNode("把脚本输出的宿主机 "),
                      _createElementVNode("code", null, "7zz"),
                      _createTextVNode(" 路径映射成容器内 "),
                      _createElementVNode("code", null, "/usr/local/bin/7z"),
                      _createTextVNode("，比映射系统 "),
                      _createElementVNode("code", null, "7z"),
                      _createTextVNode(" 更少动态库问题。")
                    ]),
                    _createElementVNode("pre", null, "volumes:\n  - /volume1/docker/moviepilot/tools/7zz:/usr/local/bin/7z:ro\n\ndocker exec moviepilot which 7z")
                  ])
                ], -1)),
                (rarDependencyStatus.value.message)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
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
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-97231c96"]]);

export { AppPage as default };
