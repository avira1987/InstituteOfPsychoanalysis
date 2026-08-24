/** Sentry/GlitchTip client — loaded only when a frontend DSN is present. */

let sentryModule = null

export function getObservabilityConfig() {
  if (typeof window === 'undefined') return {}
  return window.__ANISTITO_OBS__ || {}
}

export function getLastRequestId() {
  if (typeof window === 'undefined') return ''
  return window.__ANISTITO_LAST_REQUEST_ID__ || ''
}

export function setLastRequestId(id) {
  if (typeof window !== 'undefined' && id) {
    window.__ANISTITO_LAST_REQUEST_ID__ = String(id)
  }
}

export function newRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 10)}`
}

export async function initClientObservability() {
  const cfg = getObservabilityConfig()
  const dsn = (cfg.sentryDsn || (import.meta.env && import.meta.env.VITE_SENTRY_DSN) || '').trim()
  if (!dsn) return null
  try {
    const Sentry = await import('@sentry/react')
    Sentry.init({
      dsn,
      environment: cfg.environment || 'production',
      release: cfg.release || undefined,
      sendDefaultPii: false,
      tracesSampleRate: 0,
    })
    sentryModule = Sentry
    return Sentry
  } catch (err) {
    console.warn('[anistito] Sentry init failed', err)
    return null
  }
}

export function captureClientException(error, extra = {}) {
  if (!sentryModule || !error) return
  try {
    sentryModule.captureException(error, { extra })
  } catch (_) {
    /* ignore */
  }
}
