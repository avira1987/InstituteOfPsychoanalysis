import React from 'react'
import { Link } from 'react-router-dom'
import { getOperatorFollowupDestination } from '../utils/operatorFollowupDeepLinks'
import { labelProcess } from '../utils/processDisplay'

/**
 * فهرست نمونه‌های فرایند باز از GET /api/panel/my-process-inbox — لینک عمیق به همان پرونده.
 */
export default function PortalProcessInbox({ items, title }) {
  if (!items?.length) return null

  return (
    <div
      className="card"
      style={{ marginBottom: '1.5rem', borderColor: 'var(--primary-light, #dbeafe)' }}
      data-testid="portal-process-inbox"
    >
      <div className="card-header">
        <h3 className="card-title">{title || 'کارهای پیشنهادی (بر اساس مرحلهٔ فرایند)'}</h3>
        <span className="badge badge-primary" data-testid="portal-process-inbox-count">
          {items.length.toLocaleString('fa-IR')}
        </span>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <p className="muted" style={{ fontSize: '0.88rem', marginBottom: '0.75rem' }}>
          این فهرست از وضعیت فعلی پرونده‌ها در دیتابیس ساخته می‌شود (نه فقط راهنمای متنی).
        </p>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {items.map((it, idx) => {
            if (it.kind === 'readiness') {
              const href = it.action_href || '/panel/profile'
              return (
                <li key={`readiness-${it.readiness_id || idx}`}>
                  <div
                    style={{
                      padding: '0.75rem 1rem',
                      borderRadius: '8px',
                      border: '1px solid #fbbf24',
                      background: '#fffbeb',
                    }}
                  >
                    <span className="badge badge-warning" style={{ fontSize: '0.68rem', marginBottom: '0.35rem' }}>
                      اقدام لازم (آمادگی نقش)
                    </span>
                    <Link to={href} style={{ display: 'block', fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                      {it.title_fa || 'هشدار آمادگی'}
                    </Link>
                    {it.detail_fa && (
                      <div className="muted" style={{ fontSize: '0.82rem', lineHeight: 1.45, marginBottom: '0.5rem' }}>
                        {it.detail_fa}
                      </div>
                    )}
                    {it.action_label_fa && it.action_href && (
                      <Link className="btn btn-sm btn-primary" to={it.action_href}>
                        {it.action_label_fa}
                      </Link>
                    )}
                  </div>
                </li>
              )
            }
            if (it.kind === 'assignment_grading') {
              const dest = getOperatorFollowupDestination({
                kind: 'assignment_grading',
                student_id: it.student_id,
                assignment_id: it.assignment_id,
              })
              return (
                <li key={`a-${it.submission_id || idx}`}>
                  <Link
                    to={dest.href}
                    style={{ fontSize: '0.9rem', fontWeight: 600 }}
                  >
                    تصحیح تکلیف: {it.title_fa || '—'} — {it.student_code}
                  </Link>
                  <div className="muted" style={{ fontSize: '0.8rem', marginTop: '0.15rem' }}>{dest.hintFa}</div>
                </li>
              )
            }
            const dest = getOperatorFollowupDestination({
              kind: 'process',
              instance_id: it.instance_id,
              student_id: it.student_id,
              responsible_role_code: it.responsible_role_code,
              process_code: it.process_code,
              state_code: it.state_code,
            })
            const ptitle = labelProcess(it.process_code)
            return (
              <li key={it.instance_id || idx}>
                <Link
                  to={dest.href}
                  style={{ fontSize: '0.9rem', fontWeight: 600 }}
                >
                  {ptitle} — {it.student_code} — {it.state_name_fa || it.state_code}
                </Link>
                <div className="muted" style={{ fontSize: '0.8rem', marginTop: '0.15rem' }}>{dest.hintFa}</div>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}
