import React, { useMemo } from 'react'
import {
  fmtIsoDate,
  resolveInterviewSchedule,
  resolveInterviewResult,
} from '../utils/internshipReadinessConsultationDisplay'
import { formatStudentCodeDisplay } from '../utils/processDisplay'

/**
 * راهنمای کمیته پیشرفت برای فرایند ۳۷ — مصاحبه و دریافت سفته.
 */
export default function InternshipReadinessProgressPanel({
  detail = null,
  user = null,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state

  const interview = useMemo(() => resolveInterviewSchedule(ctx), [ctx])
  const result = useMemo(() => resolveInterviewResult(ctx), [ctx])

  const isInterviewScheduling = detail?.process_code === 'internship_readiness_consultation'
    && currentState === 'interview_scheduling'

  const isInterviewHeld = detail?.process_code === 'internship_readiness_consultation'
    && currentState === 'interview_held'

  const isPromissoryNote = detail?.process_code === 'internship_readiness_consultation'
    && currentState === 'promissory_note'

  if (!detail || (!isInterviewScheduling && !isInterviewHeld && !isPromissoryNote)) {
    return null
  }

  const studentLabel = detail.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : null

  const windowLabel = interview.windowStart && interview.windowEnd
    ? `${fmtIsoDate(interview.windowStart)} تا ${fmtIsoDate(interview.windowEnd)}`
    : null

  return (
    <div
      data-testid="internship-readiness-progress-panel"
      style={{
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
        background: '#f0fdfa',
        borderRadius: '10px',
        borderRight: '4px solid #0d9488',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#134e4a' }}>
        {isInterviewScheduling && 'تنظیم وقت مصاحبه انترنی (فرایند ۳۷)'}
        {isInterviewHeld && 'ثبت نتیجه مصاحبه انترنی (فرایند ۳۷)'}
        {isPromissoryNote && 'ثبت دریافت سفته انترنی (فرایند ۳۷)'}
      </h4>

      {isInterviewScheduling && (
        <>
          <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
            با هماهنگی مسئول علمی، تاریخ و ساعت مصاحبه را در فرم
            {' '}
            <strong>تعیین وقت مصاحبه انترنی</strong>
            {' '}
            ثبت کنید و انتقال
            {' '}
            <code style={{ fontSize: '0.8rem' }}>interview_scheduled</code>
            {' '}
            را بزنید. پیامک دعوت برای دانشجو و اعضای کمیته ارسال می‌شود.
          </p>
          {windowLabel && (
            <div
              data-testid="internship-interview-window"
              style={{
                marginBottom: '0.75rem',
                padding: '0.65rem 0.85rem',
                borderRadius: '8px',
                background: '#fff',
                border: '1px solid #99f6e4',
                fontSize: '0.82rem',
                lineHeight: 1.65,
                color: '#334155',
              }}
            >
              <strong>بازهٔ مجاز مصاحبه:</strong>
              {' '}
              {windowLabel}
            </div>
          )}
        </>
      )}

      {isInterviewHeld && (
        <>
          <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
            پس از برگزاری مصاحبه، یکی از سه نتیجه را در فرم
            {' '}
            <strong>نتیجه مصاحبه انترنی</strong>
            {' '}
            ثبت کنید:
          </p>
          <ul style={{ margin: '0 0 0.75rem', paddingRight: '1.25rem', fontSize: '0.84rem', lineHeight: 1.75, color: '#334155' }}>
            <li>
              <code style={{ fontSize: '0.8rem' }}>result_unconditional</code>
              {' '}
              — قبولی بدون شرط (۳ ساعت در هفته)
            </li>
            <li>
              <code style={{ fontSize: '0.8rem' }}>result_conditional</code>
              {' '}
              — قبولی مشروط (۱ ساعت در هفته)
            </li>
            <li>
              <code style={{ fontSize: '0.8rem' }}>result_retry_30h</code>
              {' '}
              — درخواست دوباره پس از ۳۰ ساعت درمان
            </li>
          </ul>
          {(interview.date || interview.time) && (
            <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
              زمان مصاحبه ثبت‌شده:
              {' '}
              {fmtIsoDate(interview.date)}
              {' '}
              —
              {' '}
              {interview.time || '—'}
            </p>
          )}
          {result.resultLabel && (
            <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
              نتیجهٔ ثبت‌شده در پرونده:
              {' '}
              <strong>{result.resultLabel}</strong>
            </p>
          )}
        </>
      )}

      {isPromissoryNote && (
        <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
          پس از دریافت فیزیکی سفته از دانشجو، انتقال
          {' '}
          <code style={{ fontSize: '0.8rem' }}>promissory_received</code>
          {' '}
          را بزنید تا فرایند به بررسی ظرفیت بیمار برود.
        </p>
      )}

      {studentLabel && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          پروندهٔ دانشجو:
          {' '}
          <strong>{studentLabel}</strong>
        </p>
      )}

      {user?.role
        && !['progress_committee', 'admin'].includes(user.role)
        && isInterviewHeld && (
        <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
          ثبت نتیجه مصاحبه معمولاً بر عهدهٔ مسئول علمی کمیته پیشرفت است.
        </p>
      )}
    </div>
  )
}
