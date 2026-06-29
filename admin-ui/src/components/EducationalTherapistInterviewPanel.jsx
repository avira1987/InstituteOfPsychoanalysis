import React from 'react'
import { formatStudentCodeDisplay } from '../utils/processDisplay'
import { fmtIsoDate, fmtTimeHm, MEETING_TYPE_LABELS } from '../utils/upgradeToEducationalTherapistDisplay'

/**
 * راهنمای کمیته درمان آموزشی — مصاحبه فرایند ۷۱.
 */
export default function EducationalTherapistInterviewPanel({ detail = null, user = null }) {
  const currentState = detail?.current_state
  const ctx = detail?.context_data || {}

  const isScheduling = detail?.process_code === 'upgrade_to_educational_therapist'
    && currentState === 'interview_scheduling'
  const isHeld = detail?.process_code === 'upgrade_to_educational_therapist'
    && currentState === 'interview_held'

  if (!detail || (!isScheduling && !isHeld)) {
    return null
  }

  const studentLabel = detail?.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : null

  return (
    <div
      data-testid="et-interview-panel"
      style={{
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
        background: '#eff6ff',
        borderRadius: '10px',
        borderRight: '4px solid #2563eb',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#1e40af' }}>
        {isScheduling
          ? 'تنظیم وقت مصاحبه ارتقا به درمانگر آموزشی (فرایند ۷۱)'
          : 'نتیجه مصاحبه ارتقا به درمانگر آموزشی (فرایند ۷۱)'}
      </h4>

      {isScheduling && (
        <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
          وقت مصاحبه را در LMS ثبت کنید، فرم زمان را تکمیل کنید و انتقال
          {' '}
          <code style={{ fontSize: '0.8rem' }}>interview_scheduled</code>
          {' '}
          را بزنید. SMS به دانشجو ارسال می‌شود.
        </p>
      )}

      {isHeld && (
        <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
          پس از برگزاری مصاحبه، فرم نتیجه را تکمیل کنید و
          {' '}
          <code style={{ fontSize: '0.8rem' }}>interview_approved</code>
          {' '}
          یا
          {' '}
          <code style={{ fontSize: '0.8rem' }}>interview_rejected</code>
          {' '}
          را ثبت کنید.
        </p>
      )}

      {(ctx.interview_date || ctx.interview_time) && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          زمان ثبت‌شده:
          {' '}
          <strong>
            {fmtIsoDate(ctx.interview_date)}
            {' '}
            —
            {' '}
            {fmtTimeHm(ctx.interview_time)}
            {ctx.meeting_type ? ` (${MEETING_TYPE_LABELS[ctx.meeting_type] || ctx.meeting_type})` : ''}
          </strong>
        </p>
      )}

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
