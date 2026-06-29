/** نمایش مشترک «خاتمه درس عملی کاربردی / مشاهده فیلم — بخش TA و حضور/مشارکت» — فرایند SOP ۷۵. */

import React from 'react'
import { courseCodeFromInstanceContext } from './lessonAttendanceDisplay'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'
import { resolveStateDisplayLabel } from './processDisplay'
import { formatShamsiTehran } from './shamsiDateTime'
import { HintBlock } from './attendanceChainDisplay'
import {
  buildStudentsGradesPayload,
  computeAttendanceScore,
  labelParticipationGrade,
  labelTaPassFail,
  rosterRowToGradeRow,
  validateParticipationScore,
} from './liveTherapyObservationTaAttendanceDisplay'

export {
  buildStudentsGradesPayload,
  computeAttendanceScore,
  labelParticipationGrade,
  labelTaPassFail,
  rosterRowToGradeRow,
  validateParticipationScore,
}

export const PROCESS_CODE = 'film_observation_ta_attendance_completion'

export const PROCESS_TITLE_FA =
  'خاتمه هر درس عملی کاربردی، مشاهده فیلم‌ها – بخش کمک مدرس و نمره حضور و غیاب و مشارکت (فرایند ۷۵)'

export const TA_PASS_THRESHOLD = 74

export const FLOW_STEPS = [
  { key: 'trigger', label: 'جلسه ۱۸', states: ['grades_entry'] },
  { key: 'participation', label: 'ثبت مشارکت', states: ['grades_entry'] },
  { key: 'attendance', label: 'حضور سیستمی', states: ['grades_entry'] },
  { key: 'ta', label: 'نمره TA', states: ['grades_entry'] },
  { key: 'done', label: 'قفل نمرات', states: ['grades_locked'] },
  { key: 'delay', label: 'تأخیر', states: ['delay_reported'] },
]

export const STATE_HINTS = {
  grades_entry:
    'نمره مشارکت هر دانشجو (۰ تا ۱۰) را در روز جلسه ۱۸ ثبت کنید. نمره حضور و نمره TA به‌صورت سیستمی محاسبه می‌شود. پس از تکمیل، «ثبت نمرات مشارکت و قفل» را بزنید.',
  grades_locked:
    'نمرات مشارکت ثبت و قفل شد. گزارش PDF پایانی و نمره گزارش در فرایند «خاتمه هر درس عملی کاربردی و مشاهده فیلم‌ها» (فرایند ۶۴) پیگیری می‌شود.',
  delay_reported:
    'مهلت ثبت نمرات گذشته است؛ گزارش تأخیر به کمیته ارسال شده است. در صورت امکان همچنان می‌توانید نمرات را در فرم پایین ثبت کنید.',
}

const TERMINAL_STATES = new Set(['grades_locked', 'delay_reported'])
const SLA_DAYS = 7

export function isTerminalState(state) {
  return TERMINAL_STATES.has(state)
}

export function labelTaAttendanceState(state, processCode = PROCESS_CODE) {
  if (!state) return '—'
  return resolveStateDisplayLabel(state, null, processCode)
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function resolveLessonCompletionContext(ctx = {}) {
  const courseCode = courseCodeFromInstanceContext(ctx)
  const absenceCount =
    ctx.absence_count
    ?? ctx.class_absence_count
    ?? ctx.term_absence_count
    ?? null
  const attendanceScore =
    ctx.attendance_score != null
      ? Number(ctx.attendance_score)
      : absenceCount != null
        ? computeAttendanceScore(absenceCount)
        : null
  const taTotal =
    ctx.ta_total_score
    ?? ctx.ta_score
    ?? ctx.teaching_assistant_total_score
    ?? null

  return {
    courseCode: courseCode || null,
    courseName: ctx.course_name || ctx.lesson_name || courseCode || null,
    sessionIndex: ctx.session_index ?? ctx.session_number ?? 18,
    teachingAssistantName:
      ctx.teaching_assistant_name
      || ctx.teaching_assistant
      || ctx.ta_name
      || null,
    absenceCount: absenceCount != null ? Number(absenceCount) : null,
    attendanceScore,
    taTotalScore: taTotal != null ? Number(taTotal) : null,
    taPassFail: ctx.ta_pass_fail || (taTotal != null ? labelTaPassFail(taTotal) : null),
    studentsGrades: Array.isArray(ctx.students_grades) ? ctx.students_grades : [],
  }
}

export function resolveSlaInfo(ctx = {}, startedAt = null) {
  const merged = { ...ctx }
  if (startedAt && !merged.started_at) merged.started_at = startedAt
  return computeSlaRemaining(merged, SLA_DAYS, 'grades_entry_entered_at')
    || computeSlaRemaining(merged, SLA_DAYS, 'started_at')
}

function stepIndexForState(flowSteps, currentState) {
  if (!currentState || !flowSteps?.length) return 0
  if (currentState === 'delay_reported') {
    return flowSteps.findIndex((s) => s.key === 'delay')
  }
  if (currentState === 'grades_locked') {
    return flowSteps.findIndex((s) => s.key === 'done')
  }
  const idx = flowSteps.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function TaAttendanceFlowStepper({ currentState, compact = false }) {
  const activeIdx = stepIndexForState(FLOW_STEPS, currentState)
  const isTerminal = isTerminalState(currentState)
  const accent = '#0d9488'
  const accentBg = '#ccfbf1'
  const accentText = '#115e59'

  return (
    <div
      data-testid="film-observation-ta-flow-stepper"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.35rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {FLOW_STEPS.map((step, idx) => {
        const done = isTerminal ? idx <= activeIdx : idx < activeIdx
        const active = idx === activeIdx && !isTerminal
        const bg = done ? accentBg : active ? '#fff' : '#f8fafc'
        const border = done || active ? accent : '#e2e8f0'
        const color = done || active ? accentText : '#64748b'
        return (
          <div
            key={step.key}
            data-testid={`film-observation-ta-step-${step.key}`}
            style={{
              flex: compact ? '1 1 100%' : '1 1 auto',
              minWidth: compact ? 0 : '5rem',
              padding: compact ? '0.45rem 0.6rem' : '0.55rem 0.75rem',
              borderRadius: '8px',
              border: `1px solid ${border}`,
              borderRight: `4px solid ${border}`,
              background: bg,
              fontSize: compact ? '0.78rem' : '0.82rem',
              fontWeight: active ? 700 : 500,
              color,
              textAlign: 'center',
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

export function InfoTile({ label, value, tone = '#334155', bg = '#f8fafc' }) {
  if (value == null || value === '') return null
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

export function TaAttendanceSlaBanner({ ctx, startedAt }) {
  const slaInfo = resolveSlaInfo(ctx, startedAt)
  if (!slaInfo) return null
  return (
    <div data-testid="film-observation-ta-sla-banner">
      <SlaBanner slaInfo={slaInfo} title="مهلت ثبت نمرات مشارکت (۷ روز)" />
    </div>
  )
}

export function TaAttendanceHintBlock({ children, title = 'راهنمای مرحله', tone = 'info' }) {
  const colors = {
    info: { color: '#2563eb', bg: '#eff6ff' },
    warn: { color: '#d97706', bg: '#fffbeb' },
    danger: { color: '#dc2626', bg: '#fef2f2' },
  }
  const c = colors[tone] || colors.info
  return (
    <HintBlock title={title} color={c.color} bg={c.bg}>
      <span style={{ color: tone === 'danger' ? '#991b1b' : tone === 'warn' ? '#92400e' : '#1e40af' }}>
        {children}
      </span>
    </HintBlock>
  )
}
