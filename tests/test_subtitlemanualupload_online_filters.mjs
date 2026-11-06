import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const require = createRequire(new URL('../plugins.v3/subtitlemanualupload/package.json', import.meta.url))
const { createServer } = require('vite')
const root = fileURLToPath(new URL('..', import.meta.url))
const server = await createServer({ root, configFile: false, server: { middlewareMode: true }, appType: 'custom' })
try {
  for (const version of ['plugins.v2', 'plugins.v3']) {
    const { useOnlineSubtitles } = await server.ssrLoadModule(`/${version}/subtitlemanualupload/src/composables/useOnlineSubtitles.js`)
    const { onlineResultLanguageFilterCategory } = await server.ssrLoadModule(`/${version}/subtitlemanualupload/src/utils/onlineResult.js`)
    const ref = value => ({ value })
    const state = useOnlineSubtitles({
      pluginApi: ref({ onlineStatus: async () => ({ enabled_providers: ['subhd', 'subdl'] }),
        onlineManualLinks: async () => ({ links: [] }), onlineSearchProvider: async () => ({ results: [] }) }),
      unwrapResponse: response => response, errorMessage: error => error.message,
      error: ref(''), message: ref(''), selectedMedia: ref({}), selectedTargets: ref([]),
      selectedSeason: ref('all'), batchUploadTargets: ref([]), isLocked: () => false,
      lockedTargetPayload: () => [], compactTargetName: () => 'Sample', aiAvailable: ref(false),
    })
    const result = (result_id, language_bucket, provider = 'subhd') => ({ result_id, provider, language_bucket, title: `Sample ${result_id}` })
    state.onlineResults.value = [result('pair-en', 'chi&eng'), result('pair-jp', 'chi&jp'),
      result('pair-kr', 'chi&kr'), result('pair-other', 'other_bilingual'), result('zh', 'chi'),
      result('traditional', 'cht'), result('en', 'eng'), result('jp', 'jpn'), result('kr', 'kor'),
      result('other', 'other'), result('unknown', 'und'), result('dl-en', 'chi&eng', 'subdl'),
      result('dl-zh', 'chi', 'subdl')]
    const ids = () => state.filteredOnlineResults.value.map(item => item.result_id)
    const title = (items, value) => items.value.find(item => item.value === value)?.title
    state.onlineLanguageFilter.value = 'chi&eng'
    assert.deepEqual(ids(), ['pair-en', 'dl-en'])
    assert.equal(title(state.onlineProviderFilterItems, 'subhd'), 'SubHD 1')
    assert.equal(title(state.onlineProviderFilterItems, 'subdl'), 'SubDL 1')
    state.onlineProviderFilter.value = 'subdl'
    assert.deepEqual(ids(), ['dl-en'])
    assert.equal(title(state.onlineLanguageFilterItems, 'all'), '全部 2')
    assert.equal(title(state.onlineLanguageFilterItems, 'chi&eng'), '中英 1')
    assert.equal(title(state.onlineLanguageFilterItems, 'chinese'), '中文 1')
    state.onlineLanguageFilter.value = 'english'
    assert.deepEqual(ids(), [])
    state.onlineProviderFilter.value = 'all'
    assert.deepEqual(ids(), ['en'])
    state.onlineLanguageFilter.value = 'chinese'
    assert.deepEqual(ids(), ['zh', 'traditional', 'dl-zh'])
    state.onlineLanguageFilter.value = 'korean'
    assert.deepEqual(ids(), ['kr'])
    state.onlineLanguageFilter.value = 'und'
    assert.deepEqual(ids(), ['unknown'])
    assert.equal(onlineResultLanguageFilterCategory({ title: '中英双语', language_category: 'chinese' }), 'und')
    state.onlineLanguageFilter.value = 'all'
    assert.equal(ids().length, 13)
    state.onlineProviderFilter.value = 'subdl'
    assert.equal(ids().length, 2)
    console.log(`${version}: precise language filters, intersection, counts and reset passed`)
  }
} finally {
  await server.close()
}
