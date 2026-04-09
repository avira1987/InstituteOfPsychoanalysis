import type { TestInfo } from '@playwright/test'

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
