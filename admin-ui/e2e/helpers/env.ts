/**
 * متغیرهای محیطی E2E — در تست‌ها فقط از process.env (در CI توسط runner تزریق می‌شود).
 * در محلی، playwright.config می‌تواند .env.e2e را بارگذاری کند؛ در CI فایل بارگذاری نمی‌شود.
 */

export function isCi(): boolean {
  return process.env.CI === 'true' || process.env.CI === '1'
}

/** Playwright: headless مگر E2E_HEADED=1 */
export function isE2eHeadless(): boolean {
  if (process.env.E2E_HEADED === '1' || process.env.E2E_HEADED === 'true') return false
  return true
}

export function getE2eBaseUrl(): string {
  return process.env.E2E_BASE_URL?.replace(/\/$/, '') || 'http://127.0.0.1:5173'
}

export function getAdminUsername(): string | undefined {
  return process.env.E2E_ADMIN_USERNAME?.trim() || undefined
}

export function getAdminPassword(): string | undefined {
  return process.env.E2E_ADMIN_PASSWORD?.trim() || undefined
}

export function hasAdminCredentials(): boolean {
  return !!(getAdminUsername() && getAdminPassword())
}
