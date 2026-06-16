import React from 'react'

function Row({ label, value }) {
  if (value == null || value === '') return null
  return (
    <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.82rem', marginBottom: '0.25rem' }}>
      <span style={{ color: '#64748b', minWidth: '8rem' }}>{label}</span>
      <span>{value}</span>
    </div>
  )
}

function formatCoursesTable(courses) {
  if (!Array.isArray(courses) || !courses.length) return null
  return courses
    .map((c) => {
      const parts = [
        c.course_name,
        c.track,
        c.proposed_day || c.day,
        c.proposed_time || c.time,
        c.instructor,
        c.teaching_assistant,
        c.classroom_location,
      ].filter(Boolean)
      return parts.join(' · ')
    })
    .join(' | ')
}

/**
 * خلاصهٔ فقط‌خواندنی مراحل قبلی فرایند ۲۹ (طبق SOP: فرم‌های بعدی خروجی مراحل قبل را نشان می‌دهند).
 */
export default function FallSemesterPrepReadonlySummary({ currentState, contextData }) {
  const ctx = contextData || {}
  const showCalendar = [
    'tuition_entry',
    'license_check',
    'course_list_creation',
    'course_finalization',
    'marketing_campaign',
    'interviewer_assignment',
    'interview_scheduling',
  ].includes(currentState)

  const showTuition = [
    'license_check',
    'course_list_creation',
    'course_finalization',
    'marketing_campaign',
    'interviewer_assignment',
    'interview_scheduling',
  ].includes(currentState)

  const showCourses = ['course_finalization', 'marketing_campaign', 'interviewer_assignment', 'interview_scheduling'].includes(
    currentState,
  )

  const showFinalized = ['marketing_campaign', 'interviewer_assignment', 'interview_scheduling'].includes(currentState)

  const showInterviewers = currentState === 'interview_scheduling'

  if (!showCalendar && !showTuition && !showCourses && !showFinalized && !showInterviewers) return null

  return (
    <div
      style={{
        marginBottom: '1rem',
        padding: '0.85rem 1rem',
        background: '#f8fafc',
        borderRadius: '8px',
        border: '1px solid #e2e8f0',
      }}
      data-testid="fall-semester-readonly-summary"
    >
      <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem', color: '#475569' }}>
        خلاصهٔ مراحل قبلی (فقط مشاهده)
      </div>

      {showCalendar && (
        <div style={{ marginBottom: '0.65rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>تقویم آموزشی</div>
          <Row label="پاییز" value={ctx.fall_start_date && ctx.fall_end_date ? `${ctx.fall_start_date} تا ${ctx.fall_end_date}` : null} />
          <Row label="زمستان" value={ctx.winter_start_date && ctx.winter_end_date ? `${ctx.winter_start_date} تا ${ctx.winter_end_date}` : null} />
          <Row
            label="ثبت‌نام/پرداخت"
            value={
              ctx.registration_payment_window_start && ctx.registration_payment_window_end
                ? `${ctx.registration_payment_window_start} تا ${ctx.registration_payment_window_end}`
                : null
            }
          />
        </div>
      )}

      {showTuition && (
        <div style={{ marginBottom: '0.65rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>شهریه و مصاحبه</div>
          <Row label="واحد آشنایی" value={ctx.per_unit_cost_introductory != null ? `${ctx.per_unit_cost_introductory} ریال` : null} />
          <Row label="واحد جامع" value={ctx.per_unit_cost_comprehensive != null ? `${ctx.per_unit_cost_comprehensive} ریال` : null} />
          <Row label="مصاحبه آشنایی" value={ctx.interview_fee_introductory != null ? `${ctx.interview_fee_introductory} ریال` : ctx.interview_fee} />
          <Row label="مصاحبه جامع" value={ctx.interview_fee_comprehensive != null ? `${ctx.interview_fee_comprehensive} ریال` : null} />
        </div>
      )}

      {showCourses && ctx.courses?.length > 0 && (
        <div style={{ marginBottom: '0.65rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>لیست دروس (پیش‌نویس)</div>
          <p style={{ margin: 0, fontSize: '0.8rem', lineHeight: 1.6, color: '#334155' }}>{formatCoursesTable(ctx.courses)}</p>
        </div>
      )}

      {showFinalized && ctx.courses_finalized?.length > 0 && (
        <div style={{ marginBottom: '0.65rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>برنامه نهایی دروس</div>
          <p style={{ margin: 0, fontSize: '0.8rem', lineHeight: 1.6, color: '#334155' }}>{formatCoursesTable(ctx.courses_finalized)}</p>
        </div>
      )}

      {showInterviewers && (
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>مصاحبه‌گران و بازه</div>
          <Row
            label="جامع"
            value={
              Array.isArray(ctx.comprehensive_interviewers)
                ? `${ctx.comprehensive_interviewers.join('، ')} (${ctx.comprehensive_date_range_start || '—'} تا ${ctx.comprehensive_date_range_end || '—'})`
                : null
            }
          />
          <Row
            label="آشنایی"
            value={
              Array.isArray(ctx.introductory_interviewers)
                ? `${ctx.introductory_interviewers.join('، ')} (${ctx.introductory_date_range_start || '—'} تا ${ctx.introductory_date_range_end || '—'})`
                : null
            }
          />
        </div>
      )}
    </div>
  )
}
