import { test, expect } from '@playwright/test'
import { answerFromMathQuestion } from './helpers/challenge'

/**
 * صف «اقدامات منتظر انجام» در داشبورد پنل‌ها — GET /api/panel/action-queue
 * به‌شرط وجود کاربر دمو student1 (پس از seed دمو).
 */
test.describe('پنل — صف اقدام نقش', () => {
  test('ورود دانشجوی دمو و نمایش کارت اقدامات در پنل دانشجو', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('login-tab-password').click()
    await page.getByTestId('login-challenge-answer').waitFor({ state: 'visible', timeout: 25_000 })

    const card = page.locator('.login-card')
    const cardText = (await card.textContent()) || ''
    const ans = answerFromMathQuestion(cardText)
    await page.getByTestId('login-challenge-answer').fill(ans)
    await page.getByTestId('login-username').fill('student1')
    await page.getByTestId('login-password').fill('demo123')

    const queuePromise = page.waitForResponse(
      (r) => r.url().includes('panel/action-queue') && r.request().method() === 'GET',
      { timeout: 60_000 },
    )
    await page.getByTestId('login-submit').click()
    await page.waitForURL(/\/panel/, { timeout: 45_000 })

    const res = await queuePromise
    expect(res.status()).toBe(200)

    await expect(page.getByTestId('panel-role-action-queue')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('panel-pending-item-student-0')).toBeVisible()
  })
})
