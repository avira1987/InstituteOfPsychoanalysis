import { test, expect, type Page } from '@playwright/test'
import { getE2eBaseUrl, hasAdminCredentials } from './helpers/env'
import { loginWithPasswordChallenge } from './helpers/auth'
import {
  fetchStudentMe,
  getTokenFromPage,
  tryPatchStudentAsStudent,
  patchStudentAsAdmin,
  deactivateUserAsAdmin,
} from './helpers/student-api'
import { answerFromMathQuestion } from './helpers/challenge'
import { buildE2eRunId, e2eFullName, e2eUniquePhone, E2E_VALID_NATIONAL_CODE } from './helpers/test-data'
import { retryStep, waitForResponseAfterAction, warnIfSlow } from './helpers/waits'
import { toFaDigits } from './helpers/faDigits'

async function waitForAuthToken(page: Page, timeout = 15_000) {
  await expect
    .poll(async () => getTokenFromPage(page), { timeout, intervals: [100, 300, 600] })
    .not.toBeNull()
  return (await getTokenFromPage(page))!
}

const baseURL = getE2eBaseUrl()

function logFailure(prefix: string, err: unknown, page: Page) {
  console.error(`[E2E ${prefix}]`, err instanceof Error ? err.message : err)
  console.error(`[E2E ${prefix}] URL:`, page.url())
}

async function openStudentProfileTab(page: Page) {
  const tab = page.locator('.tab-bar .tab-item').filter({ hasText: 'پروفایل' })
  await tab.waitFor({ state: 'visible' })
  await tab.click()
}

/** پس از پر کردن نام کاربری و رمز؛ فقط پاسخ چالش و ارسال */
async function submitPasswordLoginChallenge(page: Page) {
  const card = page.locator('.login-card')
  await card.waitFor({ state: 'visible' })
  const cardText = (await card.textContent()) || ''
  const ans = answerFromMathQuestion(cardText)
  await page.getByTestId('login-challenge-answer').fill(ans)
  await page.getByTestId('login-submit').click()
}

test.describe('انستیتو — یکپارچگی UI و API (بدون mock)', () => {
  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== 'passed') {
      logFailure(testInfo.title, testInfo.error?.message || testInfo.error, page)
    }
  })

  test('ثبت‌نام، ورود، پایداری، students/me، محدودیت نقش، و اختیاری: ادمین/درمان', async ({
    page,
    request,
  }, testInfo) => {
    const runId = buildE2eRunId(testInfo)
    const fullName = e2eFullName(runId)

    let studentCode = ''
    let username = ''
    let password = ''
    let userIdForCleanup: string | undefined

    try {
      await test.step('ثبت‌نام از UI — انتظار پاسخ ۲۰۰ از public/register', async () => {
        const maxAttempts = 3
        let apiRegistered = false
        let lastErr: unknown
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
          try {
            const phone = e2eUniquePhone(testInfo, attempt)

            await page.goto('/register', { waitUntil: 'domcontentloaded' })
            await page.getByRole('heading', { name: 'ثبت‌نام دانشجو' }).waitFor({ state: 'visible' })

            const res = await waitForResponseAfterAction(
              page,
              (r) => r.url().includes('public/register') && r.request().method() !== 'OPTIONS',
              async () => {
                await page.getByTestId('register-input-full_name_fa').fill(fullName)
                await page.getByTestId('register-input-phone').fill(phone)
                await page.getByTestId('register-input-national_code').fill(E2E_VALID_NATIONAL_CODE)
                await page.getByTestId('register-submit').click()
              },
              { timeout: 60_000, label: 'POST public/register' },
            )

            expect(res.status()).toBe(200)
            const body = (await res.json()) as {
              student_code: string
              username: string
              initial_password: string
            }
            studentCode = body.student_code
            username = body.username
            password = body.initial_password
            expect(studentCode).toBeTruthy()
            expect(username).toBeTruthy()
            apiRegistered = true

            await expect
              .poll(
                async () => page.getByTestId('register-success').isVisible(),
                { timeout: 25_000, intervals: [200, 400, 800] },
              )
              .toBe(true)
            await expect(page.getByTestId('register-student-code')).toContainText(toFaDigits(studentCode))
            return
          } catch (e) {
            lastErr = e
            if (apiRegistered) {
              console.error('[E2E] register failed after successful API; not retrying to avoid duplicate users')
              throw e
            }
            if (attempt >= maxAttempts) {
              throw e
            }
            const msg = e instanceof Error ? e.message : String(e)
            console.warn(`[E2E] register attempt ${attempt}/${maxAttempts} failed — ${msg}`)
            await new Promise((r) => setTimeout(r, 350 * attempt))
          }
        }
        throw lastErr
      })

      await test.step('ورود — login-json و students/me', async () => {
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
            warnIfSlow('login-json + GET students/me', startedAtMs, `login=${loginRes.status()} me=${meRes.status()}`)

            expect(loginRes.status()).toBe(200)
            expect(meRes.status()).toBe(200)
            const meBody = (await meRes.json()) as {
              student_code: string
              therapy_started: boolean
              user_id: string
            }
            expect(meBody.student_code).toBe(studentCode)
            expect(meBody.therapy_started).toBe(false)
            userIdForCleanup = meBody.user_id

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

      await test.step('سازگاری UI و API (کد دانشجویی)', async () => {
        const token = await waitForAuthToken(page, 15_000)
        const api = await fetchStudentMe(request, baseURL, token)
        userIdForCleanup = api.user_id
        expect(api.student_code).toBe(studentCode)
        await page.getByText(toFaDigits(studentCode), { exact: false }).first().waitFor({ state: 'visible' })
      })

      await test.step('reload پنل — دوباره GET students/me و تطابق', async () => {
        const startedAtMs = Date.now()
        const nav = page.waitForResponse(
          (r) => r.url().includes('/api/students/me') && r.request().method() === 'GET',
          { timeout: 30_000 },
        )
        await page.reload({ waitUntil: 'domcontentloaded' })
        const r = await nav
        warnIfSlow('GET students/me (after reload)', startedAtMs, `HTTP ${r.status()}`)
        expect(r.status()).toBe(200)
        const j = (await r.json()) as { student_code: string }
        expect(j.student_code).toBe(studentCode)
        await page.getByRole('heading', { name: 'پنل دانشجو' }).waitFor({ state: 'visible' })
      })

      await test.step('بارگذاری dashboard فرایند (در صورت وجود primary)', async () => {
        const startedAtMs = Date.now()
        const dashP = page.waitForResponse(
          (r) => r.url().includes('/api/process/') && r.url().includes('/dashboard'),
          { timeout: 45_000 },
        )
        await page.goto('/panel/portal/student', { waitUntil: 'domcontentloaded' })
        const dr = await dashP.catch(() => null)
        if (dr) {
          warnIfSlow('process dashboard', startedAtMs, `HTTP ${dr.status()}`)
          expect(dr.status()).toBe(200)
        }
      })

      await test.step('بک‌اند: دانشجو نمی‌تواند therapy_started را مستقیم PATCH کند', async () => {
        const token = await waitForAuthToken(page, 10_000)
        const me = await fetchStudentMe(request, baseURL, token)
        const status = await tryPatchStudentAsStudent(request, baseURL, token!, me.id, {
          therapy_started: true,
        })
        expect([401, 403, 422]).toContain(status)
      })

      await test.step('پروفایل — نمایش درمان مطابق GET students/me', async () => {
        await page.goto('/panel/portal/student', { waitUntil: 'domcontentloaded' })
        await openStudentProfileTab(page)
        const token = (await getTokenFromPage(page))!
        const me = await fetchStudentMe(request, baseURL, token)
        const expected = me.therapy_started ? 'بله' : 'خیر'
        await page.getByText('درمان آغاز شده', { exact: false }).waitFor({ state: 'visible' })
        await expect
          .poll(
            async () => {
              const vis = await page.getByText(expected, { exact: true }).first().isVisible()
              return vis
            },
            { timeout: 15_000, intervals: [200, 500] },
          )
          .toBe(true)
      })

      if (hasAdminCredentials()) {
        await test.step('ادمین: PATCH therapy_started و انعکاس در API و UI', async () => {
          const adminUser = process.env.E2E_ADMIN_USERNAME!
          const adminPass = process.env.E2E_ADMIN_PASSWORD!

          const studentToken = await waitForAuthToken(page, 10_000)
          const meBefore = await fetchStudentMe(request, baseURL, studentToken)
          expect(meBefore.therapy_started).toBe(false)

          const adminToken = await loginWithPasswordChallenge(request, baseURL, adminUser, adminPass)
          const updated = await patchStudentAsAdmin(request, baseURL, adminToken, meBefore.id, {
            therapy_started: true,
          })
          expect(updated.therapy_started).toBe(true)

          const startedAtMs = Date.now()
          const meWait = page.waitForResponse(
            (r) => r.url().includes('/api/students/me') && r.request().method() === 'GET',
            { timeout: 30_000 },
          )
          await page.reload({ waitUntil: 'domcontentloaded' })
          const r = await meWait
          warnIfSlow('GET students/me (after admin PATCH)', startedAtMs, `HTTP ${r.status()}`)
          expect(r.status()).toBe(200)
          const body = (await r.json()) as { therapy_started: boolean }
          expect(body.therapy_started).toBe(true)

          await openStudentProfileTab(page)
          await expect
            .poll(
              async () => page.getByText('بله', { exact: true }).first().isVisible(),
              { timeout: 15_000, intervals: [200, 400] },
            )
            .toBe(true)
        })
      }
    } finally {
      if (userIdForCleanup && hasAdminCredentials()) {
        try {
          const adminToken = await loginWithPasswordChallenge(
            request,
            baseURL,
            process.env.E2E_ADMIN_USERNAME!,
            process.env.E2E_ADMIN_PASSWORD!,
          )
          await deactivateUserAsAdmin(request, baseURL, adminToken, userIdForCleanup)
        } catch (e) {
          console.warn('[E2E] cleanup (deactivate user) failed:', e)
        }
      }
    }
  })
})
