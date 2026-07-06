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
    await expect(page.locator('.episode-row').filter({ hasText: 'S01E01' }).first()).toBeVisible()
    await expectNoHorizontalOverflow(page)
    if (viewport.width <= 600) {
      await expectTouchTargets(page.locator('.toolbar-row').getByRole('button', { name: '全选当前列表' }).or(page.locator('.subtitle-mobile-action-bar').getByRole('button', { name: /搜索全部季字幕包|上传|AI 生成/ })), {
        label: `Subtitle detail ${viewport.name}`,
      })
    } else {
      await expectTouchTargets(page.locator('.toolbar-row').getByRole('button', { name: /全选当前列表|批量上传整季字幕/ }).or(page.locator('.episode-row').first().getByRole('button', { name: '单集上传' })), {
        label: `Subtitle detail ${viewport.name}`,
      })
    }
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
    await expectTouchTargets(page.locator('.autosub-toolbar').getByRole('button', { name: /最新在前|最早在前|全选|刷新任务|关闭 AI字幕生成/ }), {
      label: `AutoSub root ${viewport.name}`,
    })
    await expectBottomContentNotObscured(page, '.task-row')
    await screenshot(page, testInfo, `autosub-mobile-contract-root-${viewport.name}.png`)

    await page.getByText('失败 1').click()
    await page.getByRole('checkbox').first().check()
    if (viewport.width <= 600) {
      await page.locator('.autosub-mobile-batch-bar').getByRole('button', { name: '重跑' }).click()
    } else {
      await page.getByRole('button', { name: '批量重新生成' }).click()
    }
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
  await expect(page.locator('.task-mobile-card').filter({ hasText: '移动端布局回归测试剧集 S01E01' }).first()).toBeVisible()
  await expect(page.locator('.task-mobile-card').filter({ hasText: '测试用失败信息：模型返回内容格式不完整' }).first()).toBeVisible()

  await page.getByText('失败 1').click()
  await expect(page.locator('.task-mobile-card').filter({ hasText: '移动端布局回归测试剧集 S01E02' }).first()).toBeVisible()
  await page.getByRole('checkbox').first().check()
  await page.locator('.autosub-mobile-batch-bar').getByRole('button', { name: '重跑' }).click()
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
  await expect(page.locator('.autosub-mobile-batch-bar').getByRole('button', { name: '重跑' })).toBeEnabled()
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
  await expect(page.locator('.episode-row').filter({ hasText: 'S01E01' }).first()).toBeVisible()
  await screenshot(page, testInfo, 'subtitle-detail-desktop-1440.png')

  const columns = await page.locator('.episode-row').first().evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(columns).toBeGreaterThanOrEqual(9)
  await expectNoHorizontalOverflow(page)
})

test('SubtitleManualUpload episode mobile cards expose key actions @subtitle-episode-card-polish @subtitle', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'SubtitleManualUpload')

  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()
  const firstCard = page.locator('.episode-mobile-card').filter({ hasText: 'S01E01' }).first()
  await expect(firstCard).toBeVisible()
  await expectTouchTargets(firstCard.getByRole('button', { name: /在线搜索|上传/ }).or(firstCard.getByTitle('调用 AI 字幕生成')), {
    label: 'Subtitle episode mobile primary actions',
  })
  await firstCard.getByRole('checkbox').check()
  await expect(page.getByText('1 个已选').first()).toBeVisible()

  await firstCard.getByTitle('展开详情').click()
  await expect(firstCard.getByText('完整路径')).toBeVisible()
  await expect(firstCard.locator('.episode-mobile-detail-block').filter({ hasText: '/mnt/media/TV/移动端布局回归测试剧集/Season 01/' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-episode-card-polish-mobile-390.png')

  await firstCard.getByRole('button', { name: '在线搜索' }).click()
  await expect(page.getByText('Mobile Layout Regression S01E01 English SDH')).toBeVisible()
  await page.getByRole('button', { name: '关闭在线字幕搜索' }).click()

  await firstCard.getByRole('button', { name: '上传' }).click()
  await expect(page.getByText('把字幕或压缩包拖到这里')).toBeVisible()
  await page.getByRole('button', { name: '关闭上传字幕' }).click()

  await firstCard.getByTitle('调用 AI 字幕生成').click()
  await expect(page.getByText('AI 状态 · S01E01')).toBeVisible()
  await page.getByRole('button', { name: '关闭 AI 字幕生成状态' }).click()
  await expectNoHorizontalOverflow(page)

  await page.setViewportSize({ width: 1440, height: 900 })
  await expect(page.locator('.episode-mobile-card').first()).toBeHidden()
  await expect(page.locator('.episode-row').first()).toBeVisible()
  const columns = await page.locator('.episode-row').first().evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(columns).toBeGreaterThanOrEqual(9)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-episode-card-polish-desktop-1440.png')
})

test('SubtitleManualUpload mobile batch bar and AI guidance stay concise @subtitle-detail-batch-polish @subtitle', async ({ page }, testInfo) => {
  await page.route('**/api/v1/plugin/SubtitleManualUpload/status', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        enabled: true,
        source: 'MoviePilot 本地整理记录',
        index: {
          ready: true,
          updated_at: '2026-07-07 02:26:00',
          entry_count: 50,
          media_count: 1,
          expires_in: 3600,
        },
        archive_support: {
          zip: true,
          rar: true,
          rar_tool: 'unar',
          rar_tool_path: '/usr/bin/unar',
          rar_python: true,
          dependency_mode: 'container_install',
          dependency_status: { state: 'ready' },
        },
        timeline_fixer: {
          available: true,
          ffmpeg: true,
          ffprobe: true,
          modules: { numpy: true, pysubs2: true, webrtcvad: true },
          configured_max_offset_seconds: 120,
        },
        ai_subtitle: {
          enabled: true,
          installed: false,
          available: false,
          running: false,
          queue_ready: false,
          plugin_name: 'AI字幕生成(联动版)',
          plugin_version: '',
          message: '插件未启用',
          counts: {},
          updated_at: '2026-07-07 02:31:00',
        },
        auto_transfer_queue: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, skipped: 0, failed: 0 },
      }),
    })
  })

  await page.route('**/api/v1/plugin/SubtitleManualUpload/ai_tasks', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        status: {
          enabled: true,
          installed: false,
          available: false,
          running: false,
          queue_ready: false,
          plugin_name: 'AI字幕生成(联动版)',
          plugin_version: '',
          message: '插件未启用',
          counts: {},
          updated_at: '2026-07-07 02:31:00',
        },
        summary: {},
        tasks: [],
        task_by_target: {},
        tasks_by_target: {},
      }),
    })
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'SubtitleManualUpload')
  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()

  const firstCard = page.locator('.episode-mobile-card').filter({ hasText: 'S01E01' }).first()
  await expect(firstCard).toBeVisible()
  await firstCard.getByRole('checkbox').check()
  await expect(page.getByText('1 个已选').first()).toBeVisible()

  const batchBar = page.locator('.subtitle-mobile-action-bar')
  await expect(batchBar).toBeVisible()
  await expect(batchBar).toContainText('1 个已选')
  await expectTouchTargets(batchBar.getByRole('button', { name: /搜索选中|上传|AI 生成|调轴|恢复|清空/ }), {
    label: 'Subtitle mobile batch action bar',
  })
  await batchBar.getByRole('button', { name: /搜索选中/ }).click()
  await expect(page.getByText('Mobile Layout Regression S01E01 English SDH')).toBeVisible()
  await page.getByRole('button', { name: '关闭在线字幕搜索' }).click()

  await batchBar.getByRole('button', { name: /AI 生成/ }).click({ force: true })
  await expect(page.getByText('请安装 AI字幕生成(联动版) 以启用相关功能').first()).toBeVisible()
  await expect(page.getByText('AI字幕生成(联动版) 插件未启用，请安装 AI字幕生成(联动版) 以启用相关功能')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)
  await expectBottomContentNotObscured(page, '.episode-row')
  await screenshot(page, testInfo, 'subtitle-detail-batch-polish-mobile-390.png')

  await page.setViewportSize({ width: 1440, height: 900 })
  await expect(page.locator('.subtitle-mobile-action-bar')).toBeHidden()
  await expect(page.locator('.toolbar-row').getByRole('button', { name: '上传选中字幕' })).toBeVisible()
  await expect(page.locator('.toolbar-row').getByRole('button', { name: /搜索选中/ })).toBeVisible()
  const toolbarWraps = await page.locator('.toolbar-row').evaluate(element => element.scrollHeight > element.clientHeight + 8)
  expect(toolbarWraps).toBe(false)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-detail-batch-polish-desktop-1440.png')
})

test('SubtitleManualUpload upload and online dialogs behave as mobile sheets @subtitle-upload-online-sheet-polish @subtitle', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'SubtitleManualUpload')
  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()

  const firstCard = page.locator('.episode-mobile-card').filter({ hasText: 'S01E01' }).first()
  await expect(firstCard).toBeVisible()
  await firstCard.getByRole('button', { name: '上传' }).click()
  const uploadDialog = page.getByRole('dialog')
  await expect(uploadDialog.locator('.upload-dialog')).toBeVisible()
  await expect(uploadDialog.getByText('把字幕或压缩包拖到这里')).toBeVisible()
  await expectTouchTargets(uploadDialog.getByRole('button', { name: /选择文件|关闭/ }), {
    label: 'Subtitle upload mobile sheet entry actions',
  })
  const uploadBox = await uploadDialog.locator('.upload-dialog').boundingBox()
  expect(uploadBox.width).toBeLessThanOrEqual(390)
  expect(uploadBox.height).toBeLessThanOrEqual(844)

  await page.locator('input[type="file"]').setInputFiles({
    name: 'The.Longest.Mobile.Layout.Regression.Title.2026.S01E01.English.SDH.Very.Long.Subtitle.File.Name.srt',
    mimeType: 'application/x-subrip',
    buffer: Buffer.from('1\\n00:00:01,000 --> 00:00:02,000\\nhello\\n'),
  })
  await expect(uploadDialog.getByText('确认集数与输出文件名')).toBeVisible()
  await expectTouchTargets(uploadDialog.locator('.dialog-actions-top').getByRole('button', { name: /关闭|重新选择文件|写入字幕/ }), {
    label: 'Subtitle upload mobile sheet fixed actions',
  })
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-upload-online-sheet-upload-mobile-390.png')
  await uploadDialog.getByRole('button', { name: '关闭上传字幕' }).click()
  await expect(uploadDialog).toBeHidden()

  await firstCard.getByRole('button', { name: '在线搜索' }).click()
  const onlineDialog = page.getByRole('dialog')
  await expect(onlineDialog.locator('.online-dialog')).toBeVisible()
  await expect(onlineDialog.getByText('Mobile Layout Regression S01E01 English SDH')).toBeVisible()
  await expectTouchTargets(onlineDialog.getByRole('button', { name: /下载并生成预览|提交 AI 翻译|搜索/ }).or(onlineDialog.locator('.online-result-action')), {
    label: 'Subtitle online mobile sheet actions',
  })
  const onlineBox = await onlineDialog.locator('.online-dialog').boundingBox()
  expect(onlineBox.width).toBeLessThanOrEqual(390)
  expect(onlineBox.height).toBeLessThanOrEqual(844)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-upload-online-sheet-online-mobile-390.png')
  await onlineDialog.getByRole('button', { name: '关闭在线字幕搜索' }).click()
  await expect(onlineDialog).toBeHidden()

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.locator('.episode-row').filter({ hasText: 'S01E01' }).first().getByTitle('搜索此集在线字幕').click()
  await expect(page.locator('.online-layout')).toBeVisible()
  const columns = await page.locator('.online-layout').evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(columns).toBe(2)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-upload-online-sheet-online-desktop-1440.png')
})

test('SubtitleManualUpload AI status and auto queue dialogs behave as mobile sheets @subtitle-ai-queue-sheet-polish @subtitle', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'SubtitleManualUpload')
  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()

  await page.getByRole('button', { name: /AI：/ }).click()
  const aiDialog = page.getByRole('dialog')
  await expect(aiDialog.locator('.ai-task-dialog')).toBeVisible()
  await expect(aiDialog.getByText('极端失败原因：ASR 提取成功')).toBeVisible()
  await expectTouchTargets(aiDialog.getByRole('button', { name: /刷新|重新生成|关闭 AI 字幕生成状态/ }), {
    label: 'Subtitle AI mobile sheet actions',
  })
  const aiBox = await aiDialog.locator('.ai-task-dialog').boundingBox()
  expect(aiBox.width).toBeLessThanOrEqual(390)
  expect(aiBox.height).toBeLessThanOrEqual(844)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-ai-queue-sheet-ai-mobile-390.png')
  await aiDialog.getByRole('button', { name: '关闭 AI 字幕生成状态' }).click()
  await expect(aiDialog).toBeHidden()

  await page.getByRole('button', { name: '返回资源列表' }).click()
  await page.getByRole('button', { name: '匹配历史' }).click()
  await page.getByText('入库自动字幕队列').first().click()
  const queueDialog = page.getByRole('dialog')
  await expect(queueDialog.locator('.auto-queue-card')).toBeVisible()
  await expect(queueDialog.getByText(/Cloudflare challenge/)).toBeVisible()
  await expectTouchTargets(queueDialog.getByRole('button', { name: /刷新|关闭入库自动字幕队列/ }), {
    label: 'Subtitle auto queue mobile sheet actions',
  })
  const queueBox = await queueDialog.locator('.auto-queue-card').boundingBox()
  expect(queueBox.width).toBeLessThanOrEqual(390)
  expect(queueBox.height).toBeLessThanOrEqual(844)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-ai-queue-sheet-queue-mobile-390.png')
  await queueDialog.getByRole('button', { name: '关闭入库自动字幕队列' }).click()
  await expect(queueDialog).toBeHidden()

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.reload()
  await expect(page.locator('.plugin-app-page')).toBeVisible()
  await page.getByText('移动端布局回归测试剧集：特别长的中文标题和 English Alias').first().click()
  await page.locator('.episode-row').filter({ hasText: 'S01E01' }).first().locator('.ai-row-btn').click()
  await expect(aiDialog.locator('.ai-task-dialog')).toBeVisible()
  const desktopAiBox = await aiDialog.locator('.ai-task-dialog').boundingBox()
  expect(desktopAiBox.width).toBeLessThanOrEqual(860)
  expect(desktopAiBox.height).toBeLessThan(900)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'subtitle-ai-queue-sheet-ai-desktop-1440.png')
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
  await expect(page.locator('.task-mobile-card').filter({ hasText: '移动端布局回归测试剧集 S01E01' }).first()).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-toolbar-mobile-390.png')

  await page.getByRole('button', { name: /最新在前|最早在前/ }).click()
  await page.getByText('失败 1').click()
  await expect(page.locator('.task-mobile-card').filter({ hasText: '移动端布局回归测试剧集 S01E02' }).first()).toBeVisible()
  await page.getByRole('checkbox').first().check()
  await expect(page.locator('.autosub-mobile-batch-bar').getByRole('button', { name: '重跑' })).toBeEnabled()
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

test('AutoSubv3 restart dialog behaves as a mobile sheet @autosub-restart-sheet-polish @autosub', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'AutoSubv3')

  await page.getByText('失败 1').click()
  const failedCard = page.locator('.task-mobile-card').filter({ hasText: '移动端布局回归测试剧集 S01E02' }).first()
  await failedCard.getByRole('button', { name: '重新生成' }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('重新生成 AI 字幕').first()).toBeVisible()
  await expect(dialog.locator('.restart-dialog-count')).toHaveText('1 个任务')
  await expect(dialog.getByRole('combobox')).toBeVisible()
  await expectTouchTargets(dialog.getByRole('button', { name: /取消|重新生成/ }), {
    label: 'AutoSub restart sheet actions',
  })
  const dialogBox = await dialog.boundingBox()
  expect(dialogBox.width).toBeLessThanOrEqual(390)
  expect(dialogBox.height).toBeLessThanOrEqual(844)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-restart-sheet-polish-mobile-390.png')
  await dialog.getByRole('button', { name: '取消' }).click()
  await expect(dialog).toBeHidden()

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.locator('.task-row').filter({ hasText: '移动端布局回归测试剧集 S01E02' }).first().getByRole('button', { name: '重新生成' }).click()
  await expect(dialog).toBeVisible()
  const desktopCardBox = await dialog.locator('.restart-dialog-card').boundingBox()
  expect(desktopCardBox.width).toBeLessThanOrEqual(560)
  expect(desktopCardBox.height).toBeLessThan(900)
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-restart-sheet-polish-desktop-1440.png')
  await dialog.getByRole('button', { name: '取消' }).click()
})

test('AutoSubv3 task cards and restart dialog stay usable on mobile @autosub-tasks @autosub', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPluginPage(page, 'AutoSubv3')

  await page.getByText('失败 1').click()
  await expect(page.locator('.task-mobile-card').filter({ hasText: '移动端布局回归测试剧集 S01E02' }).first()).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await screenshot(page, testInfo, 'autosub-tasks-mobile-390.png')

  await page.getByRole('checkbox').first().check()
  await page.locator('.autosub-mobile-batch-bar').getByRole('button', { name: '重跑' }).click()
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
  await expect(page.locator('.task-row').filter({ hasText: '移动端布局回归测试剧集 S01E01' }).first()).toBeVisible()
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
    await expect(page.locator('.task-row').filter({ hasText: '移动端布局回归测试剧集 S01E01' }).first()).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await screenshot(page, testInfo, `autosub-root-${themeCase.name}-theme-mobile-430.png`)
  })
}
