import React from 'react'
import { formatStudentCodeDisplay } from '../utils/processDisplay'

/**
 * راهنمای بررسی درمانگر پیشنهادی — فرایند ۷۱.
 */
export default function EducationalTherapistTherapistReviewPanel({ detail = null, user = null }) {
  const currentState = detail?.current_state
  const ctx = detail?.context_data || {}

  if (
    !detail
    || detail.process_code !== 'upgrade_to_educational_therapist'
    || currentState !== 'therapist_committee_review'
  ) {
    return null
  }

  const studentLabel = detail?.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : null
  const therapistLabel = ctx.selected_therapist_label || ctx.therapist_id || '—'

  return (
    <div
      data-testid="et-therapist-review-panel"
      style={{
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
        background: '#f5f3ff',
        borderRadius: '10px',
        borderRight: '4px solid #7c3aed',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#5b21b6' }}>
        بررسی درمانگر پیشنهادی (فرایند ۷۱)
      </h4>

      <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
        درمانگر پیشنهادی متقاضی را بررسی کنید. در صورت تأیید
        {' '}
        <code style={{ fontSize: '0.8rem' }}>approved</code>
        {' '}
        و در صورت عدم تأیید
        {' '}
        <code style={{ fontSize: '0.8rem' }}>rejected</code>
        {' '}
        (دانشجو باید درمانگر دیگری انتخاب کند).
      </p>

      <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
        درمانگر پیشنهادی:
        {' '}
        <strong>{therapistLabel}</strong>
      </p>

      {studentLabel && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          پروندهٔ دانشجو:
          {' '}
          <strong>{studentLabel}</strong>
        </p>
      )}

      {user?.role && user.role !== 'education_committee' && user.role !== 'admin' && (
        <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
          این مرحله بر عهدهٔ کمیته درمان آموزشی و سوپرویژن است.
        </p>
      )}
    </div>
  )
}
