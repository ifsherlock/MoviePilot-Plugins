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

function timelineBaseText(base) {
  const value = String(base || '');
  if (value.startsWith('embedded:')) return '内嵌字幕基准'
  if (value === 'audio:rms' || value === 'audio:rms:cache') return 'RMS 音频检测（低精度）'
  if (value === 'audio:webrtc' || value === 'audio:webrtc:cache') return 'WebRTC 音频检测'
  if (value.startsWith('audio:')) return '音频基准'
  return value || '未知基准'
}

function timelineConfidenceText(value) {
  const known = {
    high: '高可信',
    medium: '中可信',
    low: '低可信',
    rejected: '已拒绝',
  };
  return known[value] || value || '未知可信度'
}

function timelineRiskText(value) {
  const known = {
    offset_over_120s: '偏移超过 120s',
    offset_over_configured_max: '超过配置最大偏移',
    low_score: '匹配分数过低',
    weak_score_margin: '最佳与次优差距过小',
    unstable_subtitle_activity: '字幕活动区间异常',
    unusual_scale_factor: '帧率比例异常',
  };
  return known[value] || value
}

function timelineResultText(item) {
  const timeline = item?.timeline || {};
  if (!timeline.enabled) return '未启用智能调轴'
  const base = timelineBaseText(timeline.base);
  if (timeline.applied) {
    return `已调轴 ${formatOffset(timeline.offset_seconds)} · ${base}`
  }
  return `未调整：偏移 ${formatOffset(timeline.offset_seconds)} 小于阈值 · ${base}`
}

function timelineMetaItems(item) {
  const timeline = item?.timeline || item || {};
  if (!timeline.enabled) return []
  const items = [];
  if (timeline.confidence) items.push(`置信度：${timelineConfidenceText(timeline.confidence)}`);
  if (timeline.score_margin !== undefined) items.push(`差距：${Number(timeline.score_margin || 0).toFixed(3)}`);
  if (timeline.active_ratio !== undefined) items.push(`活动：${(Number(timeline.active_ratio || 0) * 100).toFixed(1)}%`)
  ;(timeline.risk_flags || []).forEach(flag => items.push(timelineRiskText(flag)));
  return items
}

function readableErrorDetail(value) {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    return value
      .map(item => readableErrorDetail(item))
      .filter(Boolean)
      .join('；')
  }
  if (typeof value === 'object') {
    const direct = value.message || value.msg || value.detail || value.reason || value.error;
    if (direct) return readableErrorDetail(direct)
    const parts = [];
    if (Array.isArray(value.loc) && value.loc.length) parts.push(value.loc.join('.'));
    if (value.type) parts.push(value.type);
    if (parts.length) return parts.join('：')
    try {
      return JSON.stringify(value, null, 0)
    } catch (_) {
      return String(value)
    }
  }
  return String(value)
}

function errorMessage(err, fallback) {
  return readableErrorDetail(
    err?.response?.data?.detail
    || err?.response?.data?.message
    || err?.data?.detail
    || err?.data?.message
    || err?.message
    || fallback
  )
}

function buildOutputName(target, item) {
  if (!target) return ''
  const basename = target.basename || 'subtitle';
  const suffix = item?.language_suffix || 'und';
  let ext = item?.ext || '.srt';
  if (!ext.startsWith('.')) ext = `.${ext}`;
  return `${basename}.${suffix}${ext.toLowerCase()}`
}

function resolvePluginBase(pluginBase) {
  const raw = typeof pluginBase === 'function' ? pluginBase() : (pluginBase?.value ?? pluginBase);
  return raw || 'plugin/SubtitleManualUpload'
}

function createSubtitleManualUploadApi(api, pluginBase) {
  const get = endpoint => api.get(`${resolvePluginBase(pluginBase)}${endpoint}`);
  const post = (endpoint, payload) => api.post(`${resolvePluginBase(pluginBase)}${endpoint}`, payload);

  return {
    unwrapResponse,
    clearSubtitles(payload) {
      return post('/clear_subtitles', payload)
    },
    timelineFixExisting(payload) {
      return post('/timeline_fix_existing', payload)
    },
    restoreSubtitleBackup(payload) {
      return post('/restore_subtitle_backup', payload)
    },
    aiTasks(payload) {
      return post('/ai_tasks', payload)
    },
    timelineTasks(payload) {
      return post('/timeline_tasks', payload)
    },
    aiSubmit(payload) {
      return post('/ai_submit', payload)
    },
    aiCancel(payload) {
      return post('/ai_cancel', payload)
    },
    aiRestart(payload) {
      return post('/ai_restart', payload)
    },
    status() {
      return get('/status')
    },
    autoTransferQueue() {
      return get('/auto_transfer_queue')
    },
    onlineStatus() {
      return get('/online_status')
    },
    refreshIndex(payload = {}) {
      return post('/refresh_index', payload)
    },
    search(params) {
      return get(`/search?${params.toString()}`)
    },
    matchHistory(params) {
      return get(`/match_history?${params.toString()}`)
    },
    targets(params) {
      return get(`/targets?${params.toString()}`)
    },
    deleteSubtitle(payload) {
      return post('/delete_subtitle', payload)
    },
    onlineManualLinks(payload) {
      return post('/online_manual_links', payload)
    },
    onlineSearchProvider(payload) {
      return post('/online_search_provider', payload)
    },
    onlineAiSubmit(payload) {
      return post('/online_ai_submit', payload)
    },
    onlineDownloadPreview(payload) {
      return post('/online_download_preview', payload)
    },
    prepareUpload(formData) {
      return post('/prepare_upload', formData)
    },
    applyUpload(payload) {
      return post('/apply_upload', payload)
    },
  }
}

const {computed: computed$8,nextTick: nextTick$1,ref: ref$9} = await importShared('vue');


const EMPTY_AI_TASK_DATA = {
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, ignored: 0, no_audio: 0, failed: 0, cancelled: 0 }};

const aiRestartSourceOptions = [
  { title: '沿用原任务来源', value: 'reuse' },
  { title: '自动选择', value: 'auto' },
  { title: '选中外挂字幕', value: 'matched_external' },
  { title: '本地外挂字幕', value: 'local_external' },
  { title: '视频内嵌字幕', value: 'embedded' },
  { title: '音轨 ASR', value: 'asr' },
];

function createEmptyAiTaskData(current = {}) {
  return {
    ...current,
    summary: { ...EMPTY_AI_TASK_DATA.summary },
    tasks: [],
    task_by_target: {},
    tasks_by_target: {},
  }
}

function useAiTasks({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  status,
  visibleTargets,
  selectedMedia,
  selectedSeason,
  selectedTargets,
  batchUploadTargets,
  targetById,
  isLocked,
  lockedTargetPayload,
  isStreamTarget,
  formatBytes,
}) {
  const aiSubmitting = ref$9(false);
  const aiCancelling = ref$9(false);
  const aiTasksLoading = ref$9(false);
  const aiTaskDialog = ref$9(false);
  const aiTaskDialogTarget = ref$9(null);
  const aiTaskScopeTargets = ref$9([]);
  const aiTaskLoadToken = ref$9(0);
  const aiRestartSourcePolicy = ref$9('reuse');
  const aiRestartSubtitlePath = ref$9('');
  const aiSelectedTaskIds = ref$9([]);
  const aiStatusStripRef = ref$9(null);
  const aiTaskData = ref$9(createEmptyAiTaskData());
  let aiTaskTimer = null;

  const aiStatus = computed$8(() => aiTaskData.value.status || status.value?.ai_subtitle || {});
  const aiEnabled = computed$8(() => aiStatus.value.enabled !== false);
  const aiAvailable = computed$8(() => aiEnabled.value && aiStatus.value.available === true);
  const aiSummary = computed$8(() => aiTaskData.value.summary || {});
  const aiHasActiveTasks = computed$8(() => Number(aiSummary.value.active || 0) > 0);
  const aiBatchCancelTargets = computed$8(() => batchUploadTargets.value.filter(target => isAiTaskActive(aiTaskForTarget(target))));
  const aiCapableBatchTargets = computed$8(() => batchUploadTargets.value.filter(target => !isStreamTarget(target)));
  const aiBatchLabel = computed$8(() => {
    if (selectedMedia.value?.media_type !== 'tv') return 'AI 生成字幕'
    if (selectedTargets.value.length) return `AI 生成选中 ${selectedTargets.value.length} 集`
    return selectedSeason.value === 'all' ? 'AI 生成全部季' : 'AI 生成本季'
  });
  const aiSummaryText = computed$8(() => {
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
  const aiDialogTasks = computed$8(() => {
    const targetId = aiTaskDialogTarget.value?.id;
    if (targetId) {
      return (aiTaskData.value.tasks_by_target || {})[targetId] || []
    }
    return aiTaskData.value.tasks || []
  });
  const aiDialogHasExistingTasks = computed$8(() => Boolean(aiDialogTasks.value.length));
  const aiDialogActiveTasks = computed$8(() => aiDialogTasks.value.filter(task => isAiTaskActive(task)));
  const aiDialogHasActiveTasks = computed$8(() => aiDialogActiveTasks.value.length > 0);
  const aiDialogRestartableTasks = computed$8(() => aiDialogTasks.value.filter(task => isAiTaskRestartable(task)));
  const aiDialogSelectedRestartableTasks = computed$8(() => {
    const selected = new Set(aiSelectedTaskIds.value);
    return aiDialogRestartableTasks.value.filter(task => selected.has(task.task_id))
  });
  const aiDialogSelectedAllowedTasks = computed$8(() => aiDialogSelectedRestartableTasks.value.filter(isAiTaskAllowed));
  const aiDialogActionText = computed$8(() => (aiDialogHasExistingTasks.value ? '重新生成选中' : '生成'));
  const aiDialogSourceLabel = computed$8(() => (aiDialogHasExistingTasks.value ? '重新生成来源' : '生成来源'));
  const aiRestartSubtitleOptions = computed$8(() => {
    const target = aiTaskDialogTarget.value;
    const subtitles = target?.subtitles || [];
    return subtitles
      .filter(subtitle => String(subtitle.ext || '').toLowerCase() === '.srt')
      .map(subtitle => ({
        title: `${subtitle.name} · ${formatBytes(subtitle.size)}`,
        value: subtitle.path,
      }))
  });

  function applyAiTaskData(data) {
    aiTaskData.value = data || aiTaskData.value;
    if (aiTaskData.value.status) {
      status.value = { ...status.value, ai_subtitle: aiTaskData.value.status };
    }
  }

  function resetAiTasks() {
    aiTaskDialogTarget.value = null;
    aiTaskScopeTargets.value = [];
    aiTaskData.value = createEmptyAiTaskData(aiTaskData.value);
    stopAiPolling();
  }

  function stopAiPolling() {
    if (aiTaskTimer) {
      clearTimeout(aiTaskTimer);
      aiTaskTimer = null;
    }
  }

  function scheduleAiPolling() {
    stopAiPolling();
    if (!aiHasActiveTasks.value || !currentAiTaskTargets().length) return
    aiTaskTimer = setTimeout(() => {
      loadAiTasks({ silent: true });
    }, 5000);
  }

  function currentAiTaskTargets() {
    return aiTaskScopeTargets.value.length ? aiTaskScopeTargets.value : visibleTargets.value
  }

  async function loadAiTasks(options = {}) {
    const scopeTargets = Array.isArray(options.targets) && options.targets.length
      ? options.targets
      : currentAiTaskTargets();
    const requestToken = options.requestToken || 0;
    const requestTargetIds = scopeTargets.map(item => item.id).join('|');
    if (!scopeTargets.length) {
      if (requestToken && requestToken !== aiTaskLoadToken.value) return
      aiTaskData.value = createEmptyAiTaskData(aiTaskData.value);
      stopAiPolling();
      return
    }
    if (!options.silent) aiTasksLoading.value = true;
    try {
      const response = await pluginApi.value.aiTasks({
        target_ids: scopeTargets.map(item => item.id),
      });
      if (requestToken && requestToken !== aiTaskLoadToken.value) return
      if (requestToken) {
        const currentTargetIds = currentAiTaskTargets().map(item => item.id).join('|');
        if (currentTargetIds !== requestTargetIds) return
      }
      applyAiTaskData(unwrapResponse(response) || aiTaskData.value);
      aiSelectedTaskIds.value = aiSelectedTaskIds.value.filter(taskId => {
        const task = (aiTaskData.value.tasks || []).find(item => item.task_id === taskId);
        return task && isAiTaskAllowed(task)
      });
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

  function isAiTaskRestartable(task) {
    return Boolean(task && !isAiTaskActive(task) && ['completed', 'failed', 'cancelled', 'ignored', 'no_audio'].includes(task.status))
  }

  function targetForAiTask(task) {
    return targetById.value.get(task?.target_id) || null
  }

  function isAiTaskAllowed(task) {
    if (!isAiTaskRestartable(task)) return false
    const target = targetForAiTask(task);
    if (!target) return false
    return !isLocked(target.id) && target.writable !== false && !isStreamTarget(target)
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

  function aiTaskIconForTask(task) {
    if (!task) return 'mdi-robot-outline'
    if (task.status === 'completed') return 'mdi-robot-happy-outline'
    if (task.status === 'failed') return 'mdi-alert-circle-outline'
    if (task.status === 'cancelled') return 'mdi-cancel'
    if (task.status === 'no_audio') return 'mdi-volume-off'
    if (task.status === 'ignored') return 'mdi-debug-step-over'
    if (isAiTaskActive(task)) return 'mdi-progress-clock'
    return 'mdi-robot-outline'
  }

  function aiStatusText(task) {
    if (!task) return '未提交'
    return task.message || task.status_label || task.status
  }

  function openAiTaskDialog(target = null) {
    aiTaskDialogTarget.value = target;
    aiRestartSubtitlePath.value = '';
    aiSelectedTaskIds.value = [];
    aiTaskDialog.value = true;
    const scopeTargets = target
      ? [target]
      : (aiTaskScopeTargets.value.length ? aiTaskScopeTargets.value : visibleTargets.value);
    aiTaskScopeTargets.value = scopeTargets;
    const existingTasks = target
      ? (aiTaskForTarget(target) ? [aiTaskForTarget(target)] : [])
      : (aiTaskData.value.tasks || []).filter(task => scopeTargets.some(item => item.id === task.target_id));
    aiRestartSourcePolicy.value = existingTasks.length ? 'reuse' : 'auto';
    const requestToken = ++aiTaskLoadToken.value;
    loadAiTasks({ silent: true, targets: scopeTargets, requestToken }).then(() => {
      if (aiTaskDialog.value && requestToken === aiTaskLoadToken.value) {
        aiRestartSourcePolicy.value = aiDialogHasExistingTasks.value ? 'reuse' : 'auto';
      }
    });
  }

  async function focusAiStatusStrip() {
    await nextTick$1();
    const el = aiStatusStripRef.value;
    if (!el) return
    el.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
    el.focus?.({ preventScroll: true });
  }

  async function submitAiForTargets(scopeTargets) {
    return submitAiForTargetsWithOptions(scopeTargets)
  }

  async function submitAiForTargetsWithOptions(scopeTargets, options = {}) {
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
      const payload = {
        target_ids: usableTargets.map(item => item.id),
        locked_target_ids: lockedTargetPayload(),
      };
      if (options.source_policy) payload.source_policy = options.source_policy;
      if (options.source_subtitle_path) payload.source_subtitle_path = options.source_subtitle_path;
      if (options.overwrite_policy) payload.overwrite_policy = options.overwrite_policy;
      const response = await pluginApi.value.aiSubmit(payload);
      const data = unwrapResponse(response) || {};
      if (data.tasks) {
        applyAiTaskData(data.tasks);
      }
      aiTaskScopeTargets.value = usableTargets;
      message.value = response?.message || '已提交 AI 字幕生成任务';
      await loadAiTasks({ silent: true, targets: usableTargets });
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
      const response = await pluginApi.value.aiCancel({
        target_ids: activeTargets.map(item => item.id),
        locked_target_ids: lockedTargetPayload(),
      });
      const data = unwrapResponse(response) || {};
      if (data.tasks) {
        applyAiTaskData(data.tasks);
      }
      aiTaskScopeTargets.value = activeTargets;
      message.value = response?.message || '已取消 AI 字幕任务';
      await loadAiTasks({ silent: true, targets: activeTargets });
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

  async function regenerateDialogAiTasks() {
    const selectedTaskIds = aiDialogSelectedAllowedTasks.value
      .map(task => task.task_id);
    return regenerateAiTasksByIds(selectedTaskIds)
  }

  async function regenerateSingleAiTask(task) {
    if (!isAiTaskAllowed(task)) return
    await regenerateAiTasksByIds([task.task_id]);
  }

  async function regenerateAiTasksByIds(taskIds = []) {
    const scopeTargets = aiTaskDialogTarget.value
      ? [aiTaskDialogTarget.value]
      : (aiTaskScopeTargets.value.length ? aiTaskScopeTargets.value : visibleTargets.value);
    const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false && !isStreamTarget(item));
    if (!usableTargets.length) {
      message.value = '没有可重新生成 AI 字幕的目标：选中的集数可能都已锁定或是 STRM';
      return
    }
    if (aiRestartSourcePolicy.value === 'matched_external' && !aiRestartSubtitlePath.value) {
      message.value = '请先选择要用于重新生成的外挂 SRT 字幕';
      return
    }
    const hasExistingTasks = aiDialogHasExistingTasks.value;
    if (hasExistingTasks && !taskIds.length) {
      message.value = '请先勾选可重新生成的 AI 历史任务；锁定、不可写、STRM 或正在处理的任务不能重跑';
      return
    }
    const sourcePolicy = !hasExistingTasks && aiRestartSourcePolicy.value === 'reuse'
      ? 'auto'
      : aiRestartSourcePolicy.value;
    const overwritePolicy = hasExistingTasks
      ? (sourcePolicy === 'reuse' ? 'backup_replace' : 'new_variant')
      : (sourcePolicy === 'auto' ? 'skip' : 'new_variant');
    if (!hasExistingTasks) {
      await submitAiForTargetsWithOptions(usableTargets, {
        source_policy: sourcePolicy,
        source_subtitle_path: sourcePolicy === 'matched_external' ? aiRestartSubtitlePath.value : '',
        overwrite_policy: overwritePolicy,
      });
      return
    }
    aiSubmitting.value = true;
    error.value = '';
    message.value = '';
    try {
      const response = await pluginApi.value.aiRestart({
        target_ids: usableTargets.map(item => item.id),
        task_ids: taskIds,
        locked_target_ids: lockedTargetPayload(),
        source_policy: sourcePolicy,
        source_subtitle_path: sourcePolicy === 'matched_external' ? aiRestartSubtitlePath.value : '',
        overwrite_policy: overwritePolicy,
      });
      const data = unwrapResponse(response) || {};
      if (data.tasks) {
        applyAiTaskData(data.tasks);
      }
      aiTaskScopeTargets.value = usableTargets;
      message.value = response?.message || '已重新提交 AI 字幕生成任务';
      await loadAiTasks({ silent: true, targets: usableTargets });
    } catch (err) {
      error.value = errorMessage(err, '重新生成 AI 字幕任务失败');
    } finally {
      aiSubmitting.value = false;
    }
  }

  function openSingleAiGenerate(target) {
    openAiTaskDialog(target);
  }

  return {
    aiSubmitting,
    aiCancelling,
    aiTasksLoading,
    aiTaskDialog,
    aiTaskDialogTarget,
    aiTaskScopeTargets,
    aiRestartSourcePolicy,
    aiRestartSubtitlePath,
    aiSelectedTaskIds,
    aiStatusStripRef,
    aiTaskData,
    aiStatus,
    aiEnabled,
    aiAvailable,
    aiSummary,
    aiHasActiveTasks,
    aiBatchCancelTargets,
    aiCapableBatchTargets,
    aiBatchLabel,
    aiSummaryText,
    aiDialogTasks,
    aiDialogHasExistingTasks,
    aiDialogActiveTasks,
    aiDialogHasActiveTasks,
    aiDialogRestartableTasks,
    aiDialogSelectedRestartableTasks,
    aiDialogSelectedAllowedTasks,
    aiDialogActionText,
    aiDialogSourceLabel,
    aiRestartSubtitleOptions,
    applyAiTaskData,
    resetAiTasks,
    stopAiPolling,
    scheduleAiPolling,
    currentAiTaskTargets,
    loadAiTasks,
    aiTaskForTarget,
    isAiTaskActive,
    isAiTaskRestartable,
    targetForAiTask,
    isAiTaskAllowed,
    aiTaskColor,
    aiTaskIcon,
    aiTaskTitle,
    aiTaskStatusClass,
    aiTaskIconForTask,
    aiStatusText,
    openAiTaskDialog,
    focusAiStatusStrip,
    submitAiForTargets,
    submitAiForTargetsWithOptions,
    cancelAiForTargets,
    openBatchAiGenerate,
    cancelBatchAiGenerate,
    cancelDialogAiTasks,
    regenerateDialogAiTasks,
    regenerateSingleAiTask,
    regenerateAiTasksByIds,
    openSingleAiGenerate,
  }
}

const {computed: computed$7,ref: ref$8} = await importShared('vue');


const EMPTY_AUTO_TRANSFER_QUEUE = {
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, skipped: 0, failed: 0 }};

function createEmptyAutoTransferQueue() {
  return {
    summary: { ...EMPTY_AUTO_TRANSFER_QUEUE.summary },
    tasks: [],
    rate_limits: {},
    season_package_cache: [],
  }
}

function useAutoTransferQueue({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
}) {
  const autoTransferQueue = ref$8(createEmptyAutoTransferQueue());
  const autoQueueDialog = ref$8(false);
  let autoQueueTimer = null;

  const autoQueueSummary = computed$7(() => autoTransferQueue.value?.summary || {});
  const autoQueueTasks = computed$7(() => autoTransferQueue.value?.tasks || []);
  const autoQueueActive = computed$7(() => Number(autoQueueSummary.value.active || 0) > 0);
  const autoQueueSummaryText = computed$7(() => {
    const parts = [];
    if (autoQueueSummary.value.in_progress) parts.push(`${autoQueueSummary.value.in_progress} 个处理中`);
    if (autoQueueSummary.value.pending) parts.push(`${autoQueueSummary.value.pending} 个排队`);
    if (autoQueueSummary.value.failed) parts.push(`${autoQueueSummary.value.failed} 个失败`);
    if (autoQueueSummary.value.completed) parts.push(`${autoQueueSummary.value.completed} 个完成`);
    if (autoQueueSummary.value.skipped) parts.push(`${autoQueueSummary.value.skipped} 个跳过`);
    return parts.length ? parts.join(' / ') : '暂无入库自动字幕任务'
  });

  function applyAutoTransferSummary(summary) {
    autoTransferQueue.value = { ...autoTransferQueue.value, summary };
  }

  function stopAutoQueuePolling() {
    if (autoQueueTimer) {
      clearTimeout(autoQueueTimer);
      autoQueueTimer = null;
    }
  }

  function scheduleAutoQueuePolling() {
    stopAutoQueuePolling();
    if (!autoQueueActive.value) return
    autoQueueTimer = setTimeout(() => {
      loadAutoTransferQueue();
    }, 3000);
  }

  async function loadAutoTransferQueue() {
    try {
      const response = await pluginApi.value.autoTransferQueue();
      autoTransferQueue.value = unwrapResponse(response) || autoTransferQueue.value;
      scheduleAutoQueuePolling();
    } catch (err) {
      error.value = errorMessage(err, '读取入库自动字幕队列失败');
    }
  }

  return {
    autoTransferQueue,
    autoQueueDialog,
    autoQueueSummary,
    autoQueueTasks,
    autoQueueActive,
    autoQueueSummaryText,
    applyAutoTransferSummary,
    stopAutoQueuePolling,
    scheduleAutoQueuePolling,
    loadAutoTransferQueue,
  }
}

const {computed: computed$6,ref: ref$7} = await importShared('vue');


const MATCH_HISTORY_PAGE_SIZE = 20;

function useMatchHistory({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  clearing,
  searchKeyword,
  mediaType,
  selectedMedia,
  clearTargetState,
  lockedTargetPayload,
  isStreamTarget,
  seasonLabel,
  runSearch,
  fixExistingTimeline,
}) {
  const rootTab = ref$7('match');
  const matchHistoryLoading = ref$7(false);
  const matchHistoryItems = ref$7([]);
  const matchHistoryPage = ref$7(1);
  const matchHistoryPageSize = MATCH_HISTORY_PAGE_SIZE;
  const matchHistoryTotal = ref$7(0);
  const matchHistoryHasMore = ref$7(false);
  const expandedHistoryIds = ref$7([]);
  const expandedHistorySeasonKeys = ref$7([]);
  const expandedHistoryTargetIds = ref$7([]);
  const selectedHistoryTargetIds = ref$7({});
  let historyTimelineTimer = null;

  const matchHistorySummary = computed$6(() => {
    if (!matchHistoryTotal.value) return '暂无已匹配字幕记录'
    return `${matchHistoryTotal.value} 部资源有外挂字幕记录`
  });

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

  function historySeasonKey(item, group) {
    return `${item?.id || 'history'}:${group?.key || group?.season || 'all'}`
  }

  function historySeasonExpanded(item, group) {
    return expandedHistorySeasonKeys.value.includes(historySeasonKey(item, group))
  }

  function toggleHistorySeasonExpanded(item, group) {
    const key = historySeasonKey(item, group);
    if (expandedHistorySeasonKeys.value.includes(key)) {
      expandedHistorySeasonKeys.value = expandedHistorySeasonKeys.value.filter(value => value !== key);
      return
    }
    expandedHistorySeasonKeys.value = [...expandedHistorySeasonKeys.value, key];
  }

  function historyTargetExpanded(target) {
    return expandedHistoryTargetIds.value.includes(target?.id)
  }

  function toggleHistoryTargetExpanded(target) {
    const id = target?.id;
    if (!id) return
    if (expandedHistoryTargetIds.value.includes(id)) {
      expandedHistoryTargetIds.value = expandedHistoryTargetIds.value.filter(value => value !== id);
      return
    }
    expandedHistoryTargetIds.value = [...expandedHistoryTargetIds.value, id];
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
    return targets.length > 0 && historySelectedCount(item) === targets.length
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
    const targets = historyDeletableTargets(item);
    if (!targets.length) return []
    if (item?.media_type !== 'tv') {
      return [
        {
          key: 'movie',
          direct: true,
          targets,
          subtitleCount: targets.reduce((sum, target) => sum + (target.subtitles || []).length, 0),
        },
      ]
    }
    const groups = new Map();
    targets.forEach(target => {
      const season = Number(target.season || 0);
      if (!groups.has(season)) {
        groups.set(season, {
          key: `season-${season}`,
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

  function historySeasonSelectedCount(item, group) {
    const selected = new Set(historySelectedIds(item));
    return (group?.targets || []).filter(target => selected.has(target.id)).length
  }

  function allHistorySeasonTargetsSelected(item, group) {
    const targets = group?.targets || [];
    if (!targets.length) return false
    return historySeasonSelectedCount(item, group) === targets.length
  }

  function historySeasonPartiallySelected(item, group) {
    const count = historySeasonSelectedCount(item, group);
    return count > 0 && count < (group?.targets || []).length
  }

  function toggleHistorySeasonTargets(item, group, checked) {
    if (!item?.id || !group?.targets?.length) return
    const selected = new Set(historySelectedIds(item))
    ;(group.targets || []).forEach(target => {
      if (!target?.id) return
      if (checked) {
        selected.add(target.id);
      } else {
        selected.delete(target.id);
      }
    });
    setHistorySelection(item, Array.from(selected));
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
      const response = await pluginApi.value.clearSubtitles({
        target_ids: targetIds,
        locked_target_ids: lockedTargetPayload(),
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

  function historyTimelineTargets(item) {
    return historyDeletableTargets(item).filter(target => !isStreamTarget(target) && (target.subtitles || []).length)
  }

  function historySelectedTimelineTargets(item) {
    const selected = new Set(historySelectedIds(item));
    return historyTimelineTargets(item).filter(target => selected.has(target.id))
  }

  function fixHistorySelectedTimeline(item) {
    const targets = historySelectedTimelineTargets(item);
    fixExistingTimeline(targets.map(target => ({ target_id: target.id })), '选中集数');
  }

  function fixHistorySubtitleTimeline(target, subtitle) {
    if (!target || !subtitle) return
    fixExistingTimeline(
      [{ target_id: target.id, subtitle_path: subtitle.path }],
      subtitle.name || '单个字幕',
    );
  }

  function stopHistoryTimelinePolling() {
    if (historyTimelineTimer) {
      clearTimeout(historyTimelineTimer);
      historyTimelineTimer = null;
    }
  }

  function historyHasActiveTimelineTask() {
    return matchHistoryItems.value.some(item => (item.targets || []).some(target => {
      const task = target.timeline_task;
      return task && (task.active || ['pending', 'in_progress'].includes(task.status))
    }))
  }

  function scheduleHistoryTimelinePolling() {
    stopHistoryTimelinePolling();
    if (!historyHasActiveTimelineTask()) return
    historyTimelineTimer = setTimeout(async () => {
      await loadMatchHistory();
      scheduleHistoryTimelinePolling();
    }, 3000);
  }

  function submitRootSearch() {
    if (rootTab.value === 'history') {
      loadMatchHistory();
      return
    }
    runSearch();
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
      const response = await pluginApi.value.matchHistory(params);
      const data = unwrapResponse(response) || {};
      matchHistoryPage.value = Number(data.page || page);
      matchHistoryTotal.value = Number(data.total || 0);
      matchHistoryHasMore.value = Boolean(data.has_more);
      matchHistoryItems.value = append ? [...matchHistoryItems.value, ...(data.items || [])] : (data.items || []);
      scheduleHistoryTimelinePolling();
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

  return {
    rootTab,
    matchHistoryLoading,
    matchHistoryItems,
    matchHistoryPage,
    matchHistoryPageSize,
    matchHistoryTotal,
    matchHistoryHasMore,
    expandedHistoryIds,
    expandedHistorySeasonKeys,
    expandedHistoryTargetIds,
    selectedHistoryTargetIds,
    matchHistorySummary,
    historyExpanded,
    toggleHistoryExpanded,
    historySeasonKey,
    historySeasonExpanded,
    toggleHistorySeasonExpanded,
    historyTargetExpanded,
    toggleHistoryTargetExpanded,
    historyDeletableTargets,
    historySelectedIds,
    historySelectedCount,
    allHistoryTargetsSelected,
    setHistorySelection,
    toggleHistoryTarget,
    toggleHistoryItemTargets,
    historySeasonGroups,
    historySeasonSelectedCount,
    allHistorySeasonTargetsSelected,
    historySeasonPartiallySelected,
    toggleHistorySeasonTargets,
    clearHistoryTargets,
    clearHistorySelectedSubtitles,
    historyTimelineTargets,
    historySelectedTimelineTargets,
    fixHistorySelectedTimeline,
    fixHistorySubtitleTimeline,
    stopHistoryTimelinePolling,
    historyHasActiveTimelineTask,
    scheduleHistoryTimelinePolling,
    submitRootSearch,
    loadMatchHistory,
    loadMoreMatchHistory,
    setRootTab,
  }
}

const {ref: ref$6} = await importShared('vue');


function useMediaSearch({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  selectedMedia,
  clearTargetState,
}) {
  const searching = ref$6(false);
  const searchKeyword = ref$6('');
  const mediaType = ref$6('all');
  const medias = ref$6([]);
  const mediaPage = ref$6(1);
  const mediaPageSize = 24;
  const mediaTotal = ref$6(0);
  const mediaHasMore = ref$6(false);
  const mediaPrefetchPages = ref$6({});
  const failedPosterImages = ref$6({});
  let mediaSearchToken = 0;

  function posterImageKey(item, url) {
    return `${item?.id || item?.media_id || item?.title || ''}\u0000${url || ''}`
  }

  function posterImageSrc(item) {
    const url = item?.poster_thumb_url || item?.poster_url || '';
    if (!url || failedPosterImages.value[posterImageKey(item, url)]) return ''
    return url
  }

  function markPosterFailed(item) {
    const url = item?.poster_thumb_url || item?.poster_url || '';
    if (!url) return
    failedPosterImages.value = {
      ...failedPosterImages.value,
      [posterImageKey(item, url)]: true,
    };
  }

  function posterLoading(index) {
    return index < 6 ? 'eager' : 'lazy'
  }

  function posterFetchPriority(index) {
    return index < 6 ? 'high' : 'low'
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
    const response = await pluginApi.value.search(params);
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
      clearTargetState?.();
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

  function loadMoreMedia() {
    if (searching.value || !mediaHasMore.value) return
    runSearch({ append: true });
  }

  return {
    searching,
    searchKeyword,
    mediaType,
    medias,
    mediaPage,
    mediaPageSize,
    mediaTotal,
    mediaHasMore,
    mediaPrefetchPages,
    failedPosterImages,
    posterImageKey,
    posterImageSrc,
    markPosterFailed,
    posterLoading,
    posterFetchPriority,
    mediaRequestKey,
    clearMediaPrefetch,
    fetchMediaPage,
    applyMediaPage,
    prefetchMediaPage,
    runSearch,
    loadMoreMedia,
  }
}

const onlineProviderItems = [
  { title: 'SubHD', value: 'subhd' },
  { title: 'Zimuku', value: 'zimuku' },
  { title: '射手网(伪)', value: 'assrt' },
  { title: 'OpenSubtitles', value: 'opensubtitles' },
];

function onlineResultKey(item) {
  return `${item?.provider || 'unknown'}:${item?.result_id || item?.page_url || item?.title || ''}`
}

function providerName(providerId) {
  const known = onlineProviderItems.find(item => item.value === providerId);
  return known?.title || providerId || '未知来源'
}

function providerPriority(providerId) {
  if (providerId === 'subhd') return 35
  if (providerId === 'assrt') return 30
  if (providerId === 'zimuku') return 25
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

const {computed: computed$5,nextTick,ref: ref$5} = await importShared('vue');

const ONLINE_PROVIDER_TIMEOUT_MS = 25000;
const ONLINE_DOWNLOAD_TIMEOUT_MS = 35000;

function useOnlineSubtitles({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  selectedMedia,
  selectedTargets,
  selectedSeason,
  batchUploadTargets,
  isLocked,
  lockedTargetPayload,
  compactTargetName,
  aiAvailable,
  timelineNeedsRiskyConfirm,
  confirmRiskyTimelineOffset,
  prepareOnlineUploadState,
  openOnlinePreview,
  closeUploadDialog,
  applyAiTaskData,
  setAiTaskScopeTargets,
  loadAiTasks,
  focusAiStatusStrip,
  applyTimelineTaskData,
  loadTimelineTasks,
}) {
  const onlineSearching = ref$5(false);
  const onlineDownloading = ref$5(false);
  const onlinePreviewDownloading = ref$5(false);
  const onlineAiDownloading = ref$5(false);
  const onlineError = ref$5('');
  const onlineDialog = ref$5(false);
  const onlineAiConfirmDialog = ref$5(false);
  const onlineTitle = ref$5('');
  const onlineScope = ref$5('auto');
  const onlineKeyword = ref$5('');
  const onlineTargets = ref$5([]);
  const onlineStatus = ref$5({ providers: [], capabilities: {} });
  const onlineSelectedProviders = ref$5(['assrt', 'opensubtitles']);
  const onlineResults = ref$5([]);
  const onlineLanguageFilter = ref$5('all');
  const onlineProviderFilter = ref$5('all');
  const onlineMessages = ref$5([]);
  const onlineMessagesCollapsed = ref$5(false);
  const onlineManualLinks = ref$5([]);
  const onlineProviderProgress = ref$5({});
  const selectedOnlineResultIds = ref$5([]);
  let onlineSearchSeq = 0;
  let onlineDownloadSeq = 0;

  const hasOnlineResults = computed$5(() => onlineResults.value.length > 0);
  const filteredOnlineResults = computed$5(() => {
    return onlineResults.value.filter(item => {
      const languageMatched = onlineLanguageFilter.value === 'all' || onlineResultLanguageFilterCategory(item) === onlineLanguageFilter.value;
      const providerMatched = onlineProviderFilter.value === 'all' || item.provider === onlineProviderFilter.value;
      return languageMatched && providerMatched
    })
  });
  const onlineLanguageFilterItems = computed$5(() => {
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
  const onlineProviderFilterItems = computed$5(() => {
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
  const selectedOnlineResults = computed$5(() => {
    const picked = new Set(selectedOnlineResultIds.value);
    return onlineResults.value.filter(item => picked.has(onlineResultKey(item)) && isOnlineResultDownloadable(item))
  });
  const canSubmitOnlineAiTranslate = computed$5(() => {
    return aiAvailable.value && selectedOnlineResults.value.length > 0 && selectedOnlineResults.value.every(isForeignOnlineResult)
  });
  const onlineMessageSummary = computed$5(() => {
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
  const onlineMessageType = computed$5(() => {
    return (onlineMessages.value || []).some(item => item.level !== 'info') ? 'warning' : 'info'
  });
  const onlineProviderProgressItems = computed$5(() => onlineSelectedProviders.value.map(provider => ({
    provider,
    state: onlineProviderProgress.value[provider] || 'idle',
  })));
  const onlineAiConfirmText = computed$5(() => {
    const count = selectedOnlineResults.value.length;
    const targetCount = onlineTargets.value.length;
    return `将把当前范围的 ${targetCount} 个目标提交给 AI字幕生成(联动版)；已选择 ${count} 个外语结果，提交后会关闭在线搜索并打开 AI 状态。`
  });
  const onlineBatchLabel = computed$5(() => {
    if (selectedMedia.value?.media_type !== 'tv') return '搜索在线字幕'
    if (selectedTargets.value.length) return `搜索选中 ${selectedTargets.value.length} 集`
    return selectedSeason.value === 'all' ? '搜索全部季字幕包' : '搜索本季字幕包'
  });

  function ensureConfiguredApiProvidersSelected() {
    const configured = [...(onlineStatus.value?.enabled_providers || [])]
      .filter(provider => onlineProviderItems.some(item => item.value === provider));
    if (onlineStatus.value?.assrt_api_configured) configured.push('assrt');
    if (onlineStatus.value?.opensubtitles_api_configured) configured.push('opensubtitles');
    if (!configured.length) return
    onlineSelectedProviders.value = Array.from(new Set(configured));
  }

  async function loadOnlineStatus() {
    try {
      const response = await pluginApi.value.onlineStatus();
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

  async function openOnlineDialog(scopeTargets, title, scope) {
    const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false);
    if (!usableTargets.length) {
      error.value = '没有可搜索的目标：选中的集数可能都已锁定';
      return
    }
    onlineTitle.value = title;
    onlineScope.value = scope;
    onlineTargets.value = usableTargets;
    prepareOnlineUploadState(usableTargets, title);
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
      locked_target_ids: lockedTargetPayload(),
      media: selectedMedia.value,
      scope: onlineScope.value,
      keyword: onlineKeyword.value.trim(),
      providers: onlineSelectedProviders.value,
    }
  }

  async function loadOnlineManualLinks() {
    if (!onlineTargets.value.length) return
    try {
      const response = await pluginApi.value.onlineManualLinks(onlinePayload());
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
          pluginApi.value.onlineSearchProvider({
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

  function closeOnlineDialog() {
    if (onlineSearching.value) {
      stopOnlineSearch();
    }
    if (onlineDownloading.value) {
      stopOnlineDownload();
    }
    onlineDialog.value = false;
  }

  function updateOnlineDialog(value) {
    if (value) {
      onlineDialog.value = true;
      return
    }
    closeOnlineDialog();
  }

  function withTimeout(promise, timeoutMs, timeoutMessage) {
    let timer = null;
    const timeout = new Promise((resolve, reject) => {
      timer = window.setTimeout(() => {
        const err = new Error(timeoutMessage);
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
    submitOnlineAiTranslate();
  }

  async function submitOnlineAiTranslate() {
    if (!selectedOnlineResults.value.length || onlineDownloading.value) return
    if (!canSubmitOnlineAiTranslate.value) {
      onlineError.value = aiAvailable.value
        ? '请只选择外语字幕结果后再提交 AI 翻译。'
        : 'AI 字幕生成联动当前不可用，无法提交翻译任务。';
      return
    }
    const allowRiskyOffset = timelineNeedsRiskyConfirm.value;
    if (allowRiskyOffset && !confirmRiskyTimelineOffset('在线字幕提交 AI 前智能调轴')) return
    const downloadSeq = ++onlineDownloadSeq;
    onlineDownloading.value = true;
    onlineAiDownloading.value = true;
    onlineError.value = '';
    const submittedTargets = [...onlineTargets.value];
    try {
      const response = await withTimeout(
        pluginApi.value.onlineAiSubmit({
          ...onlinePayload(),
          results: selectedOnlineResults.value,
          allow_risky_offset: allowRiskyOffset,
        }),
        ONLINE_DOWNLOAD_TIMEOUT_MS,
        'AI 字幕任务提交仍在等待响应，已停止等待；可稍后打开 AI 状态刷新查看。',
      );
      if (downloadSeq !== onlineDownloadSeq) return
      const data = unwrapResponse(response) || {};
      const aiResult = data.ai_translate || data;
      if (data.tasks) {
        applyAiTaskData(data.tasks);
      } else if (aiResult.tasks) {
        applyAiTaskData(aiResult.tasks);
      }
      if (data.timeline_tasks) {
        applyTimelineTaskData(data.timeline_tasks);
      }
      closeUploadDialog();
      onlineDialog.value = false;
      message.value = response?.message || '已提交 AI 字幕翻译任务，请查看 AI 字幕生成状态';
      setAiTaskScopeTargets(submittedTargets);
      await loadAiTasks({ silent: true, targets: submittedTargets });
      await loadTimelineTasks({ silent: true, targets: submittedTargets });
      await focusAiStatusStrip();
    } catch (err) {
      if (downloadSeq !== onlineDownloadSeq) return
      onlineError.value = errorMessage(err, '提交 AI 字幕翻译失败');
    } finally {
      if (downloadSeq === onlineDownloadSeq) {
        onlineDownloading.value = false;
        onlineAiDownloading.value = false;
      }
    }
  }

  async function downloadOnlinePreview() {
    if (!selectedOnlineResults.value.length || onlineDownloading.value) return
    const downloadSeq = ++onlineDownloadSeq;
    onlineDownloading.value = true;
    onlinePreviewDownloading.value = true;
    onlineError.value = '';
    try {
      const response = await withTimeout(
        pluginApi.value.onlineDownloadPreview({
          ...onlinePayload(),
          results: selectedOnlineResults.value,
        }),
        ONLINE_DOWNLOAD_TIMEOUT_MS,
        '在线字幕下载仍在源站验证中，已停止等待；可换一个结果重试，或打开手动链接下载后上传。',
      );
      if (downloadSeq !== onlineDownloadSeq) return
      const data = unwrapResponse(response) || {};
      openOnlinePreview(data, response?.message || '已下载在线字幕并生成匹配预览');
      onlineDialog.value = false;
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

  return {
    onlineSearching,
    onlineDownloading,
    onlinePreviewDownloading,
    onlineAiDownloading,
    onlineError,
    onlineDialog,
    onlineAiConfirmDialog,
    onlineTitle,
    onlineScope,
    onlineKeyword,
    onlineTargets,
    onlineStatus,
    onlineSelectedProviders,
    onlineResults,
    onlineLanguageFilter,
    onlineProviderFilter,
    onlineMessages,
    onlineMessagesCollapsed,
    onlineManualLinks,
    onlineProviderProgress,
    selectedOnlineResultIds,
    hasOnlineResults,
    filteredOnlineResults,
    onlineLanguageFilterItems,
    onlineProviderFilterItems,
    selectedOnlineResults,
    canSubmitOnlineAiTranslate,
    onlineMessageSummary,
    onlineMessageType,
    onlineProviderProgressItems,
    onlineAiConfirmText,
    onlineBatchLabel,
    ensureConfiguredApiProvidersSelected,
    loadOnlineStatus,
    openOnlineDialog,
    openBatchOnlineSearch,
    openSingleOnlineSearch,
    onlinePayload,
    loadOnlineManualLinks,
    runOnlineSearch,
    stopOnlineSearch,
    closeOnlineDialog,
    updateOnlineDialog,
    withTimeout,
    mergeOnlineResults,
    appendOnlineMessages,
    toggleOnlineResult,
    requestOnlineAiTranslate,
    confirmOnlineAiTranslate,
    submitOnlineAiTranslate,
    downloadOnlinePreview,
    stopOnlineDownload,
  }
}

const {computed: computed$4,ref: ref$4} = await importShared('vue');


const DEFAULT_STATUS = {
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
};

function usePluginStatus({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  rootTab,
  selectedMedia,
  selectedSeason,
  applyAiStatus,
  applyAutoTransferSummary,
  loadAutoTransferQueue,
  loadTargets,
  loadMatchHistory,
  runSearch,
}) {
  const status = ref$4({ ...DEFAULT_STATUS });
  const loading = ref$4(false);
  const refreshing = ref$4(false);
  let indexRefreshTimer = null;

  const indexStatus = computed$4(() => status.value?.index || {});
  const indexSummary = computed$4(() => {
    if (!indexStatus.value.ready) return '媒体库清单尚未缓存'
    const parts = [
      `${indexStatus.value.media_count || 0} 个媒体`,
      `${indexStatus.value.entry_count || 0} 个视频`,
    ];
    if (indexStatus.value.updated_at) parts.push(`更新于 ${indexStatus.value.updated_at}`);
    return parts.join(' · ')
  });
  const archiveStatus = computed$4(() => status.value?.archive_support || { zip: true, rar: false, rar_tool: '', rar_python: false });
  const rarAvailable = computed$4(() => archiveStatus.value.rar === true);
  const rarPythonAvailable = computed$4(() => archiveStatus.value.rar_python === true);
  const rarDependencyStatus = computed$4(() => archiveStatus.value.dependency_status || {});
  const timelineStatus = computed$4(() => status.value?.timeline_fixer || { available: false, modules: {} });
  const timelineAvailable = computed$4(() => timelineStatus.value.available === true);
  const timelineConfiguredMaxOffset = computed$4(() => {
    const value = Number(timelineStatus.value.configured_max_offset_seconds || timelineStatus.value.max_offset_seconds || 120);
    return Number.isFinite(value) && value > 0 ? value : 120
  });
  const timelineNeedsRiskyConfirm = computed$4(() => timelineConfiguredMaxOffset.value > 120);
  const timelineMissing = computed$4(() => {
    const missing = [];
    if (timelineStatus.value.ffmpeg === false) missing.push('ffmpeg');
    if (timelineStatus.value.ffprobe === false) missing.push('ffprobe');
    const modules = timelineStatus.value.modules || {};
    Object.entries(modules).forEach(([name, ok]) => {
      if (name === 'webrtcvad') return
      if (!ok) missing.push(name);
    });
    return missing.join('、')
  });

  function applyStatus(nextStatus, options = {}) {
    status.value = nextStatus || status.value;
    if (status.value.ai_subtitle) {
      applyAiStatus?.(status.value.ai_subtitle);
    }
    if (options.syncAutoTransfer && status.value.auto_transfer_queue) {
      applyAutoTransferSummary?.(status.value.auto_transfer_queue);
      if (Number(status.value.auto_transfer_queue.active || 0) > 0) {
        loadAutoTransferQueue?.();
      }
    }
  }

  async function loadStatus() {
    loading.value = true;
    error.value = '';
    try {
      const response = await pluginApi.value.status();
      applyStatus(unwrapResponse(response) || status.value, { syncAutoTransfer: true });
    } catch (err) {
      error.value = errorMessage(err, '加载插件状态失败');
    } finally {
      loading.value = false;
    }
  }

  function stopIndexRefreshPolling() {
    if (indexRefreshTimer) {
      clearTimeout(indexRefreshTimer);
      indexRefreshTimer = null;
    }
  }

  function scheduleIndexRefreshPolling() {
    stopIndexRefreshPolling();
    if (!status.value?.index?.refreshing) {
      refreshing.value = false;
      return
    }
    refreshing.value = true;
    indexRefreshTimer = setTimeout(async () => {
      await pollIndexRefresh();
    }, 3000);
  }

  async function pollIndexRefresh() {
    try {
      const response = await pluginApi.value.status();
      const nextStatus = unwrapResponse(response) || status.value;
      const wasRefreshing = Boolean(status.value?.index?.refreshing);
      applyStatus(nextStatus);
      if (nextStatus.index?.refresh_error) {
        error.value = nextStatus.index.refresh_error;
        refreshing.value = false;
        return
      }
      if (wasRefreshing && !nextStatus.index?.refreshing) {
        refreshing.value = false;
        if (selectedMedia.value) {
          await loadTargets?.(selectedMedia.value, selectedSeason.value || 'all');
        } else if (rootTab.value === 'history') {
          await loadMatchHistory?.();
        } else {
          await runSearch?.();
        }
        message.value = '媒体库资源清单刷新完成';
        return
      }
      scheduleIndexRefreshPolling();
    } catch (err) {
      refreshing.value = false;
      error.value = errorMessage(err, '刷新媒体库清单状态失败');
    }
  }

  async function refreshIndex() {
    refreshing.value = true;
    error.value = '';
    try {
      const response = await pluginApi.value.refreshIndex({});
      const data = unwrapResponse(response) || {};
      if (data.index) {
        status.value = { ...status.value, index: data.index };
      }
      if (data.index?.refreshing) {
        scheduleIndexRefreshPolling();
      } else if (selectedMedia.value) {
        await loadTargets?.(selectedMedia.value, selectedSeason.value || 'all');
      } else if (rootTab.value === 'history') {
        await loadMatchHistory?.();
      } else {
        await runSearch?.();
      }
      message.value = response?.message || '已刷新媒体库资源清单';
    } catch (err) {
      error.value = errorMessage(err, '刷新媒体库清单失败');
      refreshing.value = false;
    } finally {
      if (!status.value?.index?.refreshing) {
        refreshing.value = false;
      }
    }
  }

  return {
    status,
    loading,
    refreshing,
    indexStatus,
    indexSummary,
    archiveStatus,
    rarAvailable,
    rarPythonAvailable,
    rarDependencyStatus,
    timelineStatus,
    timelineAvailable,
    timelineConfiguredMaxOffset,
    timelineNeedsRiskyConfirm,
    timelineMissing,
    loadStatus,
    refreshIndex,
    stopIndexRefreshPolling,
    scheduleIndexRefreshPolling,
  }
}

const {computed: computed$3,ref: ref$3} = await importShared('vue');


function useTargets({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  mediaLabel,
  clearRelatedState,
  beforeLoadTargets,
  afterTargetsLoaded,
  runSearch,
}) {
  const resolving = ref$3(false);
  const selectedMedia = ref$3(null);
  const detailTab = ref$3('match');
  const seasons = ref$3([]);
  const selectedSeason = ref$3('all');
  const targets = ref$3([]);
  const selectedTargetIds = ref$3([]);
  const lockedTargetIds = ref$3([]);
  const expandedDetailTargetIds = ref$3([]);

  const visibleTargets = computed$3(() => targets.value || []);
  const selectedTargets = computed$3(() => {
    const picked = new Set(selectedTargetIds.value || []);
    return visibleTargets.value.filter(item => picked.has(item.id))
  });
  const targetById = computed$3(() => new Map(visibleTargets.value.map(target => [target.id, target])));
  const unlockedVisibleTargets = computed$3(() => visibleTargets.value.filter(item => !isLocked(item.id) && item.writable !== false));
  const allVisibleSelected = computed$3(() => {
    if (!visibleTargets.value.length) return false
    const picked = new Set(selectedTargetIds.value || []);
    return visibleTargets.value.every(item => picked.has(item.id))
  });

  function isLocked(targetId) {
    return lockedTargetIds.value.includes(targetId)
  }

  function lockedTargetPayload() {
    return [...lockedTargetIds.value]
  }

  function isTargetActionDisabled(target) {
    return isLocked(target.id) || target.writable === false
  }

  function detailExpanded(target) {
    return expandedDetailTargetIds.value.includes(target?.id)
  }

  function toggleDetailExpanded(target) {
    const id = target?.id;
    if (!id) return
    if (expandedDetailTargetIds.value.includes(id)) {
      expandedDetailTargetIds.value = expandedDetailTargetIds.value.filter(item => item !== id);
      return
    }
    expandedDetailTargetIds.value = [...expandedDetailTargetIds.value, id];
  }

  function clearTargetState() {
    seasons.value = [];
    detailTab.value = 'match';
    selectedSeason.value = 'all';
    targets.value = [];
    selectedTargetIds.value = [];
    clearRelatedState?.();
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
    beforeLoadTargets?.();
    try {
      const params = buildMediaParams(media, season || 'all');
      const response = await pluginApi.value.targets(params);
      const data = unwrapResponse(response) || {};
      selectedMedia.value = data.media || media;
      seasons.value = data.seasons || [];
      selectedSeason.value = data.selected_season ?? 'all';
      targets.value = data.targets || [];
      selectedTargetIds.value = [];
      await afterTargetsLoaded?.(targets.value);

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
    runSearch?.();
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

  return {
    resolving,
    selectedMedia,
    detailTab,
    seasons,
    selectedSeason,
    targets,
    selectedTargetIds,
    lockedTargetIds,
    expandedDetailTargetIds,
    visibleTargets,
    selectedTargets,
    targetById,
    unlockedVisibleTargets,
    allVisibleSelected,
    isLocked,
    lockedTargetPayload,
    isTargetActionDisabled,
    detailExpanded,
    toggleDetailExpanded,
    clearTargetState,
    buildMediaParams,
    loadTargets,
    selectMedia,
    changeSeason,
    resetSelection,
    toggleSelectAll,
    toggleTarget,
    toggleLock,
  }
}

const {computed: computed$2,ref: ref$2} = await importShared('vue');


const EMPTY_TIMELINE_TASK_DATA = {
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, skipped: 0, failed: 0 }};

function createEmptyTimelineTaskData() {
  return {
    summary: { ...EMPTY_TIMELINE_TASK_DATA.summary },
    tasks: [],
    task_by_target: {},
  }
}

function useTimelineTasks({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  visibleTargets,
  selectedSubtitleTargets,
  lockedTargetPayload,
  timelineAvailable,
  timelineNeedsRiskyConfirm,
  timelineMissing,
  confirmRiskyTimelineOffset,
  isStreamTarget,
  timelineResultText,
  loadMatchHistory,
  scheduleHistoryTimelinePolling,
}) {
  const timelineFixing = ref$2(false);
  const timelineTaskData = ref$2(createEmptyTimelineTaskData());
  let timelineTaskTimer = null;

  const selectedTimelineTargets = computed$2(() => selectedSubtitleTargets.value.filter(target => !isStreamTarget(target)));

  function applyTimelineTaskData(data) {
    timelineTaskData.value = data || timelineTaskData.value;
  }

  function resetTimelineTasks() {
    timelineTaskData.value = createEmptyTimelineTaskData();
    stopTimelinePolling();
  }

  function stopTimelinePolling() {
    if (timelineTaskTimer) {
      clearTimeout(timelineTaskTimer);
      timelineTaskTimer = null;
    }
  }

  function scheduleTimelinePolling() {
    stopTimelinePolling();
    if (!Number(timelineTaskData.value?.summary?.active || 0) || !visibleTargets.value.length) return
    timelineTaskTimer = setTimeout(() => {
      loadTimelineTasks({ silent: true });
    }, 4000);
  }

  async function loadTimelineTasks(options = {}) {
    const scopeTargets = Array.isArray(options.targets) && options.targets.length
      ? options.targets
      : visibleTargets.value;
    if (!scopeTargets.length) {
      timelineTaskData.value = createEmptyTimelineTaskData();
      stopTimelinePolling();
      return
    }
    try {
      const response = await pluginApi.value.timelineTasks({
        target_ids: scopeTargets.map(item => item.id),
      });
      applyTimelineTaskData(unwrapResponse(response) || timelineTaskData.value);
    } catch (err) {
      if (!options.silent) {
        error.value = errorMessage(err, '读取智能调轴任务失败');
      }
    } finally {
      scheduleTimelinePolling();
    }
  }

  function timelineTaskForTarget(target) {
    if (!target) return null
    return (timelineTaskData.value.task_by_target || {})[target.id] || target.timeline_task || null
  }

  function timelineTaskText(task) {
    if (!task) return '暂无调轴记录'
    if (task.status === 'completed' && task.timeline) {
      return timelineResultText({ timeline: task.timeline })
    }
    return task.message || task.status_label || task.status || '暂无调轴记录'
  }

  async function fixExistingTimeline(items, label = '选中字幕') {
    if (!timelineAvailable.value) {
      error.value = `智能调轴不可用：缺少 ${timelineMissing.value || '依赖'}`;
      return
    }
    if (!items.length) {
      error.value = '没有可调轴的历史字幕';
      return
    }
    const confirmed = window.confirm(`确认对${label}提交 ${items.length} 个智能调轴任务？`);
    if (!confirmed) return
    const allowRiskyOffset = timelineNeedsRiskyConfirm.value;
    if (allowRiskyOffset && !confirmRiskyTimelineOffset(`${label}智能调轴`)) return
    timelineFixing.value = true;
    error.value = '';
    message.value = '';
    try {
      const response = await pluginApi.value.timelineFixExisting({
        items,
        locked_target_ids: lockedTargetPayload(),
        allow_risky_offset: allowRiskyOffset,
      });
      const data = unwrapResponse(response) || {};
      message.value = response?.message || `已提交 ${data.accepted || 0} 个智能调轴任务`;
      await loadMatchHistory();
      scheduleHistoryTimelinePolling();
    } catch (err) {
      error.value = errorMessage(err, '提交历史字幕智能调轴失败');
    } finally {
      timelineFixing.value = false;
    }
  }

  function fixSelectedDetailTimeline() {
    fixExistingTimeline(
      selectedTimelineTargets.value.map(target => ({ target_id: target.id })),
      '选中集数',
    );
  }

  return {
    timelineFixing,
    timelineTaskData,
    selectedTimelineTargets,
    applyTimelineTaskData,
    resetTimelineTasks,
    stopTimelinePolling,
    scheduleTimelinePolling,
    loadTimelineTasks,
    timelineTaskForTarget,
    timelineTaskText,
    fixExistingTimeline,
    fixSelectedDetailTimeline,
  }
}

const {computed: computed$1,ref: ref$1} = await importShared('vue');


function useUploadPreview({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  selectedTargets,
  visibleTargets,
  selectedMedia,
  selectedSeason,
  isLocked,
  lockedTargetPayload,
  loadTargets,
  timelineAvailable,
  timelineNeedsRiskyConfirm,
  confirmRiskyTimelineOffset,
  isStreamTarget,
  compactTargetName,
  seasonLabel,
  buildOutputName,
}) {
  const preparing = ref$1(false);
  const applying = ref$1(false);
  const dragging = ref$1(false);
  const uploadDialog = ref$1(false);
  const rarHelpDialog = ref$1(false);
  const uploadTitle = ref$1('');
  const uploadScopeTargets = ref$1([]);
  const files = ref$1([]);
  const preview = ref$1(null);
  const fileInputRef = ref$1(null);
  const fixTimeline = ref$1(false);
  const batchLanguageSuffix = ref$1('');
  const copyMessage = ref$1('');
  const copyError = ref$1('');
  const lastWritten = ref$1([]);

  const uploadTargets = computed$1(() => uploadScopeTargets.value.filter(item => !isLocked(item.id) && item.writable !== false));
  const batchUploadTargets = computed$1(() => {
    const base = selectedTargets.value.length ? selectedTargets.value : visibleTargets.value;
    return base.filter(item => !isLocked(item.id) && item.writable !== false)
  });
  const targetSelectItems = computed$1(() => uploadTargets.value.map(target => ({
    title: compactTargetName(target),
    value: target.id,
  })));
  const canPrepare = computed$1(() => uploadTargets.value.length > 0 && files.value.length > 0);
  const canApply = computed$1(() => {
    const items = selectedPreviewItems.value;
    return items.length > 0 && items.every(item => item.target_id)
  });
  const hasPreviewItems = computed$1(() => (preview.value?.items || []).length > 0);
  const selectedPreviewItems = computed$1(() => (preview.value?.items || []).filter(item => item.selected !== false));
  const selectedPreviewTargets = computed$1(() => {
    const targetMap = new Map(uploadTargets.value.map(target => [target.id, target]));
    return selectedPreviewItems.value
      .map(item => targetMap.get(item.target_id))
      .filter(Boolean)
  });
  const allSelectedPreviewTargetsAreStream = computed$1(() => {
    const items = selectedPreviewTargets.value;
    return items.length > 0 && items.every(isStreamTarget)
  });
  const hasSelectedPreviewStreamTargets = computed$1(() => selectedPreviewTargets.value.some(isStreamTarget));
  const timelineEnabledForApply = computed$1(() => fixTimeline.value && timelineAvailable.value && !allSelectedPreviewTargetsAreStream.value);

  function clearUploadPreviewState() {
    preview.value = null;
    lastWritten.value = [];
  }

  function clearUploadDialogState() {
    files.value = [];
    preview.value = null;
    batchLanguageSuffix.value = '';
  }

  function normalizePreviewItems() {
    if (!preview.value?.items) return
    const preferSingleCandidate = preview.value.source === 'online' && preview.value.items.length > 1;
    preview.value.items.forEach((item, index) => {
      const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id);
      item.output_name = item.output_name || buildOutputName(target, item);
      item.selected = item.selected !== false && (!preferSingleCandidate || index === 0);
    });
  }

  function openUploadDialog(scopeTargets, title) {
    const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false);
    if (!usableTargets.length) {
      error.value = '没有可上传的目标：选中的集数可能都已锁定';
      return false
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
    return true
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

  function prepareOnlineUploadState(scopeTargets, title) {
    uploadScopeTargets.value = scopeTargets;
    uploadTitle.value = `${title} · 在线字幕`;
    lastWritten.value = [];
    preview.value = null;
    files.value = [];
  }

  function openOnlinePreview(data, responseMessage) {
    preview.value = data;
    batchLanguageSuffix.value = '';
    normalizePreviewItems();
    uploadDialog.value = true;
    message.value = responseMessage || '已下载在线字幕并生成匹配预览';
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
      const response = await pluginApi.value.prepareUpload(formData);
      preview.value = unwrapResponse(response);
      batchLanguageSuffix.value = '';
      normalizePreviewItems();
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
    const allowRiskyOffset = timelineEnabledForApply.value && timelineNeedsRiskyConfirm.value;
    if (allowRiskyOffset && !confirmRiskyTimelineOffset('写入字幕智能调轴')) return
    applying.value = true;
    error.value = '';
    try {
      const payload = {
        session_id: preview.value.session_id,
        fix_timeline: timelineEnabledForApply.value,
        allow_risky_offset: allowRiskyOffset,
        locked_target_ids: lockedTargetPayload(),
        items: selectedPreviewItems.value.map(item => ({
          upload_id: item.upload_id,
          target_id: item.target_id,
          ext: item.ext,
          language_suffix: item.language_suffix,
        })),
      };
      const response = await pluginApi.value.applyUpload(payload);
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

  return {
    preparing,
    applying,
    dragging,
    uploadDialog,
    rarHelpDialog,
    uploadTitle,
    uploadScopeTargets,
    files,
    preview,
    fileInputRef,
    fixTimeline,
    batchLanguageSuffix,
    copyMessage,
    copyError,
    lastWritten,
    uploadTargets,
    batchUploadTargets,
    targetSelectItems,
    canPrepare,
    canApply,
    hasPreviewItems,
    selectedPreviewItems,
    selectedPreviewTargets,
    allSelectedPreviewTargetsAreStream,
    hasSelectedPreviewStreamTargets,
    timelineEnabledForApply,
    clearUploadPreviewState,
    clearUploadDialogState,
    normalizePreviewItems,
    openUploadDialog,
    openBatchUpload,
    openSingleUpload,
    prepareOnlineUploadState,
    openOnlinePreview,
    onPickFiles,
    mergeFiles,
    removeFile,
    openFileDialog,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    prepareUpload,
    prepareUploadAfterFiles,
    updatePreviewTarget,
    updateLanguageSuffix,
    togglePreviewItem,
    applyBatchLanguageSuffix,
    resetUploadPreview,
    openRarHelp,
    copyHelpText,
    applyUpload,
  }
}

function isStreamTarget(target) {
  if (!target) return false
  if (target.is_stream === true) return true
  const text = `${target.path || ''} ${target.relative_path || ''} ${target.basename || ''}`.toLowerCase();
  return /\.strm(?:$|[\s?#])/.test(text)
}

const {unref:_unref,normalizeClass:_normalizeClass,createElementVNode:_createElementVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,resolveComponent:_resolveComponent,createBlock:_createBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,createVNode:_createVNode,isRef:_isRef,withKeys:_withKeys,renderList:_renderList,Fragment:_Fragment,withModifiers:_withModifiers,mergeProps:_mergeProps} = await importShared('vue');


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
const _hoisted_11 = ["src", "alt", "loading", "fetchpriority", "onError"];
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
  class: "auto-queue-entry"
};
const _hoisted_18 = {
  key: 4,
  class: "global-history-list"
};
const _hoisted_19 = ["onClick"];
const _hoisted_20 = { class: "poster-frame compact" };
const _hoisted_21 = ["src", "alt", "loading", "fetchpriority", "onError"];
const _hoisted_22 = { key: 1 };
const _hoisted_23 = { class: "media-copy" };
const _hoisted_24 = { class: "media-type" };
const _hoisted_25 = {
  key: 0,
  class: "global-history-targets"
};
const _hoisted_26 = { class: "history-bulk-toolbar" };
const _hoisted_27 = { class: "history-bulk-copy" };
const _hoisted_28 = { class: "history-bulk-actions" };
const _hoisted_29 = { class: "history-season-tree" };
const _hoisted_30 = {
  key: 0,
  class: "history-season-row"
};
const _hoisted_31 = ["onClick"];
const _hoisted_32 = { key: 0 };
const _hoisted_33 = { class: "history-episode-row" };
const _hoisted_34 = ["onClick"];
const _hoisted_35 = { class: "episode-title" };
const _hoisted_36 = {
  key: 0,
  class: "history-subtitle-children"
};
const _hoisted_37 = { class: "episode-path" };
const _hoisted_38 = {
  key: 0,
  class: "history-status compact-status"
};
const _hoisted_39 = { class: "subtitle-history-list compact-subtitles" };
const _hoisted_40 = { class: "subtitle-history-copy" };
const _hoisted_41 = { class: "subtitle-history-actions" };
const _hoisted_42 = {
  key: 0,
  class: "empty-state compact-empty"
};
const _hoisted_43 = {
  key: 5,
  class: "pager-row"
};
const _hoisted_44 = {
  key: 6,
  class: "empty-state"
};
const _hoisted_45 = {
  key: 5,
  class: "episode-stage"
};
const _hoisted_46 = { class: "detail-head" };
const _hoisted_47 = { class: "selected-media" };
const _hoisted_48 = { class: "mini-poster" };
const _hoisted_49 = ["src", "alt"];
const _hoisted_50 = { key: 1 };
const _hoisted_51 = { class: "section-kicker" };
const _hoisted_52 = {
  key: 0,
  class: "season-strip"
};
const _hoisted_53 = ["onClick"];
const _hoisted_54 = { class: "ai-status-orb" };
const _hoisted_55 = { class: "match-panel" };
const _hoisted_56 = { class: "toolbar-row" };
const _hoisted_57 = {
  key: 0,
  class: "episode-list"
};
const _hoisted_58 = { class: "episode-index" };
const _hoisted_59 = { class: "episode-copy" };
const _hoisted_60 = { class: "episode-title" };
const _hoisted_61 = { class: "episode-path" };
const _hoisted_62 = {
  key: 3,
  class: "episode-expanded"
};
const _hoisted_63 = { class: "history-status compact-status" };
const _hoisted_64 = { key: 0 };
const _hoisted_65 = { key: 1 };
const _hoisted_66 = {
  key: 0,
  class: "subtitle-history-list compact-subtitles"
};
const _hoisted_67 = { class: "subtitle-history-copy" };
const _hoisted_68 = { class: "subtitle-history-actions" };
const _hoisted_69 = {
  key: 1,
  class: "empty-state compact-empty"
};
const _hoisted_70 = {
  key: 1,
  class: "empty-state"
};
const _hoisted_71 = {
  key: 2,
  class: "result-panel"
};
const _hoisted_72 = {
  key: 0,
  class: "timeline-meta-list"
};
const _hoisted_73 = { class: "online-title-actions" };
const _hoisted_74 = { class: "auto-queue-rates" };
const _hoisted_75 = {
  key: 0,
  class: "auto-queue-list"
};
const _hoisted_76 = {
  key: 1,
  class: "empty-state compact-empty"
};
const _hoisted_77 = { class: "online-title-actions" };
const _hoisted_78 = {
  key: 1,
  class: "ai-restart-options"
};
const _hoisted_79 = {
  key: 2,
  class: "ai-task-list"
};
const _hoisted_80 = { class: "ai-task-badge" };
const _hoisted_81 = { class: "ai-task-main" };
const _hoisted_82 = { key: 0 };
const _hoisted_83 = { class: "ai-task-time" };
const _hoisted_84 = {
  key: 3,
  class: "empty-state"
};
const _hoisted_85 = { class: "online-title-actions" };
const _hoisted_86 = { class: "online-message-summary-content" };
const _hoisted_87 = { class: "online-layout" };
const _hoisted_88 = { class: "online-results-panel" };
const _hoisted_89 = { class: "online-panel-head" };
const _hoisted_90 = {
  key: 2,
  class: "online-provider-progress"
};
const _hoisted_91 = {
  key: 3,
  class: "online-loading"
};
const _hoisted_92 = {
  key: 4,
  class: "online-result-list"
};
const _hoisted_93 = { class: "online-result-main" };
const _hoisted_94 = { class: "online-result-title" };
const _hoisted_95 = { class: "online-result-meta" };
const _hoisted_96 = {
  key: 0,
  class: "online-manual-badge"
};
const _hoisted_97 = { key: 0 };
const _hoisted_98 = {
  key: 1,
  class: "online-match-detail"
};
const _hoisted_99 = ["href"];
const _hoisted_100 = {
  key: 5,
  class: "empty-state"
};
const _hoisted_101 = { class: "manual-links-panel" };
const _hoisted_102 = { class: "manual-provider-head" };
const _hoisted_103 = { class: "manual-keywords" };
const _hoisted_104 = ["href"];
const _hoisted_105 = {
  key: 1,
  class: "support-row"
};
const _hoisted_106 = {
  key: 2,
  class: "file-list"
};
const _hoisted_107 = {
  key: 3,
  class: "preview-list"
};
const _hoisted_108 = { class: "preview-head" };
const _hoisted_109 = { class: "batch-language" };
const _hoisted_110 = { class: "subtitle-source" };
const _hoisted_111 = { class: "output-name" };
const _hoisted_112 = { class: "rar-help-list" };
const _hoisted_113 = { class: "rar-help-row-head" };
const _hoisted_114 = { class: "rar-help-row-title" };
const _hoisted_115 = { class: "rar-help-step" };
const _hoisted_116 = ["onClick"];
const _hoisted_117 = { class: "command-block" };

const {computed,onBeforeUnmount,onMounted,ref} = await importShared('vue');

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
const pluginApi = computed(() => createSubtitleManualUploadApi(props.api, pluginBase));
const clearing = ref(false);
const message = ref('');
const error = ref('');

const {
  resolving,
  selectedMedia,
  seasons,
  selectedSeason,
  selectedTargetIds,
  lockedTargetIds,
  visibleTargets,
  selectedTargets,
  targetById,
  unlockedVisibleTargets,
  allVisibleSelected,
  isLocked,
  lockedTargetPayload,
  isTargetActionDisabled,
  detailExpanded,
  toggleDetailExpanded,
  clearTargetState,
  loadTargets,
  selectMedia,
  changeSeason,
  resetSelection,
  toggleSelectAll,
  toggleTarget,
  toggleLock,
} = useTargets({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  mediaLabel,
  clearRelatedState() {
    clearUploadPreviewState();
    resetAiTasks();
    resetTimelineTasks();
  },
  beforeLoadTargets() {
    preview.value = null;
  },
  async afterTargetsLoaded(nextTargets) {
    aiTaskScopeTargets.value = nextTargets;
    await loadAiTasks({ silent: true });
    await loadTimelineTasks({ silent: true });
  },
  runSearch: () => runSearch(),
});

const {
  searching,
  searchKeyword,
  mediaType,
  medias,
  mediaTotal,
  mediaHasMore,
  posterImageSrc,
  markPosterFailed,
  posterLoading,
  posterFetchPriority,
  runSearch,
  loadMoreMedia,
} = useMediaSearch({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  selectedMedia,
  clearTargetState,
});

const {
  autoTransferQueue,
  autoQueueDialog,
  autoQueueSummary,
  autoQueueTasks,
  autoQueueSummaryText,
  applyAutoTransferSummary,
  stopAutoQueuePolling,
  loadAutoTransferQueue,
} = useAutoTransferQueue({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
});

const {
  rootTab,
  matchHistoryLoading,
  matchHistoryItems,
  matchHistoryTotal,
  matchHistoryHasMore,
  historyExpanded,
  toggleHistoryExpanded,
  historySeasonKey,
  historySeasonExpanded,
  toggleHistorySeasonExpanded,
  historyTargetExpanded,
  toggleHistoryTargetExpanded,
  historyDeletableTargets,
  historySelectedIds,
  historySelectedCount,
  allHistoryTargetsSelected,
  toggleHistoryTarget,
  toggleHistoryItemTargets,
  historySeasonGroups,
  historySeasonSelectedCount,
  allHistorySeasonTargetsSelected,
  historySeasonPartiallySelected,
  toggleHistorySeasonTargets,
  clearHistorySelectedSubtitles,
  historySelectedTimelineTargets,
  fixHistorySelectedTimeline,
  fixHistorySubtitleTimeline,
  stopHistoryTimelinePolling,
  scheduleHistoryTimelinePolling,
  submitRootSearch,
  loadMatchHistory,
  loadMoreMatchHistory,
  setRootTab,
  matchHistorySummary,
} = useMatchHistory({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  clearing,
  searchKeyword,
  mediaType,
  selectedMedia,
  clearTargetState,
  lockedTargetPayload,
  isStreamTarget,
  seasonLabel,
  runSearch,
  fixExistingTimeline: (...args) => fixExistingTimeline(...args),
});

const {
  status,
  loading,
  refreshing,
  indexSummary,
  archiveStatus,
  rarAvailable,
  rarPythonAvailable,
  rarDependencyStatus,
  timelineAvailable,
  timelineConfiguredMaxOffset,
  timelineNeedsRiskyConfirm,
  timelineMissing,
  loadStatus,
  refreshIndex,
  stopIndexRefreshPolling,
} = usePluginStatus({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  rootTab,
  selectedMedia,
  selectedSeason,
  applyAiStatus(nextAiStatus) {
    aiTaskData.value = { ...aiTaskData.value, status: nextAiStatus };
  },
  applyAutoTransferSummary,
  loadAutoTransferQueue,
  loadTargets,
  loadMatchHistory,
  runSearch,
});

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

const {
  preparing,
  applying,
  dragging,
  uploadDialog,
  rarHelpDialog,
  uploadTitle,
  files,
  preview,
  fileInputRef,
  fixTimeline,
  batchLanguageSuffix,
  copyMessage,
  copyError,
  lastWritten,
  uploadTargets,
  batchUploadTargets,
  targetSelectItems,
  canApply,
  hasPreviewItems,
  selectedPreviewTargets,
  allSelectedPreviewTargetsAreStream,
  hasSelectedPreviewStreamTargets,
  timelineEnabledForApply,
  clearUploadPreviewState,
  prepareOnlineUploadState,
  openOnlinePreview,
  openBatchUpload,
  openSingleUpload,
  onPickFiles,
  removeFile,
  openFileDialog,
  handleDrop,
  handleDragOver,
  handleDragLeave,
  updatePreviewTarget,
  updateLanguageSuffix,
  togglePreviewItem,
  applyBatchLanguageSuffix,
  resetUploadPreview,
  openRarHelp,
  copyHelpText,
  applyUpload,
} = useUploadPreview({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  selectedTargets,
  visibleTargets,
  selectedMedia,
  selectedSeason,
  isLocked,
  lockedTargetPayload,
  loadTargets,
  timelineAvailable,
  timelineNeedsRiskyConfirm,
  confirmRiskyTimelineOffset,
  isStreamTarget,
  compactTargetName,
  seasonLabel,
  buildOutputName,
});

const selectedSubtitleTargets = computed(() => selectedTargets.value.filter(target => !isLocked(target.id) && (target.subtitles || []).length));

const {
  timelineFixing,
  selectedTimelineTargets,
  applyTimelineTaskData,
  resetTimelineTasks,
  stopTimelinePolling,
  loadTimelineTasks,
  timelineTaskForTarget,
  timelineTaskText,
  fixExistingTimeline,
  fixSelectedDetailTimeline,
} = useTimelineTasks({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  visibleTargets,
  selectedSubtitleTargets,
  lockedTargetPayload,
  timelineAvailable,
  timelineNeedsRiskyConfirm,
  timelineMissing,
  confirmRiskyTimelineOffset,
  isStreamTarget,
  timelineResultText,
  loadMatchHistory,
  scheduleHistoryTimelinePolling,
});

const {
  aiSubmitting,
  aiCancelling,
  aiTasksLoading,
  aiTaskDialog,
  aiTaskDialogTarget,
  aiTaskScopeTargets,
  aiRestartSourcePolicy,
  aiRestartSubtitlePath,
  aiSelectedTaskIds,
  aiStatusStripRef,
  aiTaskData,
  aiStatus,
  aiEnabled,
  aiAvailable,
  aiHasActiveTasks,
  aiBatchCancelTargets,
  aiCapableBatchTargets,
  aiBatchLabel,
  aiSummaryText,
  aiDialogTasks,
  aiDialogHasExistingTasks,
  aiDialogHasActiveTasks,
  aiDialogSelectedAllowedTasks,
  aiDialogActionText,
  aiDialogSourceLabel,
  aiRestartSubtitleOptions,
  applyAiTaskData,
  resetAiTasks,
  stopAiPolling,
  loadAiTasks,
  aiTaskForTarget,
  aiTaskColor,
  aiTaskIcon,
  aiTaskTitle,
  aiTaskStatusClass,
  aiTaskIconForTask,
  aiStatusText,
  focusAiStatusStrip,
  openBatchAiGenerate,
  cancelBatchAiGenerate,
  cancelDialogAiTasks,
  regenerateDialogAiTasks,
  regenerateSingleAiTask,
  openSingleAiGenerate,
} = useAiTasks({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  status,
  visibleTargets,
  selectedMedia,
  selectedSeason,
  selectedTargets,
  batchUploadTargets,
  targetById,
  isLocked,
  lockedTargetPayload,
  isStreamTarget,
  formatBytes,
});

const {
  onlineSearching,
  onlineDownloading,
  onlinePreviewDownloading,
  onlineAiDownloading,
  onlineError,
  onlineDialog,
  onlineAiConfirmDialog,
  onlineTitle,
  onlineKeyword,
  onlineTargets,
  onlineSelectedProviders,
  onlineResults,
  onlineLanguageFilter,
  onlineProviderFilter,
  onlineMessages,
  onlineMessagesCollapsed,
  onlineManualLinks,
  selectedOnlineResultIds,
  hasOnlineResults,
  filteredOnlineResults,
  onlineLanguageFilterItems,
  onlineProviderFilterItems,
  selectedOnlineResults,
  canSubmitOnlineAiTranslate,
  onlineMessageSummary,
  onlineMessageType,
  onlineProviderProgressItems,
  onlineAiConfirmText,
  onlineBatchLabel,
  openBatchOnlineSearch,
  openSingleOnlineSearch,
  runOnlineSearch,
  stopOnlineSearch,
  closeOnlineDialog,
  updateOnlineDialog,
  toggleOnlineResult,
  requestOnlineAiTranslate,
  confirmOnlineAiTranslate,
  downloadOnlinePreview,
  stopOnlineDownload,
} = useOnlineSubtitles({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  selectedMedia,
  selectedTargets,
  selectedSeason,
  batchUploadTargets,
  isLocked,
  lockedTargetPayload,
  compactTargetName,
  aiAvailable,
  timelineNeedsRiskyConfirm,
  confirmRiskyTimelineOffset,
  prepareOnlineUploadState,
  openOnlinePreview,
  closeUploadDialog() {
    preview.value = null;
    uploadDialog.value = false;
  },
  applyAiTaskData,
  setAiTaskScopeTargets(targetsToSet) {
    aiTaskScopeTargets.value = targetsToSet;
  },
  loadAiTasks,
  focusAiStatusStrip,
  applyTimelineTaskData,
  loadTimelineTasks,
});

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
const matchHistoryRows = computed(() => visibleTargets.value.map(target => {
  const subtitles = target.subtitles || [];
  const task = aiTaskForTarget(target);
  const timelineTask = timelineTaskForTarget(target);
  const written = (lastWritten.value || []).filter(item => (
    item.target_label === target.label
    || subtitles.some(subtitle => subtitle.path === item.output_path || subtitle.name === item.output_name)
  ));
  return {
    target,
    subtitles,
    task,
    timelineTask,
    written,
    hasTimelineRunning: applying.value && selectedPreviewTargets.value.some(item => item.id === target.id) && timelineEnabledForApply.value,
  }
}));
const selectedRestorableTargets = computed(() => selectedSubtitleTargets.value.filter(target => (target.subtitles || []).some(subtitle => subtitle.backup_available)));

function detailRowForTarget(target) {
  return matchHistoryRows.value.find(row => row.target.id === target?.id) || {
    target,
    subtitles: target?.subtitles || [],
    task: aiTaskForTarget(target),
    timelineTask: timelineTaskForTarget(target),
    written: [],
  }
}

async function restoreSubtitleBackup(target, subtitle) {
  if (!target || !subtitle) return
  clearing.value = true;
  error.value = '';
  message.value = '';
  try {
    const response = await pluginApi.value.restoreSubtitleBackup({
      target_id: target.id,
      subtitle_path: subtitle.path,
      subtitle_name: subtitle.name,
      locked_target_ids: lockedTargetPayload(),
    });
    message.value = response?.message || `已恢复调轴前字幕：${subtitle.name}`;
    await loadTargets(selectedMedia.value, selectedSeason.value);
  } catch (err) {
    error.value = errorMessage(err, '恢复调轴前字幕失败');
  } finally {
    clearing.value = false;
  }
}

async function restoreSelectedBackups() {
  const items = [];
  selectedRestorableTargets.value.forEach(target => {
(target.subtitles || []).forEach(subtitle => {
      if (subtitle.backup_available) items.push({ target, subtitle });
    });
  });
  if (!items.length || clearing.value) return
  const confirmed = window.confirm(`确认恢复选中集数的 ${items.length} 个调轴前备份？`);
  if (!confirmed) return
  clearing.value = true;
  error.value = '';
  message.value = '';
  try {
    for (const item of items) {
      await pluginApi.value.restoreSubtitleBackup({
        target_id: item.target.id,
        subtitle_path: item.subtitle.path,
        subtitle_name: item.subtitle.name,
        locked_target_ids: lockedTargetPayload(),
      });
    }
    message.value = `已恢复 ${items.length} 个调轴前备份`;
    await loadTargets(selectedMedia.value, selectedSeason.value);
  } catch (err) {
    error.value = errorMessage(err, '批量恢复调轴前字幕失败');
  } finally {
    clearing.value = false;
  }
}

function confirmRiskyTimelineOffset(actionLabel = '智能调轴') {
  if (!timelineNeedsRiskyConfirm.value) return false
  return window.confirm(
    `${actionLabel}当前允许最大偏移 ${timelineConfiguredMaxOffset.value}s。\n\n` +
    '超过 120s 的调轴结果通常意味着错集、错版本或整季包映射错误，不建议超过 120s。\n\n' +
    '确认后，本次请求才会允许 120-300s 的结果人工写入；自动入库不会放行高风险偏移。',
  )
}

function timelineResultForTarget(row) {
  if (row.timelineTask) return timelineTaskText(row.timelineTask)
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
    const response = await pluginApi.value.deleteSubtitle({
      target_id: target.id,
      subtitle_path: subtitle.path,
      subtitle_name: subtitle.name,
      locked_target_ids: lockedTargetPayload(),
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

async function clearSelectedSubtitles() {
  const targetIds = selectedSubtitleTargets.value.map(target => target.id);
  if (!targetIds.length) return
  clearing.value = true;
  error.value = '';
  try {
    const response = await pluginApi.value.clearSubtitles({
      target_ids: targetIds,
      locked_target_ids: lockedTargetPayload(),
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
  loadAutoTransferQueue();
  runSearch();
});

onBeforeUnmount(() => {
  stopAiPolling();
  stopTimelinePolling();
  stopHistoryTimelinePolling();
  stopAutoQueuePolling();
  stopIndexRefreshPolling();
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
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VChipGroup = _resolveComponent("VChipGroup");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VTooltip = _resolveComponent("VTooltip");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!_unref(selectedMedia))
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _createElementVNode("button", {
            type: "button",
            class: _normalizeClass({ active: _unref(rootTab) === 'match' }),
            onClick: _cache[0] || (_cache[0] = $event => (_unref(setRootTab)('match')))
          }, " 字幕匹配 ", 2),
          _createElementVNode("button", {
            type: "button",
            class: _normalizeClass({ active: _unref(rootTab) === 'history' }),
            onClick: _cache[1] || (_cache[1] = $event => (_unref(setRootTab)('history')))
          }, " 匹配历史 ", 2)
        ]))
      : _createCommentVNode("", true),
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_3, [...(_cache[37] || (_cache[37] = [
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
    (!_unref(selectedMedia))
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
                      _createElementVNode("div", _hoisted_6, _toDisplayString(_unref(rootTab) === 'history' ? '历史记录' : '资源选择'), 1),
                      _createElementVNode("h2", null, _toDisplayString(_unref(rootTab) === 'history' ? '查看已匹配字幕' : '选择本地已有资源'), 1),
                      _createElementVNode("p", null, _toDisplayString(_unref(rootTab) === 'history' ? _unref(matchHistorySummary) : `仅展示 MoviePilot 已整理到本地库的视频资源。${_unref(indexSummary)}`), 1)
                    ]),
                    _createVNode(_component_VBtn, {
                      variant: "tonal",
                      color: "primary",
                      "prepend-icon": "mdi-refresh",
                      loading: _unref(refreshing),
                      onClick: _unref(refreshIndex)
                    }, {
                      default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                        _createTextVNode(" 刷新媒体库清单 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "onClick"])
                  ]),
                  _createElementVNode("div", _hoisted_7, [
                    _createVNode(_component_VTextField, {
                      modelValue: _unref(searchKeyword),
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => (_isRef(searchKeyword) ? (searchKeyword).value = $event : null)),
                      label: "片名、剧名或文件关键词",
                      variant: "outlined",
                      density: "comfortable",
                      "hide-details": "",
                      clearable: "",
                      onKeyup: _withKeys(_unref(submitRootSearch), ["enter"])
                    }, null, 8, ["modelValue", "onKeyup"]),
                    _createVNode(_component_VSelect, {
                      modelValue: _unref(mediaType),
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => (_isRef(mediaType) ? (mediaType).value = $event : null)),
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
                      loading: _unref(rootTab) === 'history' ? _unref(matchHistoryLoading) : _unref(searching),
                      onClick: _unref(submitRootSearch)
                    }, {
                      default: _withCtx(() => [...(_cache[39] || (_cache[39] = [
                        _createTextVNode(" 搜索 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "onClick"])
                  ])
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          (_unref(rootTab) === 'match' && _unref(medias).length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(medias), (media, index) => {
                  return (_openBlock(), _createElementBlock("button", {
                    key: media.id,
                    class: "media-card",
                    onClick: $event => (_unref(selectMedia)(media))
                  }, [
                    _createElementVNode("div", _hoisted_10, [
                      (_unref(posterImageSrc)(media))
                        ? (_openBlock(), _createElementBlock("img", {
                            key: 0,
                            src: _unref(posterImageSrc)(media),
                            alt: _unref(mediaLabel)(media),
                            loading: _unref(posterLoading)(index),
                            fetchpriority: _unref(posterFetchPriority)(index),
                            decoding: "async",
                            draggable: "false",
                            onError: $event => (_unref(markPosterFailed)(media))
                          }, null, 40, _hoisted_11))
                        : (_openBlock(), _createElementBlock("span", _hoisted_12, _toDisplayString(_unref(formatMediaType)(media.media_type)), 1))
                    ]),
                    _createElementVNode("div", _hoisted_13, [
                      _createElementVNode("div", _hoisted_14, _toDisplayString(_unref(formatMediaType)(media.media_type)), 1),
                      _createElementVNode("h3", null, _toDisplayString(_unref(mediaLabel)(media)), 1),
                      _createElementVNode("p", null, _toDisplayString(_unref(mediaStat)(media)), 1)
                    ]),
                    _createVNode(_component_VIcon, { icon: "mdi-chevron-right" })
                  ], 8, _hoisted_9))
                }), 128))
              ]))
            : _createCommentVNode("", true),
          (_unref(rootTab) === 'match' && _unref(medias).length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_15, [
                _createElementVNode("span", null, _toDisplayString(_unref(medias).length) + "/" + _toDisplayString(_unref(mediaTotal) || _unref(medias).length) + " 个资源", 1),
                (_unref(mediaHasMore))
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 0,
                      variant: "tonal",
                      loading: _unref(searching),
                      onClick: _unref(loadMoreMedia)
                    }, {
                      default: _withCtx(() => [...(_cache[40] || (_cache[40] = [
                        _createTextVNode(" 加载下一页 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "onClick"]))
                  : _createCommentVNode("", true)
              ]))
            : (_unref(rootTab) === 'match')
              ? (_openBlock(), _createElementBlock("div", _hoisted_16, _toDisplayString(_unref(searching) ? '正在读取本地资源...' : '输入关键词搜索；留空搜索会显示最近整理的视频。'), 1))
              : _createCommentVNode("", true),
          (_unref(rootTab) === 'history' && (_unref(autoQueueTasks).length || _unref(autoQueueSummary).active))
            ? (_openBlock(), _createElementBlock("div", _hoisted_17, [
                _createVNode(_component_VBtn, {
                  variant: "tonal",
                  color: "primary",
                  "prepend-icon": "mdi-tray-full",
                  onClick: _cache[4] || (_cache[4] = $event => (autoQueueDialog.value = true))
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 入库自动字幕队列 · " + _toDisplayString(_unref(autoQueueSummaryText)), 1)
                  ]),
                  _: 1
                })
              ]))
            : _createCommentVNode("", true),
          (_unref(rootTab) === 'history' && _unref(matchHistoryItems).length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_18, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(matchHistoryItems), (item, index) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: item.id,
                    class: "global-history-card"
                  }, [
                    _createElementVNode("button", {
                      type: "button",
                      class: "global-history-head",
                      onClick: $event => (_unref(toggleHistoryExpanded)(item))
                    }, [
                      _createElementVNode("div", _hoisted_20, [
                        (_unref(posterImageSrc)(item))
                          ? (_openBlock(), _createElementBlock("img", {
                              key: 0,
                              src: _unref(posterImageSrc)(item),
                              alt: _unref(mediaLabel)(item),
                              loading: _unref(posterLoading)(index),
                              fetchpriority: _unref(posterFetchPriority)(index),
                              decoding: "async",
                              draggable: "false",
                              onError: $event => (_unref(markPosterFailed)(item))
                            }, null, 40, _hoisted_21))
                          : (_openBlock(), _createElementBlock("span", _hoisted_22, _toDisplayString(_unref(formatMediaType)(item.media_type)), 1))
                      ]),
                      _createElementVNode("div", _hoisted_23, [
                        _createElementVNode("div", _hoisted_24, _toDisplayString(_unref(formatMediaType)(item.media_type)), 1),
                        _createElementVNode("h3", null, _toDisplayString(_unref(mediaLabel)(item)), 1),
                        _createElementVNode("p", null, _toDisplayString(_unref(historyMediaStat)(item)) + " · " + _toDisplayString(item.latest_at || '未知时间'), 1)
                      ]),
                      _createVNode(_component_VIcon, {
                        icon: _unref(historyExpanded)(item) ? 'mdi-chevron-up' : 'mdi-chevron-down'
                      }, null, 8, ["icon"])
                    ], 8, _hoisted_19),
                    (_unref(historyExpanded)(item))
                      ? (_openBlock(), _createElementBlock("div", _hoisted_25, [
                          _createElementVNode("div", _hoisted_26, [
                            _createElementVNode("div", _hoisted_27, [
                              _createElementVNode("strong", null, "已选 " + _toDisplayString(_unref(historySelectedCount)(item)) + "/" + _toDisplayString(_unref(historyDeletableTargets)(item).length) + " 集", 1),
                              _createElementVNode("span", null, _toDisplayString(item.subtitle_count) + " 个外挂字幕", 1)
                            ]),
                            _createElementVNode("div", _hoisted_28, [
                              _createVNode(_component_VBtn, {
                                size: "small",
                                variant: "tonal",
                                "prepend-icon": "mdi-checkbox-multiple-marked-outline",
                                disabled: !_unref(historyDeletableTargets)(item).length || clearing.value,
                                onClick: _withModifiers($event => (_unref(toggleHistoryItemTargets)(item)), ["stop"])
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(_unref(allHistoryTargetsSelected)(item) ? '取消全选' : '全选'), 1)
                                ]),
                                _: 2
                              }, 1032, ["disabled", "onClick"]),
                              _createVNode(_component_VBtn, {
                                size: "small",
                                color: "error",
                                variant: "tonal",
                                "prepend-icon": "mdi-delete-sweep",
                                disabled: !_unref(historySelectedCount)(item) || clearing.value,
                                loading: clearing.value,
                                onClick: _withModifiers($event => (_unref(clearHistorySelectedSubtitles)(item)), ["stop"])
                              }, {
                                default: _withCtx(() => [...(_cache[41] || (_cache[41] = [
                                  _createTextVNode(" 删除选中 ", -1)
                                ]))]),
                                _: 1
                              }, 8, ["disabled", "loading", "onClick"]),
                              _createVNode(_component_VBtn, {
                                size: "small",
                                color: "warning",
                                variant: "tonal",
                                "prepend-icon": "mdi-timeline-clock-outline",
                                disabled: !_unref(historySelectedTimelineTargets)(item).length || _unref(timelineFixing) || !_unref(timelineAvailable),
                                loading: _unref(timelineFixing),
                                onClick: _withModifiers($event => (_unref(fixHistorySelectedTimeline)(item)), ["stop"])
                              }, {
                                default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
                                  _createTextVNode(" 调轴选中 ", -1)
                                ]))]),
                                _: 1
                              }, 8, ["disabled", "loading", "onClick"])
                            ])
                          ]),
                          _createElementVNode("div", _hoisted_29, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(historySeasonGroups)(item), (season) => {
                              return (_openBlock(), _createElementBlock("div", {
                                key: _unref(historySeasonKey)(item, season),
                                class: "history-season-node"
                              }, [
                                (!season.direct)
                                  ? (_openBlock(), _createElementBlock("div", _hoisted_30, [
                                      _createVNode(_component_VCheckbox, {
                                        "model-value": _unref(allHistorySeasonTargetsSelected)(item, season),
                                        indeterminate: _unref(historySeasonPartiallySelected)(item, season),
                                        density: "compact",
                                        "hide-details": "",
                                        disabled: !season.targets.length || clearing.value,
                                        onClick: _cache[5] || (_cache[5] = _withModifiers(() => {}, ["stop"])),
                                        "onUpdate:modelValue": value => _unref(toggleHistorySeasonTargets)(item, season, value)
                                      }, null, 8, ["model-value", "indeterminate", "disabled", "onUpdate:modelValue"]),
                                      _createElementVNode("button", {
                                        type: "button",
                                        class: "history-season-toggle",
                                        onClick: _withModifiers($event => (_unref(toggleHistorySeasonExpanded)(item, season)), ["stop"])
                                      }, [
                                        _createVNode(_component_VIcon, {
                                          icon: _unref(historySeasonExpanded)(item, season) ? 'mdi-chevron-down' : 'mdi-chevron-right'
                                        }, null, 8, ["icon"]),
                                        _createElementVNode("strong", null, _toDisplayString(season.label), 1),
                                        _createElementVNode("span", null, _toDisplayString(season.targets.length) + " 集 · " + _toDisplayString(season.subtitleCount) + " 个外挂字幕", 1),
                                        (_unref(historySeasonSelectedCount)(item, season))
                                          ? (_openBlock(), _createElementBlock("em", _hoisted_32, "已选 " + _toDisplayString(_unref(historySeasonSelectedCount)(item, season)), 1))
                                          : _createCommentVNode("", true)
                                      ], 8, _hoisted_31)
                                    ]))
                                  : _createCommentVNode("", true),
                                (season.direct || _unref(historySeasonExpanded)(item, season))
                                  ? (_openBlock(), _createElementBlock("div", {
                                      key: 1,
                                      class: _normalizeClass(["history-episode-list", { 'direct-targets': season.direct }])
                                    }, [
                                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(season.targets, (target) => {
                                        return (_openBlock(), _createElementBlock("div", {
                                          key: `${_unref(historySeasonKey)(item, season)}-${target.id}`,
                                          class: "history-episode-node"
                                        }, [
                                          _createElementVNode("div", _hoisted_33, [
                                            _createVNode(_component_VCheckbox, {
                                              "model-value": _unref(historySelectedIds)(item).includes(target.id),
                                              density: "compact",
                                              "hide-details": "",
                                              disabled: !(target.subtitles || []).length || clearing.value,
                                              onClick: _cache[6] || (_cache[6] = _withModifiers(() => {}, ["stop"])),
                                              "onUpdate:modelValue": value => _unref(toggleHistoryTarget)(item, target.id, value)
                                            }, null, 8, ["model-value", "disabled", "onUpdate:modelValue"]),
                                            _createElementVNode("button", {
                                              type: "button",
                                              class: "history-episode-toggle",
                                              onClick: _withModifiers($event => (_unref(toggleHistoryTargetExpanded)(target)), ["stop"])
                                            }, [
                                              _createVNode(_component_VIcon, {
                                                icon: _unref(historyTargetExpanded)(target) ? 'mdi-chevron-down' : 'mdi-chevron-right'
                                              }, null, 8, ["icon"]),
                                              _createElementVNode("span", _hoisted_35, _toDisplayString(_unref(compactTargetName)(target)), 1),
                                              _createElementVNode("small", null, _toDisplayString((target.subtitles || []).length) + " 个外挂字幕", 1)
                                            ], 8, _hoisted_34),
                                            _createVNode(_component_VBtn, {
                                              size: "small",
                                              variant: "tonal",
                                              "prepend-icon": "mdi-magnify",
                                              disabled: _unref(isTargetActionDisabled)(target),
                                              onClick: _withModifiers($event => (_unref(openSingleOnlineSearch)(target)), ["stop"])
                                            }, {
                                              default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
                                                _createTextVNode(" 重新搜索 ", -1)
                                              ]))]),
                                              _: 1
                                            }, 8, ["disabled", "onClick"])
                                          ]),
                                          (_unref(historyTargetExpanded)(target))
                                            ? (_openBlock(), _createElementBlock("div", _hoisted_36, [
                                                _createElementVNode("div", _hoisted_37, _toDisplayString(target.relative_path), 1),
                                                (target.timeline_task)
                                                  ? (_openBlock(), _createElementBlock("div", _hoisted_38, [
                                                      _createElementVNode("span", null, "调轴：" + _toDisplayString(_unref(timelineTaskText)(target.timeline_task)), 1),
                                                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(timelineMetaItems)(target.timeline_task.timeline), (meta) => {
                                                        return (_openBlock(), _createElementBlock("span", {
                                                          key: `${target.id}-${meta}`,
                                                          class: "timeline-meta"
                                                        }, _toDisplayString(meta), 1))
                                                      }), 128))
                                                    ]))
                                                  : _createCommentVNode("", true),
                                                _createElementVNode("div", _hoisted_39, [
                                                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(target.subtitles, (subtitle) => {
                                                    return (_openBlock(), _createElementBlock("div", {
                                                      key: subtitle.path,
                                                      class: "subtitle-history-item"
                                                    }, [
                                                      _createElementVNode("div", _hoisted_40, [
                                                        _createElementVNode("strong", null, _toDisplayString(subtitle.name), 1),
                                                        _createElementVNode("span", null, _toDisplayString(_unref(formatBytes)(subtitle.size)) + " · " + _toDisplayString(subtitle.modified_at || '未知时间'), 1)
                                                      ]),
                                                      _createElementVNode("div", _hoisted_41, [
                                                        _createVNode(_component_VBtn, {
                                                          size: "small",
                                                          variant: "tonal",
                                                          color: "warning",
                                                          loading: _unref(timelineFixing),
                                                          disabled: _unref(timelineFixing) || !_unref(timelineAvailable) || _unref(isStreamTarget)(target),
                                                          onClick: _withModifiers($event => (_unref(fixHistorySubtitleTimeline)(target, subtitle)), ["stop"])
                                                        }, {
                                                          default: _withCtx(() => [...(_cache[44] || (_cache[44] = [
                                                            _createTextVNode(" 调轴 ", -1)
                                                          ]))]),
                                                          _: 1
                                                        }, 8, ["loading", "disabled", "onClick"]),
                                                        _createVNode(_component_VBtn, {
                                                          size: "small",
                                                          variant: "tonal",
                                                          color: "error",
                                                          loading: clearing.value,
                                                          onClick: _withModifiers($event => (deleteSubtitle(target, subtitle)), ["stop"])
                                                        }, {
                                                          default: _withCtx(() => [...(_cache[45] || (_cache[45] = [
                                                            _createTextVNode(" 删除 ", -1)
                                                          ]))]),
                                                          _: 1
                                                        }, 8, ["loading", "onClick"])
                                                      ])
                                                    ]))
                                                  }), 128))
                                                ])
                                              ]))
                                            : _createCommentVNode("", true)
                                        ]))
                                      }), 128))
                                    ], 2))
                                  : _createCommentVNode("", true)
                              ]))
                            }), 128))
                          ]),
                          (!_unref(historySeasonGroups)(item).length)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_42, " 暂无可管理的外挂字幕 "))
                            : _createCommentVNode("", true)
                        ]))
                      : _createCommentVNode("", true)
                  ]))
                }), 128))
              ]))
            : _createCommentVNode("", true),
          (_unref(rootTab) === 'history' && _unref(matchHistoryItems).length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_43, [
                _createElementVNode("span", null, _toDisplayString(_unref(matchHistoryItems).length) + "/" + _toDisplayString(_unref(matchHistoryTotal) || _unref(matchHistoryItems).length) + " 部资源", 1),
                (_unref(matchHistoryHasMore))
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 0,
                      variant: "tonal",
                      loading: _unref(matchHistoryLoading),
                      onClick: _unref(loadMoreMatchHistory)
                    }, {
                      default: _withCtx(() => [...(_cache[46] || (_cache[46] = [
                        _createTextVNode(" 加载下一页 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "onClick"]))
                  : _createCommentVNode("", true)
              ]))
            : (_unref(rootTab) === 'history')
              ? (_openBlock(), _createElementBlock("div", _hoisted_44, _toDisplayString(_unref(matchHistoryLoading) ? '正在读取匹配历史...' : '还没有找到已匹配字幕记录。'), 1))
              : _createCommentVNode("", true)
        ]))
      : (_openBlock(), _createElementBlock("section", _hoisted_45, [
          _createVNode(_component_VCard, {
            class: "glass-card detail-card",
            rounded: "xl",
            elevation: "0"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardText, null, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_46, [
                    _createElementVNode("div", _hoisted_47, [
                      _createElementVNode("button", {
                        class: "back-btn",
                        onClick: _cache[7] || (_cache[7] = (...args) => (_unref(resetSelection) && _unref(resetSelection)(...args)))
                      }, [
                        _createVNode(_component_VIcon, { icon: "mdi-arrow-left" })
                      ]),
                      _createElementVNode("div", _hoisted_48, [
                        (_unref(posterImageSrc)(_unref(selectedMedia)))
                          ? (_openBlock(), _createElementBlock("img", {
                              key: 0,
                              src: _unref(posterImageSrc)(_unref(selectedMedia)),
                              alt: _unref(mediaLabel)(_unref(selectedMedia)),
                              loading: "eager",
                              fetchpriority: "high",
                              decoding: "async",
                              draggable: "false",
                              onError: _cache[8] || (_cache[8] = $event => (_unref(markPosterFailed)(_unref(selectedMedia))))
                            }, null, 40, _hoisted_49))
                          : (_openBlock(), _createElementBlock("span", _hoisted_50, _toDisplayString(_unref(formatMediaType)(_unref(selectedMedia).media_type)), 1))
                      ]),
                      _createElementVNode("div", null, [
                        _createElementVNode("div", _hoisted_51, _toDisplayString(_unref(formatMediaType)(_unref(selectedMedia).media_type)), 1),
                        _createElementVNode("h2", null, _toDisplayString(_unref(mediaLabel)(_unref(selectedMedia))), 1),
                        _createElementVNode("p", null, _toDisplayString(_unref(visibleTargets).length) + " 个本地目标 · " + _toDisplayString(_unref(selectedTargets).length) + " 个已选 · " + _toDisplayString(_unref(lockedTargetIds).length) + " 个锁定", 1)
                      ])
                    ]),
                    _createVNode(_component_VBtn, {
                      variant: "tonal",
                      loading: _unref(resolving),
                      onClick: _cache[9] || (_cache[9] = $event => (_unref(loadTargets)(_unref(selectedMedia), _unref(selectedSeason))))
                    }, {
                      default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                        _createTextVNode(" 刷新列表 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  (_unref(selectedMedia).media_type === 'tv')
                    ? (_openBlock(), _createElementBlock("div", _hoisted_52, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(seasonCards.value, (season) => {
                          return (_openBlock(), _createElementBlock("button", {
                            key: season.value,
                            class: _normalizeClass(["season-card", { active: _unref(selectedSeason) === season.value }]),
                            onClick: $event => (_unref(changeSeason)(season.value))
                          }, [
                            _createElementVNode("span", null, _toDisplayString(season.title), 1),
                            _createElementVNode("strong", null, _toDisplayString(season.subtitle), 1)
                          ], 10, _hoisted_53))
                        }), 128))
                      ]))
                    : _createCommentVNode("", true),
                  (_unref(aiEnabled))
                    ? (_openBlock(), _createElementBlock("button", {
                        key: 1,
                        ref_key: "aiStatusStripRef",
                        ref: aiStatusStripRef,
                        class: _normalizeClass(["ai-status-strip", { unavailable: !_unref(aiAvailable), active: _unref(aiHasActiveTasks) }]),
                        type: "button",
                        onClick: _cache[10] || (_cache[10] = $event => (_ctx.openAiTaskDialog()))
                      }, [
                        _createElementVNode("span", _hoisted_54, [
                          (_unref(aiTasksLoading) || _unref(aiHasActiveTasks))
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
                        _createElementVNode("strong", null, _toDisplayString(_unref(aiSummaryText)), 1),
                        _createElementVNode("em", null, _toDisplayString(_unref(aiAvailable) ? '点击查看当前资源任务' : _unref(aiStatus).message), 1)
                      ], 2))
                    : _createCommentVNode("", true),
                  _createElementVNode("div", _hoisted_55, [
                    _createElementVNode("div", _hoisted_56, [
                      _createVNode(_component_VBtn, {
                        variant: "tonal",
                        onClick: _unref(toggleSelectAll)
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(_unref(allVisibleSelected) ? '取消全选' : '全选当前列表'), 1)
                        ]),
                        _: 1
                      }, 8, ["onClick"]),
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        disabled: !_unref(unlockedVisibleTargets).length,
                        onClick: _unref(openBatchUpload)
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(_unref(selectedTargets).length ? '上传选中字幕' : '批量上传整季字幕'), 1)
                        ]),
                        _: 1
                      }, 8, ["disabled", "onClick"]),
                      (_unref(aiEnabled))
                        ? (_openBlock(), _createBlock(_component_VBtn, {
                            key: 0,
                            color: "warning",
                            variant: "tonal",
                            "prepend-icon": "mdi-robot-outline",
                            disabled: !_unref(aiCapableBatchTargets).length || !_unref(aiAvailable),
                            loading: _unref(aiSubmitting),
                            onClick: _unref(openBatchAiGenerate)
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(_unref(aiBatchLabel)), 1)
                            ]),
                            _: 1
                          }, 8, ["disabled", "loading", "onClick"]))
                        : _createCommentVNode("", true),
                      (_unref(aiEnabled) && _unref(aiBatchCancelTargets).length)
                        ? (_openBlock(), _createBlock(_component_VBtn, {
                            key: 1,
                            color: "error",
                            variant: "tonal",
                            "prepend-icon": "mdi-cancel",
                            loading: _unref(aiCancelling),
                            onClick: _unref(cancelBatchAiGenerate)
                          }, {
                            default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
                              _createTextVNode(" 取消 AI ", -1)
                            ]))]),
                            _: 1
                          }, 8, ["loading", "onClick"]))
                        : _createCommentVNode("", true),
                      _createVNode(_component_VBtn, {
                        class: "online-batch-btn",
                        color: "success",
                        variant: "flat",
                        "prepend-icon": "mdi-cloud-search-outline",
                        disabled: !_unref(batchUploadTargets).length,
                        loading: _unref(onlineSearching),
                        onClick: _unref(openBatchOnlineSearch)
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(_unref(onlineBatchLabel)), 1)
                        ]),
                        _: 1
                      }, 8, ["disabled", "loading", "onClick"]),
                      _createVNode(_component_VBtn, {
                        color: "error",
                        variant: "tonal",
                        disabled: !_unref(selectedTargetIds).length,
                        loading: clearing.value,
                        onClick: clearSelectedSubtitles
                      }, {
                        default: _withCtx(() => [...(_cache[49] || (_cache[49] = [
                          _createTextVNode(" 清空选中外挂字幕 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled", "loading"]),
                      _createVNode(_component_VBtn, {
                        color: "warning",
                        variant: "tonal",
                        "prepend-icon": "mdi-timeline-clock",
                        disabled: !_unref(selectedTimelineTargets).length || _unref(timelineFixing) || !_unref(timelineAvailable),
                        loading: _unref(timelineFixing),
                        onClick: _unref(fixSelectedDetailTimeline)
                      }, {
                        default: _withCtx(() => [...(_cache[50] || (_cache[50] = [
                          _createTextVNode(" 批量调轴 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled", "loading", "onClick"]),
                      _createVNode(_component_VBtn, {
                        color: "secondary",
                        variant: "tonal",
                        "prepend-icon": "mdi-restore",
                        disabled: !selectedRestorableTargets.value.length || clearing.value,
                        loading: clearing.value,
                        onClick: restoreSelectedBackups
                      }, {
                        default: _withCtx(() => [...(_cache[51] || (_cache[51] = [
                          _createTextVNode(" 批量恢复 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled", "loading"])
                    ]),
                    (_unref(visibleTargets).length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_57, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(visibleTargets), (target) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: target.id,
                              class: _normalizeClass(["episode-row", { locked: _unref(isLocked)(target.id) }])
                            }, [
                              _createVNode(_component_VCheckbox, {
                                "model-value": _unref(selectedTargetIds).includes(target.id),
                                density: "compact",
                                "hide-details": "",
                                "onUpdate:modelValue": value => _unref(toggleTarget)(target.id, value)
                              }, null, 8, ["model-value", "onUpdate:modelValue"]),
                              _createVNode(_component_VBtn, {
                                class: "episode-expand-btn",
                                variant: "tonal",
                                density: "comfortable",
                                icon: _unref(detailExpanded)(target) ? 'mdi-chevron-down' : 'mdi-chevron-right',
                                title: _unref(detailExpanded)(target) ? '收起外挂字幕' : '展开外挂字幕',
                                onClick: $event => (_unref(toggleDetailExpanded)(target))
                              }, null, 8, ["icon", "title", "onClick"]),
                              _createElementVNode("div", _hoisted_58, _toDisplayString(target.media_type === 'tv' ? `E${String(target.episode || 0).padStart(2, '0')}` : 'MOV'), 1),
                              _createElementVNode("div", _hoisted_59, [
                                _createElementVNode("div", _hoisted_60, _toDisplayString(_unref(compactTargetName)(target)), 1),
                                _createElementVNode("div", _hoisted_61, _toDisplayString(target.relative_path), 1)
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
                                                default: _withCtx(() => [...(_cache[52] || (_cache[52] = [
                                                  _createTextVNode("已有外挂字幕", -1)
                                                ]))]),
                                                _: 1
                                              }),
                                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(target.subtitles, (subtitle) => {
                                                return (_openBlock(), _createBlock(_component_VListItem, {
                                                  key: subtitle.path,
                                                  title: subtitle.name,
                                                  subtitle: _unref(formatBytes)(subtitle.size)
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
                              (_unref(aiEnabled))
                                ? (_openBlock(), _createBlock(_component_VBtn, {
                                    key: 2,
                                    class: _normalizeClass(["ai-row-btn", _unref(aiTaskStatusClass)(target)]),
                                    variant: "text",
                                    icon: _unref(aiTaskIcon)(target),
                                    color: _unref(aiTaskColor)(target),
                                    title: _unref(aiTaskTitle)(target),
                                    disabled: _unref(isTargetActionDisabled)(target) || _unref(isStreamTarget)(target) || (!_unref(aiAvailable) && !_unref(aiTaskForTarget)(target)),
                                    onClick: $event => (_unref(openSingleAiGenerate)(target))
                                  }, null, 8, ["class", "icon", "color", "title", "disabled", "onClick"]))
                                : _createCommentVNode("", true),
                              _createVNode(_component_VBtn, {
                                variant: "text",
                                icon: "mdi-magnify",
                                title: "搜索此集在线字幕",
                                disabled: _unref(isTargetActionDisabled)(target),
                                onClick: $event => (_unref(openSingleOnlineSearch)(target))
                              }, null, 8, ["disabled", "onClick"]),
                              _createVNode(_component_VBtn, {
                                variant: "text",
                                icon: _unref(isLocked)(target.id) ? 'mdi-lock' : 'mdi-lock-open-variant',
                                color: _unref(isLocked)(target.id) ? 'warning' : undefined,
                                title: _unref(isLocked)(target.id) ? '解锁此集' : '锁定此集，批量上传跳过',
                                onClick: $event => (_unref(toggleLock)(target.id))
                              }, null, 8, ["icon", "color", "title", "onClick"]),
                              _createVNode(_component_VBtn, {
                                color: "primary",
                                variant: "tonal",
                                size: "small",
                                disabled: _unref(isTargetActionDisabled)(target),
                                onClick: $event => (_unref(openSingleUpload)(target))
                              }, {
                                default: _withCtx(() => [...(_cache[53] || (_cache[53] = [
                                  _createTextVNode(" 单集上传 ", -1)
                                ]))]),
                                _: 1
                              }, 8, ["disabled", "onClick"]),
                              (_unref(detailExpanded)(target))
                                ? (_openBlock(), _createElementBlock("div", _hoisted_62, [
                                    _createElementVNode("div", _hoisted_63, [
                                      _createElementVNode("span", null, _toDisplayString((target.subtitles || []).length ? `${target.subtitles.length} 个外挂字幕` : '暂无外挂字幕'), 1),
                                      (detailRowForTarget(target).task)
                                        ? (_openBlock(), _createElementBlock("span", _hoisted_64, "AI：" + _toDisplayString(_unref(aiStatusText)(detailRowForTarget(target).task)), 1))
                                        : _createCommentVNode("", true),
                                      _createElementVNode("span", null, _toDisplayString(timelineResultForTarget(detailRowForTarget(target))), 1),
                                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(timelineMetaItems)(_unref(timelineTaskForTarget)(target)?.timeline), (meta) => {
                                        return (_openBlock(), _createElementBlock("span", {
                                          key: `${target.id}-detail-${meta}`,
                                          class: "timeline-meta"
                                        }, _toDisplayString(meta), 1))
                                      }), 128)),
                                      (_unref(isStreamTarget)(target))
                                        ? (_openBlock(), _createElementBlock("span", _hoisted_65, "STRM 资源不启用 AI 生成和智能调轴"))
                                        : _createCommentVNode("", true)
                                    ]),
                                    ((target.subtitles || []).length)
                                      ? (_openBlock(), _createElementBlock("div", _hoisted_66, [
                                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(target.subtitles, (subtitle) => {
                                            return (_openBlock(), _createElementBlock("div", {
                                              key: subtitle.path,
                                              class: "subtitle-history-item"
                                            }, [
                                              _createElementVNode("div", _hoisted_67, [
                                                _createElementVNode("strong", null, _toDisplayString(subtitle.name), 1),
                                                _createElementVNode("span", null, _toDisplayString(_unref(formatBytes)(subtitle.size)) + " · " + _toDisplayString(subtitle.modified_at || '未知时间'), 1)
                                              ]),
                                              _createElementVNode("div", _hoisted_68, [
                                                _createVNode(_component_VBtn, {
                                                  size: "small",
                                                  variant: "tonal",
                                                  color: "warning",
                                                  loading: _unref(timelineFixing),
                                                  disabled: _unref(timelineFixing) || !_unref(timelineAvailable) || _unref(isTargetActionDisabled)(target) || _unref(isStreamTarget)(target),
                                                  onClick: _withModifiers($event => (_unref(fixHistorySubtitleTimeline)(target, subtitle)), ["stop"])
                                                }, {
                                                  default: _withCtx(() => [...(_cache[54] || (_cache[54] = [
                                                    _createTextVNode(" 调轴 ", -1)
                                                  ]))]),
                                                  _: 1
                                                }, 8, ["loading", "disabled", "onClick"]),
                                                _createVNode(_component_VBtn, {
                                                  size: "small",
                                                  variant: "tonal",
                                                  color: "secondary",
                                                  loading: clearing.value,
                                                  disabled: !subtitle.backup_available || _unref(isTargetActionDisabled)(target),
                                                  onClick: _withModifiers($event => (restoreSubtitleBackup(target, subtitle)), ["stop"])
                                                }, {
                                                  default: _withCtx(() => [...(_cache[55] || (_cache[55] = [
                                                    _createTextVNode(" 恢复 ", -1)
                                                  ]))]),
                                                  _: 1
                                                }, 8, ["loading", "disabled", "onClick"]),
                                                _createVNode(_component_VBtn, {
                                                  size: "small",
                                                  variant: "tonal",
                                                  color: "error",
                                                  loading: clearing.value,
                                                  disabled: _unref(isTargetActionDisabled)(target),
                                                  onClick: _withModifiers($event => (deleteSubtitle(target, subtitle)), ["stop"])
                                                }, {
                                                  default: _withCtx(() => [...(_cache[56] || (_cache[56] = [
                                                    _createTextVNode(" 删除 ", -1)
                                                  ]))]),
                                                  _: 1
                                                }, 8, ["loading", "disabled", "onClick"])
                                              ])
                                            ]))
                                          }), 128))
                                        ]))
                                      : (_openBlock(), _createElementBlock("div", _hoisted_69, " 当前集暂无外挂字幕。 "))
                                  ]))
                                : _createCommentVNode("", true)
                            ], 2))
                          }), 128))
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_70, _toDisplayString(_unref(resolving) ? '正在读取本地视频目标...' : '这个资源没有本地视频文件。'), 1)),
                    (_unref(lastWritten).length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_71, [
                          _cache[57] || (_cache[57] = _createElementVNode("div", { class: "section-kicker" }, "写入结果", -1)),
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(lastWritten), (item) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: item.output_path,
                              class: "result-row"
                            }, [
                              _createElementVNode("div", null, [
                                _createElementVNode("strong", null, _toDisplayString(item.output_name), 1),
                                _createElementVNode("span", null, _toDisplayString(item.target_label), 1)
                              ]),
                              _createElementVNode("em", null, _toDisplayString(_unref(timelineResultText)(item)), 1),
                              (_unref(timelineMetaItems)(item).length)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_72, [
                                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(timelineMetaItems)(item), (meta) => {
                                      return (_openBlock(), _createElementBlock("span", {
                                        key: `${item.output_path}-${meta}`,
                                        class: "timeline-meta"
                                      }, _toDisplayString(meta), 1))
                                    }), 128))
                                  ]))
                                : _createCommentVNode("", true)
                            ]))
                          }), 128))
                        ]))
                      : _createCommentVNode("", true)
                  ])
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ])),
    _createVNode(_component_VDialog, {
      modelValue: _unref(autoQueueDialog),
      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => (_isRef(autoQueueDialog) ? (autoQueueDialog).value = $event : null)),
      "max-width": "760"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, {
          class: "auto-queue-card",
          rounded: "xl"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dialog-title" }, {
              default: _withCtx(() => [
                _createElementVNode("div", null, [
                  _cache[58] || (_cache[58] = _createElementVNode("span", null, "入库自动字幕队列", -1)),
                  _createElementVNode("p", null, _toDisplayString(_unref(autoQueueSummaryText)), 1)
                ]),
                _createElementVNode("div", _hoisted_73, [
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    "prepend-icon": "mdi-refresh",
                    onClick: _unref(loadAutoTransferQueue)
                  }, {
                    default: _withCtx(() => [...(_cache[59] || (_cache[59] = [
                      _createTextVNode(" 刷新 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["onClick"]),
                  _createVNode(_component_VBtn, {
                    icon: "mdi-close",
                    variant: "text",
                    onClick: _cache[11] || (_cache[11] = $event => (autoQueueDialog.value = false))
                  })
                ])
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_74, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(autoTransferQueue).rate_limits || {}, (rate, provider) => {
                    return (_openBlock(), _createElementBlock("span", { key: provider }, _toDisplayString(provider) + "：" + _toDisplayString(rate.remaining) + "/" + _toDisplayString(rate.limit_per_minute) + " 可用 ", 1))
                  }), 128))
                ]),
                (_unref(autoQueueTasks).length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_75, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(autoQueueTasks).slice().reverse().slice(0, 12), (task) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: task.id,
                          class: _normalizeClass(["auto-queue-row", `auto-queue-${task.status}`])
                        }, [
                          _createElementVNode("strong", null, _toDisplayString(task.target_label || task.title || task.id), 1),
                          _createElementVNode("span", null, [
                            _createTextVNode(_toDisplayString(task.message || task.status), 1),
                            (task.next_run_at)
                              ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                  _createTextVNode(" · 下次 " + _toDisplayString(task.next_run_at), 1)
                                ], 64))
                              : _createCommentVNode("", true)
                          ])
                        ], 2))
                      }), 128))
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_76, " 当前没有入库自动字幕任务。 "))
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
      modelValue: _unref(aiTaskDialog),
      "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => (_isRef(aiTaskDialog) ? (aiTaskDialog).value = $event : null)),
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
                  _createElementVNode("span", null, _toDisplayString(_unref(aiTaskDialogTarget) ? `AI 状态 · ${_unref(compactTargetName)(_unref(aiTaskDialogTarget))}` : 'AI 字幕生成状态'), 1),
                  _createElementVNode("p", null, _toDisplayString(_unref(aiSummaryText)) + " · 状态来自 AI字幕生成(联动版) 队列", 1)
                ]),
                _createElementVNode("div", _hoisted_77, [
                  (_unref(aiDialogHasActiveTasks))
                    ? (_openBlock(), _createBlock(_component_VBtn, {
                        key: 0,
                        variant: "tonal",
                        color: "error",
                        "prepend-icon": "mdi-cancel",
                        loading: _unref(aiCancelling),
                        onClick: _unref(cancelDialogAiTasks)
                      }, {
                        default: _withCtx(() => [...(_cache[60] || (_cache[60] = [
                          _createTextVNode(" 取消任务 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading", "onClick"]))
                    : _createCommentVNode("", true),
                  (_unref(aiAvailable) && (_unref(aiTaskDialogTarget) || _unref(aiDialogTasks).length))
                    ? (_openBlock(), _createBlock(_component_VBtn, {
                        key: 1,
                        variant: "tonal",
                        color: "warning",
                        "prepend-icon": "mdi-robot-happy-outline",
                        disabled: _unref(aiDialogHasExistingTasks) && !_unref(aiDialogSelectedAllowedTasks).length,
                        loading: _unref(aiSubmitting),
                        onClick: _unref(regenerateDialogAiTasks)
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(_unref(aiDialogActionText)), 1)
                        ]),
                        _: 1
                      }, 8, ["disabled", "loading", "onClick"]))
                    : _createCommentVNode("", true),
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    color: "primary",
                    "prepend-icon": "mdi-refresh",
                    loading: _unref(aiTasksLoading),
                    onClick: _unref(loadAiTasks)
                  }, {
                    default: _withCtx(() => [...(_cache[61] || (_cache[61] = [
                      _createTextVNode(" 刷新 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading", "onClick"]),
                  _createVNode(_component_VBtn, {
                    icon: "mdi-close",
                    variant: "text",
                    onClick: _cache[13] || (_cache[13] = $event => (aiTaskDialog.value = false))
                  })
                ])
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                (!_unref(aiAvailable))
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      class: "mb-4",
                      type: "warning",
                      variant: "tonal",
                      text: _unref(aiStatus).message || '请先安装并启用 AI字幕生成(联动版)'
                    }, null, 8, ["text"]))
                  : _createCommentVNode("", true),
                (_unref(aiAvailable) && (_unref(aiTaskDialogTarget) || _unref(aiDialogTasks).length))
                  ? (_openBlock(), _createElementBlock("div", _hoisted_78, [
                      _createVNode(_component_VSelect, {
                        modelValue: _unref(aiRestartSourcePolicy),
                        "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => (_isRef(aiRestartSourcePolicy) ? (aiRestartSourcePolicy).value = $event : null)),
                        items: _unref(aiRestartSourceOptions),
                        label: _unref(aiDialogSourceLabel),
                        density: "comfortable",
                        hint: "改选来源会写入来源变体后缀，如 .aiasr.srt 或 .aiembedded.srt",
                        "persistent-hint": ""
                      }, null, 8, ["modelValue", "items", "label"]),
                      (_unref(aiRestartSourcePolicy) === 'matched_external')
                        ? (_openBlock(), _createBlock(_component_VSelect, {
                            key: 0,
                            modelValue: _unref(aiRestartSubtitlePath),
                            "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => (_isRef(aiRestartSubtitlePath) ? (aiRestartSubtitlePath).value = $event : null)),
                            class: "mt-3",
                            items: _unref(aiRestartSubtitleOptions),
                            label: "外挂字幕",
                            density: "comfortable",
                            hint: _unref(aiRestartSubtitleOptions).length ? '使用这条外挂 SRT 作为 AI 翻译来源' : '当前集没有可用于 AI 翻译的 SRT 外挂字幕',
                            "persistent-hint": "",
                            disabled: !_unref(aiRestartSubtitleOptions).length
                          }, null, 8, ["modelValue", "items", "hint", "disabled"]))
                        : _createCommentVNode("", true)
                    ]))
                  : _createCommentVNode("", true),
                (_unref(aiDialogTasks).length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_79, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(aiDialogTasks), (task) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: task.task_id,
                          class: _normalizeClass(["ai-task-row", `ai-${task.status}`])
                        }, [
                          _createVNode(_component_VCheckbox, {
                            modelValue: _unref(aiSelectedTaskIds),
                            "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => (_isRef(aiSelectedTaskIds) ? (aiSelectedTaskIds).value = $event : null)),
                            value: task.task_id,
                            density: "compact",
                            "hide-details": "",
                            disabled: !_ctx.isAiTaskAllowed(task)
                          }, null, 8, ["modelValue", "value", "disabled"]),
                          _createElementVNode("div", _hoisted_80, [
                            _createVNode(_component_VIcon, {
                              icon: _unref(aiTaskIconForTask)(task)
                            }, null, 8, ["icon"])
                          ]),
                          _createElementVNode("div", _hoisted_81, [
                            _createElementVNode("strong", null, _toDisplayString(task.target_label || task.video_name), 1),
                            _createElementVNode("span", null, _toDisplayString(task.source_asset_name || task.source_subtitle_name ? `字幕源：${task.source_asset_name || task.source_subtitle_name}` : (task.resolved_source_label || task.source_policy_label || task.video_name)), 1),
                            (task.output_name)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_82, "输出：" + _toDisplayString(task.output_name), 1))
                              : _createCommentVNode("", true),
                            _createElementVNode("p", null, _toDisplayString(_unref(aiStatusText)(task)), 1)
                          ]),
                          _createElementVNode("div", _hoisted_83, [
                            _createVNode(_component_VChip, {
                              size: "small",
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(task.status_label), 1)
                              ]),
                              _: 2
                            }, 1024),
                            _createElementVNode("span", null, _toDisplayString(task.complete_time || task.add_time || '-'), 1),
                            _createVNode(_component_VBtn, {
                              size: "small",
                              variant: "tonal",
                              color: "warning",
                              disabled: !_ctx.isAiTaskAllowed(task),
                              loading: _unref(aiSubmitting),
                              onClick: $event => (_unref(regenerateSingleAiTask)(task))
                            }, {
                              default: _withCtx(() => [...(_cache[62] || (_cache[62] = [
                                _createTextVNode(" 重新生成 ", -1)
                              ]))]),
                              _: 1
                            }, 8, ["disabled", "loading", "onClick"])
                          ])
                        ], 2))
                      }), 128))
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_84, " 当前资源还没有 AI 字幕生成任务。可以点击单集 AI 图标，或使用上方“AI 生成”批量提交。 "))
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
      "model-value": _unref(onlineDialog),
      "max-width": "1080",
      "onUpdate:modelValue": _unref(updateOnlineDialog)
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
                  _createElementVNode("span", null, _toDisplayString(_unref(onlineTitle) || '在线字幕搜索'), 1),
                  _createElementVNode("p", null, _toDisplayString(_unref(onlineTargets).length) + " 个目标 · 下载会进入匹配预览，提交 AI 翻译会直接进入 AI 状态", 1)
                ]),
                _createElementVNode("div", _hoisted_85, [
                  _createVNode(_component_VBtn, {
                    color: "success",
                    disabled: !_unref(selectedOnlineResults).length || _unref(onlineAiDownloading),
                    loading: _unref(onlinePreviewDownloading),
                    onClick: _unref(downloadOnlinePreview)
                  }, {
                    default: _withCtx(() => [...(_cache[63] || (_cache[63] = [
                      _createTextVNode(" 下载并生成预览 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "loading", "onClick"]),
                  _createVNode(_component_VBtn, {
                    color: "primary",
                    variant: "tonal",
                    disabled: !_unref(canSubmitOnlineAiTranslate) || _unref(onlinePreviewDownloading),
                    loading: _unref(onlineAiDownloading),
                    onClick: _unref(requestOnlineAiTranslate)
                  }, {
                    default: _withCtx(() => [...(_cache[64] || (_cache[64] = [
                      _createTextVNode(" 提交 AI 翻译 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "loading", "onClick"]),
                  (_unref(onlineDownloading))
                    ? (_openBlock(), _createBlock(_component_VBtn, {
                        key: 0,
                        color: "warning",
                        variant: "tonal",
                        onClick: _unref(stopOnlineDownload)
                      }, {
                        default: _withCtx(() => [...(_cache[65] || (_cache[65] = [
                          _createTextVNode(" 停止等待 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["onClick"]))
                    : _createCommentVNode("", true),
                  _createVNode(_component_VBtn, {
                    icon: "mdi-close",
                    variant: "text",
                    onClick: _unref(closeOnlineDialog)
                  }, null, 8, ["onClick"])
                ])
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, { class: "online-search-actions" }, {
              default: _withCtx(() => [
                _createVNode(_component_VTextField, {
                  modelValue: _unref(onlineKeyword),
                  "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => (_isRef(onlineKeyword) ? (onlineKeyword).value = $event : null)),
                  label: "手动关键词（可选）",
                  placeholder: "留空按资源名、季集号自动生成",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": "",
                  clearable: "",
                  onKeyup: _withKeys(_unref(runOnlineSearch), ["enter"])
                }, null, 8, ["modelValue", "onKeyup"]),
                _createVNode(_component_VSelect, {
                  modelValue: _unref(onlineSelectedProviders),
                  "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => (_isRef(onlineSelectedProviders) ? (onlineSelectedProviders).value = $event : null)),
                  items: _unref(onlineProviderItems),
                  label: "字幕源",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": "",
                  multiple: "",
                  chips: ""
                }, null, 8, ["modelValue", "items"]),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  disabled: !_unref(onlineSelectedProviders).length,
                  loading: _unref(onlineSearching),
                  onClick: _unref(runOnlineSearch)
                }, {
                  default: _withCtx(() => [...(_cache[66] || (_cache[66] = [
                    _createTextVNode(" 搜索 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading", "onClick"]),
                (_unref(onlineSearching))
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 0,
                      color: "warning",
                      variant: "tonal",
                      onClick: _unref(stopOnlineSearch)
                    }, {
                      default: _withCtx(() => [...(_cache[67] || (_cache[67] = [
                        _createTextVNode(" 停止等待 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["onClick"]))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                (_unref(onlineError))
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      class: "mb-4",
                      type: "error",
                      variant: "tonal",
                      text: _unref(onlineError)
                    }, null, 8, ["text"]))
                  : _createCommentVNode("", true),
                (_unref(onlineMessages).length && !_unref(onlineMessagesCollapsed))
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 1,
                      class: "online-message-summary",
                      type: _unref(onlineMessageType),
                      variant: "tonal",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_86, [
                          _createElementVNode("span", null, _toDisplayString(_unref(onlineMessageSummary)), 1),
                          _createVNode(_component_VBtn, {
                            size: "x-small",
                            variant: "text",
                            onClick: _cache[20] || (_cache[20] = $event => (onlineMessagesCollapsed.value = true))
                          }, {
                            default: _withCtx(() => [...(_cache[68] || (_cache[68] = [
                              _createTextVNode(" 收起 ", -1)
                            ]))]),
                            _: 1
                          })
                        ])
                      ]),
                      _: 1
                    }, 8, ["type"]))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_87, [
                  _createElementVNode("section", _hoisted_88, [
                    _createElementVNode("div", _hoisted_89, [
                      _cache[69] || (_cache[69] = _createElementVNode("div", null, [
                        _createElementVNode("div", { class: "section-kicker" }, "自动搜索"),
                        _createElementVNode("h3", null, "选择要下载的字幕")
                      ], -1)),
                      _createElementVNode("span", null, _toDisplayString(_unref(hasOnlineResults) ? `${_unref(filteredOnlineResults).length}/${_unref(onlineResults).length} 条结果` : '暂无结果'), 1)
                    ]),
                    (_unref(hasOnlineResults))
                      ? (_openBlock(), _createBlock(_component_VChipGroup, {
                          key: 0,
                          modelValue: _unref(onlineLanguageFilter),
                          "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => (_isRef(onlineLanguageFilter) ? (onlineLanguageFilter).value = $event : null)),
                          class: "online-provider-filter",
                          mandatory: "",
                          "selected-class": "online-provider-filter-active"
                        }, {
                          default: _withCtx(() => [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(onlineLanguageFilterItems), (item) => {
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
                    (_unref(hasOnlineResults))
                      ? (_openBlock(), _createBlock(_component_VChipGroup, {
                          key: 1,
                          modelValue: _unref(onlineProviderFilter),
                          "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => (_isRef(onlineProviderFilter) ? (onlineProviderFilter).value = $event : null)),
                          class: "online-provider-filter",
                          mandatory: "",
                          "selected-class": "online-provider-filter-active"
                        }, {
                          default: _withCtx(() => [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(onlineProviderFilterItems), (item) => {
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
                    (_unref(onlineProviderProgressItems).length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_90, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(onlineProviderProgressItems), (item) => {
                            return (_openBlock(), _createBlock(_component_VChip, {
                              key: item.provider,
                              size: "small",
                              variant: "tonal",
                              color: _unref(providerProgressColor)(item.state)
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(_unref(providerName)(item.provider)) + " · " + _toDisplayString(_unref(providerProgressText)(item.state)), 1)
                              ]),
                              _: 2
                            }, 1032, ["color"]))
                          }), 128))
                        ]))
                      : _createCommentVNode("", true),
                    (_unref(onlineSearching) && !_unref(filteredOnlineResults).length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_91, " 正在从 API 搜索字幕，先返回的结果会先显示... "))
                      : _createCommentVNode("", true),
                    (_unref(filteredOnlineResults).length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_92, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(filteredOnlineResults), (item) => {
                            return (_openBlock(), _createElementBlock("div", {
                              key: _unref(onlineResultKey)(item),
                              class: _normalizeClass(["online-result-card", {
                    active: _unref(selectedOnlineResultIds).includes(_unref(onlineResultKey)(item)),
                    disabled: !_unref(isOnlineResultDownloadable)(item),
                  }])
                            }, [
                              _createVNode(_component_VCheckbox, {
                                "model-value": _unref(selectedOnlineResultIds).includes(_unref(onlineResultKey)(item)),
                                density: "compact",
                                "hide-details": "",
                                disabled: !_unref(isOnlineResultDownloadable)(item),
                                "onUpdate:modelValue": value => _unref(toggleOnlineResult)(item, value)
                              }, null, 8, ["model-value", "disabled", "onUpdate:modelValue"]),
                              _createElementVNode("div", _hoisted_93, [
                                _createElementVNode("div", _hoisted_94, _toDisplayString(item.title), 1),
                                _createElementVNode("div", _hoisted_95, [
                                  _createElementVNode("span", null, _toDisplayString(_unref(providerName)(item.provider)), 1),
                                  _createElementVNode("span", null, _toDisplayString(_unref(onlineResultMeta)(item)), 1),
                                  (!_unref(isOnlineResultDownloadable)(item))
                                    ? (_openBlock(), _createElementBlock("span", _hoisted_96, " 需手动下载 "))
                                    : _createCommentVNode("", true)
                                ]),
                                (item.note)
                                  ? (_openBlock(), _createElementBlock("p", _hoisted_97, _toDisplayString(item.note), 1))
                                  : _createCommentVNode("", true),
                                (item.match_detail)
                                  ? (_openBlock(), _createElementBlock("p", _hoisted_98, _toDisplayString(item.match_detail), 1))
                                  : _createCommentVNode("", true)
                              ]),
                              (item.page_url)
                                ? (_openBlock(), _createElementBlock("a", {
                                    key: 0,
                                    class: "online-open-link",
                                    href: item.page_url,
                                    target: "_blank",
                                    rel: "noopener noreferrer"
                                  }, " 查看 ", 8, _hoisted_99))
                                : _createCommentVNode("", true)
                            ], 2))
                          }), 128))
                        ]))
                      : (!_unref(onlineSearching))
                        ? (_openBlock(), _createElementBlock("div", _hoisted_100, _toDisplayString(_unref(hasOnlineResults) ? '当前平台筛选下没有结果。' : '没有可自动下载的字幕结果。可以换关键词重试，或使用右侧手动搜索。'), 1))
                        : _createCommentVNode("", true)
                  ]),
                  _createElementVNode("aside", _hoisted_101, [
                    _cache[70] || (_cache[70] = _createElementVNode("div", { class: "section-kicker" }, "手动搜索", -1)),
                    _cache[71] || (_cache[71] = _createElementVNode("h3", null, "跳转字幕站", -1)),
                    _cache[72] || (_cache[72] = _createElementVNode("p", null, "自动搜索失败或源站需要验证时，可打开链接下载字幕包后回到本页上传。", -1)),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(onlineManualLinks), (provider) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: provider.provider,
                        class: "manual-provider"
                      }, [
                        _createElementVNode("div", _hoisted_102, [
                          _createElementVNode("strong", null, _toDisplayString(provider.name), 1)
                        ]),
                        _createElementVNode("div", _hoisted_103, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(provider.links, (link) => {
                            return (_openBlock(), _createElementBlock("a", {
                              key: `${provider.provider}-${link.keyword}`,
                              href: link.url,
                              target: "_blank",
                              rel: "noopener noreferrer"
                            }, _toDisplayString(link.keyword), 9, _hoisted_104))
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
    }, 8, ["model-value", "onUpdate:modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: _unref(onlineAiConfirmDialog),
      "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => (_isRef(onlineAiConfirmDialog) ? (onlineAiConfirmDialog).value = $event : null)),
      "max-width": "520"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { rounded: "lg" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dialog-title compact" }, {
              default: _withCtx(() => [
                _createElementVNode("div", null, [
                  _cache[73] || (_cache[73] = _createElementVNode("span", null, "确认提交 AI 翻译", -1)),
                  _createElementVNode("p", null, _toDisplayString(_unref(onlineAiConfirmText)), 1)
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
                  text: "确认后会在后台下载所选外语字幕，智能调轴后提交到 AI 字幕生成队列；不会打开匹配预览，误触后可在 AI 状态里取消。"
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, { class: "justify-end" }, {
              default: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[23] || (_cache[23] = $event => (onlineAiConfirmDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[74] || (_cache[74] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  loading: _unref(onlineAiDownloading),
                  onClick: _unref(confirmOnlineAiTranslate)
                }, {
                  default: _withCtx(() => [...(_cache[75] || (_cache[75] = [
                    _createTextVNode(" 确认提交 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading", "onClick"])
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
      modelValue: _unref(uploadDialog),
      "onUpdate:modelValue": _cache[34] || (_cache[34] = $event => (_isRef(uploadDialog) ? (uploadDialog).value = $event : null)),
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
                _createElementVNode("span", null, _toDisplayString(_unref(uploadTitle) || '上传字幕'), 1),
                _createVNode(_component_VBtn, {
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[25] || (_cache[25] = $event => (uploadDialog.value = false))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardActions, { class: "dialog-actions dialog-actions-top" }, {
              default: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[26] || (_cache[26] = $event => (uploadDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[76] || (_cache[76] = [
                    _createTextVNode("关闭", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VSpacer),
                (_unref(hasPreviewItems))
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 0,
                      variant: "tonal",
                      onClick: _unref(resetUploadPreview)
                    }, {
                      default: _withCtx(() => [...(_cache[77] || (_cache[77] = [
                        _createTextVNode(" 重新选择文件 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["onClick"]))
                  : _createCommentVNode("", true),
                (_unref(hasPreviewItems))
                  ? (_openBlock(), _createBlock(_component_VTooltip, {
                      key: 1,
                      location: "top",
                      text: _unref(allSelectedPreviewTargetsAreStream) ? 'STRM 资源暂不支持智能调轴。' : (_unref(hasSelectedPreviewStreamTargets) ? 'STRM 目标会跳过调轴，其余本地视频正常处理。' : '写入前会分析视频/字幕时间轴，可能占用 CPU 并造成短暂卡顿。')
                    }, {
                      activator: _withCtx(({ props: tooltipProps }) => [
                        _createElementVNode("div", _mergeProps(tooltipProps, { class: "timeline-action" }), [
                          _createVNode(_component_VSwitch, {
                            modelValue: _unref(fixTimeline),
                            "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => (_isRef(fixTimeline) ? (fixTimeline).value = $event : null)),
                            color: "primary",
                            density: "comfortable",
                            "hide-details": "",
                            disabled: !_unref(timelineAvailable) || _unref(allSelectedPreviewTargetsAreStream),
                            label: _unref(hasSelectedPreviewStreamTargets) ? '智能调轴（STRM跳过）' : '智能调轴'
                          }, null, 8, ["modelValue", "disabled", "label"])
                        ], 16)
                      ]),
                      _: 1
                    }, 8, ["text"]))
                  : _createCommentVNode("", true),
                (_unref(hasPreviewItems))
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 2,
                      color: "success",
                      disabled: !_unref(canApply),
                      loading: _unref(applying),
                      onClick: _unref(applyUpload)
                    }, {
                      default: _withCtx(() => [...(_cache[78] || (_cache[78] = [
                        _createTextVNode(" 写入字幕 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled", "loading", "onClick"]))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                (!_unref(hasPreviewItems))
                  ? (_openBlock(), _createElementBlock("div", {
                      key: 0,
                      class: _normalizeClass(["dropzone", { dragging: _unref(dragging) }]),
                      onDrop: _cache[29] || (_cache[29] = (...args) => (_unref(handleDrop) && _unref(handleDrop)(...args))),
                      onDragover: _cache[30] || (_cache[30] = (...args) => (_unref(handleDragOver) && _unref(handleDragOver)(...args))),
                      onDragleave: _cache[31] || (_cache[31] = (...args) => (_unref(handleDragLeave) && _unref(handleDragLeave)(...args)))
                    }, [
                      _cache[80] || (_cache[80] = _createElementVNode("div", { class: "dropzone-icon" }, "SRT / ASS / ZIP / RAR / 7Z", -1)),
                      _cache[81] || (_cache[81] = _createElementVNode("div", { class: "dropzone-title" }, "把字幕或压缩包拖到这里", -1)),
                      _cache[82] || (_cache[82] = _createElementVNode("div", { class: "dropzone-text" }, " 支持字幕文件、ZIP、RAR、7Z；RAR/7Z 需容器内解压器支持。 ", -1)),
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        variant: "flat",
                        disabled: _unref(preparing),
                        loading: _unref(preparing),
                        onClick: _unref(openFileDialog)
                      }, {
                        default: _withCtx(() => [...(_cache[79] || (_cache[79] = [
                          _createTextVNode(" 选择文件 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled", "loading", "onClick"]),
                      _createElementVNode("input", {
                        ref_key: "fileInputRef",
                        ref: fileInputRef,
                        class: "hidden-input",
                        type: "file",
                        multiple: "",
                        accept: ".srt,.ass,.ssa,.sbv,.sub,.vtt,.webvtt,.zip,.rar,.7z",
                        onChange: _cache[28] || (_cache[28] = (...args) => (_unref(onPickFiles) && _unref(onPickFiles)(...args)))
                      }, null, 544)
                    ], 34))
                  : _createCommentVNode("", true),
                (!_unref(hasPreviewItems))
                  ? (_openBlock(), _createElementBlock("div", _hoisted_105, [
                      _createElementVNode("span", {
                        class: _normalizeClass({ ok: _unref(rarPythonAvailable) })
                      }, "rarfile：" + _toDisplayString(_unref(rarPythonAvailable) ? '已安装' : '将由 requirements.txt 安装'), 3),
                      _createElementVNode("span", {
                        class: _normalizeClass({ ok: _unref(rarAvailable) })
                      }, "RAR 解压器：" + _toDisplayString(_unref(rarAvailable) ? _unref(archiveStatus).rar_tool || '可用' : '未检测到'), 3),
                      _createElementVNode("span", {
                        class: _normalizeClass({ ok: _unref(rarDependencyStatus).state === 'ready' })
                      }, " 处理方式：" + _toDisplayString(_unref(rarDependencyModeLabel)(_unref(archiveStatus).dependency_mode)), 3),
                      _createElementVNode("button", {
                        class: "support-help",
                        type: "button",
                        onClick: _cache[32] || (_cache[32] = (...args) => (_unref(openRarHelp) && _unref(openRarHelp)(...args)))
                      }, " RAR 不能解压？查看处理方式 "),
                      _createElementVNode("span", {
                        class: _normalizeClass({ ok: _unref(timelineAvailable) })
                      }, " 智能调轴：" + _toDisplayString(_unref(timelineAvailable) ? '可用' : `缺少 ${_unref(timelineMissing) || '依赖'}`), 3)
                    ]))
                  : _createCommentVNode("", true),
                (!_unref(hasPreviewItems) && _unref(files).length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_106, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(files), (file) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: `${file.name}-${file.size}`,
                          class: "file-row"
                        }, [
                          _createElementVNode("div", null, [
                            _createElementVNode("strong", null, _toDisplayString(file.name), 1),
                            _createElementVNode("span", null, _toDisplayString(_unref(formatBytes)(file.size)), 1)
                          ]),
                          _createVNode(_component_VBtn, {
                            size: "small",
                            variant: "text",
                            color: "error",
                            onClick: $event => (_unref(removeFile)(file))
                          }, {
                            default: _withCtx(() => [...(_cache[83] || (_cache[83] = [
                              _createTextVNode("移除", -1)
                            ]))]),
                            _: 1
                          }, 8, ["onClick"])
                        ]))
                      }), 128))
                    ]))
                  : _createCommentVNode("", true),
                (_unref(hasPreviewItems))
                  ? (_openBlock(), _createElementBlock("div", _hoisted_107, [
                      _createElementVNode("div", _hoisted_108, [
                        _cache[85] || (_cache[85] = _createElementVNode("div", null, [
                          _createElementVNode("div", { class: "section-kicker" }, "字幕匹配"),
                          _createElementVNode("h3", null, "确认集数与输出文件名")
                        ], -1)),
                        _createElementVNode("div", _hoisted_109, [
                          _createVNode(_component_VTextField, {
                            modelValue: _unref(batchLanguageSuffix),
                            "onUpdate:modelValue": _cache[33] || (_cache[33] = $event => (_isRef(batchLanguageSuffix) ? (batchLanguageSuffix).value = $event : null)),
                            label: "批量语言后缀",
                            placeholder: "chi / eng / jpn",
                            variant: "outlined",
                            density: "comfortable",
                            "hide-details": "",
                            onKeyup: _withKeys(_unref(applyBatchLanguageSuffix), ["enter"])
                          }, null, 8, ["modelValue", "onKeyup"]),
                          _createVNode(_component_VBtn, {
                            variant: "tonal",
                            color: "primary",
                            disabled: !_unref(batchLanguageSuffix).trim(),
                            onClick: _unref(applyBatchLanguageSuffix)
                          }, {
                            default: _withCtx(() => [...(_cache[84] || (_cache[84] = [
                              _createTextVNode(" 应用到全部 ", -1)
                            ]))]),
                            _: 1
                          }, 8, ["disabled", "onClick"])
                        ])
                      ]),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(preview).items, (item) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: item.upload_id,
                          class: _normalizeClass(["preview-row", { disabled: item.selected === false }])
                        }, [
                          _createVNode(_component_VCheckbox, {
                            "model-value": item.selected !== false,
                            density: "compact",
                            "hide-details": "",
                            "onUpdate:modelValue": value => _unref(togglePreviewItem)(item.upload_id, value)
                          }, null, 8, ["model-value", "onUpdate:modelValue"]),
                          _createElementVNode("div", _hoisted_110, [
                            _createElementVNode("strong", null, _toDisplayString(item.source_name), 1),
                            _createElementVNode("span", null, _toDisplayString(item.archive_name ? `来自 ${item.archive_name} · ` : '') + _toDisplayString(item.detected_label || '未知语言'), 1)
                          ]),
                          _createVNode(_component_VSelect, {
                            "model-value": item.target_id,
                            items: _unref(targetSelectItems),
                            label: "对应集数",
                            variant: "outlined",
                            density: "comfortable",
                            "hide-details": "",
                            disabled: item.selected === false,
                            "onUpdate:modelValue": value => _unref(updatePreviewTarget)(item.upload_id, value)
                          }, null, 8, ["model-value", "items", "disabled", "onUpdate:modelValue"]),
                          _createVNode(_component_VTextField, {
                            "model-value": item.language_suffix,
                            label: "语言后缀",
                            variant: "outlined",
                            density: "comfortable",
                            "hide-details": "",
                            disabled: item.selected === false,
                            "onUpdate:modelValue": value => _unref(updateLanguageSuffix)(item.upload_id, value)
                          }, null, 8, ["model-value", "disabled", "onUpdate:modelValue"]),
                          _createElementVNode("div", _hoisted_111, [
                            _cache[86] || (_cache[86] = _createElementVNode("span", null, "改名为", -1)),
                            _createElementVNode("strong", null, _toDisplayString(item.output_name || _unref(buildOutputName)(_unref(uploadTargets).find(target => target.id === item.target_id), item) || '待选择目标'), 1)
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
      modelValue: _unref(rarHelpDialog),
      "onUpdate:modelValue": _cache[36] || (_cache[36] = $event => (_isRef(rarHelpDialog) ? (rarHelpDialog).value = $event : null)),
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
                _cache[87] || (_cache[87] = _createElementVNode("span", null, "RAR 解压器说明", -1)),
                _createVNode(_component_VBtn, {
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[35] || (_cache[35] = $event => (rarHelpDialog.value = false))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _cache[88] || (_cache[88] = _createElementVNode("div", { class: "rar-help-summary" }, [
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
                _createElementVNode("div", _hoisted_112, [
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(rarHelpItems, (item) => {
                    return _createElementVNode("section", {
                      key: item.title,
                      class: "rar-help-row"
                    }, [
                      _createElementVNode("div", _hoisted_113, [
                        _createElementVNode("div", _hoisted_114, [
                          _createElementVNode("span", _hoisted_115, _toDisplayString(item.badge), 1),
                          _createElementVNode("strong", null, _toDisplayString(item.title), 1)
                        ]),
                        _createElementVNode("button", {
                          type: "button",
                          class: "rar-help-copy",
                          onClick: $event => (_unref(copyHelpText)(item.command, item.copyLabel))
                        }, _toDisplayString(item.button), 9, _hoisted_116)
                      ]),
                      _createElementVNode("p", null, _toDisplayString(item.description), 1),
                      _createElementVNode("div", _hoisted_117, [
                        _createElementVNode("pre", null, _toDisplayString(item.command), 1)
                      ])
                    ])
                  }), 64))
                ]),
                (_unref(copyMessage))
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      class: "mt-4",
                      type: "success",
                      variant: "tonal",
                      text: _unref(copyMessage)
                    }, null, 8, ["text"]))
                  : (_unref(copyError))
                    ? (_openBlock(), _createBlock(_component_VAlert, {
                        key: 1,
                        class: "mt-4",
                        type: "warning",
                        variant: "tonal",
                        text: _unref(copyError)
                      }, null, 8, ["text"]))
                    : _createCommentVNode("", true),
                (_unref(rarDependencyStatus).message)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 2,
                      class: "mt-4",
                      type: _unref(rarDependencyStatus).state === 'ready' ? 'success' : 'warning',
                      variant: "tonal",
                      text: _unref(rarDependencyStatus).message
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
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-9a18668c"]]);

export { AppPage as default };
