/** نمایش مشترک فرایند ۴۸ — ثبت تاریخ ۲ جلسه تدریس خصوصی مدرس به کمک‌مدرس */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

export const MENTOR_PRIVATE_SESSIONS_PROCESS_CODE = 'mentor_private_sessions'

export const MENTOR_FLOW_STEPS = [
  { key: 'start', label: 'شروع مدرس', states: ['instructor_click'] },
  { key: 'registered', label: 'ثبت جلسات', states: ['sessions_registered'] },
  { key: 'done', label: 'نهایی', states: ['process_complete'] },
  { key: 'violation', label: 'تخلف', states: ['deadline_missed'] },
]

export const MENTOR_STATE_LABELS = {
  instructor_click: 'کلیک مدرس — ثبت زمان جلسات',
  sessions_registered: '۲ جلسه ثبت شد',
  process_complete: 'ثبت نهایی — SMS و یادآوری',
  deadline_missed: 'تخلف — عدم ثبت تا جلسه دوم',
}

export const PROCESS_TITLE_FA = 'ثبت تاریخ ۲ جلسه تدریس خصوصی مدرس به کمک‌مدرس (فرایند ۴۸)'

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

export function isMentorPrivateSessionsProcess(processCode) {
  return processCode === MENTOR_PRIVATE_SESSIONS_PROCESS_CODE
}

export function labelMentorPrivateState(state) {
  if (!state) return '—'
  return MENTOR_STATE_LABELS[state] || state
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function fmtSessionSlot(dateVal, timeVal) {
  const datePart = dateVal ? fmtIsoDate(dateVal) : ''
  const timePart = str(timeVal)
  if (datePart && timePart) return `${datePart} — ساعت ${timePart}`
  if (datePart) return datePart
  if (timePart) return `ساعت ${timePart}`
  return '—'
}

function courseCodeFromCtx(ctx = {}, lms = {}) {
  return str(
    ctx.course_id
    || ctx.course_code
    || ctx.lesson_course_label
    || '',
  )
}

function findClassSession2(lms = {}, courseCode = '') {
  const sessions = lms.course_sessions || []
  if (!Array.isArray(sessions)) return null
  const code = str(courseCode)
  for (const sess of sessions) {
    if (!sess || typeof sess !== 'object') continue
    const idx = sess.session_index ?? sess.session_number
    if (Number(idx) !== 2) continue
    const sessCourse = str(sess.course_id || sess.course_code || '')
    if (code && sessCourse && sessCourse !== code) continue
    return sess
  }
  return sessions.find((s) => Number(s?.session_index ?? s?.session_number) === 2) || null
}

/** داده‌های کلیدی فرایند ۴۸ از context و extra_data.lms. */
export function resolveMentorSessionContext(ctx = {}, extraData = {}) {
  const lms = extraData?.lms || ctx.lms || {}
  const courseCode = courseCodeFromCtx(ctx, lms)
  const taMap = lms.teaching_assistants_by_course || {}
  const classSession2 = findClassSession2(lms, courseCode)
  const session2Date = classSession2?.session_date || classSession2?.date || ctx.session_2_class_date || null
  const session2Time = str(classSession2?.session_time || classSession2?.start_time || ctx.session_2_class_time)

  return {
    courseCode,
    courseName: str(ctx.course_name) || str(ctx.lesson_course_label) || courseCode || '—',
    instructorName: str(ctx.instructor_name) || '—',
    teachingAssistantName: str(ctx.teaching_assistant_name)
      || str(ctx.teaching_assistant)
      || str(taMap[courseCode])
      || str(taMap[String(courseCode)])
      || '—',
    session1Date: ctx.session_1_date || null,
    session1Time: str(ctx.session_1_time) || null,
    session1Label: fmtSessionSlot(ctx.session_1_date, ctx.session_1_time),
    session2Date: ctx.session_2_date || null,
    session2Time: str(ctx.session_2_time) || null,
    session2Label: fmtSessionSlot(ctx.session_2_date, ctx.session_2_time),
    classSession2Date: session2Date,
    classSession2Time: session2Time,
    classSession2Label: fmtSessionSlot(session2Date, session2Time || null),
    sessionsRegistered: Boolean(
      ctx.session_1_date && ctx.session_1_time && ctx.session_2_date && ctx.session_2_time,
    ),
  }
}

export function activeMentorPrivateStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'deadline_missed') return 3
  if (currentState === 'process_complete') return 2
  if (currentState === 'sessions_registered') return 1
  return 0
}

export function MentorPrivateSessionsFlowStepper({
  currentState,
  compact = false,
  testId = 'mentor-private-sessions-stepper',
}) {
  const activeIdx = activeMentorPrivateStepIndex(currentState)
  const isViolation = currentState === 'deadline_missed'
  const isComplete = currentState === 'process_complete'

  return (
    <div
      data-testid={testId}
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.35rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {MENTOR_FLOW_STEPS.map((step, idx) => {
        let done = idx < activeIdx
        let current = idx === activeIdx
        if (isComplete && idx <= 2) done = true
        if (isViolation && step.key === 'violation') current = true
        if (isViolation && idx < 3 && step.key !== 'violation') done = idx === 0
        const tone = step.key === 'violation' && (current || isViolation)
          ? '#dc2626'
          : done ? '#16a34a' : current ? '#d97706' : '#94a3b8'
        const bg = step.key === 'violation' && (current || isViolation)
          ? '#fef2f2'
          : done ? '#ecfdf5' : current ? '#fffbeb' : '#f8fafc'
        return (
          <div
            key={step.key}
            data-testid={`mentor-private-step-${step.key}`}
            style={{
              flex: compact ? '1 1 42%' : '1 1 7rem',
              minWidth: compact ? '6.5rem' : '7rem',
              padding: compact ? '0.45rem 0.55rem' : '0.55rem 0.7rem',
              borderRadius: '8px',
              background: bg,
              borderRight: `3px solid ${tone}`,
              fontSize: compact ? '0.74rem' : '0.8rem',
              fontWeight: current ? 700 : 500,
              color: step.key === 'violation' && (current || isViolation)
                ? '#991b1b'
                : done ? '#166534' : current ? '#92400e' : '#64748b',
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

function InfoTile({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
  if (value == null || value === '' || value === '—') return null
  return (
    <div
      style={{
        flex: '1 1 10rem',
        padding: '0.6rem 0.75rem',
        background: bg,
        borderRadius: '8px',
        borderRight: `4px solid ${tone}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.72rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <strong style={{ fontSize: '0.88rem', color: tone }}>{value}</strong>
    </div>
  )
}

export function MentorSessionInfoTiles({ mentorCtx, compact = false }) {
  if (!mentorCtx) return null
  return (
    <div
      data-testid="mentor-session-info-tiles"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.4rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      <InfoTile label="نام درس" value={mentorCtx.courseName} tone="#2563eb" bg="#eff6ff" />
      <InfoTile label="نام مدرس" value={mentorCtx.instructorName} tone="#7c3aed" bg="#f5f3ff" />
      <InfoTile label="نام کمک‌مدرس" value={mentorCtx.teachingAssistantName} tone="#0d9488" bg="#f0fdfa" />
    </div>
  )
}

export function MentorDeadlineBanner({ mentorCtx, currentState }) {
  if (!mentorCtx || currentState !== 'instructor_click') return null
  const deadlineLabel = mentorCtx.classSession2Label
  if (!deadlineLabel || deadlineLabel === '—') {
    return (
      <div
        data-testid="mentor-deadline-banner"
        style={{
          padding: '0.65rem 0.85rem',
          marginBottom: '0.75rem',
          background: '#fffbeb',
          borderRadius: '8px',
          border: '1px solid #fde68a',
          fontSize: '0.82rem',
          lineHeight: 1.65,
          color: '#92400e',
        }}
      >
        <strong>مهلت:</strong>
        {' '}
        تکمیل این فرایند باید تا پیش از شروع جلسهٔ دوم کلاس انجام شود.
      </div>
    )
  }
  return (
    <div
      data-testid="mentor-deadline-banner"
      style={{
        padding: '0.65rem 0.85rem',
        marginBottom: '0.75rem',
        background: '#fff7ed',
        borderRadius: '8px',
        border: '1px solid #fdba74',
        fontSize: '0.82rem',
        lineHeight: 1.65,
        color: '#9a3412',
      }}
    >
      <strong>مهلت:</strong>
      {' '}
      ثبت تاریخ و ساعت دو جلسهٔ تدریس خصوصی باید تا پیش از شروع جلسهٔ دوم کلاس انجام شود.
      <br />
      <span style={{ fontSize: '0.8rem', color: '#c2410c' }}>
        شروع جلسهٔ دوم کلاس:
        {' '}
        <strong>{deadlineLabel}</strong>
      </span>
    </div>
  )
}

export function MentorSessionsSummary({ mentorCtx, testId = 'mentor-sessions-summary' }) {
  if (!mentorCtx?.sessionsRegistered && mentorCtx?.session1Label === '—' && mentorCtx?.session2Label === '—') {
    return null
  }
  return (
    <div
      data-testid={testId}
      style={{
        padding: '0.75rem',
        marginBottom: '0.75rem',
        background: '#ecfdf5',
        borderRadius: '8px',
        border: '1px solid #86efac',
        fontSize: '0.85rem',
        lineHeight: 1.75,
        color: '#166534',
      }}
    >
      <strong>جلسات تدریس خصوصی ثبت‌شده</strong>
      <ul style={{ margin: '0.35rem 0 0', paddingRight: '1.25rem' }}>
        <li>
          جلسهٔ اول:
          {' '}
          {mentorCtx.session1Label}
        </li>
        <li>
          جلسهٔ دوم:
          {' '}
          {mentorCtx.session2Label}
        </li>
      </ul>
    </div>
  )
}
