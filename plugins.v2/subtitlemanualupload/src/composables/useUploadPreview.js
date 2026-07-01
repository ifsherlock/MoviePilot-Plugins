import { computed, ref } from 'vue'

export function useUploadPreview({
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
  const preparing = ref(false)
  const applying = ref(false)
  const dragging = ref(false)
  const uploadDialog = ref(false)
  const uploadTitle = ref('')
  const uploadScopeTargets = ref([])
  const files = ref([])
  const preview = ref(null)
  const fileInputRef = ref(null)
  const fixTimeline = ref(false)
  const batchLanguageSuffix = ref('')
  const lastWritten = ref([])

  const uploadTargets = computed(() => uploadScopeTargets.value.filter(item => !isLocked(item.id) && item.writable !== false))
  const batchUploadTargets = computed(() => {
    const base = selectedTargets.value.length ? selectedTargets.value : visibleTargets.value
    return base.filter(item => !isLocked(item.id) && item.writable !== false)
  })
  const targetSelectItems = computed(() => uploadTargets.value.map(target => ({
    title: compactTargetName(target),
    value: target.id,
  })))
  const canPrepare = computed(() => uploadTargets.value.length > 0 && files.value.length > 0)
  const canApply = computed(() => {
    const items = selectedPreviewItems.value
    return items.length > 0 && items.every(item => item.target_id)
  })
  const hasPreviewItems = computed(() => (preview.value?.items || []).length > 0)
  const selectedPreviewItems = computed(() => (preview.value?.items || []).filter(item => item.selected !== false))
  const selectedPreviewTargets = computed(() => {
    const targetMap = new Map(uploadTargets.value.map(target => [target.id, target]))
    return selectedPreviewItems.value
      .map(item => targetMap.get(item.target_id))
      .filter(Boolean)
  })
  const allSelectedPreviewTargetsAreStream = computed(() => {
    const items = selectedPreviewTargets.value
    return items.length > 0 && items.every(isStreamTarget)
  })
  const hasSelectedPreviewStreamTargets = computed(() => selectedPreviewTargets.value.some(isStreamTarget))
  const timelineEnabledForApply = computed(() => fixTimeline.value && timelineAvailable.value && !allSelectedPreviewTargetsAreStream.value)

  function clearUploadPreviewState() {
    preview.value = null
    lastWritten.value = []
  }

  function clearUploadDialogState() {
    files.value = []
    preview.value = null
    batchLanguageSuffix.value = ''
  }

  function normalizePreviewItems() {
    if (!preview.value?.items) return
    const preferSingleCandidate = preview.value.source === 'online' && preview.value.items.length > 1
    preview.value.items.forEach((item, index) => {
      const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
      item.output_name = item.output_name || buildOutputName(target, item)
      item.selected = item.selected !== false && (!preferSingleCandidate || index === 0)
    })
  }

  function openUploadDialog(scopeTargets, title) {
    const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false)
    if (!usableTargets.length) {
      error.value = '没有可上传的目标：选中的集数可能都已锁定'
      return false
    }
    uploadScopeTargets.value = usableTargets
    uploadTitle.value = title
    if (usableTargets.every(isStreamTarget)) {
      fixTimeline.value = false
    }
    files.value = []
    preview.value = null
    batchLanguageSuffix.value = ''
    lastWritten.value = []
    error.value = ''
    message.value = ''
    uploadDialog.value = true
    return true
  }

  function openBatchUpload() {
    const title = selectedTargets.value.length
      ? `批量上传选中 ${batchUploadTargets.value.length} 集`
      : `批量上传 ${selectedSeason.value === 'all' ? '全部季' : seasonLabel(selectedSeason.value)}`
    openUploadDialog(batchUploadTargets.value, title)
  }

  function openSingleUpload(target) {
    openUploadDialog([target], `上传 ${compactTargetName(target)}`)
  }

  function prepareOnlineUploadState(scopeTargets, title) {
    uploadScopeTargets.value = scopeTargets
    uploadTitle.value = `${title} · 在线字幕`
    lastWritten.value = []
    preview.value = null
    files.value = []
  }

  function openOnlinePreview(data, responseMessage) {
    preview.value = data
    batchLanguageSuffix.value = ''
    normalizePreviewItems()
    uploadDialog.value = true
    message.value = responseMessage || '已下载在线字幕并生成匹配预览'
  }

  async function onPickFiles(event) {
    const pickedFiles = Array.from(event?.target?.files || [])
    mergeFiles(pickedFiles)
    if (fileInputRef.value) {
      fileInputRef.value.value = ''
    }
    await prepareUploadAfterFiles(pickedFiles)
  }

  function mergeFiles(inputFiles) {
    const existing = new Map(files.value.map(item => [`${item.name}-${item.size}`, item]))
    for (const file of inputFiles) {
      const key = `${file.name}-${file.size}`
      if (!existing.has(key)) {
        existing.set(key, file)
      }
    }
    files.value = Array.from(existing.values())
    lastWritten.value = []
  }

  function removeFile(file) {
    files.value = files.value.filter(item => !(item.name === file.name && item.size === file.size))
  }

  function openFileDialog() {
    fileInputRef.value?.click()
  }

  async function handleDrop(event) {
    event.preventDefault()
    dragging.value = false
    const dropped = Array.from(event.dataTransfer?.files || [])
    mergeFiles(dropped)
    await prepareUploadAfterFiles(dropped)
  }

  function handleDragOver(event) {
    event.preventDefault()
    dragging.value = true
  }

  function handleDragLeave(event) {
    event.preventDefault()
    dragging.value = false
  }

  async function prepareUpload() {
    if (!canPrepare.value || preparing.value) return
    preparing.value = true
    error.value = ''
    try {
      const targetIds = uploadTargets.value.map(item => item.id)
      const formData = new FormData()
      formData.append('target_ids', JSON.stringify(targetIds))
      files.value.forEach(file => {
        formData.append('files', file)
      })
      const response = await pluginApi.value.prepareUpload(formData)
      preview.value = unwrapResponse(response)
      batchLanguageSuffix.value = ''
      normalizePreviewItems()
      message.value = response?.message || '已生成匹配预览'
    } catch (err) {
      error.value = errorMessage(err, '上传预解析失败')
    } finally {
      preparing.value = false
    }
  }

  async function prepareUploadAfterFiles(inputFiles) {
    if (!inputFiles.length || hasPreviewItems.value || !canPrepare.value) return
    await prepareUpload()
  }

  function updatePreviewTarget(uploadId, targetId) {
    const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId)
    if (!item) return
    const target = uploadTargets.value.find(targetItem => targetItem.id === targetId)
    item.target_id = targetId
    item.output_name = buildOutputName(target, item)
  }

  function updateLanguageSuffix(uploadId, value) {
    const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId)
    if (!item) return
    item.language_suffix = String(value || '').trim() || 'und'
    const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
    item.output_name = buildOutputName(target, item)
  }

  function togglePreviewItem(uploadId, checked) {
    const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId)
    if (!item) return
    item.selected = Boolean(checked)
  }

  function applyBatchLanguageSuffix() {
    const suffix = batchLanguageSuffix.value.trim()
    if (!suffix || !preview.value?.items?.length) return
    selectedPreviewItems.value.forEach(item => {
      item.language_suffix = suffix
      const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
      item.output_name = buildOutputName(target, item)
    })
  }

  function resetUploadPreview() {
    files.value = []
    preview.value = null
    batchLanguageSuffix.value = ''
    lastWritten.value = []
    error.value = ''
    message.value = ''
  }

  async function applyUpload() {
    if (!canApply.value || !preview.value) return
    const allowRiskyOffset = timelineEnabledForApply.value && timelineNeedsRiskyConfirm.value
    if (allowRiskyOffset && !confirmRiskyTimelineOffset('写入字幕智能调轴')) return
    applying.value = true
    error.value = ''
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
      }
      const response = await pluginApi.value.applyUpload(payload)
      const data = unwrapResponse(response) || {}
      const written = data.written || []
      const successMessage = response?.message || `已写入 ${data.count || 0} 个字幕文件`
      files.value = []
      preview.value = null
      uploadDialog.value = false
      await loadTargets(selectedMedia.value, selectedSeason.value)
      message.value = successMessage
      lastWritten.value = written
    } catch (err) {
      error.value = errorMessage(err, '写入字幕失败')
    } finally {
      applying.value = false
    }
  }

  return {
    preparing,
    applying,
    dragging,
    uploadDialog,
    uploadTitle,
    uploadScopeTargets,
    files,
    preview,
    fileInputRef,
    fixTimeline,
    batchLanguageSuffix,
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
    applyUpload,
  }
}
