/** نمایش مشترک زنجیره «پایان ترم‌های دوره جامع» — فرایند ۳۶. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'
export { resolveTermTranscriptRows } from './termEndTranscriptRows'

/** مراحل اصلی (milestone) فرایند پایان ترم دوره جامع. */
export const COMPREHENSIVE_TERM_END_FLOW_STEPS = [
  {
    key: 'transcripts',
    label: 'صدور کارنامه ترمی و کلی',
    states: ['grades_submitted', 'transcript_generated'],
  },
  {
    key: 'graduation_check',
    label: 'بررسی اتمام دروس جامع',
    states: ['graduation_check', 'completed_all_courses', 'registration_notification_sent'],
  },
  {
    key: 'complete',
    label: 'پایان فرایند',
    states: ['completed_all_courses', 'process_complete'],
  },
]

/** برچسب فارسی هر وضعیت فرایند ۳۶. */
export const COMPREHENSIVE_TERM_END_STATE_LABELS = {
  grades_submitted: 'تمام نمرات ترم وارد شده',
  transcript_generated: 'کارنامه‌های ترمی و کلی تولید شده',
  graduation_check: 'بررسی وضعیت اتمام دروس جامع',
  completed_all_courses: 'تمام دروس جامع پاس شده',
  registration_notification_sent: 'اطلاعیه ثبت‌نام ترم بعدی ارسال شد',
  process_complete: 'فرایند تکمیل شد',
}

const TRANSCRIPT_READY_STATES = new Set([
  'transcript_generated',
  'graduation_check',
  'completed_all_courses',
  'registration_notification_sent',
  'process_complete',
])

const REGISTRATION_REMINDER_STATES = new Set([
  'registration_notification_sent',
  'process_complete',
])

const TERMINAL_STATES = new Set(['completed_all_courses', 'process_complete'])

export function labelComprehensiveTermEndState(state) {
  if (!state) return '—'
  return COMPREHENSIVE_TERM_END_STATE_LABELS[state] || state
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function activeComprehensiveTermEndStepIndex(currentState) {
  if (!currentState) return 0
  if (TERMINAL_STATES.has(currentState)) {
    return COMPREHENSIVE_TERM_END_FLOW_STEPS.length - 1
  }
  const idx = COMPREHENSIVE_TERM_END_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function hasTranscriptsReady(state) {
  return TRANSCRIPT_READY_STATES.has(state)
}

export function showRegistrationReminder(state) {
  return REGISTRATION_REMINDER_STATES.has(state)
}

export function isProcessComplete(state) {
  return TERMINAL_STATES.has(state)
}

export function resolveTermEndContext(ctx = {}, extraData = {}) {
  const remainingCourses = Array.isArray(ctx.remaining_comprehensive_courses)
    ? ctx.remaining_comprehensive_courses
    : Array.isArray(ctx.remaining_courses)
      ? ctx.remaining_courses
      : Array.isArray(ctx.remainingCourses)
        ? ctx.remainingCourses
        : []

  return {
    termCode: ctx.term_code ?? ctx.term_number ?? ctx.term_label_fa ?? null,
    termGpa: ctx.term_gpa ?? ctx.termGPA ?? null,
    cumulativeGpa: ctx.cumulative_gpa ?? ctx.cumulativeGPA ?? null,
    nextTermDeadline:
      ctx.next_term_registration_deadline
      ?? ctx.registration_deadline
      ?? ctx.deadline_date
      ?? extraData?.institute_calendar?.registration_deadline
      ?? null,
    remainingCourses,
    allCoursesPassed:
      ctx.all_comprehensive_courses_passed === true
      || ctx.all_comprehensive_subjects_passed === true
      || currentStateImpliesGraduation(ctx),
  }
}

function currentStateImpliesGraduation(ctx) {
  return ctx.graduation_status === 'completed_all_courses'
}

export function ComprehensiveTermEndFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeComprehensiveTermEndStepIndex(currentState)
  const completed = isProcessComplete(currentState)

  return (
    <div
      data-testid="comprehensive-term-end-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {COMPREHENSIVE_TERM_END_FLOW_STEPS.map((step, i) => {
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
              .
              {' '}
              {step.label}
            </div>
            {current && <div style={{ fontSize: '0.72rem' }}>← مرحلهٔ فعلی</div>}
            {completed && i === COMPREHENSIVE_TERM_END_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
