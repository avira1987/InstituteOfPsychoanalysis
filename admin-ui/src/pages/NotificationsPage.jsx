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
  { id: 'actions', label: 'اعلان‌ها' },
  { id: 'popup', label: 'پاپ‌آپ' },
  { id: 'system', label: 'سیستم' },
]

function isFlashItem(it) {
  return it?.kind === 'flash_message'
}

function flashCategory(it) {
  return it?.category === 'system' ? 'system' : 'popup'
}

function ActionRow({ it, onDismiss }) {
  return (
    <li className="notifications-page-row notifications-page-row--action">
      <div className="notifications-page-row-inner">
        <Link className="notifications-page-link" to={appendNotificationFollow(it.action_path || '/panel')}>
          <span className="notifications-page-title">
            <span className="notification-bell-action-badge">اعلان</span>
            {it.title_fa}
          </span>
          {it.summary_fa ? (
            <span className="notifications-page-summary">{it.summary_fa}</span>
          ) : null}
        </Link>
        <button
          type="button"
          className="notifications-page-dismiss"
          title="انجام شد / بستن"
          aria-label="حذف از لیست وظایف"
          onClick={(e) => onDismiss(e, it)}
        >
          ✓
        </button>
      </div>
    </li>
  )
}

function MessageRow({ it, onDismiss }) {
  const when = it.sort_at ? formatShamsiTehran(it.sort_at) : ''
  const cat = flashCategory(it)
  const badgeLabel = cat === 'system' ? 'سیستم' : 'پاپ‌آپ'
  const badgeClass =
    cat === 'system' ? 'notification-bell-system-badge' : 'notification-bell-popup-badge'
  return (
    <li
      className={`notifications-page-row notifications-page-row--flash notifications-page-row--flash-${it.level || 'success'} notifications-page-row--${cat}`}
    >
      <div className="notifications-page-flash notifications-page-row-inner">
        <div className="notifications-page-flash-body">
          <span className="notifications-page-title">
            <span className={badgeClass}>{badgeLabel}</span>
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
          onClick={(e) => onDismiss(e, it)}
        >
          ✕
        </button>
      </div>
    </li>
  )
}

function SectionBlock({ ariaLabel, title, hint, emptyText, items, renderRow }) {
  return (
    <section className="notifications-page-section" aria-label={ariaLabel}>
      <div className="notifications-page-section-head">
        <h2 className="notifications-page-section-title">{title}</h2>
        <p className="notifications-page-section-hint muted">{hint}</p>
      </div>
      {items.length === 0 ? (
        <div className="card" style={{ padding: '1rem 1.25rem' }}>
          <p className="muted" style={{ margin: 0 }}>{emptyText}</p>
        </div>
      ) : (
        <ul className="notifications-page-list">
          {items.map((it) => renderRow(it))}
        </ul>
      )}
    </section>
  )
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

  const { actions, popups, systems } = useMemo(() => {
    const acts = []
    const pops = []
    const sys = []
    for (const it of items) {
      if (!isFlashItem(it)) acts.push(it)
      else if (flashCategory(it) === 'system') sys.push(it)
      else pops.push(it)
    }
    return { actions: acts, popups: pops, systems: sys }
  }, [items])

  const filteredItems = useMemo(() => {
    if (tab === 'popup') return popups
    if (tab === 'system') return systems
    if (tab === 'actions') return actions
    if (tab === 'messages') return [...popups, ...systems]
    return items
  }, [items, tab, actions, popups, systems])

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
    tab === 'popup'
      ? 'هنوز پیام پاپ‌آپی ذخیره نشده است.'
      : tab === 'system'
        ? 'هنوز پیام سیستمی ذخیره نشده است.'
        : tab === 'actions'
          ? 'در حال حاضر اعلانی برای اقدام در کارتابل شما ثبت نشده است.'
          : 'در حال حاضر اعلان یا پیامی برای نمایش وجود ندارد.'

  const rowKey = (it) => it.notification_id || `${it.title_fa}-${it.sort_at}`

  const renderAllSeparated = () => {
    if (actions.length === 0 && popups.length === 0 && systems.length === 0) {
      return (
        <div className="card" style={{ padding: '1.5rem' }}>
          <p className="muted" style={{ margin: 0 }}>{emptyMessage}</p>
        </div>
      )
    }
    return (
      <div className="notifications-page-sections">
        <SectionBlock
          ariaLabel="اعلان‌ها"
          title="اعلان‌ها"
          hint="کارهای نیازمند اقدام در کارتابل"
          emptyText="اعلانی نیست."
          items={actions}
          renderRow={(it) => <ActionRow key={rowKey(it)} it={it} onDismiss={dismissItem} />}
        />
        <SectionBlock
          ariaLabel="پیام‌های پاپ‌آپ"
          title="پاپ‌آپ"
          hint="پیام‌های toast رابط کاربری برای مرور"
          emptyText="پیام پاپ‌آپی نیست."
          items={popups}
          renderRow={(it) => <MessageRow key={rowKey(it)} it={it} onDismiss={dismissItem} />}
        />
        <SectionBlock
          ariaLabel="پیام‌های سیستم"
          title="سیستم"
          hint="اعلان‌های بک‌اند مثل تقویم و مصاحبه"
          emptyText="پیام سیستمی نیست."
          items={systems}
          renderRow={(it) => <MessageRow key={rowKey(it)} it={it} onDismiss={dismissItem} />}
        />
      </div>
    )
  }

  const tabCount = (id) => {
    if (id === 'actions' && actions.length > 0) return actions.length
    if (id === 'popup' && popups.length > 0) return popups.length
    if (id === 'system' && systems.length > 0) return systems.length
    return null
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">اعلان‌ها و پیام‌ها</h1>
          <p className="page-subtitle">
            اعلان‌ها، پاپ‌آپ و پیام‌های سیستم جداگانه
            {total > 0 ? ` — ${total.toLocaleString('fa-IR')} مورد` : ''}
          </p>
        </div>
      </div>

      <div className="notifications-page-tabs" role="tablist">
        {TABS.map((t) => {
          const count = tabCount(t.id)
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id || (t.id === 'popup' && tab === 'messages')}
              className={`notifications-page-tab${
                tab === t.id || (t.id === 'popup' && tab === 'messages')
                  ? ' notifications-page-tab--active'
                  : ''
              }`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {count != null ? (
                <span className="notifications-page-tab-count">{count.toLocaleString('fa-IR')}</span>
              ) : null}
            </button>
          )
        })}
      </div>

      {tab === 'all' ? (
        renderAllSeparated()
      ) : filteredItems.length === 0 ? (
        <div className="card" style={{ padding: '1.5rem' }}>
          <p className="muted" style={{ margin: 0 }}>{emptyMessage}</p>
        </div>
      ) : (
        <ul className="notifications-page-list">
          {filteredItems.map((it) =>
            isFlashItem(it) ? (
              <MessageRow key={rowKey(it)} it={it} onDismiss={dismissItem} />
            ) : (
              <ActionRow key={rowKey(it)} it={it} onDismiss={dismissItem} />
            ),
          )}
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
