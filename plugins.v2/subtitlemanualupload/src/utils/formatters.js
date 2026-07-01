export function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'data') && response.success !== undefined) {
    return response.data
  }
  return response?.data ?? response
}

export function mediaLabel(media) {
  if (!media) return ''
  return media.year ? `${media.title} (${media.year})` : `${media.title || ''}`
}

export function targetLabel(target) {
  return target?.label || target?.target_label || ''
}

export function formatMediaType(type) {
  return type === 'tv' ? '剧集' : '电影'
}

export function rarDependencyModeLabel(mode) {
  if (mode === 'container_install') return '容器内自动安装'
  if (mode === 'mapped_binary') return '宿主机映射文件'
  return '仅检测'
}

export function seasonLabel(season) {
  const value = Number(season || 0)
  return value === 0 ? '特别篇' : `第 ${value} 季`
}

export function compactTargetName(target) {
  if (!target) return ''
  if (target.media_type !== 'tv') return target.basename || targetLabel(target)
  const season = Number(target.season || 0)
  const episode = Number(target.episode || 0)
  if (season && episode) {
    return `S${String(season).padStart(2, '0')}E${String(episode).padStart(2, '0')} · ${target.basename || targetLabel(target)}`
  }
  return target.basename || targetLabel(target)
}

export function mediaStat(media) {
  const count = Number(media?.local_count || 0)
  if (media?.media_type === 'tv') {
    const seasonCount = Number(media?.season_count || 0)
    return `${seasonCount || '-'} 季 · ${count} 集本地资源`
  }
  return `${count || 1} 个本地资源`
}

export function historyMediaStat(item) {
  const subtitleCount = Number(item?.subtitle_count || 0)
  const targetCount = Number(item?.target_count || 0)
  if (item?.media_type === 'tv') return `${targetCount} 集 · ${subtitleCount} 个外挂字幕`
  return `${subtitleCount} 个外挂字幕`
}

export function formatBytes(value) {
  const size = Number(value || 0)
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size >= 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${size} B`
}

export function formatOffset(value) {
  const number = Number(value || 0)
  return `${number >= 0 ? '+' : ''}${number.toFixed(3)}s`
}

export function timelineBaseText(base) {
  const value = String(base || '')
  if (value.startsWith('embedded:')) return '内嵌字幕基准'
  if (value === 'audio:rms' || value === 'audio:rms:cache') return 'RMS 音频检测（低精度）'
  if (value === 'audio:webrtc' || value === 'audio:webrtc:cache') return 'WebRTC 音频检测'
  if (value.startsWith('audio:')) return '音频基准'
  return value || '未知基准'
}

export function timelineConfidenceText(value) {
  const known = {
    high: '高可信',
    medium: '中可信',
    low: '低可信',
    rejected: '已拒绝',
  }
  return known[value] || value || '未知可信度'
}

export function timelineRiskText(value) {
  const known = {
    offset_over_120s: '偏移超过 120s',
    offset_over_configured_max: '超过配置最大偏移',
    low_score: '匹配分数过低',
    weak_score_margin: '最佳与次优差距过小',
    unstable_subtitle_activity: '字幕活动区间异常',
    unusual_scale_factor: '帧率比例异常',
  }
  return known[value] || value
}

export function timelineResultText(item) {
  const timeline = item?.timeline || {}
  if (!timeline.enabled) return '未启用智能调轴'
  const base = timelineBaseText(timeline.base)
  if (timeline.applied) {
    return `已调轴 ${formatOffset(timeline.offset_seconds)} · ${base}`
  }
  return `未调整：偏移 ${formatOffset(timeline.offset_seconds)} 小于阈值 · ${base}`
}

export function timelineMetaItems(item) {
  const timeline = item?.timeline || item || {}
  if (!timeline.enabled) return []
  const items = []
  if (timeline.confidence) items.push(`置信度：${timelineConfidenceText(timeline.confidence)}`)
  if (timeline.score_margin !== undefined) items.push(`差距：${Number(timeline.score_margin || 0).toFixed(3)}`)
  if (timeline.active_ratio !== undefined) items.push(`活动：${(Number(timeline.active_ratio || 0) * 100).toFixed(1)}%`)
  ;(timeline.risk_flags || []).forEach(flag => items.push(timelineRiskText(flag)))
  return items
}

export function readableErrorDetail(value) {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    return value
      .map(item => readableErrorDetail(item))
      .filter(Boolean)
      .join('；')
  }
  if (typeof value === 'object') {
    const direct = value.message || value.msg || value.detail || value.reason || value.error
    if (direct) return readableErrorDetail(direct)
    const parts = []
    if (Array.isArray(value.loc) && value.loc.length) parts.push(value.loc.join('.'))
    if (value.type) parts.push(value.type)
    if (parts.length) return parts.join('：')
    try {
      return JSON.stringify(value, null, 0)
    } catch (_) {
      return String(value)
    }
  }
  return String(value)
}

export function errorMessage(err, fallback) {
  return readableErrorDetail(
    err?.response?.data?.detail
    || err?.response?.data?.message
    || err?.data?.detail
    || err?.data?.message
    || err?.message
    || fallback
  )
}

export function buildOutputName(target, item) {
  if (!target) return ''
  const basename = target.basename || 'subtitle'
  const suffix = item?.language_suffix || 'und'
  let ext = item?.ext || '.srt'
  if (!ext.startsWith('.')) ext = `.${ext}`
  return `${basename}.${suffix}${ext.toLowerCase()}`
}
