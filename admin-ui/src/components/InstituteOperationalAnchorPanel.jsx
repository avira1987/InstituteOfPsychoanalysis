import React from 'react'
import { Link } from 'react-router-dom'
import { INSTITUTE_OPS_LABEL_FA } from '../utils/instituteOperationalAnchor'

const PROCESS_LABELS = {
  fall_semester_preparation: 'آماده‌سازی پاییز',
  winter_semester_preparation: 'آماده‌سازی زمستان',
}

/**
 * پنل پرونده عملیاتی انستیتو (INST-OPS) روی هاب آماده‌سازی ترم.
 * جایگزین نمایش این رکورد در لیست دانشجویان.
 */
export default function InstituteOperationalAnchorPanel({ status }) {
  const anchor = status?.anchor
  if (!anchor) return null

  const code = anchor.student_code || status.anchor_student_code || 'INST-OPS'
  const processes = status?.processes || {}
  const activeCodes = anchor.active_process_codes || []
  const overdueCodes = anchor.overdue_process_codes || []
  const activeCount = anchor.active_count ?? activeCodes.length
  const overdueCount = anchor.overdue_count ?? overdueCodes.length
  const readinessReady = anchor.readiness_ready
  const blockingCount = anchor.readiness_blocking_count ?? 0

  const primaryActive = activeCodes[0]
  const primaryEntry = primaryActive ? processes[primaryActive] : null
  const technicalHref = primaryEntry?.instance_id
    ? `/panel/students?student_id=${anchor.student_id || status.anchor_student_id}&instance_id=${primaryEntry.instance_id}`
    : null

  return (
    <section
      data-testid="institute-ops-anchor-panel"
      style={{
        marginBottom: '1.25rem',
        border: '1px solid #c7d2fe',
        borderRadius: '12px',
        background: 'linear-gradient(135deg, #eef2ff 0%, #f8fafc 55%, #fff 100%)',
        padding: '1rem 1.15rem',
        boxShadow: '0 1px 3px rgba(67, 56, 202, 0.08)',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          gap: '0.75rem',
          alignItems: 'flex-start',
        }}
      >
        <div style={{ flex: '1 1 240px', minWidth: 0 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <h2 style={{ fontSize: '1.05rem', margin: 0 }}>{anchor.label_fa || INSTITUTE_OPS_LABEL_FA}</h2>
            <span
              className="badge badge-info"
              style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.02em' }}
            >
              سیستمی
            </span>
            <code
              style={{
                fontSize: '0.8rem',
                direction: 'ltr',
                background: '#e0e7ff',
                color: '#312e81',
                padding: '0.15rem 0.45rem',
                borderRadius: '6px',
              }}
            >
              {code}
            </code>
          </div>
          <p style={{ margin: '0 0 0.65rem', fontSize: '0.84rem', color: '#475569', lineHeight: 1.7 }}>
            {anchor.description_fa
              || 'رکورد سیستمی برای فرایندهای سطح مؤسسه. دانشجوی واقعی نیست.'}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
            <span
              className={`badge ${activeCount ? 'badge-warning' : 'badge-success'}`}
              style={{ fontSize: '0.75rem' }}
            >
              {activeCount
                ? `${activeCount.toLocaleString('fa-IR')} فرایند فعال`
                : 'فرایند فعالی روی این پرونده نیست'}
            </span>
            {overdueCount > 0 ? (
              <span className="badge badge-danger" style={{ fontSize: '0.75rem' }}>
                {overdueCount.toLocaleString('fa-IR')} مهلت گذشته
              </span>
            ) : null}
            <span
              className={`badge ${readinessReady ? 'badge-success' : 'badge-warning'}`}
              style={{ fontSize: '0.75rem' }}
            >
              {readinessReady
                ? 'پیش‌نیازها کامل'
                : `${(blockingCount || 0).toLocaleString('fa-IR')} پیش‌نیاز ناقص`}
            </span>
          </div>
          {activeCodes.length > 0 ? (
            <ul style={{ margin: '0.65rem 0 0', paddingInlineStart: '1.1rem', fontSize: '0.82rem', color: '#334155', lineHeight: 1.7 }}>
              {activeCodes.map((pc) => {
                const entry = processes[pc] || {}
                return (
                  <li key={pc}>
                    <strong>{PROCESS_LABELS[pc] || pc}</strong>
                    {' — '}
                    {entry.state_name_fa || entry.current_state || '—'}
                    {entry.sla_overdue ? (
                      <span style={{ color: '#b91c1c' }}> (مهلت گذشته)</span>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          ) : null}
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.45rem',
            alignItems: 'stretch',
            minWidth: '11.5rem',
          }}
        >
          {primaryActive && primaryEntry?.instance_id ? (
            <Link
              className="btn btn-primary btn-sm"
              to={`/panel/semester-prep/workbench?process_code=${primaryActive}`}
              style={{ textAlign: 'center', textDecoration: 'none', fontWeight: 700 }}
            >
              ادامه مرحله فعلی
            </Link>
          ) : (
            <Link
              className="btn btn-primary btn-sm"
              to={anchor.readiness_path || '/panel/semester-prep/readiness'}
              style={{ textAlign: 'center', textDecoration: 'none', fontWeight: 700 }}
            >
              مدیریت پیش‌نیازها
            </Link>
          )}
          <Link
            className="btn btn-secondary btn-sm"
            to={anchor.sla_warnings_path || '/panel/semester-prep/sla-warnings'}
            style={{ textAlign: 'center', textDecoration: 'none' }}
          >
            هشدارهای مهلت
          </Link>
          <Link
            className="btn btn-secondary btn-sm"
            to={anchor.academic_calendar_path || '/panel/academic-calendar'}
            style={{ textAlign: 'center', textDecoration: 'none' }}
          >
            تقویم آموزشی
          </Link>
          {technicalHref ? (
            <Link
              className="btn btn-outline btn-sm"
              to={technicalHref}
              style={{ textAlign: 'center', textDecoration: 'none', fontSize: '0.78rem' }}
              title="مشاهدهٔ خام نمونهٔ فرایند، ریست و انتقال دستی"
            >
              جزئیات فنی نمونه
            </Link>
          ) : null}
        </div>
      </div>
    </section>
  )
}
