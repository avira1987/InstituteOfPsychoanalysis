import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createPortal } from 'react-dom'
import { panelApi } from '../services/api'
import { appendNotificationFollow } from '../utils/appendNotificationFollow'

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
      const r = await panelApi.actionNotifications({ limit: 5, offset: 0 })
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
    document.addEventListener('visibilitychange', onVis)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [load])

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
  }, [open, updatePanelPosition, loading, items.length])

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
            <div className="notification-bell-dropdown-head">کارهای نیازمند اقدام</div>
            {loading && items.length === 0 ? (
              <div className="notification-bell-empty muted">در حال بارگذاری…</div>
            ) : null}
            {!loading && items.length === 0 ? (
              <div className="notification-bell-empty muted">موردی برای نمایش نیست.</div>
            ) : null}
            <ul className="notification-bell-list">
              {items.map((it) => (
                <li key={it.notification_id || it.title_fa}>
                  <Link
                    role="menuitem"
                    className="notification-bell-item"
                    to={appendNotificationFollow(it.action_path || '/panel')}
                    onClick={() => setOpen(false)}
                  >
                    <span className="notification-bell-item-title">{it.title_fa}</span>
                    {it.summary_fa ? (
                      <span className="notification-bell-item-summary">{it.summary_fa}</span>
                    ) : null}
                  </Link>
                </li>
              ))}
            </ul>
            <div className="notification-bell-dropdown-foot">
              <button
                type="button"
                className="btn btn-sm btn-primary notification-bell-all-btn"
                onClick={() => {
                  setOpen(false)
                  navigate('/panel/notifications')
                }}
              >
                نمایش همه اعلان‌ها
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
        aria-label="اعلان‌ها و کارهای معلق"
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
