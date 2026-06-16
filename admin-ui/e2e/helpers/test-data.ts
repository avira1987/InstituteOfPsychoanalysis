import type { APIRequestContext, TestInfo } from '@playwright/test'
import { expect } from '@playwright/test'

const E2E_PREFIX = 'e2e_'

/**
 * شناسهٔ یکتا و دادهٔ ثبت‌نام برای تست‌هایی که خودشان کاربر می‌سازند (public/register).
 * نیازی به seed کاربر دمو در DB نیست.
 */
export function buildE2eRunId(testInfo: Pick<TestInfo, 'workerIndex' | 'retry' | 'parallelIndex'>): string {
  return `${E2E_PREFIX}w${testInfo.workerIndex}_p${testInfo.parallelIndex}_r${testInfo.retry}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

/** Persian-friendly label; includes `e2e_` tag; must stay ≥2 chars for public/register validation. */
export function e2eFullName(runId: string): string {
  return `کاربر ${runId}`
}

/**
 * Iranian mobile: 09 + 9 digits. Spread across workers/time/random to avoid collisions in parallel.
 * `stepAttempt` differentiates register/login retries so a new phone is used per retry when needed.
 */
/** کد ملی معتبر برای E2E (ثابت؛ با قوانین رقم کنترل ایران سازگار است). */
export const E2E_VALID_NATIONAL_CODE = '0499370899'

/** فیلدهای تکمیلی ثبت‌نام (الزامی پس از گسترش فرم). */
export const E2E_REGISTRATION_PROFILE = {
  first_name_fa: 'کاربر',
  last_name_fa: 'تست',
  age: 28,
  birth_certificate_number: '12345',
  birth_date: '1370/01/15',
  residence_city: 'تهران',
  home_address: 'خیابان تست ۱',
  work_address: 'خیابان تست ۲',
  email: 'e2e.student@example.com',
  home_phone: '02112345678',
  work_phone: '02187654321',
  had_psychotherapy: 'no' as const,
  used_psychiatric_meds: 'no' as const,
  psychiatric_hospitalization_history: 'no' as const,
  has_work_permit: 'no' as const,
  has_university_degree: 'yes' as const,
  course_participation_mode: 'online' as const,
  referral_source: 'website' as const,
}

/** ثبت‌نام دانشجو از طریق API (صفحهٔ عمومی /register به ورود با موبایل هدایت می‌شود). */
export async function e2eRegisterStudentViaApi(
  request: APIRequestContext,
  body: {
    full_name_fa: string
    phone: string
    national_code?: string
    course_type?: 'introductory' | 'comprehensive'
  },
) {
  const res = await request.post('/api/public/register', {
    data: {
      full_name_fa: body.full_name_fa,
      phone: body.phone,
      national_code: body.national_code ?? E2E_VALID_NATIONAL_CODE,
      course_type: body.course_type ?? 'introductory',
      ...E2E_REGISTRATION_PROFILE,
    },
  })
  expect(res.ok(), `public/register failed: ${res.status()} ${await res.text()}`).toBeTruthy()
  return res.json() as Promise<{
    student_code: string
    username: string
    initial_password: string
  }>
}

export function e2eUniquePhone(
  testInfo: Pick<TestInfo, 'workerIndex' | 'retry' | 'parallelIndex'>,
  stepAttempt = 0,
): string {
  const salt =
    testInfo.workerIndex * 17_000_000 +
    testInfo.parallelIndex * 1_010_101 +
    testInfo.retry * 97_331 +
    stepAttempt * 1_000_003 +
    (Date.now() % 100_000_000) * 31 +
    Math.floor(Math.random() * 10_000)
  const nine = String(salt % 1_000_000_000).padStart(9, '0')
  return `09${nine}`
}
