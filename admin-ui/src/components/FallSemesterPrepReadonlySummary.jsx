import React from 'react'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

function formatDateDisplay(value) {
  if (!value) return null
  return formatShamsiTehran(value, { dateOnly: true })
}

function Row({ label, value }) {
  if (value == null || value === '') return null
  return (
    <div className="fall-semester-readonly-summary__row">
      <span className="fall-semester-readonly-summary__label">{label}</span>
      <span className="fall-semester-readonly-summary__value">{value}</span>
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
export default function FallSemesterPrepReadonlySummary({ currentState, contextData, processCode }) {
  const ctx = contextData || {}
  const isWinter = processCode === 'winter_semester_preparation'
  const isMarketing = currentState === 'marketing_campaign'
  const showCalendar = [
    'tuition_entry',
    'license_check',
    'course_list_creation',
    'course_list_review',
    'course_finalization',
    'marketing_campaign',
    'interviewer_assignment',
    'interview_scheduling',
  ].includes(currentState)

  const showTuition = [
    'license_check',
    'course_list_creation',
    'course_list_review',
    'course_finalization',
    'marketing_campaign',
    'interviewer_assignment',
    'interview_scheduling',
  ].includes(currentState)

  const showCourses = [
    'course_finalization',
    'course_list_review',
    'interviewer_assignment',
    'interview_scheduling',
  ].includes(currentState) || (isWinter && currentState === 'marketing_campaign')

  const showFinalized = ['marketing_campaign', 'interviewer_assignment', 'interview_scheduling'].includes(
    currentState,
  )

  if (!showCalendar && !showTuition && !showCourses && !showFinalized) return null

  return (
    <div
      className="fall-semester-readonly-summary"
      data-testid="fall-semester-readonly-summary"
    >
      <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem', color: '#475569' }}>
        {isMarketing
          ? 'خروجی فعالیت‌های قبلی (فقط مشاهده — برای ارسال به مدیر مارکتینگ)'
          : 'خلاصهٔ مراحل قبلی (فقط مشاهده)'}
      </div>

      {showCalendar && ctx.fall_start_date && (
        <div style={{ marginBottom: '0.65rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>
            {isMarketing && !isWinter ? 'فعالیت ۱ — تقویم آموزشی' : 'تقویم آموزشی'}
          </div>
          <Row label="پاییز" value={ctx.fall_start_date && ctx.fall_end_date ? `${formatDateDisplay(ctx.fall_start_date)} تا ${formatDateDisplay(ctx.fall_end_date)}` : null} />
          <Row label="زمستان" value={ctx.winter_start_date && ctx.winter_end_date ? `${formatDateDisplay(ctx.winter_start_date)} تا ${formatDateDisplay(ctx.winter_end_date)}` : null} />
          <Row
            label="ثبت‌نام/پرداخت"
            value={
              ctx.registration_payment_window_start && ctx.registration_payment_window_end
                ? `${formatDateDisplay(ctx.registration_payment_window_start)} تا ${formatDateDisplay(ctx.registration_payment_window_end)}`
                : null
            }
          />
        </div>
      )}

      {showTuition && ctx.per_unit_cost_introductory != null && (
        <div style={{ marginBottom: '0.65rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>
            {isMarketing && !isWinter ? 'فعالیت ۲ — شهریه و مصاحبه' : 'شهریه و مصاحبه'}
          </div>
          <Row label="واحد آشنایی" value={ctx.per_unit_cost_introductory != null ? `${ctx.per_unit_cost_introductory} ریال` : null} />
          <Row label="واحد جامع" value={ctx.per_unit_cost_comprehensive != null ? `${ctx.per_unit_cost_comprehensive} ریال` : null} />
          <Row label="مصاحبه آشنایی" value={ctx.interview_fee_introductory != null ? `${ctx.interview_fee_introductory} ریال` : ctx.interview_fee} />
          <Row label="مصاحبه جامع" value={ctx.interview_fee_comprehensive != null ? `${ctx.interview_fee_comprehensive} ریال` : null} />
        </div>
      )}

      {showCourses && (ctx.courses_fall?.length > 0 || ctx.courses_winter?.length > 0 || ctx.courses?.length > 0) && (
        <div style={{ marginBottom: '0.65rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>
            {isMarketing && isWinter ? 'فعالیت ۲ — لیست دروس زمستان' : 'لیست دروس (پیش‌نویس)'}
          </div>
          {ctx.courses_fall?.length > 0 && (
            <div style={{ marginBottom: '0.35rem' }}>
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.15rem' }}>ترم پاییز</div>
              <p className="fall-semester-readonly-summary__text">{formatCoursesTable(ctx.courses_fall)}</p>
            </div>
          )}
          {ctx.courses_winter?.length > 0 && (
            <div style={{ marginBottom: '0.35rem' }}>
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.15rem' }}>ترم زمستان</div>
              <p className="fall-semester-readonly-summary__text">{formatCoursesTable(ctx.courses_winter)}</p>
            </div>
          )}
          {!ctx.courses_fall?.length && !ctx.courses_winter?.length && ctx.courses?.length > 0 && (
            <p className="fall-semester-readonly-summary__text">{formatCoursesTable(ctx.courses)}</p>
          )}
        </div>
      )}

      {showFinalized && (ctx.courses_finalized_fall?.length > 0 || ctx.courses_finalized_winter?.length > 0 || ctx.courses_finalized?.length > 0) && (
        <div style={{ marginBottom: '0.65rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>
            {isMarketing
              ? isWinter
                ? 'فعالیت ۳ — برنامه نهایی دروس زمستان'
                : 'فعالیت ۵ — برنامه نهایی دروس'
              : 'برنامه نهایی دروس'}
          </div>
          {ctx.courses_finalized_fall?.length > 0 && (
            <div style={{ marginBottom: '0.35rem' }}>
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.15rem' }}>ترم پاییز</div>
              <p className="fall-semester-readonly-summary__text">{formatCoursesTable(ctx.courses_finalized_fall)}</p>
            </div>
          )}
          {ctx.courses_finalized_winter?.length > 0 && (
            <div style={{ marginBottom: '0.35rem' }}>
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.15rem' }}>ترم زمستان</div>
              <p className="fall-semester-readonly-summary__text">{formatCoursesTable(ctx.courses_finalized_winter)}</p>
            </div>
          )}
          {!ctx.courses_finalized_fall?.length && !ctx.courses_finalized_winter?.length && ctx.courses_finalized?.length > 0 && (
            <p className="fall-semester-readonly-summary__text">{formatCoursesTable(ctx.courses_finalized)}</p>
          )}
        </div>
      )}
    </div>
  )
}
