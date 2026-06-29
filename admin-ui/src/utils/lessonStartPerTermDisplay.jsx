/** نمایش مشترک زنجیره «آغاز هر درس در هر ترم» — فرایند ۴۱. */

import React from 'react'
import { fmtIsoDate } from './introductoryCourseRegistrationDisplay'

export { fmtIsoDate }

/** مراحل اصلی (milestone) فرایند ۴۱. */
export const LESSON_START_FLOW_STEPS = [
  { key: 'enrollment', label: 'ثبت‌نام در درس', states: ['student_enrollment'] },
  { key: 'links', label: 'لینک آنلاین', states: ['links_created'] },
  { key: 'roster', label: 'لیست حضور', states: ['attendance_list_ready'] },
  { key: 'active', label: 'درس فعال', states: ['lesson_active'] },
]

/** برچسب فارسی هر وضعیت فرایند ۴۱. */
export const LESSON_START_STATE_LABELS = {
  student_enrollment: 'ثبت‌نام دانشجو در درس',
  links_created: 'لینک آنلاین ایجاد و فعال',
  attendance_list_ready: 'لیست حضور و غیاب آماده',
  lesson_active: 'درس فعال — حضور توسط مدرس',
}

export function labelLessonStartState(state) {
  if (!state) return '—'
  return LESSON_START_STATE_LABELS[state] || state
}

/** شاخص مرحلهٔ فعال در stepper بر اساس وضعیت جاری. */
export function activeLessonStartStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'lesson_active') return LESSON_START_FLOW_STEPS.length - 1
  const idx = LESSON_START_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

function courseCodeFromCtx(ctx = {}, lms = {}) {
  const selected = ctx.selected_courses
  if (Array.isArray(selected) && selected.length) return String(selected[0])
  if (ctx.lesson_course_label) return String(ctx.lesson_course_label)
  const enrolled = lms.enrolled_courses || []
  if (enrolled.length) {
    const last = enrolled[enrolled.length - 1]
    return typeof last === 'object' ? (last.code || last.course_code || '') : String(last)
  }
  return ''
}

/** داده‌های کلیدی آغاز درس از context و extra_data.lms. */
export function resolveLessonStartContext(ctx = {}, extraData = {}) {
  const lms = extraData?.lms || ctx.lms || {}
  const courseCode = courseCodeFromCtx(ctx, lms)
  const portalLinks = lms.portal_course_links || lms.course_links || {}
  const onlineLink = ctx.online_class_link
    || portalLinks[courseCode]
    || portalLinks[String(courseCode)]
    || ''
  const taMap = lms.teaching_assistants_by_course || {}
  const teachingAssistant = ctx.teaching_assistant_name
    || taMap[courseCode]
    || taMap[String(courseCode)]
    || ''
  const attendanceRosters = lms.lesson_attendance || {}
  const roster = attendanceRosters[courseCode] || attendanceRosters[String(courseCode)] || {}
  const sessions = Array.isArray(roster.sessions) ? roster.sessions : []

  return {
    courseCode,
    courseLabel: ctx.lesson_course_label || courseCode || '—',
    onlineLink,
    teachingAssistant,
    sessions,
    linksPlaced: Boolean(lms.links_placed),
    attendanceListReady: Boolean(lms.attendance_list_ready),
    lessonActiveAt: lms.lesson_active_at || null,
  }
}

export function LessonStartFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeLessonStartStepIndex(currentState)
  const completed = currentState === 'lesson_active'

  return (
    <div
      data-testid="lesson-start-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {LESSON_START_FLOW_STEPS.map((step, i) => {
        const done = completed ? true : i < activeIdx
        const current = !completed && i === activeIdx
        const tone = done ? '#16a34a' : current ? '#0d9488' : '#94a3b8'
        const bg = done ? '#f0fdf4' : current ? '#f0fdfa' : '#f8fafc'
        return (
          <div
            key={step.key}
            style={{
              padding: compact ? '0.5rem 0.6rem' : '0.55rem 0.65rem',
              borderRadius: '8px',
              background: bg,
              borderRight: `3px solid ${tone}`,
              fontSize: compact ? '0.74rem' : '0.76rem',
              lineHeight: 1.55,
              color: done ? '#14532d' : current ? '#134e4a' : '#64748b',
            }}
          >
            <div style={{ fontWeight: 800, marginBottom: '0.15rem' }}>
              {i + 1}
              .{' '}
              {step.label}
            </div>
            {current && <div style={{ fontSize: '0.72rem' }}>← مرحلهٔ فعلی</div>}
            {completed && i === LESSON_START_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/** برچسب وضعیت حضور جلسه. */
export function labelAttendanceSessionStatus(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'present' || s === 'حاضر') return 'حاضر'
  if (s === 'absent' || s === 'غایب' || s === 'absent_unexcused') return 'غایب'
  return status || '—'
}
