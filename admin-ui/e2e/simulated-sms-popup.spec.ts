import { test, expect } from '@playwright/test'
import { getE2eBaseUrl } from './helpers/env'

const baseURL = getE2eBaseUrl()

function uniquePhone() {
  const tail = String(Date.now()).slice(-7)
  return `0912${tail}`
}

test.describe('پاپ‌آپ پیامک شبیه‌سازی‌شده', () => {
  test('درخواست OTP — overlay بلافاصله نمایش داده می‌شود', async ({ page, request }) => {
    const phone = uniquePhone()

    // sanity: API باید simulated_sms برگرداند (بک‌اند log + SMS_SIMULATION_UI)
    const apiBase = baseURL.replace(/:\d+$/, ':3000')
    let apiOk = false
    try {
      const apiRes = await request.post(`${apiBase}/api/auth/otp/request`, {
        data: { phone },
        timeout: 15_000,
      })
      if (apiRes.ok()) {
        const body = await apiRes.json()
        apiOk = Boolean(body?.simulated_sms?.message)
      }
    } catch {
      /* vite proxy — از UI تست می‌کنیم */
    }

    await page.goto(`${baseURL}/login`)
    await page.getByTestId('login-otp-phone').fill(phone)
    await page.getByRole('button', { name: 'ارسال کد پیامکی' }).click()

    const overlay = page.locator('[data-testid="simulated-sms-overlay"]')
    await expect(overlay).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('[data-testid="simulated-sms-message"]')).toContainText('کد ورود')

    if (!apiOk) {
      test.info().annotations.push({
        type: 'warning',
        description:
          'API مستقیم simulated_sms نداشت — پاپ‌آپ UI کار کرد؛ SMS_PROVIDER=log و SMS_SIMULATION_UI=true را روی بک‌اند چک کنید.',
      })
    }

    await page.getByTestId('simulated-sms-close').click()
    await expect(overlay).toBeHidden({ timeout: 5_000 })
  })
})
