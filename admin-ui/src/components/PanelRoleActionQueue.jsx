import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { panelApi } from '../services/api'

/**
 * صف اقدامات پیشنهادی برای نقش جاری — از GET /api/panel/action-queue
 * data-testid برای اتوماسیون وب (Playwright)
 */
export default function PanelRoleActionQueue() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const role = user?.role || 'unknown'

  useEffect(() => {
    if (!user) return
    let cancelled = false
    setErr(null)
    panelApi
      .actionQueue()
      .then((r) => {
        if (!cancelled) setData(r.data)
      })
      .catch((e) => {
        if (!cancelled) setErr(e?.response?.data?.detail || e.message || 'خطا')
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
          راهنمای اقدامات نقش بارگذاری نشد ({String(err)})
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
        <h3 className="card-title">اقدامات منتظر انجام (راهنمای نقش)</h3>
        {data.stats?.total != null && (
          <span className="badge badge-primary" data-testid="panel-role-action-queue-count">
            {data.stats.total.toLocaleString('fa-IR')} مورد
          </span>
        )}
      </div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', lineHeight: 1.6 }}>
        بر اساس نقش شما در سامانه و فرایندهای رجیستری که این نقش در آن‌ها ذکر شده؛ برای آموزش تیم و سناریوهای اتوماسیون.
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
            {it.process_code ? (
              <code
                style={{
                  fontSize: '0.72rem',
                  marginRight: '0.35rem',
                  padding: '0.1rem 0.35rem',
                  borderRadius: '4px',
                  background: '#f1f5f9',
                }}
                dir="ltr"
              >
                {it.process_code}
              </code>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  )
}
