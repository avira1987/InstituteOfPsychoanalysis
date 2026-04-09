import type { Page, Response } from '@playwright/test'

/** Log a warning when an API round-trip exceeds this (end-to-end, includes UI action). */
export const SLOW_API_WARNING_MS = 8_000

export function warnIfSlow(label: string, startedAtMs: number, extra?: string) {
  const elapsed = Date.now() - startedAtMs
  if (elapsed > SLOW_API_WARNING_MS) {
    console.warn(`[E2E] slow API ${label}: ${elapsed}ms${extra ? ` — ${extra}` : ''}`)
  }
}

/**
 * Arms waitForResponse, runs action, awaits response, logs if slow.
 */
export async function waitForResponseAfterAction(
  page: Page,
  predicate: (r: Response) => boolean,
  action: () => Promise<void>,
  options: { timeout?: number; label: string },
): Promise<Response> {
  const startedAtMs = Date.now()
  const resPromise = page.waitForResponse(predicate, { timeout: options.timeout ?? 60_000 })
  await action()
  const res = await resPromise
  warnIfSlow(options.label, startedAtMs, `HTTP ${res.status()} ${res.url()}`)
  return res
}

/**
 * Retries flaky UI/network steps (e.g. login). Each attempt should be safe to re-run.
 */
export async function retryStep<T>(
  name: string,
  fn: (attemptIndex: number) => Promise<T>,
  options?: { maxAttempts?: number; delayMs?: number },
): Promise<T> {
  const maxAttempts = options?.maxAttempts ?? 3
  const delayMs = options?.delayMs ?? 350
  let lastErr: unknown
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn(attempt)
    } catch (e) {
      lastErr = e
      const msg = e instanceof Error ? e.message : String(e)
      if (attempt >= maxAttempts) {
        console.error(`[E2E] ${name} failed after ${maxAttempts} attempts: ${msg}`)
        throw e
      }
      console.warn(`[E2E] ${name} attempt ${attempt}/${maxAttempts} failed, retrying — ${msg}`)
      await new Promise((r) => setTimeout(r, delayMs * attempt))
    }
  }
  throw lastErr
}
