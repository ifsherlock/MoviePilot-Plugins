import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

const require = createRequire(new URL('../plugins.v2/subtitlemanualupload/package.json', import.meta.url))
const { ref } = require('vue')

for (const version of ['plugins.v2', 'plugins.v3']) {
  const { useUploadPreview } = await import(new URL(`../${version}/subtitlemanualupload/src/composables/useUploadPreview.js`, import.meta.url))
  const targets = [{ id: 'one', basename: 'Episode.01' }, { id: 'two', basename: 'Episode.02' }]
  let submitted
  const state = useUploadPreview({
    pluginApi: ref({ applyUpload: async payload => {
      submitted = payload
      return { data: { count: payload.items.length, written: [] } }
    } }),
    unwrapResponse: response => response.data,
    errorMessage: error => error.message,
    error: ref(''),
    message: ref(''),
    selectedTargets: ref(targets),
    visibleTargets: ref(targets),
    selectedMedia: ref({}),
    selectedSeason: ref(1),
    isLocked: () => false,
    lockedTargetPayload: () => [],
    loadTargets: async () => {},
    timelineAvailable: ref(true),
    timelineNeedsRiskyConfirm: ref(false),
    confirmRiskyTimelineOffset: () => true,
    isStreamTarget: () => false,
    compactTargetName: target => target.basename,
    seasonLabel: String,
    buildOutputName: (target, item) => `${target.basename}.${item.language_suffix}${item.ext}`,
  })
  state.openUploadDialog(targets, 'Upload')
  state.preview.value = {
    session_id: 'sup-session',
    items: [
      { upload_id: 'sup-one', target_id: 'one', ext: '.sup', language_suffix: 'und', selected: true },
      { upload_id: 'sup-two', target_id: 'two', ext: '.sup', language_suffix: 'und', selected: false },
    ],
  }
  state.batchLanguageSuffix.value = 'und'
  state.applyBatchLanguageSuffix('chi&eng')
  assert.equal(state.preview.value.items[0].output_name, 'Episode.01.chi&eng.sup')
  assert.equal(state.preview.value.items[0].language_suffix, 'chi&eng')
  assert.equal(state.preview.value.items[1].language_suffix, 'und')

  state.applyBatchLanguageSuffix('')
  assert.equal(state.preview.value.items[0].language_suffix, 'chi&eng')
  state.updateLanguageSuffix('sup-one', 'chi')
  await state.applyUpload()
  assert.equal(submitted.items.length, 1)
  assert.equal(submitted.items[0].language_suffix, 'chi')
  assert.equal(submitted.items[0].ext, '.sup')
  assert.equal(submitted.session_id, 'sup-session')
}
console.log('V2/V3 upload preview suffix and submission checks passed')
