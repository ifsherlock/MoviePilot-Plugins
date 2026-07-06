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

test('drives SubtitleManualUpload core fake-data flows @fixtures', async ({ page }) => {
  await openPluginPage(page, 'SubtitleManualUpload')

  await expect(page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first()).toBeVisible()
  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()
  await expect(page.getByText('50 个本地目标').first()).toBeVisible()
  await expect(page.getByText('S01E01').first()).toBeVisible()

  await page.getByTitle('搜索此集在线字幕').first().click()
  await expect(page.getByText('在线字幕搜索').or(page.getByText(/搜索 S01E01/)).first()).toBeVisible()
  await expect(page.getByText('Mobile Layout Regression S01E01 English SDH')).toBeVisible()
  await page.getByRole('button', { name: '关闭在线字幕搜索' }).click()
  await expect(page.getByText('Mobile Layout Regression S01E01 English SDH')).toBeHidden()

  await page.getByRole('button', { name: /AI：/ }).click()
  await expect(page.getByText('Whisper 识别中')).toBeVisible()
  await page.getByRole('button', { name: '关闭 AI 字幕生成状态' }).click()
  await expect(page.getByText('Whisper 识别中')).toBeHidden()

  await page.getByRole('button', { name: '返回资源列表' }).click()
  await page.getByRole('button', { name: '匹配历史' }).click()
  await expect(page.getByText('入库自动字幕队列').first()).toBeVisible()
  await page.getByText('入库自动字幕队列').first().click()
  await expect(page.getByText('正在搜索英文字幕并准备提交 AI 翻译')).toBeVisible()
})

test('drives AutoSubv3 core fake-data flows @fixtures', async ({ page }) => {
  await openPluginPage(page, 'AutoSubv3')

  await expect(page.getByText('队列运行中')).toBeVisible()
  await expect(page.getByText('移动端布局回归测试剧集 S01E01')).toBeVisible()
  await expect(page.getByText('测试用失败信息：模型返回内容格式不完整')).toBeVisible()

  await page.getByText('失败 1').click()
  await expect(page.getByText('移动端布局回归测试剧集 S01E02')).toBeVisible()
  await page.getByRole('checkbox').first().check()
  await page.getByRole('button', { name: '批量重新生成' }).click()
  await expect(page.getByText('重新生成 AI 字幕').last()).toBeVisible()
})
