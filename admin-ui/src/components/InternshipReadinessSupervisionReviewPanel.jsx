import React, { useMemo } from 'react'
import { formatStudentCodeDisplay } from '../utils/processDisplay'

/**
 * راهنمای کمیته نظارت برای فرایند ۳۷ — بررسی مجوز و ظرفیت بیمار.
 */
export default function InternshipReadinessSupervisionReviewPanel({
  detail = null,
  user = null,
}) {
  const currentState = detail?.current_state

  const studentLabel = detail?.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : null

  const isSupervisionReview = detail?.process_code === 'internship_readiness_consultation'
    && currentState === 'supervision_committee_review'

  const isCapacityCheck = detail?.process_code === 'internship_readiness_consultation'
    && currentState === 'capacity_check'

  if (!detail || (!isSupervisionReview && !isCapacityCheck)) {
    return null
  }

  return (
    <div
      data-testid="internship-readiness-supervision-review-panel"
      style={{
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
        background: '#fffbeb',
        borderRadius: '10px',
        borderRight: '4px solid #d97706',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#92400e' }}>
        {isSupervisionReview
          ? 'بررسی مجوز آغاز انترنی (فرایند ۳۷)'
          : 'بررسی بیمار برای ارجاع انترن (فرایند ۳۷)'}
      </h4>

      {isSupervisionReview && (
        <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
          پروندهٔ دانشجو را برای ورود به انترنی بررسی کنید. در صورت صدور مجوز، انتقال
          {' '}
          <code style={{ fontSize: '0.8rem' }}>supervision_approved</code>
          {' '}
          را بزنید تا فرایند به تنظیم وقت مصاحبه کمیته پیشرفت برود. در صورت عدم مجوز، انتقال
          {' '}
          <code style={{ fontSize: '0.8rem' }}>supervision_rejected</code>
          {' '}
          را انجام دهید.
        </p>
      )}

      {isCapacityCheck && (
        <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
          بررسی کنید آیا بیمار مناسب برای ارجاع به انترن موجود است. در صورت وجود بیمار، انتقال
          {' '}
          <code style={{ fontSize: '0.8rem' }}>patient_available</code>
          {' '}
          و در غیر این صورت
          {' '}
          <code style={{ fontSize: '0.8rem' }}>no_patient_available</code>
          {' '}
          را ثبت کنید (وضعیت Pending تا تأمین بیمار).
        </p>
      )}

      {studentLabel && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          پروندهٔ دانشجو:
          {' '}
          <strong>{studentLabel}</strong>
        </p>
      )}

      {user?.role && user.role !== 'supervision_committee' && user.role !== 'admin' && (
        <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
          این مرحله معمولاً بر عهدهٔ کمیته نظارت است.
        </p>
      )}
    </div>
  )
}
