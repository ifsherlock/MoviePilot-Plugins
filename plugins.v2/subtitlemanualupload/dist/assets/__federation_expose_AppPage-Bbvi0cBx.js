import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'data') && response.success !== undefined) {
    return response.data
  }
  return response?.data ?? response
}

function groupLabel(group) {
  if (!group) return ''
  return group.year ? `${group.title} (${group.year})` : `${group.title || ''}`
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
const _hoisted_5 = { class: "meta-value" };
const _hoisted_6 = { class: "meta-hint" };
const _hoisted_7 = { class: "workspace-grid" };
const _hoisted_8 = { class: "toolbar-row" };
const _hoisted_9 = { class: "toolbar-actions" };
const _hoisted_10 = { class: "library-hint" };
const _hoisted_11 = {
  key: 0,
  class: "group-list"
};
const _hoisted_12 = ["onClick"];
const _hoisted_13 = { class: "group-head" };
const _hoisted_14 = { class: "group-type" };
const _hoisted_15 = { class: "group-count" };
const _hoisted_16 = { class: "group-title" };
const _hoisted_17 = { class: "group-subtitle" };
const _hoisted_18 = {
  key: 1,
  class: "empty-state"
};
const _hoisted_19 = {
  key: 2,
  class: "target-shell"
};
const _hoisted_20 = { class: "target-header" };
const _hoisted_21 = { class: "target-title" };
const _hoisted_22 = { class: "target-list" };
const _hoisted_23 = ["value"];
const _hoisted_24 = {
  key: 0,
  class: "file-list"
};
const _hoisted_25 = { class: "file-name" };
const _hoisted_26 = { class: "file-size" };
const _hoisted_27 = { class: "toolbar-actions mt-4" };
const _hoisted_28 = {
  key: 1,
  class: "preview-shell"
};
const _hoisted_29 = { class: "preview-list" };
const _hoisted_30 = { class: "preview-main" };
const _hoisted_31 = { class: "preview-name" };
const _hoisted_32 = { class: "preview-meta" };
const _hoisted_33 = { key: 0 };
const _hoisted_34 = { class: "toolbar-actions mt-4" };

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
  libraries: [],
  index: { ready: false, updated_at: '', entry_count: 0 },
});
const loading = ref(false);
const searching = ref(false);
const refreshing = ref(false);
const preparing = ref(false);
const applying = ref(false);
const message = ref('');
const error = ref('');
const searchKeyword = ref('');
const mediaType = ref('all');
const groups = ref([]);
const selectedGroup = ref(null);
const selectedTargetIds = ref([]);
const files = ref([]);
const preview = ref(null);
const fileInputRef = ref(null);

const selectedTargets = computed(() => {
  if (!selectedGroup.value) return []
  const allTargets = selectedGroup.value.targets || [];
  const picked = new Set(selectedTargetIds.value || []);
  return allTargets.filter(item => picked.has(item.id))
});

const canPrepare = computed(() => selectedTargetIds.value.length > 0 && files.value.length > 0);
const canApply = computed(() => {
  const items = preview.value?.items || [];
  return items.length > 0 && items.every(item => item.target_id)
});

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
    const data = unwrapResponse(response) || {};
    message.value = `索引已刷新，共 ${data.entry_count || 0} 个媒体文件`;
    await loadStatus();
    await runSearch();
  } catch (err) {
    error.value = err?.message || '刷新索引失败';
  } finally {
    refreshing.value = false;
  }
}

function resetSelection() {
  selectedGroup.value = null;
  selectedTargetIds.value = [];
  preview.value = null;
}

async function runSearch() {
  searching.value = true;
  error.value = '';
  preview.value = null;
  try {
    const params = new URLSearchParams();
    params.set('keyword', searchKeyword.value || '');
    params.set('media_type', mediaType.value);
    params.set('limit', '50');
    const response = await props.api.get(`${pluginBase.value}/search?${params.toString()}`);
    const data = unwrapResponse(response) || {};
    groups.value = data.groups || [];
    if (groups.value.length === 1) {
      selectGroup(groups.value[0]);
    }
  } catch (err) {
    error.value = err?.message || '搜索失败';
  } finally {
    searching.value = false;
  }
}

function selectGroup(group) {
  selectedGroup.value = group;
  selectedTargetIds.value = (group?.targets || []).map(item => item.id);
  preview.value = null;
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

onMounted(async () => {
  await loadStatus();
  if (status.value.index?.ready) {
    await runSearch();
  }
});

__expose({
  loadStatus,
  refreshIndex,
  runSearch,
  loading,
  searching,
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
          _cache[4] || (_cache[4] = _createElementVNode("div", { class: "hero-copy" }, [
            _createElementVNode("div", { class: "hero-eyebrow" }, "MoviePilot 插件"),
            _createElementVNode("h1", { class: "hero-title" }, "字幕手传匹配"),
            _createElementVNode("p", { class: "hero-text" }, " 先选电影或剧集，再拖拽字幕或 ZIP 上传。插件会尽量自动匹配季集，并按目标视频文件名直接落盘。 ")
          ], -1)),
          _createElementVNode("div", _hoisted_3, [
            _createElementVNode("div", _hoisted_4, [
              _cache[3] || (_cache[3] = _createElementVNode("div", { class: "meta-label" }, "媒体索引", -1)),
              _createElementVNode("div", _hoisted_5, _toDisplayString(status.value.index?.entry_count || 0), 1),
              _createElementVNode("div", _hoisted_6, _toDisplayString(status.value.index?.updated_at || '尚未建立索引'), 1)
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
    _createElementVNode("div", _hoisted_7, [
      _createVNode(_component_VCard, {
        class: "panel-card",
        rounded: "xl",
        elevation: "0"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "panel-title" }, {
            default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
              _createTextVNode("1. 选择目标媒体", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardText, null, {
            default: _withCtx(() => [
              _createElementVNode("div", _hoisted_8, [
                _createVNode(_component_VTextField, {
                  modelValue: searchKeyword.value,
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((searchKeyword).value = $event)),
                  label: "搜索电影名、剧名或文件名",
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
              _createElementVNode("div", _hoisted_9, [
                _createVNode(_component_VBtn, {
                  color: "primary",
                  loading: searching.value,
                  onClick: runSearch
                }, {
                  default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
                    _createTextVNode("搜索", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"]),
                _createVNode(_component_VBtn, {
                  variant: "tonal",
                  loading: refreshing.value,
                  onClick: refreshIndex
                }, {
                  default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                    _createTextVNode("刷新索引", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _createElementVNode("div", _hoisted_10, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(status.value.libraries || [], (library) => {
                  return (_openBlock(), _createElementBlock("span", {
                    key: library.name,
                    class: "library-chip"
                  }, _toDisplayString(library.name), 1))
                }), 128))
              ]),
              (groups.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_11, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(groups.value, (group) => {
                      return (_openBlock(), _createElementBlock("button", {
                        key: group.group_id,
                        class: _normalizeClass(["group-item", { active: selectedGroup.value?.group_id === group.group_id }]),
                        onClick: $event => (selectGroup(group))
                      }, [
                        _createElementVNode("div", _hoisted_13, [
                          _createElementVNode("span", _hoisted_14, _toDisplayString(group.media_type === 'movie' ? '电影' : '剧集'), 1),
                          _createElementVNode("span", _hoisted_15, _toDisplayString(group.summary), 1)
                        ]),
                        _createElementVNode("div", _hoisted_16, _toDisplayString(_unref(groupLabel)(group)), 1),
                        _createElementVNode("div", _hoisted_17, _toDisplayString((group.library_names || []).join(' / ')), 1)
                      ], 10, _hoisted_12))
                    }), 128))
                  ]))
                : (_openBlock(), _createElementBlock("div", _hoisted_18, " 先搜索目标电影或剧集。若结果为空，可以先刷新索引。 ")),
              (selectedGroup.value)
                ? (_openBlock(), _createElementBlock("div", _hoisted_19, [
                    _createElementVNode("div", _hoisted_20, [
                      _createElementVNode("div", _hoisted_21, "已选：" + _toDisplayString(_unref(groupLabel)(selectedGroup.value)), 1),
                      _cache[8] || (_cache[8] = _createElementVNode("div", { class: "target-caption" }, "默认全选，可取消无关集数。", -1))
                    ]),
                    _createElementVNode("div", _hoisted_22, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(selectedGroup.value.targets || [], (target) => {
                        return (_openBlock(), _createElementBlock("label", {
                          key: target.id,
                          class: "target-item"
                        }, [
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((selectedTargetIds).value = $event)),
                            type: "checkbox",
                            value: target.id
                          }, null, 8, _hoisted_23), [
                            [_vModelCheckbox, selectedTargetIds.value]
                          ]),
                          _createElementVNode("span", null, _toDisplayString(_unref(targetLabel)(target)), 1)
                        ]))
                      }), 128))
                    ])
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
            default: _withCtx(() => [...(_cache[9] || (_cache[9] = [
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
                _cache[11] || (_cache[11] = _createElementVNode("div", { class: "dropzone-icon" }, "SRT / ASS / ZIP", -1)),
                _cache[12] || (_cache[12] = _createElementVNode("div", { class: "dropzone-title" }, "拖拽字幕文件或 ZIP 到这里", -1)),
                _cache[13] || (_cache[13] = _createElementVNode("div", { class: "dropzone-text" }, "也可以点按钮选择多个文件。ZIP 会自动解包，只保留字幕文件。", -1)),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  onClick: openFileDialog
                }, {
                  default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
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
                ? (_openBlock(), _createElementBlock("div", _hoisted_24, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(files.value, (file) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: `${file.name}-${file.size}`,
                        class: "file-item"
                      }, [
                        _createElementVNode("div", null, [
                          _createElementVNode("div", _hoisted_25, _toDisplayString(file.name), 1),
                          _createElementVNode("div", _hoisted_26, _toDisplayString(Math.max(1, Math.round(file.size / 1024))) + " KB", 1)
                        ]),
                        _createVNode(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          color: "error",
                          onClick: $event => (removeFile(file))
                        }, {
                          default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
                            _createTextVNode("移除", -1)
                          ]))]),
                          _: 1
                        }, 8, ["onClick"])
                      ]))
                    }), 128))
                  ]))
                : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_27, [
                _createVNode(_component_VBtn, {
                  color: "primary",
                  disabled: !canPrepare.value,
                  loading: preparing.value,
                  onClick: prepareUpload
                }, {
                  default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                    _createTextVNode(" 生成匹配预览 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"]),
                _createVNode(_component_VBtn, {
                  variant: "tonal",
                  onClick: resetSelection
                }, {
                  default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                    _createTextVNode("清空选择", -1)
                  ]))]),
                  _: 1
                })
              ]),
              (preview.value?.items?.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_28, [
                    _cache[18] || (_cache[18] = _createElementVNode("div", { class: "preview-header" }, [
                      _createElementVNode("div", { class: "target-title" }, "3. 检查并写入"),
                      _createElementVNode("div", { class: "target-caption" }, "每个字幕都需要对应一个目标视频。")
                    ], -1)),
                    _createElementVNode("div", _hoisted_29, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(preview.value.items, (item) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: item.upload_id,
                          class: "preview-item"
                        }, [
                          _createElementVNode("div", _hoisted_30, [
                            _createElementVNode("div", _hoisted_31, _toDisplayString(item.source_name), 1),
                            _createElementVNode("div", _hoisted_32, [
                              (item.archive_name)
                                ? (_openBlock(), _createElementBlock("span", _hoisted_33, "来自 " + _toDisplayString(item.archive_name), 1))
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
                    _createElementVNode("div", _hoisted_34, [
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        disabled: !canApply.value,
                        loading: applying.value,
                        onClick: applyUpload
                      }, {
                        default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
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
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-bfbe0509"]]);

export { AppPage as default };
