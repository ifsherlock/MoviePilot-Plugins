import { unwrapResponse } from '../utils/formatters'

function resolvePluginBase(pluginBase) {
  const raw = typeof pluginBase === 'function' ? pluginBase() : (pluginBase?.value ?? pluginBase)
  return raw || 'plugin/SubtitleManualUpload'
}

export function createSubtitleManualUploadApi(api, pluginBase) {
  const get = endpoint => api.get(`${resolvePluginBase(pluginBase)}${endpoint}`)
  const post = (endpoint, payload) => api.post(`${resolvePluginBase(pluginBase)}${endpoint}`, payload)

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
