import { expect } from '@playwright/test'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

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
    await route.fulfill(jsonResponse(hostApiFallback(requestUrl.pathname)))
  })

  await page.addInitScript(() => {
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
