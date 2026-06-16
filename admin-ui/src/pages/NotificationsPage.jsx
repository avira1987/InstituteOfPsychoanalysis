import React, { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { panelApi } from '../services/api'
import { appendNotificationFollow } from '../utils/appendNotificationFollow'

const PAGE = 20

export default function NotificationsPage() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)

  const loadInitial = useCallback(async () => {
    setLoading(true)
    try {
      const r = await panelApi.actionNotifications({ limit: PAGE, offset: 0 })
      setItems(Array.isArray(r.data?.items) ? r.data.items : [])
      setTotal(typeof r.data?.total === 'number' ? r.data.total : 0)
      setOffset((r.data?.items?.length) || 0)
    } catch {
      setItems([])
      setTotal(0)
      setOffset(0)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadInitial()
  }, [loadInitial])

  const loadMore = async () => {
    if (loadingMore || items.length >= total) return
    setLoadingMore(true)
    try {
      const r = await panelApi.actionNotifications({ limit: PAGE, offset })
      const next = Array.isArray(r.data?.items) ? r.data.items : []
      setItems((prev) => [...prev, ...next])
      setOffset((o) => o + next.length)
    } catch { /* ignore */ } finally {
      setLoadingMore(false)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <div className="loading-spinner" />
      </div>
    )
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">همه اعلان‌ها</h1>
          <p className="page-subtitle">
            فهرست اقدام‌های پیشنهادی سیستم بر اساس نقش شما
            {total > 0 ? ` — ${total.toLocaleString('fa-IR')} مورد` : ''}
          </p>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="card" style={{ padding: '1.5rem' }}>
          <p className="muted" style={{ margin: 0 }}>در حال حاضر موردی برای اقدام در کارتابل شما ثبت نشده است.</p>
        </div>
      ) : (
        <ul className="notifications-page-list">
          {items.map((it) => (
            <li key={it.notification_id || `${it.title_fa}-${it.sort_at}`} className="notifications-page-row">
              <Link className="notifications-page-link" to={appendNotificationFollow(it.action_path || '/panel')}>
                <span className="notifications-page-title">{it.title_fa}</span>
                {it.summary_fa ? (
                  <span className="notifications-page-summary">{it.summary_fa}</span>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      )}

      {items.length < total ? (
        <div style={{ marginTop: '1.25rem', textAlign: 'center' }}>
          <button
            type="button"
            className="btn btn-outline"
            disabled={loadingMore}
            onClick={loadMore}
          >
            {loadingMore ? 'در حال بارگذاری…' : 'بارگذاری بیشتر'}
          </button>
        </div>
      ) : null}
    </div>
  )
}
