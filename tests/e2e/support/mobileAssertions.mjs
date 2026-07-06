import { expect } from '@playwright/test'

export async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const root = document.scrollingElement || document.documentElement
    return Math.ceil(root.scrollWidth - window.innerWidth)
  })
  expect(overflow).toBeLessThanOrEqual(1)
}

export async function expectTouchTargets(locator, options = {}) {
  const {
    minSize = 44,
    minGap = 8,
    label = 'touch target',
  } = options

  const visibleTargets = []
  const count = await locator.count()
  for (let index = 0; index < count; index += 1) {
    const target = locator.nth(index)
    if (!(await target.isVisible())) continue
    const box = await target.boundingBox()
    if (!box) continue
    visibleTargets.push(box)
    expect.soft(box.width, `${label} ${index + 1} width`).toBeGreaterThanOrEqual(minSize)
    expect.soft(box.height, `${label} ${index + 1} height`).toBeGreaterThanOrEqual(minSize)
  }

  for (let index = 1; index < visibleTargets.length; index += 1) {
    const previous = visibleTargets[index - 1]
    const current = visibleTargets[index]
    const overlapY = Math.max(0, Math.min(previous.y + previous.height, current.y + current.height) - Math.max(previous.y, current.y))
    if (!overlapY) continue
    const horizontalGap = current.x >= previous.x
      ? current.x - (previous.x + previous.width)
      : previous.x - (current.x + current.width)
    if (horizontalGap >= 0) {
      expect.soft(horizontalGap, `${label} gap ${index}`).toBeGreaterThanOrEqual(minGap)
    }
  }

  expect(visibleTargets.length, `${label} visible count`).toBeGreaterThan(0)
}

export async function expectBottomContentNotObscured(page, selector) {
  const visible = await page.locator(selector).first().evaluate(element => {
    element.scrollIntoView({ block: 'end' })
    const rect = element.getBoundingClientRect()
    const viewportHeight = window.innerHeight
    const bottomBars = Array.from(document.querySelectorAll('.v-bottom-navigation, [class*="bottom-nav"], [class*="bottom-navigation"]'))
      .map(node => node.getBoundingClientRect())
      .filter(rectangle => rectangle.height > 0 && rectangle.bottom > viewportHeight - 160)
    const reservedBottom = bottomBars.reduce((max, rectangle) => Math.max(max, viewportHeight - rectangle.top), 0)
    return rect.bottom <= viewportHeight - reservedBottom + 1 && rect.top < viewportHeight
  })
  expect(visible).toBe(true)
}

export async function expectDialogUsableOnMobile(page, dialogLocator) {
  await expect(dialogLocator).toBeVisible()
  await expectNoHorizontalOverflow(page)

  const dialogBox = await dialogLocator.boundingBox()
  expect(dialogBox).toBeTruthy()
  expect(dialogBox.width).toBeLessThanOrEqual((await page.viewportSize()).width + 1)
  expect(dialogBox.height).toBeLessThanOrEqual((await page.viewportSize()).height + 1)

  const closeButton = dialogLocator.getByRole('button', { name: /关闭|取消/ }).first()
  await expect(closeButton).toBeVisible()
  const closeBox = await closeButton.boundingBox()
  expect(closeBox.width).toBeGreaterThanOrEqual(44)
  expect(closeBox.height).toBeGreaterThanOrEqual(44)
}
