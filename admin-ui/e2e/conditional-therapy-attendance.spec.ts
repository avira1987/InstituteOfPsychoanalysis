import { test, expect, type Page } from '@playwright/test'
import { getE2eBaseUrl, hasAdminCredentials } from './helpers/env'
import { loginWithPasswordChallenge } from './helpers/auth'
import {
  fetchStudentMe,
  getTokenFromPage,
  patchStudentAsAdmin,
  deactivateUserAsAdmin,
} from './helpers/student-api'
import { cancelProcessInstanceAsAdmin, fetchStudentProcessInstances } from './helpers/process-api'
import { answerFromMathQuestion } from './helpers/challenge'
import { buildE2eRunId, e2eFullName, e2eUniquePhone } from './helpers/test-data'
import { retryStep, waitForResponseAfterAction, warnIfSlow } from './helpers/waits'

const baseURL = getE2eBaseUrl()

function logFailure(prefix: string, err: unknown, page: Page) {
  console.error(`[E2E ${prefix}]`, err instanceof Error ? err.message : err)
  console.error(`[E2E ${prefix}] URL:`, page.url())
}

async function submitPasswordLoginChallenge(page: Page) {
  const card = page.locator('.login-card')
  await card.waitFor({ state: 'visible' })
  const cardText = (await card.textContent()) || ''
  const ans = answerFromMathQuestion(cardText)
  await page.getByTestId('login-challenge-answer').fill(ans)
  await page.getByTestId('login-submit').click()
}

test.describe('پذیرش مشروط به درمان — قفل جلسات تا آغاز درمان', () => {
  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== 'passed') {
      logFailure(testInfo.title, testInfo.error?.message || testInfo.error, page)
    }
  })

  test('پذیرش مشروط، بدون درمان، محدودیت حضور/جلسات؛ سپس آزادسازی با درمان', async ({
    page,
    request,
  }, testInfo) => {
    test.skip(!hasAdminCredentials(), 'نیاز به E2E_ADMIN_USERNAME و E2E_ADMIN_PASSWORD (نقش admin)')

    const runId = buildE2eRunId(testInfo)
    const fullName = e2eFullName(runId)
    let username = ''
    let password = ''
    let userIdForCleanup: string | undefined

    try {
      await test.step('ثبت‌نام و ورود دانشجو', async () => {
        const phone = e2eUniquePhone(testInfo, 0)
        await page.goto('/register', { waitUntil: 'domcontentloaded' })
        await page.getByRole('heading', { name: 'ثبت‌نام دانشجو' }).waitFor({ state: 'visible' })
        const res = await waitForResponseAfterAction(
          page,
          (r) => r.url().includes('public/register') && r.request().method() !== 'OPTIONS',
          async () => {
            await page.getByTestId('register-input-full_name_fa').fill(fullName)
            await page.getByTestId('register-input-phone').fill(phone)
            await page.getByTestId('register-submit').click()
          },
          { timeout: 60_000, label: 'POST public/register' },
        )
        expect(res.status()).toBe(200)
        const body = (await res.json()) as { username: string; initial_password: string }
        username = body.username
        password = body.initial_password
        await expect
          .poll(async () => page.getByTestId('register-success').isVisible(), {
            timeout: 25_000,
            intervals: [200, 400, 800],
          })
          .toBe(true)

        await retryStep(
          'login',
          async () => {
            await page.goto('/login', { waitUntil: 'domcontentloaded' })
            await page.getByTestId('login-tab-password').click()
            await page.getByTestId('login-challenge-answer').waitFor({ state: 'visible', timeout: 25_000 })
            const startedAtMs = Date.now()
            const loginResPromise = page.waitForResponse(
              (r) => r.url().includes('login-json') && r.request().method() === 'POST',
              { timeout: 60_000 },
            )
            const meResPromise = page.waitForResponse(
              (r) => r.url().includes('/api/students/me') && r.request().method() === 'GET',
              { timeout: 60_000 },
            )
            await page.getByTestId('login-username').fill(username)
            await page.getByTestId('login-password').fill(password)
            await submitPasswordLoginChallenge(page)
            const [loginRes, meRes] = await Promise.all([loginResPromise, meResPromise])
            warnIfSlow('login-json + students/me', startedAtMs, `login=${loginRes.status()}`)
            expect(loginRes.status()).toBe(200)
            expect(meRes.status()).toBe(200)
            const meBody = (await meRes.json()) as { user_id?: string; therapy_started: boolean }
            expect(meBody.therapy_started).toBe(false)
            if (meBody.user_id) userIdForCleanup = meBody.user_id
            await expect
              .poll(
                async () => page.getByRole('heading', { name: 'پنل دانشجو' }).isVisible(),
                { timeout: 30_000, intervals: [200, 500, 1000] },
              )
              .toBe(true)
          },
          { maxAttempts: 3 },
        )
      })

      const studentToken = (await getTokenFromPage(page))!
      let me = await fetchStudentMe(request, baseURL, studentToken)
      expect(me.therapy_started).toBe(false)
      userIdForCleanup = me.user_id

      const adminUser = process.env.E2E_ADMIN_USERNAME!
      const adminPass = process.env.E2E_ADMIN_PASSWORD!
      const adminToken = await loginWithPasswordChallenge(request, baseURL, adminUser, adminPass)

      await test.step('ادمین: لغو ثبت‌نام اولیه تا رفع مسدودیت «ثبت‌نام باز»', async () => {
        const instances = await fetchStudentProcessInstances(request, baseURL, studentToken, me.id)
        const intro = instances.find(
          (i) => i.process_code === 'introductory_course_registration' && !i.is_cancelled && !i.is_completed,
        )
        expect(intro).toBeTruthy()
        await cancelProcessInstanceAsAdmin(request, baseURL, adminToken, intro!.instance_id)
      })

      await test.step('ادمین: پذیرش مشروط به درمان روی پرونده (بدون آغاز درمان)', async () => {
        me = await patchStudentAsAdmin(request, baseURL, adminToken, me.id, {
          extra_data: {
            admission_type: 'conditional_therapy',
            has_active_therapist: false,
          },
          therapy_started: false,
        })
        expect(me.therapy_started).toBe(false)
        expect(me.extra_data?.admission_type).toBe('conditional_therapy')
      })

      await test.step('دانشجو: تلاش برای «پرداخت جلسات» — قفل تا آغاز درمان (مسیر حضور در جلسات)', async () => {
        await page.goto('/panel/portal/student', { waitUntil: 'domcontentloaded' })
        await expect(page.getByRole('heading', { name: 'پنل دانشجو' })).toBeVisible({ timeout: 30_000 })

        const payBtn = page.getByRole('button', { name: 'پرداخت جلسات' })
        await payBtn.waitFor({ state: 'visible' })
        await expect(payBtn).toBeDisabled()

        const therapyTitle = (await payBtn.getAttribute('title')) || ''
        expect(therapyTitle, 'انتظار توضیح قفل مربوط به آغاز درمان آموزشی').toMatch(/درمان/)

        const sessionsTab = page.locator('.tab-bar .tab-item').filter({ hasText: 'جلسات آنلاین' })
        await sessionsTab.click()
        await expect(page.getByRole('heading', { name: 'جلسات آنلاین درمان' })).toBeVisible()
        /* بدون جلسهٔ زمان‌بندی‌شده، ورود به کلاس آنلاین وجود ندارد (غیبت خودکار در بک‌اند با زمان‌بندی جلسات تست واحد می‌شود) */
        await expect(page.getByText(/هنوز جلسه‌ای در تقویم شما ثبت نشده است/)).toBeVisible()
      })

      await test.step('ادمین: آغاز درمان (therapy_started)', async () => {
        me = await patchStudentAsAdmin(request, baseURL, adminToken, me.id, { therapy_started: true })
        expect(me.therapy_started).toBe(true)
      })

      await test.step('دانشجو: دسترسی به پرداخت جلسات باز می‌شود', async () => {
        await page.reload({ waitUntil: 'domcontentloaded' })
        await expect(page.getByRole('heading', { name: 'پنل دانشجو' })).toBeVisible({ timeout: 30_000 })
        const payBtn = page.getByRole('button', { name: 'پرداخت جلسات' })
        await expect
          .poll(async () => payBtn.isEnabled(), { timeout: 20_000, intervals: [300, 600, 1200] })
          .toBe(true)
        const t = await payBtn.getAttribute('title')
        expect(t || '').not.toContain('آغاز درمان')
      })

      await test.step('API: students/me منعکس‌کنندهٔ درمان', async () => {
        const st = await getTokenFromPage(page)
        const api = await fetchStudentMe(request, baseURL, st!)
        expect(api.therapy_started).toBe(true)
      })
    } finally {
      if (userIdForCleanup) {
        try {
          const adminToken = await loginWithPasswordChallenge(
            request,
            baseURL,
            process.env.E2E_ADMIN_USERNAME!,
            process.env.E2E_ADMIN_PASSWORD!,
          )
          await deactivateUserAsAdmin(request, baseURL, adminToken, userIdForCleanup)
        } catch (e) {
          console.warn('[E2E] cleanup failed:', e)
        }
      }
    }
  })
})
