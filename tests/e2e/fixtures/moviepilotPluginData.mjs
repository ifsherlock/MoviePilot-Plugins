const longBase = 'The.Longest.Mobile.Layout.Regression.Title.2026.S01E'

export const subtitleMedia = {
  id: 'tv-long-layout-2026',
  media_type: 'tv',
  title: '移动端布局回归测试剧集：特别长的中文标题和 English Alias',
  year: 2026,
  tmdb_id: 20260707,
  season_count: 2,
  local_count: 50,
  poster_url: '',
}

export const subtitleTargets = Array.from({ length: 50 }, (_, index) => {
  const episode = index + 1
  const id = `target-s01e${String(episode).padStart(2, '0')}`
  const basename = `${longBase}${String(episode).padStart(2, '0')}.2160p.WEB-DL.Atmos.Very.Long.Release.Group`
  return {
    id,
    media_type: 'tv',
    season: 1,
    episode,
    label: `S01E${String(episode).padStart(2, '0')}`,
    basename,
    relative_path: `/media/TV/移动端布局回归测试剧集/Season 01/${basename}.mkv`,
    path: `/mnt/media/TV/移动端布局回归测试剧集/Season 01/${basename}.mkv`,
    size: 3_221_225_472,
    writable: episode !== 7,
    has_subtitle: episode <= 4,
    subtitle_count: episode <= 4 ? 2 : 0,
    subtitles: episode <= 4 ? [
      {
        name: `${basename}.chi.srt`,
        path: `/media/TV/移动端布局回归测试剧集/Season 01/${basename}.chi.srt`,
        size: 45_218,
        modified_at: '2026-07-07 02:20:00',
        backup_available: true,
      },
      {
        name: `${basename}.eng.ass`,
        path: `/media/TV/移动端布局回归测试剧集/Season 01/${basename}.eng.ass`,
        size: 68_312,
        modified_at: '2026-07-07 02:21:00',
        backup_available: false,
      },
    ] : [],
    timeline_task: episode === 1 ? {
      status: 'completed',
      timeline: {
        enabled: true,
        applied: true,
        offset_seconds: 1.234,
        base: 'audio:webrtc',
        confidence: 'high',
        score_margin: 0.42,
        active_ratio: 0.38,
        risk_flags: [],
      },
    } : null,
  }
})

export const subtitleHistory = {
  page: 1,
  page_size: 20,
  total: 1,
  has_more: false,
  items: [
    {
      ...subtitleMedia,
      id: 'history-tv-long-layout-2026',
      latest_at: '2026-07-07 02:30:00',
      target_count: 8,
      subtitle_count: 12,
      targets: subtitleTargets.slice(0, 8),
    },
  ],
}

export const autoTransferQueue = {
  summary: {
    total: 4,
    active: 2,
    pending: 1,
    in_progress: 1,
    completed: 1,
    skipped: 0,
    failed: 1,
  },
  rate_limits: {
    subhd: '12 秒/次',
    opensubtitles: '20 秒/次',
  },
  tasks: [
    {
      id: 'queue-1',
      title: '移动端布局回归测试剧集 S01E01',
      provider: 'opensubtitles',
      status: 'in_progress',
      message: '正在搜索英文字幕并准备提交 AI 翻译',
      created_at: '2026-07-07 02:28:00',
    },
    {
      id: 'queue-2',
      title: '移动端布局回归测试剧集 S01E02',
      provider: 'subhd',
      status: 'pending',
      message: '等待限流窗口',
      created_at: '2026-07-07 02:29:00',
    },
  ],
}

export const subtitleStatus = {
  enabled: true,
  source: 'MoviePilot 本地整理记录',
  index: {
    ready: true,
    updated_at: '2026-07-07 02:26:00',
    entry_count: 50,
    media_count: 1,
    expires_in: 3600,
  },
  archive_support: {
    zip: true,
    rar: true,
    rar_tool: 'unar',
    rar_tool_path: '/usr/bin/unar',
    rar_python: true,
    dependency_mode: 'container_install',
    dependency_status: { state: 'ready' },
  },
  timeline_fixer: {
    available: true,
    ffmpeg: true,
    ffprobe: true,
    modules: { numpy: true, pysubs2: true, webrtcvad: true },
    configured_max_offset_seconds: 120,
  },
  ai_subtitle: {
    enabled: true,
    installed: true,
    available: true,
    running: true,
    queue_ready: true,
    plugin_name: 'AI字幕生成(联动版)',
    plugin_version: '3.5.57',
    message: '可提交 AI 字幕生成任务',
    counts: { pending: 1, in_progress: 1, completed: 2, failed: 1 },
    updated_at: '2026-07-07 02:31:00',
  },
  auto_transfer_queue: autoTransferQueue.summary,
}

export const onlineResults = [
  {
    provider: 'opensubtitles',
    result_id: 'os-en-1',
    title: 'Mobile Layout Regression S01E01 English SDH',
    language: 'English',
    language_category: 'english',
    format: 'srt',
    season: 1,
    episode: 1,
    score: 98,
    downloadable: true,
    page_url: 'https://example.invalid/opensubtitles/os-en-1',
    note: '用于移动端在线字幕结果卡片长文本测试',
    match_detail: 'TMDB + S/E 强匹配',
    identity_status: 'strong',
  },
  {
    provider: 'subhd',
    result_id: 'subhd-zh-1',
    title: '移动端布局回归测试剧集 S01E01 简体中文',
    language: '简体中文',
    language_category: 'chinese',
    format: 'ass',
    season: 1,
    episode: 1,
    score: 91,
    downloadable: true,
    page_url: 'https://example.invalid/subhd/subhd-zh-1',
    note: '中文结果',
    match_detail: '标题 + 季集匹配',
    identity_status: 'weak',
  },
]

export const onlineManualLinks = {
  links: [
    {
      provider: 'subhd',
      name: 'SubHD',
      links: [
        { keyword: '移动端布局回归测试剧集 S01E01', url: 'https://example.invalid/subhd?q=mobile' },
      ],
    },
    {
      provider: 'opensubtitles',
      name: 'OpenSubtitles',
      links: [
        { keyword: 'Mobile Layout Regression S01E01', url: 'https://example.invalid/os?q=mobile' },
      ],
    },
  ],
}

export const uploadPreview = {
  source: 'upload',
  items: [
    {
      upload_id: 'upload-preview-1',
      source_name: 'The.Longest.Mobile.Layout.Regression.Title.2026.S01E01.English.SDH.Very.Long.Subtitle.File.Name.srt',
      archive_name: 'Mobile.Layout.Regression.Subtitle.Pack.With.A.Long.Name.zip',
      detected_label: 'English · SRT',
      target_id: 'target-s01e01',
      language_suffix: 'eng',
      output_name: `${subtitleTargets[0].basename}.eng.srt`,
      selected: true,
    },
    {
      upload_id: 'upload-preview-2',
      source_name: 'The.Longest.Mobile.Layout.Regression.Title.2026.S01E02.Japanese.Commentary.ass',
      archive_name: 'Mobile.Layout.Regression.Subtitle.Pack.With.A.Long.Name.zip',
      detected_label: 'Japanese · ASS',
      target_id: 'target-s01e02',
      language_suffix: 'jpn',
      output_name: `${subtitleTargets[1].basename}.jpn.ass`,
      selected: true,
    },
  ],
}

export const aiTasks = {
  status: subtitleStatus.ai_subtitle,
  summary: { pending: 1, in_progress: 1, completed: 2, failed: 1 },
  tasks: [
    {
      task_id: 'ai-task-1',
      target_id: 'target-s01e01',
      target_label: 'S01E01 · 移动端布局回归测试',
      video_name: '移动端布局回归测试剧集 S01E01',
      video_file: subtitleTargets[0].path,
      status: 'in_progress',
      status_label: '生成中',
      active: true,
      source: 'asr',
      source_label: '音轨 ASR',
      source_policy_label: '自动选择',
      output_name: `${subtitleTargets[0].basename}.ai.zh.srt`,
      add_time: '2026-07-07 02:20:00',
      message: 'Whisper 识别中',
    },
    {
      task_id: 'ai-task-2',
      target_id: 'target-s01e02',
      target_label: 'S01E02 · 超长路径测试',
      video_name: '移动端布局回归测试剧集 S01E02',
      video_file: subtitleTargets[1].path,
      status: 'failed',
      status_label: '失败',
      active: false,
      source: 'matched_external',
      source_label: '外挂字幕',
      source_asset_name: `${subtitleTargets[1].basename}.eng.ass`,
      output_name: `${subtitleTargets[1].basename}.ai.zh.srt`,
      add_time: '2026-07-07 02:10:00',
      complete_time: '2026-07-07 02:12:00',
      message: '测试用失败信息：模型返回内容格式不完整',
    },
  ],
}

export const autoSubTasks = {
  status: {
    available: true,
    message: '队列运行中',
    counts: { pending: 2, in_progress: 1, completed: 2, failed: 1, cancelled: 1 },
  },
  tasks: [
    ...aiTasks.tasks,
    {
      task_id: 'autosub-completed-1',
      video_name: '桌面回归验证电影',
      video_file: '/mnt/media/Movies/Desktop Regression Movie 2026/Desktop.Regression.Movie.2026.2160p.mkv',
      status: 'completed',
      status_label: '完成',
      active: false,
      source: 'embedded',
      source_label: '视频内嵌字幕',
      resolved_source_label: '视频内嵌字幕',
      output_name: 'Desktop.Regression.Movie.2026.ai.zh.srt',
      add_time: '2026-07-07 01:50:00',
      complete_time: '2026-07-07 01:58:00',
      message: '已输出中文字幕',
    },
  ],
}

export function subtitleSearchPayload() {
  return {
    page: 1,
    page_size: 24,
    total: 1,
    has_more: false,
    medias: [subtitleMedia],
  }
}

export function subtitleTargetsPayload() {
  return {
    media: subtitleMedia,
    seasons: [
      { value: 'all', title: '全部', subtitle: '50 集' },
      { value: 1, title: '第 1 季', subtitle: '50 集' },
    ],
    selected_season: 'all',
    targets: subtitleTargets,
  }
}
