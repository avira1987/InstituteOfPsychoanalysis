import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { panelApi } from '../services/api'
import { appendNotificationFollow } from '../utils/appendNotificationFollow'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import { PANEL_FLASH_CREATED_EVENT } from '../contexts/ToastContext'
import {
  PANEL_NOTIFICATIONS_CHANGED_EVENT,
  dispatchPanelNotificationsChanged,
} from '../utils/panelNotifications'

const PAGE = 20

const TABS = [
  { id: 'all', label: 'همه' },
  { id: 'actions', label: 'کارهای معلق' },
  { id: 'messages', label: 'پیام‌های پاپ‌آپ' },
]

function isFlashItem(it) {
  return it?.kind === 'flash_message'
}

export default function NotificationsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'all'
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
    const onFlash = () => loadInitial()
    const onChanged = () => loadInitial()
    window.addEventListener(PANEL_FLASH_CREATED_EVENT, onFlash)
    window.addEventListener(PANEL_NOTIFICATIONS_CHANGED_EVENT, onChanged)
    return () => {
      window.removeEventListener(PANEL_FLASH_CREATED_EVENT, onFlash)
      window.removeEventListener(PANEL_NOTIFICATIONS_CHANGED_EVENT, onChanged)
    }
  }, [loadInitial])

  const dismissItem = async (e, it) => {
    e.preventDefault()
    e.stopPropagation()
    const nid = it?.notification_id
    if (!nid) return
    try {
      await panelApi.dismissActionNotification(nid)
      setItems((prev) => prev.filter((x) => x.notification_id !== nid))
      setTotal((prev) => Math.max(0, prev - 1))
      dispatchPanelNotificationsChanged()
    } catch {
      /* ignore */
    }
  }

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

  const filteredItems = useMemo(() => {
    if (tab === 'messages') return items.filter(isFlashItem)
    if (tab === 'actions') return items.filter((it) => !isFlashItem(it))
    return items
  }, [items, tab])

  const setTab = (id) => {
    const next = new URLSearchParams(searchParams)
    if (id === 'all') next.delete('tab')
    else next.set('tab', id)
    setSearchParams(next, { replace: true })
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <div className="loading-spinner" />
      </div>
    )
  }

  const emptyMessage =
    tab === 'messages'
      ? 'هنوز پیام پاپ‌آپی ذخیره نشده است.'
      : tab === 'actions'
        ? 'در حال حاضر موردی برای اقدام در کارتابل شما ثبت نشده است.'
        : 'در حال حاضر اعلانی برای نمایش وجود ندارد.'

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">همه اعلان‌ها</h1>
          <p className="page-subtitle">
            اقدام‌های پیشنهادی و پیام‌های سیستم
            {total > 0 ? ` — ${total.toLocaleString('fa-IR')} مورد` : ''}
          </p>
        </div>
      </div>

      <div className="notifications-page-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`notifications-page-tab${tab === t.id ? ' notifications-page-tab--active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {filteredItems.length === 0 ? (
        <div className="card" style={{ padding: '1.5rem' }}>
          <p className="muted" style={{ margin: 0 }}>{emptyMessage}</p>
        </div>
      ) : (
        <ul className="notifications-page-list">
          {filteredItems.map((it) => {
            const flash = isFlashItem(it)
            const when = it.sort_at ? formatShamsiTehran(it.sort_at) : ''
            if (flash) {
              return (
                <li
                  key={it.notification_id || `${it.title_fa}-${it.sort_at}`}
                  className={`notifications-page-row notifications-page-row--flash notifications-page-row--flash-${it.level || 'success'}`}
                >
                  <div className="notifications-page-flash notifications-page-row-inner">
                    <div className="notifications-page-flash-body">
                      <span className="notifications-page-title">
                        <span className="notification-bell-flash-badge">پیام</span>
                        {it.title_fa}
                      </span>
                      {it.summary_fa ? (
                        <span className="notifications-page-summary">{it.summary_fa}</span>
                      ) : null}
                      {when ? (
                        <span className="notifications-page-when muted">{when}</span>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      className="notifications-page-dismiss"
                      title="بستن"
                      aria-label="بستن این پیام"
                      onClick={(e) => dismissItem(e, it)}
                    >
                      ✕
                    </button>
                  </div>
                </li>
              )
            }
            return (
              <li key={it.notification_id || `${it.title_fa}-${it.sort_at}`} className="notifications-page-row">
                <div className="notifications-page-row-inner">
                  <Link className="notifications-page-link" to={appendNotificationFollow(it.action_path || '/panel')}>
                    <span className="notifications-page-title">{it.title_fa}</span>
                    {it.summary_fa ? (
                      <span className="notifications-page-summary">{it.summary_fa}</span>
                    ) : null}
                  </Link>
                  <button
                    type="button"
                    className="notifications-page-dismiss"
                    title="انجام شد / بستن"
                    aria-label="حذف از لیست وظایف"
                    onClick={(e) => dismissItem(e, it)}
                  >
                    ✓
                  </button>
                </div>
              </li>
            )
          })}
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
