import { expect, test } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import {
  installMoviePilotPluginHarness,
  logHarnessInfo,
  moviePilotFrontendPath,
  openPluginPage,
  remoteEntryUrl,
} from './support/moviepilotPluginHarness.mjs'
import {
  expectBottomContentNotObscured,
  expectDialogUsableOnMobile,
  expectNoHorizontalOverflow,
  expectTouchTargets,
} from './support/mobileAssertions.mjs'

const subtitleViewports = [
  { name: 'mobile-390', width: 390, height: 844 },
  { name: 'mobile-430', width: 430, height: 932 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'desktop-1024', width: 1024, height: 768 },
  { name: 'desktop-1440', width: 1440, height: 900 },
]
const screenshotRoot = path.resolve('test-results/plugin-mobile-screenshots')
const themeCases = [
  { name: 'light', expected: 'light' },
  { name: 'dark', expected: 'dark' },
]

test.beforeEach(async ({ page }, testInfo) => {
  logHarnessInfo(testInfo)
  await installMoviePilotPluginHarness(page)
})

async function screenshot(page, testInfo, name) {
  await mkdir(screenshotRoot, { recursive: true })
  const filePath = path.join(screenshotRoot, name)
  const body = await page.screenshot({ fullPage: true, path: filePath })
  await testInfo.attach(name, {
    body,
    contentType: 'image/png',
  })
  testInfo.annotations.push({ type: 'screenshot', description: filePath })
}

for (const viewport of subtitleViewports.filter(item => item.width <= 768)) {
  test(`Mobile UI contract holds for SubtitleManualUpload at ${viewport.name} @mobile-contract`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await openPluginPage(page, 'SubtitleManualUpload')

    await expect(page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first()).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await expectTouchTargets(page.locator('.sticky-toolbar').getByRole('button', { name: /刷新字幕匹配状态|关闭字幕匹配/ }).or(page.getByRole('button', { name: '匹配历史' })), {
      label: `Subtitle root ${viewport.name}`,
    })
    await expectBottomContentNotObscured(page, '.media-card')
    await screenshot(page, testInfo, `subtitle-mobile-contract-root-${viewport.name}.png`)

    await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()
    await expect(page.getByText('S01E01').first()).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await expectTouchTargets(page.locator('.toolbar-row').getByRole('button', { name: /全选当前列表|批量上传整季字幕/ }).or(page.locator('.episode-row').first().getByRole('button', { name: '单集上传' })), {
      label: `Subtitle detail ${viewport.name}`,
    })
    await expectBottomContentNotObscured(page, '.episode-row')

    await page.getByTitle('搜索此集在线字幕').first().click()
    await expect(page.getByText('Mobile Layout Regression S01E01 English SDH')).toBeVisible()
    await expectDialogUsableOnMobile(page, page.getByRole('dialog'))
    await screenshot(page, testInfo, `subtitle-mobile-contract-dialog-${viewport.name}.png`)
  })

  test(`Mobile UI contract holds for AutoSubv3 at ${viewport.name} @mobile-contract`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await openPluginPage(page, 'AutoSubv3')

    await expect(page.locator('.task-row').filter({ hasText: '移动端布局回归测试剧集 S01E01' }).first()).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await expectTouchTargets(page.locator('.autosub-toolbar').getByRole('button', { name: /最新在前|最早在前|全选|批量重新生成|刷新任务|关闭 AI字幕生成/ }), {
      label: `AutoSub root ${viewport.name}`,
    })
    await expectBottomContentNotObscured(page, '.task-row')
    await screenshot(page, testInfo, `autosub-mobile-contract-root-${viewport.name}.png`)

    await page.getByText('失败 1').click()
    await page.getByRole('checkbox').first().check()
    await page.getByRole('button', { name: '批量重新生成' }).click()
    await expect(page.getByText('重新生成 AI 字幕').last()).toBeVisible()
    await expectDialogUsableOnMobile(page, page.getByRole('dialog'))
    await screenshot(page, testInfo, `autosub-mobile-contract-dialog-${viewport.name}.png`)
  })
}

async function setHostTheme(page, themeName) {
  await page.addInitScript(theme => {
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
  }, themeName)
}

async function expectHostTheme(page, expectedTheme) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.getAttribute('data-theme'))).toBe(expectedTheme)
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

test('renders SubtitleManualUpload extreme fake-data states @fixtures-extreme', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'SubtitleManualUpload')

  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()
  await page.getByTitle('搜索此集在线字幕').first().click()
  await expect(page.getByText(/EXTREME MOBILE RESULT/)).toBeVisible()
  await expect(page.getByText(/需要手动打开源站验证/)).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await page.getByRole('button', { name: '关闭在线字幕搜索' }).click()

  await page.getByRole('button', { name: /AI：/ }).click()
  await expect(page.getByText('极端失败原因：ASR 提取成功')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await page.getByRole('button', { name: '关闭 AI 字幕生成状态' }).click()

  await page.getByRole('button', { name: '返回资源列表' }).click()
  await page.getByRole('button', { name: '匹配历史' }).click()
  await page.getByText('入库自动字幕队列').first().click()
  await expect(page.getByText(/Cloudflare challenge/)).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-fixtures-extreme-mobile-390.png')
})

test('renders AutoSubv3 extreme fake-data task states @fixtures-extreme', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'AutoSubv3')

  const pendingCard = page.locator('.task-mobile-card').filter({ hasText: /极端移动端任务卡片测试/ }).first()
  const failedCard = page.locator('.task-mobile-card').filter({ hasText: /翻译模型连续 3 次返回非 JSON 内容/ }).first()
  await expect(pendingCard).toBeVisible()
  await expect(pendingCard.getByText(/等待前序任务释放 GPU 队列/)).toBeVisible()
  await expect(failedCard).toBeVisible()
  await expect(failedCard.getByText(/翻译模型连续 3 次返回非 JSON 内容/)).toBeVisible()
  await expectNoHorizontalOverflow(page)

  await failedCard.getByRole('checkbox').check()
  await expect(page.getByRole('button', { name: '批量重新生成' })).toBeEnabled()
  await screenshot(page, testInfo, 'autosub-fixtures-extreme-mobile-390.png')
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

test('AutoSubv3 mobile toolbar and batch bar stay usable @autosub-batch-bar-polish @autosub', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'AutoSubv3')

  await expect(page.getByText('AI字幕生成(联动版)').first()).toBeVisible()
  await expectTouchTargets(page.locator('.autosub-toolbar').getByRole('button', { name: /刷新任务|最新在前|最早在前|全选|关闭 AI字幕生成/ }), {
    label: 'AutoSub polished mobile toolbar',
  })
  await page.locator('.autosub-toolbar').getByRole('button', { name: /最新在前|最早在前/ }).click()
  await page.getByText('失败 1').click()
  await expect(page.locator('.task-mobile-card').filter({ hasText: '移动端布局回归测试剧集 S01E02' })).toBeVisible()

  await page.locator('.autosub-toolbar').getByRole('button', { name: '全选' }).click()
  const batchBar = page.locator('.autosub-mobile-batch-bar')
  await expect(batchBar).toBeVisible()
  await expect(batchBar).toContainText('2')
  await expect(batchBar).toContainText('个已选')
  await expectTouchTargets(batchBar.getByRole('button', { name: /重跑|取消|删除/ }), {
    label: 'AutoSub mobile batch bar',
  })
  await batchBar.getByRole('button', { name: '重跑' }).click()
  await expect(page.getByText('重新生成 AI 字幕').last()).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectBottomContentNotObscured(page, '.task-mobile-card')
  await screenshot(page, testInfo, 'autosub-batch-bar-polish-mobile-390.png')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden()

  await page.setViewportSize({ width: 1440, height: 900 })
  await expect(page.locator('.autosub-mobile-batch-bar')).toBeHidden()
  await expect(page.locator('.autosub-toolbar').getByRole('button', { name: '批量重新生成' })).toBeVisible()
  const toolbarWraps = await page.locator('.autosub-toolbar').evaluate(element => element.scrollHeight > element.clientHeight + 8)
  expect(toolbarWraps).toBe(false)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-batch-bar-polish-desktop-1440.png')
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

test('AutoSubv3 mobile task cards expose summary, details, and desktop fallback @autosub-task-card-polish @autosub', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'AutoSubv3')

  const failedCard = page
    .getByText('极端移动端 AI 状态测试 S01E03 With A Very Long Alias')
    .locator('xpath=ancestor::*[contains(@class, "task-mobile-card")]')
  await expect(failedCard).toBeVisible()
  await expect(failedCard.getByText('来源')).toBeVisible()
  await expect(failedCard.getByText('输出')).toBeVisible()
  await expect(failedCard.getByText(/翻译模型连续 3 次返回非 JSON 内容/)).toBeVisible()

  await expectTouchTargets(failedCard.getByRole('button', { name: '重新生成' }), {
    label: 'AutoSub mobile primary action',
  })
  await failedCard.getByRole('button', { name: '详情' }).click()
  await expect(failedCard.getByText('视频路径')).toBeVisible()
  await expect(failedCard.getByText('/mnt/media/TV/极端移动端 AI 状态测试/Season 01/')).toBeVisible()
  await expect(failedCard.getByText('完整原因')).toBeVisible()
  await expect(failedCard.getByRole('button', { name: '删除记录' })).toBeVisible()

  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-task-card-polish-mobile-390.png')

  await page.setViewportSize({ width: 1440, height: 900 })
  await expect(page.locator('.task-mobile-card').first()).toBeHidden()
  await expect(page.locator('.task-row').first()).toBeVisible()
  const columns = await page.locator('.task-row').first().evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(columns).toBeGreaterThanOrEqual(3)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-task-card-polish-desktop-1440.png')
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

for (const themeCase of themeCases) {
  test(`SubtitleManualUpload follows host ${themeCase.name} theme @theme @subtitle`, async ({ page }, testInfo) => {
    await setHostTheme(page, themeCase.name)
    await page.setViewportSize({ width: 430, height: 932 })
    await openPluginPage(page, 'SubtitleManualUpload')

    await expectHostTheme(page, themeCase.expected)
    await expect(page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first()).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await screenshot(page, testInfo, `subtitle-root-${themeCase.name}-theme-mobile-430.png`)
  })

  test(`AutoSubv3 follows host ${themeCase.name} theme @theme @autosub`, async ({ page }, testInfo) => {
    await setHostTheme(page, themeCase.name)
    await page.setViewportSize({ width: 430, height: 932 })
    await openPluginPage(page, 'AutoSubv3')

    await expectHostTheme(page, themeCase.expected)
    await expect(page.getByText('移动端布局回归测试剧集 S01E01')).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await screenshot(page, testInfo, `autosub-root-${themeCase.name}-theme-mobile-430.png`)
  })
}
