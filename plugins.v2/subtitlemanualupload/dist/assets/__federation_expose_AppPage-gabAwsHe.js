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

const {createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,resolveComponent:_resolveComponent,createBlock:_createBlock,createTextVNode:_createTextVNode,withCtx:_withCtx,createVNode:_createVNode,withKeys:_withKeys,renderList:_renderList,Fragment:_Fragment,unref:_unref,normalizeClass:_normalizeClass,vModelCheckbox:_vModelCheckbox,withDirectives:_withDirectives} = await importShared('vue');


const _hoisted_1 = { class: "subtitle-upload-page" };
const _hoisted_2 = {
  key: 0,
  class: "hero-shell"
};
const _hoisted_3 = { class: "hero-meta" };
const _hoisted_4 = { class: "meta-card" };
const _hoisted_5 = { class: "meta-hint" };
const _hoisted_6 = { class: "workspace-grid" };
const _hoisted_7 = { class: "toolbar-row" };
const _hoisted_8 = { class: "toolbar-actions" };
const _hoisted_9 = {
  key: 0,
  class: "media-grid"
};
const _hoisted_10 = ["onClick"];
const _hoisted_11 = { class: "poster-shell" };
const _hoisted_12 = ["src", "alt"];
const _hoisted_13 = {
  key: 1,
  class: "poster-fallback"
};
const _hoisted_14 = { class: "media-info" };
const _hoisted_15 = { class: "media-type" };
const _hoisted_16 = { class: "media-title" };
const _hoisted_17 = {
  key: 0,
  class: "media-subtitle"
};
const _hoisted_18 = { class: "media-meta" };
const _hoisted_19 = { key: 0 };
const _hoisted_20 = { key: 1 };
const _hoisted_21 = {
  key: 1,
  class: "empty-state"
};
const _hoisted_22 = {
  key: 2,
  class: "target-shell"
};
const _hoisted_23 = { class: "selected-media" };
const _hoisted_24 = ["src", "alt"];
const _hoisted_25 = { class: "selected-copy" };
const _hoisted_26 = { class: "target-title" };
const _hoisted_27 = {
  key: 1,
  class: "target-list"
};
const _hoisted_28 = ["value", "disabled"];
const _hoisted_29 = {
  key: 2,
  class: "empty-state compact"
};
const _hoisted_30 = {
  key: 0,
  class: "file-list"
};
const _hoisted_31 = { class: "file-name" };
const _hoisted_32 = { class: "file-size" };
const _hoisted_33 = { class: "toolbar-actions mt-4" };
const _hoisted_34 = {
  key: 1,
  class: "preview-shell"
};
const _hoisted_35 = { class: "preview-list" };
const _hoisted_36 = { class: "preview-main" };
const _hoisted_37 = { class: "preview-name" };
const _hoisted_38 = { class: "preview-meta" };
const _hoisted_39 = { key: 0 };
const _hoisted_40 = { class: "toolbar-actions mt-4" };

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
const status = ref({ enabled: false, source: 'MoviePilot MediaChain' });
const loading = ref(false);
const searching = ref(false);
const resolving = ref(false);
const refreshing = ref(false);
const preparing = ref(false);
const applying = ref(false);
const message = ref('');
const error = ref('');
const searchKeyword = ref('');
const mediaType = ref('all');
const medias = ref([]);
const selectedMedia = ref(null);
const seasons = ref([]);
const selectedSeason = ref(null);
const targets = ref([]);
const selectedTargetIds = ref([]);
const files = ref([]);
const preview = ref(null);
const fileInputRef = ref(null);

const availableSeasonItems = computed(() => {
  return seasons.value
    .filter(item => item.available)
    .map(item => ({
      title: `${seasonLabel(item.season)} · 本地 ${item.local_count || 0} 集${item.episode_count ? ` / TMDB ${item.episode_count} 集` : ''}`,
      value: item.season,
    }))
});

const selectedTargets = computed(() => {
  const picked = new Set(selectedTargetIds.value || []);
  return targets.value.filter(item => picked.has(item.id))
});

const canPrepare = computed(() => selectedTargetIds.value.length > 0 && files.value.length > 0);
const canApply = computed(() => {
  const items = preview.value?.items || [];
  return items.length > 0 && items.every(item => item.target_id)
});

function formatMediaType(type) {
  return type === 'tv' ? '剧集' : '电影'
}

function seasonLabel(season) {
  const value = Number(season || 0);
  return value === 0 ? '特别篇' : `第 ${value} 季`
}

function clearTargetState() {
  seasons.value = [];
  selectedSeason.value = null;
  targets.value = [];
  selectedTargetIds.value = [];
  preview.value = null;
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
    message.value = response?.message || '已改用 MoviePilot 实时媒体搜索，无需刷新索引';
  } catch (err) {
    error.value = err?.message || '刷新状态失败';
  } finally {
    refreshing.value = false;
  }
}

async function runSearch() {
  const keyword = searchKeyword.value.trim();
  if (!keyword) {
    error.value = '请输入电影名或剧名';
    return
  }

  searching.value = true;
  error.value = '';
  message.value = '';
  selectedMedia.value = null;
  clearTargetState();
  try {
    const params = new URLSearchParams();
    params.set('keyword', keyword);
    params.set('media_type', mediaType.value);
    params.set('limit', '24');
    const response = await props.api.get(`${pluginBase.value}/search?${params.toString()}`);
    const data = unwrapResponse(response) || {};
    medias.value = data.medias || [];
    if (!medias.value.length) {
      message.value = '没有找到媒体候选，请换一个关键词试试';
    }
  } catch (err) {
    error.value = err?.message || '搜索媒体失败';
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
    const params = buildMediaParams(media, season);
    const response = await props.api.get(`${pluginBase.value}/targets?${params.toString()}`);
    const data = unwrapResponse(response) || {};
    selectedMedia.value = data.media || media;
    seasons.value = data.seasons || [];
    selectedSeason.value = data.selected_season ?? null;
    targets.value = data.targets || [];
    selectedTargetIds.value = targets.value.filter(item => item.writable !== false).map(item => item.id);

    if (!targets.value.length) {
      message.value = `${mediaLabel(selectedMedia.value)} 未在 MoviePilot 本地媒体库中找到可写入的视频文件`;
    } else {
      message.value = `已读取 ${targets.value.length} 个本地目标文件`;
    }
  } catch (err) {
    error.value = err?.message || '读取媒体库目标失败';
  } finally {
    resolving.value = false;
  }
}

async function selectMedia(media) {
  selectedMedia.value = media;
  clearTargetState();
  await loadTargets(media, null);
}

async function changeSeason(season) {
  selectedSeason.value = season;
  await loadTargets(selectedMedia.value, season);
}

function resetSelection() {
  selectedMedia.value = null;
  medias.value = [];
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
}

function removeFile(file) {
  files.value = files.value.filter(item => !(item.name === file.name && item.size === file.size));
}

function openFileDialog() {
  fileInputRef.value?.click();
}

function handleDrop(event) {
  event.preventDefault();
  const dropped = Array.from(event.dataTransfer?.files || []);
  mergeFiles(dropped);
}

function handleDragOver(event) {
  event.preventDefault();
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
    message.value = response?.message || '已生成匹配预览';
  } catch (err) {
    error.value = err?.message || '上传预解析失败';
  } finally {
    preparing.value = false;
  }
}

function updatePreviewTarget(uploadId, targetId) {
  const items = preview.value?.items || [];
  const target = items.find(item => item.upload_id === uploadId);
  if (target) {
    target.target_id = targetId;
  }
}

async function applyUpload() {
  if (!canApply.value || !preview.value) return
  applying.value = true;
  error.value = '';
  try {
    const payload = {
      session_id: preview.value.session_id,
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
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _cache[5] || (_cache[5] = _createElementVNode("div", { class: "hero-copy" }, [
            _createElementVNode("div", { class: "hero-eyebrow" }, "MoviePilot 媒体库字幕工具"),
            _createElementVNode("h1", { class: "hero-title" }, "字幕手传匹配"),
            _createElementVNode("p", { class: "hero-text" }, " 像 CSB 一样先搜索媒体并确认封面，再读取 MoviePilot 已入库文件。剧集可按季度选择目标，然后拖入字幕或 ZIP 自动匹配写入。 ")
          ], -1)),
          _createElementVNode("div", _hoisted_3, [
            _createElementVNode("div", _hoisted_4, [
              _cache[3] || (_cache[3] = _createElementVNode("div", { class: "meta-label" }, "当前链路", -1)),
              _cache[4] || (_cache[4] = _createElementVNode("div", { class: "meta-value" }, "MP", -1)),
              _createElementVNode("div", _hoisted_5, _toDisplayString(status.value.source || 'MoviePilot MediaChain'), 1)
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
        class: "panel-card",
        rounded: "xl",
        elevation: "0"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "panel-title" }, {
            default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
              _createTextVNode("1. 搜索并选择媒体", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardText, null, {
            default: _withCtx(() => [
              _createElementVNode("div", _hoisted_7, [
                _createVNode(_component_VTextField, {
                  modelValue: searchKeyword.value,
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((searchKeyword).value = $event)),
                  label: "电影名、剧名或英文名",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": "",
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
                }, null, 8, ["modelValue"])
              ]),
              _createElementVNode("div", _hoisted_8, [
                _createVNode(_component_VBtn, {
                  color: "primary",
                  loading: searching.value,
                  onClick: runSearch
                }, {
                  default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                    _createTextVNode("搜索媒体", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"]),
                _createVNode(_component_VBtn, {
                  variant: "tonal",
                  loading: refreshing.value,
                  onClick: refreshIndex
                }, {
                  default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                    _createTextVNode("接口状态", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              (medias.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_9, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(medias.value, (media) => {
                      return (_openBlock(), _createElementBlock("button", {
                        key: media.id,
                        class: _normalizeClass(["media-card", { active: selectedMedia.value?.id === media.id }]),
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
                          _createElementVNode("div", _hoisted_15, _toDisplayString(formatMediaType(media.media_type)), 1),
                          _createElementVNode("div", _hoisted_16, _toDisplayString(_unref(mediaLabel)(media)), 1),
                          (media.en_title)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_17, _toDisplayString(media.en_title), 1))
                            : _createCommentVNode("", true),
                          _createElementVNode("div", _hoisted_18, [
                            (media.vote_average)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_19, "TMDB " + _toDisplayString(Number(media.vote_average).toFixed(1)), 1))
                              : _createCommentVNode("", true),
                            (media.tmdb_id)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_20, "#" + _toDisplayString(media.tmdb_id), 1))
                              : _createCommentVNode("", true)
                          ])
                        ])
                      ], 10, _hoisted_10))
                    }), 128))
                  ]))
                : (_openBlock(), _createElementBlock("div", _hoisted_21, " 输入关键词搜索媒体。结果会使用 MoviePilot 的媒体搜索能力，并直接展示封面。 ")),
              (selectedMedia.value)
                ? (_openBlock(), _createElementBlock("div", _hoisted_22, [
                    _createElementVNode("div", _hoisted_23, [
                      (selectedMedia.value.poster_url)
                        ? (_openBlock(), _createElementBlock("img", {
                            key: 0,
                            class: "selected-poster",
                            src: selectedMedia.value.poster_url,
                            alt: _unref(mediaLabel)(selectedMedia.value)
                          }, null, 8, _hoisted_24))
                        : _createCommentVNode("", true),
                      _createElementVNode("div", _hoisted_25, [
                        _createElementVNode("div", _hoisted_26, "已选：" + _toDisplayString(_unref(mediaLabel)(selectedMedia.value)), 1),
                        _cache[9] || (_cache[9] = _createElementVNode("div", { class: "target-caption" }, " 正在读取 MoviePilot 媒体库中这个条目的实际视频文件。 ", -1))
                      ])
                    ]),
                    (selectedMedia.value.media_type === 'tv' && availableSeasonItems.value.length)
                      ? (_openBlock(), _createBlock(_component_VSelect, {
                          key: 0,
                          class: "season-select",
                          "model-value": selectedSeason.value,
                          items: availableSeasonItems.value,
                          label: "选择季度",
                          variant: "outlined",
                          density: "comfortable",
                          "hide-details": "",
                          loading: resolving.value,
                          "onUpdate:modelValue": changeSeason
                        }, null, 8, ["model-value", "items", "loading"]))
                      : _createCommentVNode("", true),
                    (targets.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_27, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(targets.value, (target) => {
                            return (_openBlock(), _createElementBlock("label", {
                              key: target.id,
                              class: _normalizeClass(["target-item", { disabled: target.writable === false }])
                            }, [
                              _withDirectives(_createElementVNode("input", {
                                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((selectedTargetIds).value = $event)),
                                type: "checkbox",
                                value: target.id,
                                disabled: target.writable === false
                              }, null, 8, _hoisted_28), [
                                [_vModelCheckbox, selectedTargetIds.value]
                              ]),
                              _createElementVNode("span", null, _toDisplayString(_unref(targetLabel)(target)), 1)
                            ], 2))
                          }), 128))
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_29, _toDisplayString(resolving.value ? '正在读取媒体库目标...' : '这个媒体还没有可写入的本地视频目标。'), 1))
                  ]))
                : _createCommentVNode("", true)
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VCard, {
        class: "panel-card",
        rounded: "xl",
        elevation: "0"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "panel-title" }, {
            default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
              _createTextVNode("2. 上传并确认匹配", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardText, null, {
            default: _withCtx(() => [
              _createElementVNode("div", {
                class: "dropzone",
                onDrop: handleDrop,
                onDragover: handleDragOver
              }, [
                _cache[12] || (_cache[12] = _createElementVNode("div", { class: "dropzone-icon" }, "SRT / ASS / ZIP", -1)),
                _cache[13] || (_cache[13] = _createElementVNode("div", { class: "dropzone-title" }, "拖拽字幕文件或 ZIP 到这里", -1)),
                _cache[14] || (_cache[14] = _createElementVNode("div", { class: "dropzone-text" }, "可以一次选择多个字幕。ZIP 会自动解包，只保留字幕文件参与匹配。", -1)),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  onClick: openFileDialog
                }, {
                  default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
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
              ], 32),
              (files.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_30, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(files.value, (file) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: `${file.name}-${file.size}`,
                        class: "file-item"
                      }, [
                        _createElementVNode("div", null, [
                          _createElementVNode("div", _hoisted_31, _toDisplayString(file.name), 1),
                          _createElementVNode("div", _hoisted_32, _toDisplayString(Math.max(1, Math.round(file.size / 1024))) + " KB", 1)
                        ]),
                        _createVNode(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          color: "error",
                          onClick: $event => (removeFile(file))
                        }, {
                          default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                            _createTextVNode("移除", -1)
                          ]))]),
                          _: 1
                        }, 8, ["onClick"])
                      ]))
                    }), 128))
                  ]))
                : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_33, [
                _createVNode(_component_VBtn, {
                  color: "primary",
                  disabled: !canPrepare.value,
                  loading: preparing.value,
                  onClick: prepareUpload
                }, {
                  default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                    _createTextVNode(" 生成匹配预览 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"]),
                _createVNode(_component_VBtn, {
                  variant: "tonal",
                  onClick: resetSelection
                }, {
                  default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
                    _createTextVNode("重新选择媒体", -1)
                  ]))]),
                  _: 1
                })
              ]),
              (preview.value?.items?.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_34, [
                    _cache[19] || (_cache[19] = _createElementVNode("div", { class: "preview-header" }, [
                      _createElementVNode("div", { class: "target-title" }, "3. 检查并写入"),
                      _createElementVNode("div", { class: "target-caption" }, "每个字幕都需要对应一个目标视频；自动匹配不准时可以手动改。")
                    ], -1)),
                    _createElementVNode("div", _hoisted_35, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(preview.value.items, (item) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: item.upload_id,
                          class: "preview-item"
                        }, [
                          _createElementVNode("div", _hoisted_36, [
                            _createElementVNode("div", _hoisted_37, _toDisplayString(item.source_name), 1),
                            _createElementVNode("div", _hoisted_38, [
                              (item.archive_name)
                                ? (_openBlock(), _createElementBlock("span", _hoisted_39, "来自 " + _toDisplayString(item.archive_name), 1))
                                : _createCommentVNode("", true),
                              _createElementVNode("span", null, _toDisplayString(item.detected_label || '未知语言'), 1),
                              _createElementVNode("span", null, _toDisplayString(item.language_suffix), 1)
                            ])
                          ]),
                          _createVNode(_component_VSelect, {
                            "model-value": item.target_id,
                            items: selectedTargets.value.map(target => ({ title: _unref(targetLabel)(target), value: target.id })),
                            label: "目标视频",
                            variant: "outlined",
                            density: "comfortable",
                            "hide-details": "",
                            "onUpdate:modelValue": value => updatePreviewTarget(item.upload_id, value)
                          }, null, 8, ["model-value", "items", "onUpdate:modelValue"])
                        ]))
                      }), 128))
                    ]),
                    _createElementVNode("div", _hoisted_40, [
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        disabled: !canApply.value,
                        loading: applying.value,
                        onClick: applyUpload
                      }, {
                        default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
                          _createTextVNode(" 写入字幕 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled", "loading"])
                    ])
                  ]))
                : _createCommentVNode("", true)
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
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-0db45c97"]]);

export { AppPage as default };
