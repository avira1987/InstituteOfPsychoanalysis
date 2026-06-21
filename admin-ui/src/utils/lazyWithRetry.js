import { lazy } from 'react'

const CHUNK_RELOAD_KEY = 'anistito-chunk-reload'

function isChunkLoadError(error) {
  const msg = error?.message || String(error)
  return (
    msg.includes('Failed to fetch dynamically imported module')
    || msg.includes('Importing a module script failed')
    || msg.includes('error loading dynamically imported module')
  )
}

/**
 * lazy import با بازیابی خودکار بعد از deploy: اگر hash قدیمی در کش مرورگر باشد، یک‌بار reload.
 */
export function lazyWithRetry(importFn) {
  return lazy(() =>
    importFn().catch((error) => {
      if (!isChunkLoadError(error)) throw error
      const reloaded = sessionStorage.getItem(CHUNK_RELOAD_KEY)
      if (!reloaded) {
        sessionStorage.setItem(CHUNK_RELOAD_KEY, '1')
        window.location.reload()
        return new Promise(() => {})
      }
      sessionStorage.removeItem(CHUNK_RELOAD_KEY)
      throw error
    }),
  )
}
