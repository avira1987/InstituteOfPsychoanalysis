import React from 'react'
import PortalProcessInbox from './PortalProcessInbox'

/**
 * صندوق پیگیری اپراتورها — آیتم‌ها از my-operator-followup (هشدار آمادگی در همان لیست با kind=readiness ادغام می‌شود).
 */
export default function OperatorFollowupSection({
  items = [],
  readinessAlerts: _readinessAlerts = [],
  inboxTitle = 'پرونده‌های باز مرتبط با نقش شما',
  loading = false,
}) {
  const hasInbox = Array.isArray(items) && items.length > 0

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: '1.5rem' }} data-testid="operator-followup-loading">
        <div className="card-header">
          <h3 className="card-title">صندوق پیگیری اپراتورها</h3>
        </div>
        <p style={{ padding: '1rem', color: 'var(--text-secondary)', margin: 0 }}>در حال بارگذاری…</p>
      </div>
    )
  }

  return (
    <div className="operator-followup-section" data-testid="operator-followup-section" style={{ marginBottom: '1.5rem' }}>
      <div className="card" style={{ marginBottom: '1rem', borderColor: 'var(--border, #e5e7eb)' }}>
        <div className="card-header">
          <h3 className="card-title">صندوق پیگیری اپراتورها</h3>
        </div>
        <p className="muted" style={{ fontSize: '0.88rem', padding: '0 1.25rem', marginTop: 0, marginBottom: '0.75rem' }}>
          کارتابل من — شامل پرونده‌های فرایند، تکالیف، و اقدامات آمادگی نقش (مثل تعریف وقت مصاحبه)
        </p>

        {!hasInbox && (
          <div className="empty-state" style={{ padding: '1.25rem 1.5rem 1.5rem' }}>
            <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              موردی در کارتابل ثبت نشده است.
            </p>
          </div>
        )}
      </div>

      <PortalProcessInbox items={items} title={inboxTitle} />
    </div>
  )
}
