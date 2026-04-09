import { defineConfig, devices } from '@playwright/test'
import { existsSync, readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

/* بارگذاری اختیاری .env.e2e از ریشهٔ admin-ui */
const isCI = process.env.CI === 'true' || process.env.CI === '1'

/* در CI فقط متغیرهای محیط شل/Secrets — بدون وابستگی به فایل روی دیسک */
const envE2e = resolve(__dirname, '.env.e2e')
if (!isCI && existsSync(envE2e)) {
  const lines = readFileSync(envE2e, 'utf8').split(/\r?\n/)
  for (const line of lines) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/)
    if (!m || m[1].startsWith('#')) continue
    let v = m[2].replace(/^["']|["']$/g, '')
    if (process.env[m[1]] === undefined) process.env[m[1]] = v
  }
}

const baseURL = process.env.E2E_BASE_URL?.replace(/\/$/, '') || 'http://127.0.0.1:5173'
const skipWebServer = process.env.E2E_SKIP_WEBSERVER === '1' || process.env.E2E_SKIP_WEBSERVER === 'true'

/** پیش‌فرض: headless (مخصوصاً CI). برای headed محلی: E2E_HEADED=1 */
const headed = process.env.E2E_HEADED === '1' || process.env.E2E_HEADED === 'true'

/**
 * در CI معمولاً Chromium باندل Playwright نصب است؛ msedge محلی نیست.
 * محلی: بدون متغیر → msedge. CI: Chromium. همه: E2E_BROWSER_CHANNEL=bundled|msedge|chrome
 */
function resolveBrowserUse(): Record<string, unknown> {
  const ch = process.env.E2E_BROWSER_CHANNEL?.trim()
  if (ch === 'bundled') return {}
  if (ch === 'msedge' || ch === 'chrome') return { channel: ch as 'msedge' | 'chrome' }
  /* CI: Chromium باندل؛ محلی: بدون نصب اضافهٔ msedge سیستم */
  if (isCI && (ch === undefined || ch === '')) return {}
  return { channel: 'msedge' as const }
}

/** توقف کل اجرا پس از اولین شکست (پیش‌فرض در CI) */
function resolveMaxFailures(): number | undefined {
  const raw = process.env.E2E_MAX_FAILURES?.trim()
  if (raw === '0' || raw === '') return undefined
  if (raw !== undefined && raw !== '') {
    const n = parseInt(raw, 10)
    return Number.isFinite(n) && n > 0 ? n : undefined
  }
  return isCI ? 1 : undefined
}

/**
 * E2E با بک‌اند واقعی (FastAPI + پروکسی Vite).
 *
 * اجرا:
 *   بک‌اند را روی پورت پیش‌فرض (مثلاً 3000) بالا بیاورید؛ Vite پروکسی /api را هدایت می‌کند.
 *   npm run test:e2e
 *
 * متغیرها: محیط شل / CI secrets. محلی: اختیاری .env.e2e (در CI بارگذاری نمی‌شود) — نمونه .env.e2e.example
 */
export default defineConfig({
  testDir: './e2e',
  /* هر تست دادهٔ e2e_* منحصربه‌فرد می‌سازد؛ می‌توان موازی اجرا کرد. E2E_WORKERS=1 برای اشکال‌زدایی */
  fullyParallel: true,
  forbidOnly: isCI,
  maxFailures: resolveMaxFailures(),
  retries: isCI ? 2 : 1,
  workers: process.env.E2E_WORKERS ? parseInt(process.env.E2E_WORKERS, 10) : isCI ? 1 : undefined,
  timeout: 120_000,
  expect: { timeout: 25_000 },
  reporter: [
    ['list', { printSteps: true }],
    [
      'html',
      {
        outputFolder: process.env.E2E_HTML_REPORT_DIR?.trim() || 'playwright-report',
        open: isCI ? 'never' : 'on-failure',
      },
    ],
  ],
  use: {
    baseURL,
    locale: 'fa-IR',
    /* بدون storageState از دیسک — هر تست زمینهٔ تمیز */
    storageState: undefined,
    headless: !headed,
    screenshot: 'only-on-failure',
    /* ویدیو نیاز به npx playwright install ffmpeg دارد — در CI در صورت نصب، E2E_VIDEO=1 */
    video: process.env.E2E_VIDEO === '1' ? 'retain-on-failure' : 'off',
    trace: isCI ? 'on-first-retry' : 'retain-on-failure',
    ...devices['Desktop Chrome'],
    ...resolveBrowserUse(),
    actionTimeout: 20_000,
    navigationTimeout: 45_000,
  },
  ...(skipWebServer
    ? {}
    : {
        webServer: {
          command: 'npm run dev',
          url: baseURL,
          reuseExistingServer: !isCI,
          timeout: 120_000,
        },
      }),
})
