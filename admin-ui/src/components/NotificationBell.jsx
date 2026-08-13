import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createPortal } from 'react-dom'
import { panelApi } from '../services/api'
import { appendNotificationFollow } from '../utils/appendNotificationFollow'
import { PANEL_FLASH_CREATED_EVENT } from '../contexts/ToastContext'
import { PANEL_NOTIFICATIONS_CHANGED_EVENT } from '../utils/panelNotifications'

function isFlashItem(it) {
  return it?.kind === 'flash_message'
}

function flashCategory(it) {
  return it?.category === 'system' ? 'system' : 'popup'
}

function ActionItem({ it, onNavigate }) {
  return (
    <li>
      <Link
        role="menuitem"
        className="notification-bell-item notification-bell-item--action"
        to={appendNotificationFollow(it.action_path || '/panel')}
        onClick={onNavigate}
      >
        <span className="notification-bell-item-title">
          <span className="notification-bell-action-badge">اعلان</span>
          {it.title_fa}
        </span>
        {it.summary_fa ? (
          <span className="notification-bell-item-summary">{it.summary_fa}</span>
        ) : null}
      </Link>
    </li>
  )
}

function MessageItem({ it, onNavigate }) {
  const levelClass =
    it.level === 'error'
      ? ' notification-bell-item--flash-error'
      : ' notification-bell-item--flash-success'
  const cat = flashCategory(it)
  const badgeLabel = cat === 'system' ? 'سیستم' : 'پاپ‌آپ'
  const badgeClass =
    cat === 'system' ? 'notification-bell-system-badge' : 'notification-bell-popup-badge'
  return (
    <li>
      <button
        type="button"
        role="menuitem"
        className={`notification-bell-item notification-bell-item--message notification-bell-item--${cat}${levelClass}`}
        onClick={onNavigate}
      >
        <span className="notification-bell-item-title">
          <span className={badgeClass}>{badgeLabel}</span>
          {it.title_fa}
        </span>
        {it.summary_fa ? (
          <span className="notification-bell-item-summary">{it.summary_fa}</span>
        ) : null}
      </button>
    </li>
  )
}

function BellSection({ className, ariaLabel, title, hint, emptyText, items, renderItem }) {
  return (
    <section className={`notification-bell-section ${className}`} aria-label={ariaLabel}>
      <div className="notification-bell-section-head">
        <span className="notification-bell-section-title">{title}</span>
        <span className="notification-bell-section-hint">{hint}</span>
      </div>
      {items.length === 0 ? (
        <div className="notification-bell-section-empty muted">{emptyText}</div>
      ) : (
        <ul className="notification-bell-list">
          {items.map((it) => renderItem(it))}
        </ul>
      )}
    </section>
  )
}

export default function NotificationBell({ variant = 'sidebar' }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const wrapRef = useRef(null)
  const dropdownRef = useRef(null)
  const [panelPos, setPanelPos] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await panelApi.actionNotifications({ limit: 12, offset: 0 })
      setItems(Array.isArray(r.data?.items) ? r.data.items : [])
      setTotal(typeof r.data?.total === 'number' ? r.data.total : 0)
    } catch {
      setItems([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 60000)
    const onVis = () => {
      if (document.visibilityState === 'visible') load()
    }
    const onFlash = () => load()
    const onChanged = () => load()
    document.addEventListener('visibilitychange', onVis)
    window.addEventListener(PANEL_FLASH_CREATED_EVENT, onFlash)
    window.addEventListener(PANEL_NOTIFICATIONS_CHANGED_EVENT, onChanged)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener(PANEL_FLASH_CREATED_EVENT, onFlash)
      window.removeEventListener(PANEL_NOTIFICATIONS_CHANGED_EVENT, onChanged)
    }
  }, [load])

  const { actions, popups, systems } = useMemo(() => {
    const acts = []
    const pops = []
    const sys = []
    for (const it of items) {
      if (!isFlashItem(it)) acts.push(it)
      else if (flashCategory(it) === 'system') sys.push(it)
      else pops.push(it)
    }
    return {
      actions: acts.slice(0, 4),
      popups: pops.slice(0, 3),
      systems: sys.slice(0, 3),
    }
  }, [items])

  const updatePanelPosition = useCallback(() => {
    if (!open || !wrapRef.current) return
    const btn = wrapRef.current.querySelector('button')
    if (!btn) return
    const r = btn.getBoundingClientRect()
    const margin = 10
    const maxW = Math.min(380, Math.max(260, window.innerWidth - margin * 2))
    const center = r.left + r.width / 2
    let leftPx = Math.round(center - maxW / 2)
    const maxLeft = window.innerWidth - maxW - margin
    leftPx = Math.max(margin, Math.min(leftPx, maxLeft))
    const topPx = Math.round(r.bottom + 6)
    setPanelPos({ top: topPx, left: leftPx, width: maxW })
  }, [open])

  useLayoutEffect(() => {
    if (!open) {
      setPanelPos(null)
      return
    }
    updatePanelPosition()
    window.addEventListener('resize', updatePanelPosition)
    window.addEventListener('scroll', updatePanelPosition, true)
    return () => {
      window.removeEventListener('resize', updatePanelPosition)
      window.removeEventListener('scroll', updatePanelPosition, true)
    }
  }, [open, updatePanelPosition, loading, actions.length, popups.length, systems.length])

  useEffect(() => {
    if (!open) return
    const onDoc = (e) => {
      const t = e.target
      const inWrap = wrapRef.current?.contains(t)
      const inDrop = dropdownRef.current?.contains(t)
      if (!inWrap && !inDrop) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const badge =
    total > 0 ? (total > 99 ? '۹۹+' : total.toLocaleString('fa-IR')) : null

  const btnClass =
    variant === 'mobile'
      ? 'notification-bell-btn notification-bell-btn--mobile'
      : 'notification-bell-btn'

  const wrapClass =
    variant === 'mobile' ? 'notification-bell-wrap notification-bell-wrap--mobile' : 'notification-bell-wrap'

  const close = () => setOpen(false)
  const empty = !loading && actions.length === 0 && popups.length === 0 && systems.length === 0
  const showLoading = loading && items.length === 0

  const dropdown =
    open && panelPos
      ? createPortal(
          <div
            ref={dropdownRef}
            className="notification-bell-dropdown notification-bell-dropdown--portal"
            style={{
              position: 'fixed',
              top: `${panelPos.top}px`,
              left: `${panelPos.left}px`,
              width: `${panelPos.width}px`,
              zIndex: 10050,
            }}
            role="menu"
          >
            <div className="notification-bell-dropdown-head">اعلان‌ها و پیام‌ها</div>
            {showLoading ? (
              <div className="notification-bell-empty muted">در حال بارگذاری…</div>
            ) : null}
            {empty ? (
              <div className="notification-bell-empty muted">موردی برای نمایش نیست.</div>
            ) : null}
            {!showLoading && !empty ? (
              <div className="notification-bell-sections">
                <BellSection
                  className="notification-bell-section--actions"
                  ariaLabel="اعلان‌ها"
                  title="اعلان‌ها"
                  hint="کارهای نیازمند اقدام"
                  emptyText="اعلانی نیست."
                  items={actions}
                  renderItem={(it) => (
                    <ActionItem key={it.notification_id || it.title_fa} it={it} onNavigate={close} />
                  )}
                />
                <BellSection
                  className="notification-bell-section--popup"
                  ariaLabel="پاپ‌آپ"
                  title="پاپ‌آپ"
                  hint="پیام‌های toast"
                  emptyText="پاپ‌آپی نیست."
                  items={popups}
                  renderItem={(it) => (
                    <MessageItem
                      key={it.notification_id || it.title_fa}
                      it={it}
                      onNavigate={() => {
                        close()
                        navigate('/panel/notifications?tab=popup')
                      }}
                    />
                  )}
                />
                <BellSection
                  className="notification-bell-section--system"
                  ariaLabel="سیستم"
                  title="سیستم"
                  hint="اعلان‌های بک‌اند"
                  emptyText="پیام سیستمی نیست."
                  items={systems}
                  renderItem={(it) => (
                    <MessageItem
                      key={it.notification_id || it.title_fa}
                      it={it}
                      onNavigate={() => {
                        close()
                        navigate('/panel/notifications?tab=system')
                      }}
                    />
                  )}
                />
              </div>
            ) : null}
            <div className="notification-bell-dropdown-foot">
              <button
                type="button"
                className="btn btn-sm btn-primary notification-bell-all-btn"
                onClick={() => {
                  close()
                  navigate('/panel/notifications')
                }}
              >
                نمایش همه اعلان‌ها و پیام‌ها
              </button>
            </div>
          </div>,
          document.body,
        )
      : null

  return (
    <div className={wrapClass} ref={wrapRef}>
      <button
        type="button"
        className={btnClass}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label="اعلان‌ها و پیام‌ها"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="notification-bell-icon" aria-hidden="true">🔔</span>
        {badge != null ? (
          <span className="notification-bell-badge">{badge}</span>
        ) : null}
      </button>
      {dropdown}
    </div>
  )
}
