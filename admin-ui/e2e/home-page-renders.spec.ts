import { test, expect } from '@playwright/test'
import { getE2eBaseUrl } from './helpers/env'

/** رگرسیون: خطای JS (مثلاً globalFeed is not defined) صفحهٔ سفید می‌سازد. */
test('صفحهٔ اصلی بعد از بیلد React را رندر می‌کند', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (err) => errors.push(err.message))

  await page.goto(`${getE2eBaseUrl()}/`)
  await expect(page.getByRole('heading', { name: 'انستیتو روانکاوی تهران', level: 1 })).toBeVisible({
    timeout: 15_000,
  })
  expect(errors, `JS errors: ${errors.join('; ')}`).toEqual([])
})
