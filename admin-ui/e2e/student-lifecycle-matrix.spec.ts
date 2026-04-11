import { test, expect } from '@playwright/test'

/**
 * صفحهٔ عمومی ماتریس چرخه عمر + API — بدون نیاز به لاگین.
 * برای اتوماسیون وب: data-testid روی ریشه و فازها.
 */
test.describe('ماتریس چرخه عمر دانشجو (عمومی)', () => {
  test('API و صفحه student-lifecycle بارگذاری می‌شوند', async ({ page }) => {
    const resPromise = page.waitForResponse(
      (r) =>
        r.url().includes('public/student-lifecycle-matrix') && r.request().method() === 'GET',
      { timeout: 60_000 },
    )

    await page.goto('/student-lifecycle', { waitUntil: 'domcontentloaded' })

    const res = await resPromise
    expect(res.status()).toBe(200)
    const body = (await res.json()) as {
      schema_version: string
      phases: { phase_id: string }[]
      stats: { phase_count: number }
    }
    expect(body.schema_version).toBeTruthy()
    expect(body.phases?.length).toBeGreaterThan(0)
    expect(body.stats.phase_count).toBe(body.phases.length)

    await expect(page.getByTestId('lifecycle-page-title')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('lifecycle-matrix-root')).toBeVisible()
    await expect(page.getByTestId('lifecycle-phase-P0_admissions_path')).toBeVisible()
    await expect(page.getByTestId('lifecycle-process-start_therapy')).toBeVisible()
    await expect(page.getByTestId('lifecycle-role-therapist')).toBeVisible()
  })
})
