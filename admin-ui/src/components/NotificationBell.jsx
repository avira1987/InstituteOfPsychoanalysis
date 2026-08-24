import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createPortal } from 'react-dom'
import { panelApi } from '../services/api'
import { appendNotificationFollow } from '../utils/appendNotificationFollow'
import { PANEL_FLASH_CREATED_EVENT } from '../contexts/ToastContext'
import { PANEL_NOTIFICATIONS_CHANGED_EVENT } from '../utils/panelNotifications'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import {
  ACTION_GROUPS,
  BELL_TABS,
  actionGroupMeta,
  classifyNotifications,
  flashCategory,
  tabCount,
} from '../utils/notificationCategories'

const BELL_LIMITS = {
  all: { actions: 4, popups: 3, systems: 3, group: 3 },
  actions: { actions: 12, popups: 0, systems: 0, group: 6 },
  popup: { actions: 0, popups: 10, systems: 0, group: 0 },
  system: { actions: 0, popups: 0, systems: 10, group: 0 },
}

function ItemWhen({ iso }) {
  if (!iso) return null
  return (
    <span className="notification-bell-item-when" dir="ltr">
      {formatShamsiTehran(iso, { includeMonthName: false })}
    </span>
  )
}

function ActionItem({ it, onNavigate }) {
  const group = actionGroupMeta(it)
  return (
    <li>
      <Link
        className={`notification-bell-item notification-bell-item--action notification-bell-item--group-${group.id}`}
        to={appendNotificationFollow(it.action_path || '/panel')}
        onClick={onNavigate}
      >
        <span className="notification-bell-item-title">
          <span className={`notification-bell-action-badge notification-bell-action-badge--${group.id}`}>
            {group.label}
          </span>
          {it.title_fa}
        </span>
        {it.summary_fa ? (
          <span className="notification-bell-item-summary">{it.summary_fa}</span>
        ) : null}
        <ItemWhen iso={it.sort_at} />
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
        <ItemWhen iso={it.sort_at} />
      </button>
    </li>
  )
}

function BellSection({ className, ariaLabel, title, hint, count, emptyText, items, renderItem }) {
  if (!items.length && !emptyText) return null
  return (
    <section className={`notification-bell-section ${className}`} aria-label={ariaLabel}>
      <div className="notification-bell-section-head">
        <span className="notification-bell-section-title">
          {title}
          {count > 0 ? (
            <span className="notification-bell-section-count">{count.toLocaleString('fa-IR')}</span>
          ) : null}
        </span>
        {hint ? <span className="notification-bell-section-hint">{hint}</span> : null}
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

function itemKey(it) {
  return it.notification_id || `${it.title_fa}-${it.sort_at}`
}

export default function NotificationBell({ variant = 'sidebar' }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState('all')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const wrapRef = useRef(null)
  const dropdownRef = useRef(null)
  const [panelPos, setPanelPos] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await panelApi.actionNotifications({ limit: 30, offset: 0 })
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

  const classified = useMemo(() => classifyNotifications(items), [items])
  const limits = BELL_LIMITS[tab] || BELL_LIMITS.all

  const sliced = useMemo(() => {
    const actionGroups = Object.fromEntries(
      ACTION_GROUPS.map((g) => [g.id, (classified.actionGroups[g.id] || []).slice(0, limits.group)]),
    )
    return {
      actions: classified.actions.slice(0, limits.actions),
      popups: classified.popups.slice(0, limits.popups),
      systems: classified.systems.slice(0, limits.systems),
      actionGroups,
    }
  }, [classified, limits])

  const updatePanelPosition = useCallback(() => {
    if (!open || !wrapRef.current) return
    const btn = wrapRef.current.querySelector('button')
    if (!btn) return
    const r = btn.getBoundingClientRect()
    const margin = 10
    const maxW = Math.min(400, Math.max(280, window.innerWidth - margin * 2))
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
  }, [open, updatePanelPosition, loading, tab, sliced.actions.length, sliced.popups.length, sliced.systems.length])

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
  const emptyAll =
    classified.actions.length === 0 &&
    classified.popups.length === 0 &&
    classified.systems.length === 0
  const empty =
    !loading &&
    ((tab === 'all' && emptyAll) ||
      (tab === 'actions' && classified.actions.length === 0) ||
      (tab === 'popup' && classified.popups.length === 0) ||
      (tab === 'system' && classified.systems.length === 0))
  const showLoading = loading && items.length === 0

  const emptyText =
    tab === 'actions'
      ? 'اعلانی برای اقدام نیست.'
      : tab === 'popup'
        ? 'پیام پاپ‌آپی نیست.'
        : tab === 'system'
          ? 'پیام سیستمی نیست.'
          : 'موردی برای نمایش نیست.'

  const goAll = () => {
    close()
    const path = tab === 'all' ? '/panel/notifications' : `/panel/notifications?tab=${tab}`
    navigate(path)
  }

  const renderAction = (it) => (
    <ActionItem key={itemKey(it)} it={it} onNavigate={close} />
  )
  const renderMessage = (targetTab) => (it) => (
    <MessageItem
      key={itemKey(it)}
      it={it}
      onNavigate={() => {
        close()
        navigate(`/panel/notifications?tab=${targetTab}`)
      }}
    />
  )

  const renderActionGroups = (showEmpty) =>
    ACTION_GROUPS.map((g) => {
      const groupItems = sliced.actionGroups[g.id] || []
      if (!groupItems.length && !showEmpty) return null
      return (
        <BellSection
          key={g.id}
          className={`notification-bell-section--actions notification-bell-section--group-${g.id}`}
          ariaLabel={g.label}
          title={g.label}
          hint={g.hint}
          count={classified.actionGroups[g.id]?.length || 0}
          emptyText={showEmpty ? `${g.label} نیست.` : ''}
          items={groupItems}
          renderItem={renderAction}
        />
      )
    })

  const renderBody = () => {
    if (tab === 'actions') {
      const hasAny = ACTION_GROUPS.some((g) => (classified.actionGroups[g.id] || []).length > 0)
      if (!hasAny) return null
      return <div className="notification-bell-sections">{renderActionGroups(false)}</div>
    }
    if (tab === 'popup') {
      return (
        <div className="notification-bell-sections">
          <BellSection
            className="notification-bell-section--popup"
            ariaLabel="پاپ‌آپ"
            title="پاپ‌آپ"
            hint="پیام‌های toast"
            count={classified.popups.length}
            emptyText=""
            items={sliced.popups}
            renderItem={renderMessage('popup')}
          />
        </div>
      )
    }
    if (tab === 'system') {
      return (
        <div className="notification-bell-sections">
          <BellSection
            className="notification-bell-section--system"
            ariaLabel="سیستم"
            title="سیستم"
            hint="اعلان‌های بک‌اند"
            count={classified.systems.length}
            emptyText=""
            items={sliced.systems}
            renderItem={renderMessage('system')}
          />
        </div>
      )
    }
    return (
      <div className="notification-bell-sections">
        {classified.actions.length > 0 ? (
          <section className="notification-bell-section notification-bell-section--actions" aria-label="اعلان‌ها">
            <div className="notification-bell-section-head">
              <span className="notification-bell-section-title">
                اعلان‌ها
                <span className="notification-bell-section-count">
                  {classified.actions.length.toLocaleString('fa-IR')}
                </span>
              </span>
              <span className="notification-bell-section-hint">کارهای نیازمند اقدام</span>
            </div>
            {renderActionGroups(false)}
          </section>
        ) : null}
        {classified.popups.length > 0 ? (
          <BellSection
            className="notification-bell-section--popup"
            ariaLabel="پاپ‌آپ"
            title="پاپ‌آپ"
            hint="پیام‌های toast"
            count={classified.popups.length}
            emptyText=""
            items={sliced.popups}
            renderItem={renderMessage('popup')}
          />
        ) : null}
        {classified.systems.length > 0 ? (
          <BellSection
            className="notification-bell-section--system"
            ariaLabel="سیستم"
            title="سیستم"
            hint="اعلان‌های بک‌اند"
            count={classified.systems.length}
            emptyText=""
            items={sliced.systems}
            renderItem={renderMessage('system')}
          />
        ) : null}
      </div>
    )
  }

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
            role="dialog"
            aria-label="اعلان‌ها و پیام‌ها"
          >
            <div className="notification-bell-dropdown-head">اعلان‌ها و پیام‌ها</div>
            <div className="notification-bell-tabs" role="tablist" aria-label="دسته‌بندی اعلان‌ها و پیام‌ها">
              {BELL_TABS.map((t) => {
                const count = tabCount(t.id, classified)
                const active = tab === t.id
                return (
                  <button
                    key={t.id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    className={`notification-bell-tab notification-bell-tab--${t.id}${
                      active ? ' notification-bell-tab--active' : ''
                    }`}
                    onClick={() => setTab(t.id)}
                  >
                    {t.label}
                    {count > 0 ? (
                      <span className="notification-bell-tab-count">{count.toLocaleString('fa-IR')}</span>
                    ) : null}
                  </button>
                )
              })}
            </div>
            {showLoading ? (
              <div className="notification-bell-empty muted">در حال بارگذاری…</div>
            ) : null}
            {empty ? (
              <div className="notification-bell-empty muted">{emptyText}</div>
            ) : null}
            {!showLoading && !empty ? renderBody() : null}
            <div className="notification-bell-dropdown-foot">
              <button
                type="button"
                className="btn btn-sm btn-primary notification-bell-all-btn"
                onClick={goAll}
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
