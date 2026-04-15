import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { panelApi } from '../services/api'

/** راهنمای اقدام نقش در پنل — شناسهٔ آزمایشی برای اتوماسیون تست */
export default function PanelRoleActionQueue() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [err, setErr] = useState(false)
  const role = user?.role ?? ''

  useEffect(() => {
    if (!user) return
    let cancelled = false
    setErr(false)
    panelApi
      .actionQueue()
      .then((r) => {
        if (!cancelled) setData(r.data)
      })
      .catch(() => {
        if (!cancelled) setErr(true)
      })
    return () => {
      cancelled = true
    }
  }, [user])

  if (!user) return null

  if (err) {
    return (
      <div
        className="card"
        style={{ marginBottom: '1.5rem', borderColor: '#e2e8f0', background: '#f8fafc' }}
        data-testid="panel-role-action-queue-error"
      >
        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          راهنمای اقدامات نقش بارگذاری نشد. لطفاً بعداً دوباره تلاش کنید.
        </p>
      </div>
    )
  }

  if (!data?.items?.length) return null

  return (
    <div
      className="card"
      style={{ marginBottom: '1.5rem', borderColor: 'var(--primary-light, #dbeafe)' }}
      data-testid="panel-role-action-queue"
      data-panel-role={role}
    >
      <div className="card-header">
        <h3 className="card-title">راهنمای اقدام برای نقش شما</h3>
        {data.stats?.total != null && (
          <span className="badge badge-primary" data-testid="panel-role-action-queue-count">
            {data.stats.total.toLocaleString('fa-IR')} مورد
          </span>
        )}
      </div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', lineHeight: 1.6 }}>
        بر اساس نقش شما و فرایندهایی که در سامانه با این نقش مرتبط‌اند؛ راهنمای کلی اقدامات معمول — کارهای دقیق همان
        روز را در تب‌های پنل ببینید.
      </p>
      <ol style={{ margin: 0, paddingRight: '1.25rem', lineHeight: 1.75 }}>
        {data.items.map((it, i) => (
          <li
            key={it.id || i}
            data-testid={`panel-pending-item-${role}-${i}`}
            data-item-kind={it.kind || ''}
            data-process-code={it.process_code || ''}
          >
            <span>{it.title_fa}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
