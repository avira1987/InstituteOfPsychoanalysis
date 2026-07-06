import React, { useCallback, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { panelApi } from '../services/api'
import { labelState, labelTriggerEvent, formatActorRole } from '../utils/processDisplay'
import { dispatchPanelNotificationsChanged } from '../utils/panelNotifications'

/**
 * وقتی از اعلان با nf=1 وارد می‌شوید و دیگر اقدامی برای نقش شما روی این نمونه نیست،
 * آخرین گام‌های ثبت‌شده در سیستم را نشان می‌دهد.
 */
export default function ResolvedProcessHistoryBanner({ instanceDetail, availableTransitions }) {
  const [searchParams, setSearchParams] = useSearchParams()

  const nf = searchParams.get('nf') === '1'
  const iidUrl = searchParams.get('instance_id')
  const detailId = instanceDetail?.instance_id != null ? String(instanceDetail.instance_id) : null
  const matches = nf && iidUrl && detailId && String(iidUrl) === detailId

  const nTrans = Array.isArray(availableTransitions) ? availableTransitions.length : 0
  const done = Boolean(instanceDetail?.is_completed || instanceDetail?.is_cancelled)
  const noAction = nTrans === 0 || done

  const stripNf = useCallback(() => {
    const next = new URLSearchParams(searchParams)
    next.delete('nf')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (!matches || !noAction || !detailId) return
    panelApi
      .dismissActionNotification(`process:${detailId}`)
      .then(() => dispatchPanelNotificationsChanged())
      .catch(() => {
        /* ignore */
      })
  }, [matches, noAction, detailId])

  if (!matches || !noAction) return null

  const history = Array.isArray(instanceDetail?.history) ? instanceDetail.history : []
  if (history.length === 0) {
    return (
      <div className="notification-history-banner" role="status">
        <div className="notification-history-banner-inner">
          <p className="notification-history-banner-title">این اعلان دیگر نیاز به اقدام از سوی شما ندارد</p>
          <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.88rem' }}>
            احتمالاً پرونده توسط شما یا همکاران به مرحلهٔ بعد رفته است. اگر سؤالی دارید از ردیابی دانشجو یا هماهنگی اداری پیگیری کنید.
          </p>
          <button type="button" className="btn btn-sm btn-outline" style={{ marginTop: '0.65rem' }} onClick={stripNf}>
            بستن این پیام
          </button>
        </div>
      </div>
    )
  }

  const tail = history.slice(-12)

  return (
    <div className="notification-history-banner" role="region" aria-label="تاریخچه اقدامات ثبت‌شده">
      <div className="notification-history-banner-inner">
        <p className="notification-history-banner-title">تاریخچهٔ اقدامات اخیر روی این پرونده</p>
        <p className="muted" style={{ margin: '0.25rem 0 0.75rem', fontSize: '0.85rem' }}>
          از دید سیستم، در این مرحله دیگر دکمهٔ اقدام مستقیمی برای نقش شما فعال نیست؛ آخرین گام‌های ثبت‌شده:
        </p>
        <ul className="notification-history-list">
          {tail.map((h, idx) => (
            <li key={`${h.entered_at || ''}-${idx}`}>
              <span className="notification-history-step">
                {labelState(h.from_state)} → {labelState(h.to_state)}
              </span>
              <span className="notification-history-meta">
                {labelTriggerEvent(h.trigger_event)}
                {h.actor_role ? ` — ${formatActorRole(h.actor_role)}` : ''}
                {h.entered_at ? ` — ${h.entered_at}` : ''}
              </span>
            </li>
          ))}
        </ul>
        <button type="button" className="btn btn-sm btn-outline" style={{ marginTop: '0.65rem' }} onClick={stripNf}>
          بستن
        </button>
      </div>
    </div>
  )
}
