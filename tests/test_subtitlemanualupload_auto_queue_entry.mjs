import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const require = createRequire(new URL('../plugins.v3/subtitlemanualupload/package.json', import.meta.url))
const { createServer } = require('vite')
const vuePlugin = require('@vitejs/plugin-vue')
const { createSSRApp, h, ref } = require('vue')
const { renderToString } = require('vue/server-renderer')
const root = fileURLToPath(new URL('../plugins.v3/subtitlemanualupload', import.meta.url))
const server = await createServer({
  root,
  configFile: false,
  plugins: [vuePlugin()],
  server: { middlewareMode: true },
  appType: 'custom',
})

try {
  for (const variant of ['plugins.v2', 'plugins.v3']) {
    const base = fileURLToPath(new URL(`../${variant}/subtitlemanualupload/src`, import.meta.url))
    const { default: SearchPanel } = await server.ssrLoadModule(`${base}/components/MediaSearchPanel.vue`)
    const { useAutoTransferQueue } = await server.ssrLoadModule(`${base}/composables/useAutoTransferQueue.js`)
    const queue = useAutoTransferQueue({ pluginApi: ref({}), error: ref(''), message: ref('') })
    for (const [summary, expected] of [
      [{}, '暂无自动入库任务'],
      [{ pending: 2 }, '2 个排队'],
      [{ completed: 3 }, '3 个完成'],
      [{ failed: 1 }, '1 个失败'],
    ]) {
      queue.applyAutoTransferSummary(summary)
      const app = createSSRApp(SearchPanel, {
        rootTab: 'match',
        matchHistorySummary: '',
        indexSummary: '',
        autoQueueSummaryText: queue.autoQueueSummaryText.value,
      })
      // Render the real plugin component; only third-party display controls are stubbed.
      for (const [name, tag] of Object.entries({
        VCard: 'section', VCardText: 'div', VBtn: 'button', VTextField: 'input', VSelect: 'select',
      })) {
        app.component(name, { setup: (_, { slots }) => () => h(tag, null, slots.default?.()) })
      }
      const html = await renderToString(app)
      const buttons = [...html.matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/g)].map(match => match[1])
      assert.ok(buttons.some(text => text.includes(`自动入库队列 · ${expected}`)), `${variant}: ${expected}`)
    }
    console.log(`${variant}: queue entry rendered for empty, pending, completed and failed states`)
  }
} finally {
  await server.close()
}
