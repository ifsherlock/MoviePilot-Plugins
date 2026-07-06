import { expect } from '@playwright/test'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  aiTasks,
  autoSubTasks,
  autoTransferQueue,
  onlineManualLinks,
  onlineResults,
  subtitleHistory,
  subtitleSearchPayload,
  subtitleStatus,
  subtitleTargetsPayload,
  uploadPreview,
} from '../fixtures/moviepilotPluginData.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../../..')
export const moviePilotFrontendPath = '/home/jaysherlock/文档/MoviePilot-Frontend'

export const pluginRemoteEntries = {
  SubtitleManualUpload: path.join(repoRoot, 'plugins.v2/subtitlemanualupload/dist/assets/remoteEntry.js'),
  AutoSubv3: path.join(repoRoot, 'plugins.v2/autosubv3/dist/assets/remoteEntry.js'),
}

function assertRemoteEntriesExist() {
  for (const [id, remoteEntry] of Object.entries(pluginRemoteEntries)) {
    if (!existsSync(remoteEntry)) {
      throw new Error(`Missing remoteEntry for ${id}: ${remoteEntry}. Run the plugin build first.`)
    }
  }
}

function toServedPath(remoteEntry) {
  const relative = path.relative(repoRoot, remoteEntry).split(path.sep).join('/')
  return `/__plugin_dist__/${relative}`
}

function contentTypeFor(filePath) {
  if (filePath.endsWith('.js') || filePath.endsWith('.mjs')) return 'text/javascript; charset=utf-8'
  if (filePath.endsWith('.css')) return 'text/css; charset=utf-8'
  if (filePath.endsWith('.html')) return 'text/html; charset=utf-8'
  return 'application/octet-stream'
}

async function fulfillPluginDist(route, pathname) {
  const marker = '/__plugin_dist__/'
  const markerIndex = pathname.indexOf(marker)
  if (markerIndex < 0) return false
  const relative = decodeURIComponent(pathname.slice(markerIndex + marker.length))
  const filePath = path.join(repoRoot, relative)
  if (!filePath.startsWith(repoRoot)) {
    await route.abort()
    return true
  }
  await route.fulfill({
    path: filePath,
    contentType: contentTypeFor(filePath),
  })
  return true
}

function jsonResponse(payload) {
  return {
    contentType: 'application/json',
    body: JSON.stringify(payload),
  }
}

function hostApiFallback(pathname) {
  if (pathname === '/api/v1/system/ping') return { status: 'ok' }
  if (pathname === '/api/v1/system/global' || pathname === '/api/v1/system/global/user') {
    return {
      app_name: 'MoviePilot',
      version: '2.14.2',
      user: {
        super_user: true,
        permissions: [],
      },
    }
  }
  if (pathname === '/api/v1/plugin/sidebar_nav') return []
  if (pathname === '/api/v1/plugin/') return []
  if (pathname === '/api/v1/system/message') return []
  if (pathname.startsWith('/api/v1/user/config/')) return null
  if (pathname.startsWith('/api/v1/system/setting/')) return null
  if (pathname.startsWith('/api/v1/dashboard/')) return {}
  if (pathname.startsWith('/api/v1/transfer/queue')) return []
  if (pathname.startsWith('/api/v1/history/transfer')) return { list: [], total: 0 }
  if (pathname.startsWith('/api/v1/recommend/')) return []
  if (pathname.startsWith('/api/v1/site/')) return []
  if (pathname.startsWith('/api/v1/subscribe/')) return []
  if (pathname.startsWith('/api/v1/plugin/dashboard/meta')) return []
  return {}
}

function subtitleApiPayload(pathname) {
  if (pathname.endsWith('/status')) return subtitleStatus
  if (pathname.endsWith('/auto_transfer_queue')) return autoTransferQueue
  if (pathname.endsWith('/online_status')) {
    return {
      enabled_providers: ['subhd', 'opensubtitles'],
      assrt_api_configured: false,
      opensubtitles_api_configured: true,
      capabilities: { auto_search: true },
    }
  }
  if (pathname.endsWith('/search')) return subtitleSearchPayload()
  if (pathname.endsWith('/targets')) return subtitleTargetsPayload()
  if (pathname.endsWith('/match_history')) return subtitleHistory
  if (pathname.endsWith('/ai_tasks')) return aiTasks
  if (pathname.endsWith('/timeline_tasks')) return { tasks: [] }
  if (pathname.endsWith('/online_manual_links')) return onlineManualLinks
  if (pathname.endsWith('/online_search_provider')) {
    return {
      provider: 'opensubtitles',
      results: onlineResults,
      messages: [{ level: 'info', provider: 'opensubtitles', message: '测试数据已返回' }],
    }
  }
  if (pathname.endsWith('/prepare_upload')) return uploadPreview
  return { ok: true }
}

function autoSubApiPayload(pathname) {
  if (pathname.endsWith('/tasks')) return autoSubTasks
  if (pathname.endsWith('/cancel')) return { message: '已取消测试任务' }
  if (pathname.endsWith('/restart')) return { message: '已重新提交测试任务' }
  if (pathname.endsWith('/delete')) return { message: '已删除测试任务' }
  return { ok: true }
}

export function remoteEntryUrl(id) {
  return toServedPath(pluginRemoteEntries[id])
}

export function logHarnessInfo(testInfo) {
  testInfo.annotations.push(
    { type: 'host', description: moviePilotFrontendPath },
    { type: 'remote', description: `SubtitleManualUpload=${remoteEntryUrl('SubtitleManualUpload')}` },
    { type: 'remote', description: `AutoSubv3=${remoteEntryUrl('AutoSubv3')}` },
  )
}

export async function installMoviePilotPluginHarness(page) {
  assertRemoteEntriesExist()

  page.on('console', message => {
    const type = message.type()
    if (['error', 'warning'].includes(type)) {
      console.log(`[browser:${type}] ${message.text()}`)
    }
  })
  page.on('pageerror', error => {
    console.log(`[browser:pageerror] ${error.message}`)
  })
  page.on('requestfailed', request => {
    console.log(`[browser:requestfailed] ${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`)
  })

  await page.route('**/__plugin_dist__/**', async route => {
    const requestUrl = new URL(route.request().url())
    await fulfillPluginDist(route, requestUrl.pathname)
  })

  await page.route('**/api/v1/**', async route => {
    const requestUrl = new URL(route.request().url())
    if (await fulfillPluginDist(route, requestUrl.pathname)) return
    if (requestUrl.pathname === '/api/v1/plugin/remotes') {
      await route.fulfill(jsonResponse([
        { id: 'SubtitleManualUpload', url: remoteEntryUrl('SubtitleManualUpload') },
        { id: 'AutoSubv3', url: remoteEntryUrl('AutoSubv3') },
      ]))
      return
    }
    if (requestUrl.pathname.startsWith('/api/v1/plugin/SubtitleManualUpload/')) {
      await route.fulfill(jsonResponse(subtitleApiPayload(requestUrl.pathname)))
      return
    }
    if (requestUrl.pathname.startsWith('/api/v1/plugin/AutoSubv3/')) {
      await route.fulfill(jsonResponse(autoSubApiPayload(requestUrl.pathname)))
      return
    }
    await route.fulfill(jsonResponse(hostApiFallback(requestUrl.pathname)))
  })

  await page.addInitScript(() => {
    const theme = localStorage.getItem('theme') || 'light'
    localStorage.setItem('theme', theme)
    localStorage.setItem('moviepilot-theme-customizer', JSON.stringify({
      layout: 'vertical',
      primaryColor: '#9155FD',
      radius: 'default',
      semiDarkMenu: false,
      shadow: '0',
      skin: 'default',
      theme,
    }))
    localStorage.setItem('auth', JSON.stringify({
      token: 'mobile-plugin-test-token',
      originalPath: '/plugin-app/SubtitleManualUpload',
    }))
    localStorage.setItem('user', JSON.stringify({
      superUser: true,
      userID: 1,
      userName: 'mobile-plugin-test',
      avatar: '',
      level: 1,
      permissions: [],
      wizard: false,
    }))
  })
}

export async function openPluginPage(page, pluginId) {
  await page.goto(`/#/plugin-app/${pluginId}`)
  await expect(page.locator('.plugin-app-page')).toBeVisible()
}
