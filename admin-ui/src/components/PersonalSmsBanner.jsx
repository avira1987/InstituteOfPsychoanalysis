import React, { useCallback, useEffect, useState } from 'react'
import { panelApi } from '../services/api'

/**
 * بنر inline آخرین پیامک شخصی — برای پورتال‌هایی که پروندهٔ باز ندارند (بدون پاپ‌آپ).
 */
export default function PersonalSmsBanner() {
  const [entry, setEntry] = useState(null)
  const [enabled, setEnabled] = useState(false)

  const load = useCallback(async () => {
    try {
      const r = await panelApi.smsInbox({ limit: 1 })
      const data = r.data || {}
      setEnabled(Boolean(data.enabled))
      const items = Array.isArray(data.items) ? data.items : []
      setEntry(items[0] || null)
    } catch (_) {
      setEnabled(false)
      setEntry(null)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 60_000)
    return () => clearInterval(t)
  }, [load])

  if (!enabled || !entry?.message) return null

  let when = ''
  if (entry.created_at) {
    try {
      when = new Date(entry.created_at).toLocaleString('fa-IR', {
        dateStyle: 'short',
        timeStyle: 'short',
      })
    } catch (_) {
      when = ''
    }
  }

  return (
    <div className="personal-sms-banner card" role="status" data-testid="personal-sms-banner">
      <div className="personal-sms-banner-label">آخرین پیام ارسالی سامانه به شما</div>
      {when ? <time className="personal-sms-banner-time">{when}</time> : null}
      <pre className="personal-sms-banner-message">{entry.message}</pre>
    </div>
  )
}
