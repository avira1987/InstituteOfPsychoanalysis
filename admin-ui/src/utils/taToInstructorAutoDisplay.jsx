/** نمایش مشترک فرایند ۵۰ — تبدیل خودکار کمک‌مدرس به مدرس. */

import React from 'react'
import { resolveStateDisplayLabel } from './processDisplay'
import { formatShamsiTehran } from './shamsiDateTime'

export const TA_TO_INSTRUCTOR_FLOW_STEPS = [
  { key: 'check', label: 'بررسی پایان ترم', states: ['end_of_term_check'] },
  { key: 'eligibility', label: 'احراز شرایط', states: ['conditions_not_met', 'upgrade_applied'] },
  { key: 'upgrade', label: 'اعمال ارتقا', states: ['upgrade_applied'] },
]

export const TA_TO_INSTRUCTOR_STATE_HINTS = {
  end_of_term_check:
    'سامانه در حال بررسی سوابق کمک‌مدرسی شما در پایان ترم است. این مرحله کاملاً خودکار است؛ چند دقیقه بعد صفحه را تازه کنید.',
  conditions_not_met:
    'شرایط ارتقا به مدرس در این درس احراز نشد. پیش‌نیازها: رتبه تحلیلی «دستیار هیئت علمی» و دو بار گذراندن موفق یک درس به‌عنوان کمک‌مدرس.',
  upgrade_applied:
    'تبریک! شما به‌عنوان مدرس در درس مربوطه ارتقا یافتید. درس بعدی در رسته برای شما باز شده است.',
}

export const TA_TO_INSTRUCTOR_CONGRATS_FA =
  'مسیر کمک‌مدرسی شما برای این درس با موفقیت طی شد. شما اکنون به‌عنوان مدرس همان درس با رتبه تحلیلی دستیار هیئت علمی ارتقا پیدا کرده‌اید.'

export const RANK_LABELS = {
  assistant_faculty: 'دستیار هیئت علمی',
  instructor: 'مدرس',
  teaching_assistant: 'کمک‌مدرس',
}

export function labelTaToInstructorState(state) {
  return resolveStateDisplayLabel('ta_to_instructor_auto', state) || state || '—'
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function activeTaToInstructorStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'upgrade_applied') return 2
  if (currentState === 'conditions_not_met') return 1
  return 0
}

export function resolveTaToInstructorContext(ctx = {}, extraData = {}) {
  const lms = extraData?.lms || {}
  const rank = ctx.current_rank || extraData?.rank || '—'
  const unlocked = lms?.track_progress?.unlocked || []

  return {
    rankLabel: RANK_LABELS[rank] || rank,
    sourceCourseName: ctx.source_course_name || ctx.course_name || '—',
    sourceCourseCode: ctx.source_course_code || ctx.course_code || '—',
    trackName: ctx.track_name || ctx.course_track || '—',
    trackCode: ctx.track_code || '—',
    nextCourseName: ctx.next_course_name || '—',
    nextCourseCode: ctx.next_course_code || '—',
    promotedRole: RANK_LABELS[ctx.promoted_role] || 'مدرس',
    eligibilitySummary: ctx.eligibility_summary_fa || '—',
    eligible: ctx.eligible === true,
    rankOk: ctx.rank_ok === true,
    passesOk: ctx.passes_ok === true,
    upgradeAppliedAt: ctx.upgrade_applied_at || ctx.completed_at || null,
    studentName: ctx.student_name_fa || '—',
    unlockedCourses: Array.isArray(unlocked) ? unlocked : [],
  }
}

export function buildAutomationReport(ctx = {}, extraData = {}) {
  const resolved = resolveTaToInstructorContext(ctx, extraData)
  return {
    executedAt: resolved.upgradeAppliedAt,
    studentName: resolved.studentName,
    rankLabel: resolved.rankLabel,
    sectionRoleChange: {
      sourceCourse: resolved.sourceCourseName,
      removedFrom: 'لیست کمک‌مدرسین',
      addedTo: 'لیست مدرسین',
      smsSent: true,
    },
    sectionUnlock: {
      track: resolved.trackName,
      nextCourse: resolved.nextCourseName,
      addedToNextTaList: resolved.nextCourseName !== '—',
    },
  }
}

export function HintBlock({ children, tone = '#2563eb', bg = '#eff6ff' }) {
  return (
    <div
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        fontSize: '0.86rem',
        lineHeight: 1.75,
        color: tone === '#dc2626' ? '#991b1b' : tone === '#16a34a' ? '#166534' : '#1e3a8a',
      }}
    >
      {children}
    </div>
  )
}

export function InfoTile({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
  if (value == null || value === '' || value === '—') return null
  return (
    <div
      style={{
        padding: '0.75rem 0.85rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontSize: '1.05rem', fontWeight: 800, color: tone }}>{value}</div>
    </div>
  )
}

export function TaToInstructorFlowStepper({ currentState, compact = false, testId = 'ta-to-instructor-flow-stepper' }) {
  const activeIdx = activeTaToInstructorStepIndex(currentState)
  const failed = currentState === 'conditions_not_met'

  return (
    <div
      data-testid={testId}
      style={{
        display: 'flex',
        gap: '0.35rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
        flexWrap: 'wrap',
      }}
    >
      {TA_TO_INSTRUCTOR_FLOW_STEPS.map((step, i) => {
        const done = i < activeIdx || (i === activeIdx && currentState === 'upgrade_applied')
        const active = i === activeIdx && !done
        const failActive = failed && i === 1
        return (
          <div
            key={step.key}
            style={{
              flex: '1 1 6rem',
              padding: compact ? '0.4rem 0.5rem' : '0.45rem 0.55rem',
              borderRadius: '8px',
              background: failActive ? '#fef2f2' : active ? '#0d9488' : done ? '#ccfbf1' : '#f1f5f9',
              color: failActive ? '#b91c1c' : active ? '#fff' : done ? '#115e59' : '#64748b',
              border: failActive
                ? '2px solid #dc2626'
                : active
                  ? '2px solid #0f766e'
                  : '1px solid #e2e8f0',
              fontSize: compact ? '0.68rem' : '0.72rem',
              textAlign: 'center',
              fontWeight: active || failActive ? 700 : 500,
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}
