import { expect, test } from '@playwright/test'
import {
  installMoviePilotPluginHarness,
  logHarnessInfo,
  moviePilotFrontendPath,
  openPluginPage,
  remoteEntryUrl,
} from './support/moviepilotPluginHarness.mjs'

test.beforeEach(async ({ page }, testInfo) => {
  logHarnessInfo(testInfo)
  await installMoviePilotPluginHarness(page)
})

test('loads SubtitleManualUpload in the real MoviePilot host @host-load', async ({ page }) => {
  test.info().annotations.push(
    { type: 'host-path', description: moviePilotFrontendPath },
    { type: 'remote-entry', description: remoteEntryUrl('SubtitleManualUpload') },
  )

  await openPluginPage(page, 'SubtitleManualUpload')

  await expect(page.getByText('字幕匹配').first()).toBeVisible()
})

test('loads AutoSubv3 in the real MoviePilot host @host-load', async ({ page }) => {
  test.info().annotations.push(
    { type: 'host-path', description: moviePilotFrontendPath },
    { type: 'remote-entry', description: remoteEntryUrl('AutoSubv3') },
  )

  await openPluginPage(page, 'AutoSubv3')

  await expect(page.getByText('AI字幕生成(联动版)').first()).toBeVisible()
})
