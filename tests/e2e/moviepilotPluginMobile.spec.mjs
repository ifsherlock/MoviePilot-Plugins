import { expect, test } from '@playwright/test'
import {
  installMoviePilotPluginHarness,
  logHarnessInfo,
  moviePilotFrontendPath,
  openPluginPage,
  remoteEntryUrl,
} from './support/moviepilotPluginHarness.mjs'

const subtitleViewports = [
  { name: 'mobile-390', width: 390, height: 844 },
  { name: 'mobile-430', width: 430, height: 932 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'desktop-1024', width: 1024, height: 768 },
  { name: 'desktop-1440', width: 1440, height: 900 },
]

test.beforeEach(async ({ page }, testInfo) => {
  logHarnessInfo(testInfo)
  await installMoviePilotPluginHarness(page)
})

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const root = document.scrollingElement || document.documentElement
    return Math.ceil(root.scrollWidth - window.innerWidth)
  })
  expect(overflow).toBeLessThanOrEqual(1)
}

async function screenshot(page, testInfo, name) {
  await testInfo.attach(name, {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  })
}

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

for (const viewport of subtitleViewports) {
  test(`SubtitleManualUpload root and history stay responsive at ${viewport.name} @subtitle-root @subtitle`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await openPluginPage(page, 'SubtitleManualUpload')

    await expect(page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first()).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await screenshot(page, testInfo, `subtitle-root-${viewport.name}.png`)

    if (viewport.width >= 1024) {
      const mediaGridColumns = await page.locator('.media-list').evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)
      expect(mediaGridColumns).toBeGreaterThan(1)
    }

    await page.getByRole('button', { name: '匹配历史' }).click()
    await expect(page.getByText('入库自动字幕队列').first()).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await screenshot(page, testInfo, `subtitle-history-${viewport.name}.png`)
  })
}

test('SubtitleManualUpload detail actions stay usable on mobile @subtitle-detail @subtitle', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'SubtitleManualUpload')

  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()
  await expect(page.getByText('S01E01').first()).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-detail-mobile-390.png')

  await page.getByRole('checkbox').first().check()
  await expect(page.getByText('1 个已选').first()).toBeVisible()

  await page.getByTitle('搜索此集在线字幕').first().click()
  await expect(page.getByText('Mobile Layout Regression S01E01 English SDH')).toBeVisible()
  await page.getByRole('button', { name: '关闭在线字幕搜索' }).click()

  await page.getByTitle('调用 AI 字幕生成').first().click()
  await expect(page.getByText('AI 状态 · S01E01')).toBeVisible()
  await page.getByRole('button', { name: '关闭 AI 字幕生成状态' }).click()
  await expectNoHorizontalOverflow(page)
})

test('SubtitleManualUpload detail keeps desktop row density @subtitle-detail @subtitle', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await openPluginPage(page, 'SubtitleManualUpload')

  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()
  await expect(page.getByText('S01E01').first()).toBeVisible()
  await screenshot(page, testInfo, 'subtitle-detail-desktop-1440.png')

  const columns = await page.locator('.episode-row').first().evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(columns).toBeGreaterThanOrEqual(9)
  await expectNoHorizontalOverflow(page)
})

test('SubtitleManualUpload dialogs stay scrollable and bounded on mobile @subtitle-dialogs @subtitle', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'SubtitleManualUpload')

  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()
  await expect(page.getByText('S01E01').first()).toBeVisible()

  await page.getByRole('button', { name: '单集上传' }).first().click()
  await expect(page.getByText('把字幕或压缩包拖到这里')).toBeVisible()
  await page.locator('input[type="file"]').setInputFiles({
    name: 'The.Longest.Mobile.Layout.Regression.Title.2026.S01E01.English.SDH.Very.Long.Subtitle.File.Name.srt',
    mimeType: 'application/x-subrip',
    buffer: Buffer.from('1\\n00:00:01,000 --> 00:00:02,000\\nhello\\n'),
  })
  await expect(page.getByText('确认集数与输出文件名')).toBeVisible()
  await expect(page.getByText('The.Longest.Mobile.Layout.Regression.Title.2026.S01E01.English.SDH.Very.Long.Subtitle.File.Name.srt')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-upload-dialog-mobile-390.png')
  await page.getByRole('button', { name: '关闭上传字幕' }).click()

  await page.getByTitle('搜索此集在线字幕').first().click()
  await expect(page.getByText('Mobile Layout Regression S01E01 English SDH')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-online-dialog-mobile-390.png')
  await page.getByRole('button', { name: '关闭在线字幕搜索' }).click()

  await page.getByRole('button', { name: /AI：/ }).click()
  await expect(page.getByText('Whisper 识别中')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-ai-dialog-mobile-390.png')
  await page.getByRole('button', { name: '关闭 AI 字幕生成状态' }).click()
})

test('SubtitleManualUpload online dialog keeps desktop side panel @subtitle-dialogs @subtitle', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await openPluginPage(page, 'SubtitleManualUpload')

  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()
  await page.getByTitle('搜索此集在线字幕').first().click()
  await expect(page.getByText('Mobile Layout Regression S01E01 English SDH')).toBeVisible()
  await screenshot(page, testInfo, 'subtitle-online-dialog-desktop-1440.png')

  const columns = await page.locator('.online-layout').evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(columns).toBe(2)
  await expectNoHorizontalOverflow(page)
})

test('AutoSubv3 toolbar and filters stay usable on mobile @autosub-toolbar @autosub', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'AutoSubv3')

  await expect(page.getByText('AI字幕生成(联动版)').first()).toBeVisible()
  await expect(page.getByText('移动端布局回归测试剧集 S01E01')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-toolbar-mobile-390.png')

  await page.getByRole('button', { name: /最新在前|最早在前/ }).click()
  await page.getByText('失败 1').click()
  await expect(page.getByText('移动端布局回归测试剧集 S01E02')).toBeVisible()
  await page.getByRole('checkbox').first().check()
  await expect(page.getByRole('button', { name: '批量重新生成' })).toBeEnabled()
  await expectNoHorizontalOverflow(page)
})

test('AutoSubv3 toolbar keeps desktop row layout @autosub-toolbar @autosub', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await openPluginPage(page, 'AutoSubv3')

  await expect(page.getByText('队列运行中')).toBeVisible()
  await screenshot(page, testInfo, 'autosub-toolbar-desktop-1440.png')

  const toolbarWraps = await page.locator('.autosub-toolbar').evaluate(element => element.scrollHeight > element.clientHeight + 8)
  expect(toolbarWraps).toBe(false)
  await expectNoHorizontalOverflow(page)
})

test('AutoSubv3 task cards and restart dialog stay usable on mobile @autosub-tasks @autosub', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'AutoSubv3')

  await page.getByText('失败 1').click()
  await expect(page.getByText('移动端布局回归测试剧集 S01E02')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-tasks-mobile-390.png')

  await page.getByRole('checkbox').first().check()
  await page.getByRole('button', { name: '批量重新生成' }).click()
  await expect(page.getByText('重新生成 AI 字幕').last()).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-restart-dialog-mobile-390.png')
  await page.getByRole('dialog').getByRole('button', { name: '取消' }).click()
})

test('AutoSubv3 task cards remain readable on tablet and desktop @autosub-tasks @autosub', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await openPluginPage(page, 'AutoSubv3')
  await expect(page.getByText('移动端布局回归测试剧集 S01E01')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-tasks-tablet-768.png')

  await page.setViewportSize({ width: 1440, height: 900 })
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-tasks-desktop-1440.png')
})
