import { test, expect, type Page } from '@playwright/test'
import { getE2eBaseUrl, hasAdminCredentials } from './helpers/env'
import { loginWithPasswordChallenge } from './helpers/auth'
import { deactivateUserAsAdmin, fetchStudentMe, getTokenFromPage } from './helpers/student-api'
import { answerFromMathQuestion } from './helpers/challenge'
import { buildE2eRunId, e2eFullName, e2eRegisterStudentViaApi, e2eUniquePhone } from './helpers/test-data'
import { retryStep, waitForResponseAfterAction, warnIfSlow } from './helpers/waits'
import { toFaDigits } from './helpers/faDigits'

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

/** زمان شروع/پایان را در فرم شمسی به ماه بعد (یا سال بعد) می‌برد تا بازه حتماً در آینده باشد. */
async function setInterviewSlotFormToNextCalendarMonth(page: Page) {
  const jy = parseInt(await page.locator('#slot-start-y').inputValue(), 10)
  const jm = parseInt(await page.locator('#slot-start-m').inputValue(), 10)
  let nextM = jm + 1
  let nextY = jy
  if (nextM > 12) {
    nextM = 1
    nextY = jy + 1
  }
  const yearValues = await page.locator('#slot-start-y option').evaluateAll((opts) =>
    opts.map((o) => parseInt((o as HTMLOptionElement).value, 10)),
  )
  if (!yearValues.includes(nextY)) {
    nextY = jy
    nextM = jm >= 11 ? 12 : jm + 2
    if (nextM > 12) nextM = 12
  }
  const yStr = String(nextY)
  const mStr = String(nextM)
  await page.locator('#slot-start-y').selectOption(yStr)
  await page.locator('#slot-start-m').selectOption(mStr)
  await page.locator('#slot-start-d').selectOption('15')
  await page.locator('#slot-start-h').fill('10')
  await page.locator('#slot-start-min').fill('0')

  await page.locator('#slot-end-y').selectOption(yStr)
  await page.locator('#slot-end-m').selectOption(mStr)
  await page.locator('#slot-end-d').selectOption('15')
  await page.locator('#slot-end-h').fill('11')
  await page.locator('#slot-end-min').fill('30')
}

async function loginAsPasswordUser(page: Page, username: string, password: string) {
  await retryStep(
    'login',
    async () => {
      await page.goto('/login?staff=1', { waitUntil: 'domcontentloaded' })
      await page.getByTestId('login-challenge-answer').waitFor({ state: 'visible', timeout: 25_000 })
      const loginResPromise = page.waitForResponse(
        (r) => r.url().includes('login-json') && r.request().method() === 'POST',
        { timeout: 60_000 },
      )
      await page.getByTestId('login-username').fill(username)
      await page.getByTestId('login-password').fill(password)
      await submitPasswordLoginChallenge(page)
      const loginRes = await loginResPromise
      warnIfSlow('login-json', Date.now(), `HTTP ${loginRes.status()}`)
      expect(loginRes.status()).toBe(200)
    },
    { maxAttempts: 3 },
  )
}

async function logoutAndClearSession(page: Page) {
  await page.context().clearCookies()
  await page.goto('/login', { waitUntil: 'domcontentloaded' })
  await page.evaluate(() => {
    try {
      localStorage.clear()
    } catch {
      /* ignore */
    }
  })
}

const STAFF_SLOT_USERNAME = process.env.E2E_STAFF_USERNAME || 'staff1'
const STAFF_SLOT_PASSWORD = process.env.E2E_STAFF_PASSWORD || 'demo123'

test.describe('پنل مصاحبه‌گر — وقت، رزرو دانشجو، جدول رزروها', () => {
  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== 'passed') {
      logFailure(testInfo.title, testInfo.error?.message || testInfo.error, page)
    }
  })

  test('تعریف وقت از UI، رزرو از پنل دانشجو، نمایش در رزروهای مصاحبه‌گر', async ({ page, request }, testInfo) => {
    test.skip(!hasAdminCredentials(), 'نیاز به E2E_ADMIN_USERNAME و E2E_ADMIN_PASSWORD (برای مشاهده رزرو در پنل مصاحبه‌گر)')

    const runId = buildE2eRunId(testInfo)
    const fullName = e2eFullName(runId)
    const slotLabel = `وقت e2e ${runId.slice(0, 24)}`
    const adminUser = process.env.E2E_ADMIN_USERNAME!
    const adminPass = process.env.E2E_ADMIN_PASSWORD!

    let studentUsername = ''
    let studentPassword = ''
    let studentCode = ''
    let userIdForCleanup: string | undefined

    await test.step('کارمند دفتر: ورود و تعریف وقت مصاحبه', async () => {
      await loginAsPasswordUser(page, STAFF_SLOT_USERNAME, STAFF_SLOT_PASSWORD)
      await page.goto('/panel/portal/staff/admissions?tab=interviewSlots', { waitUntil: 'domcontentloaded' })
      await page.getByRole('heading', { name: 'تعریف وقت مصاحبه' }).waitFor({ state: 'visible', timeout: 30_000 })
    })

    await test.step('کارمند دفتر: ثبت وقت (فرم شمسی + مکان + برچسب)', async () => {
      await setInterviewSlotFormToNextCalendarMonth(page)
      const slotForm = page.locator('form').filter({ has: page.getByRole('button', { name: 'ثبت وقت' }) })
      await slotForm.locator('select.psf-input').nth(0).selectOption('')
      await slotForm.locator('select.psf-input').nth(1).selectOption('in_person')
      await slotForm.locator('input.psf-input[dir="rtl"]').first().fill(`سالن تست ${runId.slice(0, 12)}`)
      await slotForm.locator('input.psf-input[dir="rtl"]').nth(1).fill(slotLabel)

      const createRes = await waitForResponseAfterAction(
        page,
        (r) => r.url().includes('/api/interview-slots/manage') && r.request().method() === 'POST',
        async () => {
          await page.getByRole('button', { name: 'ثبت وقت' }).click()
        },
        { timeout: 60_000, label: 'POST interview-slots/manage' },
      )
      expect(createRes.status()).toBe(200)
      await expect(page.getByRole('cell', { name: /آزاد/ }).first()).toBeVisible({ timeout: 20_000 })
    })

    await test.step('خروج کارمند برای ثبت‌نام دانشجو', async () => {
      await logoutAndClearSession(page)
    })

    await test.step('دانشجو: ثبت‌نام و ورود', async () => {
      const phone = e2eUniquePhone(testInfo, 0)
      const body = await e2eRegisterStudentViaApi(request, {
        full_name_fa: fullName,
        phone,
      })
      studentUsername = body.username
      studentPassword = body.initial_password
      studentCode = body.student_code

      await loginAsPasswordUser(page, studentUsername, studentPassword)
      await expect
        .poll(async () => page.getByRole('heading', { name: 'پنل آموزشی' }).isVisible(), { timeout: 30_000 })
        .toBe(true)
      const tok = (await getTokenFromPage(page))!
      expect(tok).toBeTruthy()
      const me = await fetchStudentMe(request, baseURL, tok)
      userIdForCleanup = me.user_id
    })

    await test.step('دانشجو: داشبورد — انتخاب وقت و تأیید رزرو', async () => {
      const bookP = page.waitForResponse(
        (r) => r.url().includes('/api/interview-slots/book') && r.request().method() === 'POST',
        { timeout: 90_000 },
      )
      await page.goto('/panel/portal/student', { waitUntil: 'domcontentloaded' })
      await page.getByTestId('student-quest-interview-slot-picker').waitFor({ state: 'visible', timeout: 45_000 })
      await expect(page.getByRole('heading', { name: 'انتخاب زمان مصاحبه' })).toBeVisible()
      await page.locator('.interview-slot-picker label').filter({ hasText: slotLabel }).click()
      await page.getByRole('button', { name: 'تأیید رزرو وقت مصاحبه' }).click()
      const bookRes = await bookP
      expect(bookRes.status()).toBe(200)
      const bookJson = (await bookRes.json()) as { success?: boolean; current_state?: string }
      expect(bookJson.current_state === 'interview_payment' || bookJson.success === true).toBeTruthy()
      await page.getByTestId('student-quest-sep-payment').waitFor({ state: 'visible', timeout: 30_000 })
    })

    await test.step('خروج دانشجو و ورود ادمین — رزرو در جدول رزروها', async () => {
      await logoutAndClearSession(page)
      await loginAsPasswordUser(page, adminUser, adminPass)
      await page.goto('/panel/portal/interviewer', { waitUntil: 'domcontentloaded' })
      await page.getByRole('heading', { name: 'رزروهای وقت مصاحبه' }).waitFor({ state: 'visible' })
      await expect(page.getByRole('row').filter({ hasText: fullName })).toBeVisible({ timeout: 30_000 })
      await expect(page.getByRole('row').filter({ hasText: toFaDigits(studentCode) })).toBeVisible()
    })

    await test.step('ادمین — تب ثبت نتیجه و فهرست صف', async () => {
      await page.getByTestId('interviewer-tab-result').click()
      await expect(page.getByTestId('interview-result-queue')).toBeVisible({ timeout: 15_000 })
      await expect(page.getByRole('heading', { name: 'فهرست ثبت نتیجهٔ مصاحبه' })).toBeVisible()
    })

    if (userIdForCleanup) {
      await test.step('پاکسازی: غیرفعال‌سازی کاربر دانشجو', async () => {
        try {
          const adminToken = await loginWithPasswordChallenge(request, baseURL, adminUser, adminPass)
          await deactivateUserAsAdmin(request, baseURL, adminToken, userIdForCleanup!)
        } catch (e) {
          console.warn('[E2E] cleanup deactivate failed:', e)
        }
      })
    }
  })
})
