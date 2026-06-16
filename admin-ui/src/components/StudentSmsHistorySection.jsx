import React, { useCallback, useEffect, useState } from 'react'
import { panelApi } from '../services/api'
import { getSmsTemplateLabel } from '../utils/smsTemplateLabels'

const POLL_MS = 60_000
const FETCH_LIMIT = 30
const OLDER_PREVIEW_COUNT = 3

function formatWhen(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return Number.isFinite(d.valueOf())
      ? d.toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })
      : ''
  } catch (_) {
    return ''
  }
}

/**
 * @param {{ entry: object, index: number, variant?: 'latest' | 'older' }} props
 */
function SmsHistoryItem({ entry, index, variant = 'older' }) {
  const label = getSmsTemplateLabel(entry.template_key, entry.kind)
  const when = formatWhen(entry.created_at)
  return (
    <li
      className={`student-sms-history-item ${variant === 'latest' ? 'student-sms-history-item--latest' : ''}`}
      data-testid={`student-sms-history-item-${index}`}
    >
      <div className="student-sms-history-item-head">
        <span className="student-sms-history-item-label">
          {variant === 'latest' ? 'آخرین پیامک' : label}
        </span>
        {when ? (
          <time className="student-sms-history-item-when" dateTime={entry.created_at || undefined}>
            {when}
          </time>
        ) : null}
      </div>
      {variant === 'latest' && label !== 'آخرین پیامک' && label !== 'پیامک' ? (
        <div className="student-sms-history-item-subject">{label}</div>
      ) : null}
      <pre className="student-sms-history-message">{entry.message}</pre>
    </li>
  )
}

/**
 * تاریخچهٔ پیامک‌های ارسالی به دانشجو (بدون کد ورود) — زیر «وضعیت فعلی».
 * @param {{ refreshKey?: string | number | null, className?: string }} props
 */
export default function StudentSmsHistorySection({ refreshKey = null, className = '' }) {
  const [enabled, setEnabled] = useState(false)
  const [items, setItems] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [olderOpen, setOlderOpen] = useState(false)
  const [showAllOlder, setShowAllOlder] = useState(false)

  const load = useCallback(async () => {
    try {
      const r = await panelApi.studentSmsHistory({ limit: FETCH_LIMIT })
      setEnabled(Boolean(r.data?.enabled))
      setItems(Array.isArray(r.data?.items) ? r.data.items : [])
    } catch (_) {
      setEnabled(false)
      setItems([])
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, POLL_MS)
    const onVis = () => {
      if (document.visibilityState === 'visible') load()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [load, refreshKey])

  useEffect(() => {
    setShowAllOlder(false)
  }, [refreshKey, items.length])

  if (!loaded || !enabled || items.length === 0) return null

  const latest = items[0]
  const older = items.slice(1)
  const hasOlder = older.length > 0
  const hiddenOlderCount = Math.max(0, older.length - OLDER_PREVIEW_COUNT)
  const visibleOlder = showAllOlder ? older : older.slice(0, OLDER_PREVIEW_COUNT)
  const showMoreButton = hasOlder && !showAllOlder && hiddenOlderCount > 0
  const olderScrollLimited = visibleOlder.length >= 2

  return (
    <section
      className={`student-sms-history ${className}`.trim()}
      data-testid="student-sms-history"
      aria-label="پیامک‌های ارسالی"
    >
      <div className="student-sms-history-header">
        <h4 className="student-sms-history-title">پیامک‌های ارسالی</h4>
        {hasOlder ? (
          <button
            type="button"
            className="student-sms-history-toggle"
            data-testid="student-sms-history-toggle"
            aria-expanded={olderOpen}
            onClick={() => setOlderOpen((open) => !open)}
          >
            {olderOpen ? 'بستن پیامک‌های قبلی' : `پیامک‌های قبلی (${older.length.toLocaleString('fa-IR')})`}
            <span className="student-sms-history-toggle-icon" aria-hidden="true">
              {olderOpen ? '▲' : '▼'}
            </span>
          </button>
        ) : null}
      </div>

      <ul className="student-sms-history-list student-sms-history-list--latest">
        <SmsHistoryItem entry={latest} index={0} variant="latest" />
      </ul>

      {hasOlder && olderOpen ? (
        <div className="student-sms-history-older" data-testid="student-sms-history-older">
          <p className="student-sms-history-older-label">پیامک‌های قبلی</p>
          <div
            className={`student-sms-history-older-scroll ${olderScrollLimited ? 'student-sms-history-older-scroll--limited' : ''}`}
          >
            <ul className="student-sms-history-list">
              {visibleOlder.map((entry, idx) => (
                <SmsHistoryItem
                  key={entry.id || `${entry.created_at}-${idx + 1}`}
                  entry={entry}
                  index={idx + 1}
                />
              ))}
            </ul>
          </div>
          {showMoreButton ? (
            <button
              type="button"
              className="student-sms-history-more-btn"
              data-testid="student-sms-history-show-more"
              onClick={() => setShowAllOlder(true)}
            >
              نمایش بیشتر ({hiddenOlderCount.toLocaleString('fa-IR')} پیامک دیگر)
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
