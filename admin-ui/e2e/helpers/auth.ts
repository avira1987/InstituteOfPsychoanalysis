import type { APIRequestContext } from '@playwright/test'
import { warnIfSlow } from './waits'

/**
 * ورود با رمز عبور + چالش ضدربات (همان الگوی LoginPage).
 * چند تلاش برای ناپایداری شبکه/سرور؛ هر تلاش چالش تازه می‌گیرد.
 */
export async function loginWithPasswordChallenge(
  request: APIRequestContext,
  baseURL: string,
  username: string,
  password: string,
  options?: { maxAttempts?: number },
): Promise<string> {
  const maxAttempts = options?.maxAttempts ?? 3
  let lastErr: unknown

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const startedAtMs = Date.now()
    try {
      const chRes = await request.post(`${baseURL}/api/auth/login-challenge`, {
        data: {},
      })
      if (!chRes.ok()) {
        const t = await chRes.text()
        throw new Error(`[E2E] login-challenge failed ${chRes.status()}: ${t}`)
      }
      const ch = (await chRes.json()) as { challenge_id: string; question: string }
      const m = ch.question.match(/(\d+)\s*\+\s*(\d+)/)
      const answer = m ? String(Number(m[1]) + Number(m[2])) : '0'

      const loginRes = await request.post(`${baseURL}/api/auth/login-json`, {
        data: {
          username,
          password,
          challenge_id: ch.challenge_id,
          challenge_answer: answer,
        },
      })
      if (!loginRes.ok()) {
        const t = await loginRes.text()
        throw new Error(`[E2E] login-json failed ${loginRes.status()}: ${t}`)
      }
      const body = (await loginRes.json()) as { access_token: string }
      warnIfSlow(`login-json (API) ${username}`, startedAtMs)
      return body.access_token
    } catch (e) {
      lastErr = e
      const msg = e instanceof Error ? e.message : String(e)
      if (attempt >= maxAttempts) {
        throw e
      }
      console.warn(`[E2E] loginWithPasswordChallenge attempt ${attempt}/${maxAttempts} failed — ${msg}`)
      await new Promise((r) => setTimeout(r, 250 * attempt))
    }
  }

  throw lastErr
}
