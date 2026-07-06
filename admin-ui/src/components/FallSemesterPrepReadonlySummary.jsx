import React, { useMemo } from 'react'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import {
  fmtRialDisplay,
  hasTuitionOrInterviewData,
  resolveMarketingHandoffContext,
} from '../utils/marketingHandoffDisplay'

function formatDateDisplay(value) {
  if (!value) return null
  return formatShamsiTehran(value, { dateOnly: true })
}

function Row({ label, value, emptyLabel }) {
  const display = value == null || value === '' ? emptyLabel : value
  if (display == null || display === '') return null
  return (
    <div className="fall-semester-readonly-summary__row">
      <span className="fall-semester-readonly-summary__label">{label}</span>
      <span className="fall-semester-readonly-summary__value">{display}</span>
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
  const ctx = useMemo(
    () =>
      currentState === 'marketing_campaign'
        ? resolveMarketingHandoffContext(processCode, contextData || {})
        : contextData || {},
    [currentState, contextData, processCode],
  )
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

  const finalizedFall = ctx.courses_finalized_fall
  const finalizedWinter = ctx.courses_finalized_winter
  const finalizedLegacy = ctx.courses_finalized
  const hasFinalizedCourses =
    finalizedFall?.length > 0 ||
    finalizedWinter?.length > 0 ||
    finalizedLegacy?.length > 0

  const showTuitionBlock =
    showTuition && (hasTuitionOrInterviewData(ctx) || (isMarketing && !isWinter))

  if (!showCalendar && !showTuitionBlock && !showCourses && !showFinalized) return null

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

      {showTuitionBlock && (
        <div style={{ marginBottom: '0.65rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>
            {isMarketing && !isWinter ? 'فعالیت ۲ — شهریه و مصاحبه' : 'شهریه و مصاحبه'}
          </div>
          <Row
            label="واحد آشنایی"
            value={fmtRialDisplay(ctx.per_unit_cost_introductory)}
            emptyLabel={isMarketing && !isWinter ? 'ثبت نشده' : null}
          />
          <Row
            label="واحد جامع"
            value={fmtRialDisplay(ctx.per_unit_cost_comprehensive)}
            emptyLabel={isMarketing && !isWinter ? 'ثبت نشده' : null}
          />
          <Row
            label="مصاحبه آشنایی"
            value={fmtRialDisplay(ctx.interview_fee_introductory) || ctx.interview_fee}
            emptyLabel={isMarketing && !isWinter ? 'ثبت نشده' : null}
          />
          <Row
            label="مصاحبه جامع"
            value={fmtRialDisplay(ctx.interview_fee_comprehensive)}
            emptyLabel={isMarketing && !isWinter ? 'ثبت نشده' : null}
          />
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

      {showFinalized && (hasFinalizedCourses || isMarketing) && (
        <div style={{ marginBottom: '0.65rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#334155', marginBottom: '0.25rem' }}>
            {isMarketing
              ? isWinter
                ? 'فعالیت ۳ — برنامه نهایی دروس زمستان'
                : 'فعالیت ۵ — برنامه نهایی دروس'
              : 'برنامه نهایی دروس'}
          </div>
          {finalizedFall?.length > 0 && (
            <div style={{ marginBottom: '0.35rem' }}>
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.15rem' }}>ترم پاییز</div>
              <p className="fall-semester-readonly-summary__text">{formatCoursesTable(finalizedFall)}</p>
            </div>
          )}
          {finalizedWinter?.length > 0 && (
            <div style={{ marginBottom: '0.35rem' }}>
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.15rem' }}>ترم زمستان</div>
              <p className="fall-semester-readonly-summary__text">{formatCoursesTable(finalizedWinter)}</p>
            </div>
          )}
          {!finalizedFall?.length && !finalizedWinter?.length && finalizedLegacy?.length > 0 && (
            <p className="fall-semester-readonly-summary__text">{formatCoursesTable(finalizedLegacy)}</p>
          )}
          {isMarketing && !hasFinalizedCourses && (
            <p className="fall-semester-readonly-summary__text muted">(داده‌ای ثبت نشده)</p>
          )}
        </div>
      )}
    </div>
  )
}
