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

const {createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,resolveComponent:_resolveComponent,createBlock:_createBlock,createTextVNode:_createTextVNode,withCtx:_withCtx,createVNode:_createVNode,withKeys:_withKeys,renderList:_renderList,Fragment:_Fragment,unref:_unref,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "subtitle-upload-page" };
const _hoisted_2 = {
  key: 0,
  class: "hero-shell"
};
const _hoisted_3 = { class: "hero-meta" };
const _hoisted_4 = { class: "meta-card" };
const _hoisted_5 = { class: "meta-hint" };
const _hoisted_6 = { class: "workspace-grid" };
const _hoisted_7 = { class: "search-stack" };
const _hoisted_8 = { class: "search-actions" };
const _hoisted_9 = {
  key: 0,
  class: "media-list"
};
const _hoisted_10 = ["onClick"];
const _hoisted_11 = { class: "poster-shell" };
const _hoisted_12 = ["src", "alt"];
const _hoisted_13 = {
  key: 1,
  class: "poster-fallback"
};
const _hoisted_14 = { class: "media-info" };
const _hoisted_15 = { class: "media-title" };
const _hoisted_16 = { class: "media-meta" };
const _hoisted_17 = {
  key: 1,
  class: "empty-state"
};
const _hoisted_18 = {
  key: 2,
  class: "season-section"
};
const _hoisted_19 = ["disabled", "onClick"];
const _hoisted_20 = { class: "season-dot" };
const _hoisted_21 = {
  key: 0,
  class: "panel-count"
};
const _hoisted_22 = {
  key: 0,
  class: "center-empty"
};
const _hoisted_23 = { class: "selected-header" };
const _hoisted_24 = ["src", "alt"];
const _hoisted_25 = { class: "selected-title" };
const _hoisted_26 = { class: "selected-subtitle" };
const _hoisted_27 = { class: "target-list" };
const _hoisted_28 = { class: "target-index" };
const _hoisted_29 = { class: "target-copy" };
const _hoisted_30 = { class: "target-name" };
const _hoisted_31 = { class: "target-path" };
const _hoisted_32 = {
  key: 0,
  class: "empty-state compact"
};
const _hoisted_33 = {
  key: 1,
  class: "preview-section"
};
const _hoisted_34 = { class: "match-list" };
const _hoisted_35 = { class: "subtitle-source" };
const _hoisted_36 = { class: "source-name" };
const _hoisted_37 = { class: "source-meta" };
const _hoisted_38 = { key: 0 };
const _hoisted_39 = { class: "output-name" };
const _hoisted_40 = {
  key: 2,
  class: "result-section"
};
const _hoisted_41 = { class: "result-list" };
const _hoisted_42 = { class: "source-name" };
const _hoisted_43 = { class: "source-meta" };
const _hoisted_44 = {
  key: 0,
  class: "file-list"
};
const _hoisted_45 = { class: "file-name" };
const _hoisted_46 = { class: "file-size" };
const _hoisted_47 = { class: "timeline-option" };
const _hoisted_48 = { class: "timeline-hint" };
const _hoisted_49 = { key: 0 };
const _hoisted_50 = { key: 1 };
const _hoisted_51 = { class: "action-stack" };

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
const status = ref({ enabled: false, source: 'MoviePilot 本地整理记录', timeline_fixer: { available: false, modules: {} } });
const loading = ref(false);
const searching = ref(false);
const resolving = ref(false);
const refreshing = ref(false);
const preparing = ref(false);
const applying = ref(false);
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
const files = ref([]);
const preview = ref(null);
const fileInputRef = ref(null);
const fixTimeline = ref(false);
const lastWritten = ref([]);

const selectedTargets = computed(() => {
  const picked = new Set(selectedTargetIds.value || []);
  return targets.value.filter(item => picked.has(item.id))
});

const seasonItems = computed(() => {
  if (selectedMedia.value?.media_type !== 'tv') return []
  const total = seasons.value.reduce((sum, item) => sum + Number(item.local_count || 0), 0);
  return [
    { title: `全部季度 · 本地 ${total} 集`, value: 'all', count: total },
    ...seasons.value
      .filter(item => item.available)
      .map(item => ({
        title: `${seasonLabel(item.season)} · 本地 ${item.local_count || 0} 集`,
        value: item.season,
        count: item.local_count || 0,
      })),
  ]
});

const targetSelectItems = computed(() => {
  return selectedTargets.value.map(target => ({
    title: targetLabel(target),
    value: target.id,
  }))
});

const canPrepare = computed(() => selectedTargets.value.length > 0 && files.value.length > 0);
const canApply = computed(() => {
  const items = preview.value?.items || [];
  return items.length > 0 && items.every(item => item.target_id)
});
const timelineStatus = computed(() => status.value?.timeline_fixer || { available: false, modules: {} });
const timelineAvailable = computed(() => timelineStatus.value.available === true);
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

function seasonLabel(season) {
  const value = Number(season || 0);
  return value === 0 ? '特别篇' : `第 ${value} 季`
}

function compactTargetName(target) {
  if (!target) return ''
  if (target.media_type !== 'tv') return target.basename || targetLabel(target)
  const season = Number(target.season || 0);
  const episode = Number(target.episode || 0);
  if (season && episode) return `S${String(season).padStart(2, '0')}E${String(episode).padStart(2, '0')} · ${target.basename}`
  return target.basename || targetLabel(target)
}

function mediaStat(media) {
  const count = Number(media?.local_count || 0);
  if (media?.media_type === 'tv') {
    const seasonCount = Number(media?.season_count || 0);
    return `${seasonCount || '-'} 季 · ${count} 集本地视频`
  }
  return `${count || 1} 个本地视频`
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
    return `已调轴 ${formatOffset(timeline.offset_seconds)} · ${base} · 倍率 ${Number(timeline.scale_factor || 1).toFixed(4)}`
  }
  return `未调整：偏移 ${formatOffset(timeline.offset_seconds)} 小于阈值 · ${base}`
}

function buildOutputName(target, item) {
  if (!target) return ''
  const basename = target.basename || 'subtitle';
  const suffix = item?.language_suffix || 'und';
  let ext = item?.ext || '.srt';
  if (!ext.startsWith('.')) ext = `.${ext}`;
  return `${basename}.${suffix}${ext.toLowerCase()}`
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
    error.value = err?.message || '加载插件状态失败';
  } finally {
    loading.value = false;
  }
}

async function refreshIndex() {
  refreshing.value = true;
  error.value = '';
  try {
    const response = await props.api.post(`${pluginBase.value}/refresh_index`, {});
    message.value = response?.message || '已改用 MoviePilot 本地整理记录实时读取，无需刷新索引';
  } catch (err) {
    error.value = err?.message || '刷新状态失败';
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
    params.set('limit', '36');
    const response = await props.api.get(`${pluginBase.value}/search?${params.toString()}`);
    const data = unwrapResponse(response) || {};
    medias.value = data.medias || [];
    if (!medias.value.length) {
      message.value = keyword
        ? '本地资源库里没有匹配的视频目标，请换个关键词试试'
        : '本地整理记录里暂时没有可用的视频目标';
    }
  } catch (err) {
    error.value = err?.message || '搜索本地资源失败';
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
  lastWritten.value = [];
  try {
    const params = buildMediaParams(media, season || 'all');
    const response = await props.api.get(`${pluginBase.value}/targets?${params.toString()}`);
    const data = unwrapResponse(response) || {};
    selectedMedia.value = data.media || media;
    seasons.value = data.seasons || [];
    selectedSeason.value = data.selected_season ?? 'all';
    targets.value = data.targets || [];
    selectedTargetIds.value = targets.value.filter(item => item.writable !== false).map(item => item.id);

    if (!targets.value.length) {
      message.value = `${mediaLabel(selectedMedia.value)} 没有找到本地可写入的视频文件`;
    }
  } catch (err) {
    error.value = err?.message || '读取本地视频目标失败';
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
  await loadTargets(selectedMedia.value, season);
}

function resetSelection() {
  selectedMedia.value = null;
  clearTargetState();
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
    const formData = new FormData();
    formData.append('target_ids', JSON.stringify(selectedTargetIds.value));
    files.value.forEach(file => {
      formData.append('files', file);
    });
    const response = await props.api.post(`${pluginBase.value}/prepare_upload`, formData);
    preview.value = unwrapResponse(response);
    if (preview.value?.items) {
      preview.value.items.forEach(item => {
        const target = selectedTargets.value.find(targetItem => targetItem.id === item.target_id);
        item.output_name = item.output_name || buildOutputName(target, item);
      });
    }
    lastWritten.value = [];
    message.value = response?.message || '已生成匹配预览';
  } catch (err) {
    error.value = err?.message || '上传预解析失败';
  } finally {
    preparing.value = false;
  }
}

function updatePreviewTarget(uploadId, targetId) {
  const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId);
  if (!item) return
  const target = selectedTargets.value.find(targetItem => targetItem.id === targetId);
  item.target_id = targetId;
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
    message.value = response?.message || `已写入 ${data.count || 0} 个字幕文件`;
    lastWritten.value = data.written || [];
    files.value = [];
    preview.value = null;
  } catch (err) {
    error.value = err?.message || '写入字幕失败';
  } finally {
    applying.value = false;
  }
}

onMounted(loadStatus);

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
});

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VSwitch = _resolveComponent("VSwitch");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _cache[5] || (_cache[5] = _createElementVNode("div", { class: "hero-copy" }, [
            _createElementVNode("div", { class: "hero-eyebrow" }, "MoviePilot 本地字幕工作台"),
            _createElementVNode("h1", { class: "hero-title" }, "字幕手传匹配"),
            _createElementVNode("p", { class: "hero-text" }, " 只从 MoviePilot 本地资源库里找已有视频，左侧选资源和季度，中间确认目标与改名预览，右侧拖入字幕或 ZIP 后写入。 ")
          ], -1)),
          _createElementVNode("div", _hoisted_3, [
            _createElementVNode("div", _hoisted_4, [
              _cache[3] || (_cache[3] = _createElementVNode("div", { class: "meta-label" }, "数据来源", -1)),
              _cache[4] || (_cache[4] = _createElementVNode("div", { class: "meta-value" }, "LOCAL", -1)),
              _createElementVNode("div", _hoisted_5, _toDisplayString(status.value.source || 'MoviePilot 本地整理记录'), 1)
            ])
          ])
        ]))
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
    _createElementVNode("div", _hoisted_6, [
      _createVNode(_component_VCard, {
        class: "panel-card resource-panel",
        rounded: "xl",
        elevation: "0"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "panel-title" }, {
            default: _withCtx(() => [
              _cache[7] || (_cache[7] = _createElementVNode("span", null, "选择本地资源", -1)),
              _createVNode(_component_VBtn, {
                size: "small",
                variant: "text",
                loading: refreshing.value,
                onClick: refreshIndex
              }, {
                default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
                  _createTextVNode("接口状态", -1)
                ]))]),
                _: 1
              }, 8, ["loading"])
            ]),
            _: 1
          }),
          _createVNode(_component_VCardText, null, {
            default: _withCtx(() => [
              _createElementVNode("div", _hoisted_7, [
                _createVNode(_component_VTextField, {
                  modelValue: searchKeyword.value,
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((searchKeyword).value = $event)),
                  label: "片名、剧名或文件路径关键词",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": "",
                  clearable: "",
                  onKeyup: _withKeys(runSearch, ["enter"])
                }, null, 8, ["modelValue"]),
                _createElementVNode("div", _hoisted_8, [
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
                    default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                      _createTextVNode("搜索本地", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading"])
                ])
              ]),
              (medias.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_9, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(medias.value, (media) => {
                      return (_openBlock(), _createElementBlock("button", {
                        key: media.id,
                        class: _normalizeClass(["media-row", { active: selectedMedia.value?.id === media.id }]),
                        onClick: $event => (selectMedia(media))
                      }, [
                        _createElementVNode("div", _hoisted_11, [
                          (media.poster_url)
                            ? (_openBlock(), _createElementBlock("img", {
                                key: 0,
                                class: "poster",
                                src: media.poster_url,
                                alt: _unref(mediaLabel)(media)
                              }, null, 8, _hoisted_12))
                            : (_openBlock(), _createElementBlock("div", _hoisted_13, _toDisplayString(formatMediaType(media.media_type)), 1))
                        ]),
                        _createElementVNode("div", _hoisted_14, [
                          _createElementVNode("div", _hoisted_15, _toDisplayString(_unref(mediaLabel)(media)), 1),
                          _createElementVNode("div", _hoisted_16, [
                            _createElementVNode("span", null, _toDisplayString(formatMediaType(media.media_type)), 1),
                            _createElementVNode("span", null, _toDisplayString(mediaStat(media)), 1)
                          ])
                        ])
                      ], 10, _hoisted_10))
                    }), 128))
                  ]))
                : (_openBlock(), _createElementBlock("div", _hoisted_17, " 输入关键词搜索本地已有资源；留空点击搜索会显示最近整理的视频。 ")),
              (selectedMedia.value?.media_type === 'tv')
                ? (_openBlock(), _createElementBlock("div", _hoisted_18, [
                    _cache[9] || (_cache[9] = _createElementVNode("div", { class: "section-kicker" }, "季度", -1)),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(seasonItems.value, (season) => {
                      return (_openBlock(), _createElementBlock("button", {
                        key: season.value,
                        class: _normalizeClass(["season-row", { active: String(selectedSeason.value) === String(season.value) }]),
                        disabled: resolving.value,
                        onClick: $event => (changeSeason(season.value))
                      }, [
                        _createElementVNode("span", null, _toDisplayString(season.title), 1),
                        _createElementVNode("span", _hoisted_20, _toDisplayString(season.count), 1)
                      ], 10, _hoisted_19))
                    }), 128))
                  ]))
                : _createCommentVNode("", true)
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VCard, {
        class: "panel-card preview-panel",
        rounded: "xl",
        elevation: "0"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "panel-title" }, {
            default: _withCtx(() => [
              _cache[10] || (_cache[10] = _createElementVNode("span", null, "目标与预览", -1)),
              (selectedTargets.value.length)
                ? (_openBlock(), _createElementBlock("span", _hoisted_21, _toDisplayString(selectedTargets.value.length) + " 个目标", 1))
                : _createCommentVNode("", true)
            ]),
            _: 1
          }),
          _createVNode(_component_VCardText, null, {
            default: _withCtx(() => [
              (!selectedMedia.value)
                ? (_openBlock(), _createElementBlock("div", _hoisted_22, [...(_cache[11] || (_cache[11] = [
                    _createElementVNode("div", { class: "empty-title" }, "先从左侧选择一个本地资源", -1),
                    _createElementVNode("div", { class: "empty-text" }, "这里会显示该电影或剧集季度下的真实视频文件，不再混入库里没有的视频目标。", -1)
                  ]))]))
                : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                    _createElementVNode("div", _hoisted_23, [
                      (selectedMedia.value.poster_url)
                        ? (_openBlock(), _createElementBlock("img", {
                            key: 0,
                            class: "selected-poster",
                            src: selectedMedia.value.poster_url,
                            alt: _unref(mediaLabel)(selectedMedia.value)
                          }, null, 8, _hoisted_24))
                        : _createCommentVNode("", true),
                      _createElementVNode("div", null, [
                        _createElementVNode("div", _hoisted_25, _toDisplayString(_unref(mediaLabel)(selectedMedia.value)), 1),
                        _createElementVNode("div", _hoisted_26, _toDisplayString(selectedMedia.value.media_type === 'tv' ? (String(selectedSeason.value) === 'all' ? '全部季度' : seasonLabel(selectedSeason.value)) : '电影文件'), 1)
                      ]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "tonal",
                        onClick: resetSelection
                      }, {
                        default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
                          _createTextVNode("重选", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _createElementVNode("div", _hoisted_27, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(selectedTargets.value, (target) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: target.id,
                          class: "target-row"
                        }, [
                          _createElementVNode("div", _hoisted_28, _toDisplayString(target.media_type === 'tv' ? `E${String(target.episode || 0).padStart(2, '0')}` : 'MOV'), 1),
                          _createElementVNode("div", _hoisted_29, [
                            _createElementVNode("div", _hoisted_30, _toDisplayString(compactTargetName(target)), 1),
                            _createElementVNode("div", _hoisted_31, _toDisplayString(target.relative_path), 1)
                          ])
                        ]))
                      }), 128))
                    ]),
                    (!selectedTargets.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_32, _toDisplayString(resolving.value ? '正在读取本地视频目标...' : '这个资源没有可写入的本地视频文件。'), 1))
                      : _createCommentVNode("", true),
                    (preview.value?.items?.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_33, [
                          _cache[14] || (_cache[14] = _createElementVNode("div", { class: "section-head" }, [
                            _createElementVNode("div", null, [
                              _createElementVNode("div", { class: "section-title" }, "匹配预览"),
                              _createElementVNode("div", { class: "section-desc" }, "检查每个字幕对应的视频目标和最终落盘文件名。")
                            ])
                          ], -1)),
                          _createElementVNode("div", _hoisted_34, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(preview.value.items, (item) => {
                              return (_openBlock(), _createElementBlock("div", {
                                key: item.upload_id,
                                class: "match-row"
                              }, [
                                _createElementVNode("div", _hoisted_35, [
                                  _createElementVNode("div", _hoisted_36, _toDisplayString(item.source_name), 1),
                                  _createElementVNode("div", _hoisted_37, [
                                    (item.archive_name)
                                      ? (_openBlock(), _createElementBlock("span", _hoisted_38, "来自 " + _toDisplayString(item.archive_name), 1))
                                      : _createCommentVNode("", true),
                                    _createElementVNode("span", null, _toDisplayString(item.detected_label || '未知语言'), 1),
                                    _createElementVNode("span", null, _toDisplayString(item.language_suffix), 1)
                                  ])
                                ]),
                                _createVNode(_component_VSelect, {
                                  "model-value": item.target_id,
                                  items: targetSelectItems.value,
                                  label: "匹配目标",
                                  variant: "outlined",
                                  density: "comfortable",
                                  "hide-details": "",
                                  "onUpdate:modelValue": value => updatePreviewTarget(item.upload_id, value)
                                }, null, 8, ["model-value", "items", "onUpdate:modelValue"]),
                                _createElementVNode("div", _hoisted_39, [
                                  _cache[13] || (_cache[13] = _createElementVNode("span", null, "改名为", -1)),
                                  _createElementVNode("strong", null, _toDisplayString(item.output_name || buildOutputName(selectedTargets.value.find(target => target.id === item.target_id), item) || '待选择目标'), 1)
                                ])
                              ]))
                            }), 128))
                          ])
                        ]))
                      : _createCommentVNode("", true),
                    (lastWritten.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_40, [
                          _cache[15] || (_cache[15] = _createElementVNode("div", { class: "section-title" }, "写入结果", -1)),
                          _createElementVNode("div", _hoisted_41, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(lastWritten.value, (item) => {
                              return (_openBlock(), _createElementBlock("div", {
                                key: item.output_path,
                                class: "result-row"
                              }, [
                                _createElementVNode("div", null, [
                                  _createElementVNode("div", _hoisted_42, _toDisplayString(item.output_name), 1),
                                  _createElementVNode("div", _hoisted_43, _toDisplayString(item.target_label), 1)
                                ]),
                                _createElementVNode("div", {
                                  class: _normalizeClass(["result-badge", { active: item.timeline?.applied }])
                                }, _toDisplayString(timelineResultText(item)), 3)
                              ]))
                            }), 128))
                          ])
                        ]))
                      : _createCommentVNode("", true)
                  ], 64))
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VCard, {
        class: "panel-card upload-panel",
        rounded: "xl",
        elevation: "0"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "panel-title" }, {
            default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
              _createTextVNode("上传字幕", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardText, null, {
            default: _withCtx(() => [
              _createElementVNode("div", {
                class: _normalizeClass(["dropzone", { dragging: dragging.value }]),
                onDrop: handleDrop,
                onDragover: handleDragOver,
                onDragleave: handleDragLeave
              }, [
                _cache[18] || (_cache[18] = _createElementVNode("div", { class: "dropzone-icon" }, "SRT / ASS / ZIP", -1)),
                _cache[19] || (_cache[19] = _createElementVNode("div", { class: "dropzone-title" }, "拖入字幕或压缩包", -1)),
                _cache[20] || (_cache[20] = _createElementVNode("div", { class: "dropzone-text" }, "支持多文件上传；ZIP 会自动解包，只保留字幕文件参与匹配。", -1)),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  onClick: openFileDialog
                }, {
                  default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
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
                  accept: ".srt,.ass,.ssa,.sbv,.sub,.vtt,.webvtt,.zip",
                  onChange: onPickFiles
                }, null, 544)
              ], 34),
              (files.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_44, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(files.value, (file) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: `${file.name}-${file.size}`,
                        class: "file-row"
                      }, [
                        _createElementVNode("div", null, [
                          _createElementVNode("div", _hoisted_45, _toDisplayString(file.name), 1),
                          _createElementVNode("div", _hoisted_46, _toDisplayString(Math.max(1, Math.round(file.size / 1024))) + " KB", 1)
                        ]),
                        _createVNode(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          color: "error",
                          onClick: $event => (removeFile(file))
                        }, {
                          default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                            _createTextVNode("移除", -1)
                          ]))]),
                          _: 1
                        }, 8, ["onClick"])
                      ]))
                    }), 128))
                  ]))
                : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_47, [
                _createVNode(_component_VSwitch, {
                  modelValue: fixTimeline.value,
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((fixTimeline).value = $event)),
                  color: "primary",
                  density: "comfortable",
                  "hide-details": "",
                  disabled: !timelineAvailable.value,
                  label: "写入前智能调轴"
                }, null, 8, ["modelValue", "disabled"]),
                _createElementVNode("div", _hoisted_48, [
                  (timelineAvailable.value)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_49, " 使用容器内 ffmpeg/ffprobe 与 Python 依赖计算整体偏移。 "))
                    : (_openBlock(), _createElementBlock("span", _hoisted_50, " 当前缺少调轴依赖" + _toDisplayString(timelineMissing.value ? `：${timelineMissing.value}` : '') + "。 ", 1))
                ])
              ]),
              _createElementVNode("div", _hoisted_51, [
                _createVNode(_component_VBtn, {
                  color: "primary",
                  block: "",
                  disabled: !canPrepare.value,
                  loading: preparing.value,
                  onClick: prepareUpload
                }, {
                  default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                    _createTextVNode(" 生成匹配预览 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"]),
                _createVNode(_component_VBtn, {
                  color: "success",
                  block: "",
                  variant: "tonal",
                  disabled: !canApply.value,
                  loading: applying.value,
                  onClick: applyUpload
                }, {
                  default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                    _createTextVNode(" 写入字幕 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"])
              ]),
              _cache[24] || (_cache[24] = _createElementVNode("div", { class: "upload-note" }, " 先生成预览再写入。预览会出现在中间栏，确认改名结果后再点击写入。 ", -1))
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ])
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-80b1d5ab"]]);

export { AppPage as default };
