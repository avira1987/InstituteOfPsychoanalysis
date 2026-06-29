/** نمایش مشترک زنجیره «پایان ترم‌های دوره آشنایی» — فرایند ۳۲. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

/** مراحل اصلی (milestone) فرایند پایان ترم آشنایی. */
export const INTRO_TERM_END_FLOW_STEPS = [
  {
    key: 'transcripts',
    label: 'صدور کارنامه ترمی و تجمیعی',
    states: ['grades_submitted', 'transcript_generated'],
  },
  {
    key: 'therapy',
    label: 'بررسی شرط درمان',
    states: ['therapy_check', 'therapy_blocked'],
  },
  {
    key: 'registration',
    label: 'اطلاع‌رسانی ثبت‌نام ترم بعد',
    states: ['registration_notification_sent'],
  },
  {
    key: 'decline_followup',
    label: 'پیگیری افت تحصیلی',
    states: ['decline_list_generated', 'followup_in_progress'],
  },
  {
    key: 'complete',
    label: 'پایان فرایند',
    states: ['followup_complete'],
  },
]

/** برچسب فارسی هر وضعیت فرایند ۳۲. */
export const INTRO_TERM_END_STATE_LABELS = {
  grades_submitted: 'تمام نمرات ثبت شد — شروع فرایند',
  transcript_generated: 'کارنامه ترمی و تجمیعی تولید شد',
  therapy_check: 'بررسی وضعیت شرط درمان',
  therapy_blocked: 'مسدودیت ثبت‌نام — درمانگر فعال ندارد',
  registration_notification_sent: 'پیامک اطلاع‌رسانی ثبت‌نام ارسال شد',
  decline_list_generated: 'لیست دانشجویان افت تحصیلی تولید شد',
  followup_in_progress: 'پیگیری تماس با دانشجویان افت تحصیلی',
  followup_complete: 'پیگیری تکمیل شد',
}

const TRANSCRIPT_READY_STATES = new Set([
  'transcript_generated',
  'therapy_check',
  'therapy_blocked',
  'registration_notification_sent',
  'decline_list_generated',
  'followup_in_progress',
  'followup_complete',
])

const REGISTRATION_REMINDER_STATES = new Set([
  'registration_notification_sent',
  'decline_list_generated',
  'followup_in_progress',
  'followup_complete',
])

export const THERAPY_BLOCK_MESSAGE_FA =
  'طبق توافق قبلی در مورد پذیرش شما به دوره آشنایی، باید وارد درمان شخصی شوید. چون این شرط تاکنون انجام نگرفته، ثبت‌نام در ترم دوم این دوره مشروط به آغاز این درمان شده است. لطفاً زودتر از فرایند «آغاز درمان آموزشی» در پورتال خود اقدام بفرمایید.'

export function labelIntroTermEndState(state) {
  if (!state) return '—'
  return INTRO_TERM_END_STATE_LABELS[state] || state
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function activeIntroTermEndStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'followup_complete') return INTRO_TERM_END_FLOW_STEPS.length - 1
  const idx = INTRO_TERM_END_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function hasTranscriptsReady(state) {
  return TRANSCRIPT_READY_STATES.has(state)
}

export function showRegistrationReminder(state) {
  return REGISTRATION_REMINDER_STATES.has(state)
}

export function isTherapyBlocked(extraData = {}) {
  return extraData?.gates?.next_term_registration_blocked === true
}

export function resolveTermEndContext(ctx = {}, extraData = {}) {
  const gates = extraData?.gates || {}
  return {
    termCode: ctx.term_code ?? ctx.term_label_fa ?? null,
    termGpa: ctx.term_gpa ?? ctx.termGPA ?? null,
    cumulativeGpa: ctx.cumulative_gpa ?? ctx.cumulativeGPA ?? null,
    nextTermDeadline:
      ctx.next_term_registration_deadline
      ?? ctx.registration_deadline
      ?? extraData?.institute_calendar?.registration_deadline
      ?? null,
    failedCourses: Array.isArray(ctx.failed_courses)
      ? ctx.failed_courses
      : Array.isArray(ctx.failedCourses)
        ? ctx.failedCourses
        : [],
    therapyBlocked: isTherapyBlocked(extraData) || ctx.therapy_blocked === true,
    followupEnteredAt: ctx.followup_in_progress_entered_at ?? ctx.followup_entered_at ?? null,
  }
}

export function IntroTermEndFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeIntroTermEndStepIndex(currentState)
  const completed = currentState === 'followup_complete'

  return (
    <div
      data-testid="intro-term-end-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {INTRO_TERM_END_FLOW_STEPS.map((step, i) => {
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
            {completed && i === INTRO_TERM_END_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
