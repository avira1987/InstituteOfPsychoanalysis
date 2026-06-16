import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { panelApi } from '../services/api'

/**
 * یادآوری یک‌خطی بر اساس همان شمارندهٔ منوی کناری (nav-pending-counts).
 * فقط وقتی n>0 نمایش داده می‌شود.
 */
export default function OperatorPortalReminderBanner({
  portalPath,
  pendingTab = 'pending',
  actionLabel = 'رفتن به وظایف',
}) {
  const [n, setN] = useState(0)

  useEffect(() => {
    let cancelled = false
    panelApi
      .navPendingCounts()
      .then((r) => {
        if (cancelled) return
        const raw = r.data?.counts?.[portalPath]
        const v = typeof raw === 'number' && raw > 0 ? raw : 0
        setN(v)
      })
      .catch(() => {
        if (!cancelled) setN(0)
      })
    return () => {
      cancelled = true
    }
  }, [portalPath])

  if (n === 0) return null

  const to = `${portalPath}?tab=${encodeURIComponent(pendingTab)}`

  return (
    <div className="operator-portal-reminder" role="status" data-testid="operator-portal-reminder">
      <span className="operator-portal-reminder-text">
        <strong>{n.toLocaleString('fa-IR')}</strong>
        {' '}
        مورد در کارتابل سیستم منتظر اقدام نقش شماست.
      </span>
      <Link className="operator-portal-reminder-link" to={to}>
        {actionLabel}
      </Link>
    </div>
  )
}
