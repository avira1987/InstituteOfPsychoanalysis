import React from 'react'
import { labelProcess } from '../utils/processDisplay'

/**
 * صندوق اقدام دانشجو — فهرست اقدام‌های فعال از GET /students/me/action-inbox.
 */
export default function StudentActionInbox({
  items = [],
  loading = false,
  onOpenItem,
}) {
  if (loading) {
    return (
      <div
        className="card student-action-inbox"
        data-testid="student-action-inbox"
        style={{ marginBottom: '1.25rem' }}
      >
        <div className="card-header">
          <h3 className="card-title">اقدام‌های شما</h3>
        </div>
        <div style={{ padding: '0 1.25rem 1.25rem', color: 'var(--text-secondary)' }}>
          در حال بارگذاری…
        </div>
      </div>
    )
  }

  if (!items?.length) {
    return null
  }

  return (
    <div
      className="card student-action-inbox"
      data-testid="student-action-inbox"
      style={{ marginBottom: '1.25rem', borderColor: 'var(--primary-light, #dbeafe)' }}
    >
      <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <h3 className="card-title" style={{ margin: 0 }}>اقدام‌های شما</h3>
        <span className="badge badge-primary" data-testid="student-action-inbox-count">
          {items.length.toLocaleString('fa-IR')}
        </span>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <p className="muted" style={{ fontSize: '0.86rem', marginBottom: '0.75rem', lineHeight: 1.65 }}>
          کارهایی که الان از طرف شما در پرتال باز است — برای جزئیات و فرم‌ها، همان مورد را باز کنید.
        </p>
        <ul
          style={{
            listStyle: 'none',
            padding: 0,
            margin: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: '0.55rem',
          }}
        >
          {items.map((item, idx) => {
            const title = item.process_name_fa
              || (item.process_code ? labelProcess(item.process_code) : null)
              || item.short_fa
              || 'اقدام'
            const key = item.instance_id || `hint-${idx}`
            return (
              <li key={key}>
                <button
                  type="button"
                  className="student-action-inbox-item"
                  data-testid={`student-action-inbox-item-${key}`}
                  onClick={() => onOpenItem?.(item)}
                  style={{
                    width: '100%',
                    textAlign: 'right',
                    padding: '0.75rem 1rem',
                    borderRadius: '10px',
                    border: '1px solid #e2e8f0',
                    background: item.is_primary
                      ? 'linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%)'
                      : '#fff',
                    borderRight: item.is_primary ? '4px solid #2563eb' : '4px solid #94a3b8',
                    cursor: 'pointer',
                    fontSize: '0.86rem',
                    lineHeight: 1.65,
                  }}
                >
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', alignItems: 'center', marginBottom: '0.25rem' }}>
                    <span style={{ fontWeight: 700, color: '#1e3a8a' }}>{title}</span>
                    {item.is_primary && (
                      <span className="badge badge-info" style={{ fontSize: '0.68rem' }}>مسیر اصلی</span>
                    )}
                    {item.kind === 'hint' && (
                      <span className="badge badge-outline" style={{ fontSize: '0.68rem' }}>راهنما</span>
                    )}
                  </div>
                  {item.short_fa && item.kind !== 'hint' && (
                    <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>
                      وضعیت: {item.short_fa}
                    </div>
                  )}
                  {item.task_fa && (
                    <div style={{ color: '#334155' }}>
                      <span style={{ fontWeight: 600 }}>اقدام بعدی: </span>
                      {item.task_fa}
                    </div>
                  )}
                  {item.why_fa && (
                    <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.25rem' }}>
                      {item.why_fa}
                    </div>
                  )}
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}
