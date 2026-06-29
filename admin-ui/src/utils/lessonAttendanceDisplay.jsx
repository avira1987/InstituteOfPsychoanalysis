/** نمایش مشترک ثبت حضور کلاس — فرایند class_attendance / پنل مدرس و دانشجو. */

import React from 'react'
import { fmtIsoDate, labelAttendanceSessionStatus } from './lessonStartPerTermDisplay'
import { resolveStateDisplayLabel } from './processDisplay'
import { HintBlock } from './attendanceChainDisplay'

export { fmtIsoDate, labelAttendanceSessionStatus }

export const PROCESS_CODE = 'class_attendance'

export const PROCESS_TITLE_FA = 'حضور و غیاب در تمامی کلاس‌ها (فرایند ۵۴)'

export const ATTENDANCE_STATUS_LABELS = {
  present: 'حاضر',
  absent: 'غایب',
}

export const CLASS_ATTENDANCE_STATE_LABELS = {
  attendance_list_ready: 'لیست حضور و غیاب در پورتال مدرس',
  session_recorded: 'وضعیت جلسه ثبت شد',
  incomplete_triggered: '۵ غیبت — وضعیت I و قفل نمره',
  article_violation_reported: 'غیبت درس مقاله‌نویسی — گزارش به کمیته نظارت',
}

export const FLOW_STEPS = [
  { key: 'ready', label: 'لیست آماده', states: ['attendance_list_ready'] },
  { key: 'recorded', label: 'ثبت جلسه', states: ['session_recorded'] },
  { key: 'outcome', label: 'نتیجه سیستمی', states: ['incomplete_triggered', 'article_violation_reported'] },
]

export const INSTRUCTOR_STATE_HINTS = {
  attendance_list_ready:
    'برای هر دانشجو و کمک‌مدرس «حاضر» یا «غایب» را انتخاب کنید و دکمهٔ ثبت را بزنید. ستون «غیبت‌های قبلی» تعداد غیبت در همین درس را نشان می‌دهد.',
  session_recorded: 'حضور و غیاب این جلسه ثبت شد. شمارندهٔ غیبت دانشجویان غایب به‌روز شده است.',
  incomplete_triggered: 'برای برخی افراد با ۵ غیبت، وضعیت Incomplete و قفل نمره اعمال شد.',
  article_violation_reported: 'برای درس مقاله‌نویسی، گزارش به کمیته نظارت ارجاع شد (بدون Incomplete).',
}

export const STUDENT_STATE_HINTS = {
  attendance_list_ready: 'مدرس در حال ثبت حضور و غیاب این جلسه است. پس از ثبت، وضعیت شما در جدول زیر به‌روز می‌شود.',
  session_recorded: 'حضور یا غیبت شما در این جلسه ثبت شد. شمارندهٔ غیبت در همین درس در کارت بالا نمایش داده می‌شود.',
  incomplete_triggered:
    'با ۵ غیبت در این درس، وضعیت Incomplete و قفل نمره اعمال شده است. باید در ترم‌های بعد درس را مجدداً اخذ کنید.',
  article_violation_reported:
    'تعداد غیبت‌های شما در درس مقاله‌نویسی از حد مجاز گذشته است. پرونده به کمیته نظارت ارجاع شده است؛ وضعیت Incomplete اعمال نمی‌شود.',
}

const TERMINAL_STATES = new Set(['incomplete_triggered', 'article_violation_reported'])

export function labelAttendanceStatus(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'present' || s === 'حاضر') return ATTENDANCE_STATUS_LABELS.present
  if (s === 'absent' || s === 'غایب' || s === 'absent_unexcused') return ATTENDANCE_STATUS_LABELS.absent
  return status || '—'
}

export function labelClassAttendanceState(state, processCode = PROCESS_CODE) {
  if (!state) return '—'
  return CLASS_ATTENDANCE_STATE_LABELS[state]
    || resolveStateDisplayLabel(state, null, processCode)
}

export function activeClassAttendanceStepIndex(currentState) {
  if (!currentState) return 0
  if (TERMINAL_STATES.has(currentState) || currentState === 'session_recorded') {
    return FLOW_STEPS.length - 1
  }
  const idx = FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function isTerminalClassAttendanceState(state) {
  return TERMINAL_STATES.has(state) || state === 'session_recorded'
}

export function courseCodeFromInstanceContext(ctx = {}) {
  return (
    ctx.course_code
    || ctx.course_id
    || ctx.lesson_course_label
    || ctx.lesson_name
    || ctx.course_name
    || ''
  )
}

export function isLiveSupervisionCourse(ctx = {}) {
  const ct = (ctx.course_type || '').toLowerCase()
  return ct === 'live_supervision' || Boolean(ctx.live_supervision_session)
}

export function isArticleWritingCourse(ctx = {}) {
  const ct = (ctx.course_type || '').toLowerCase()
  if (ct === 'article_writing') return true
  const code = courseCodeFromInstanceContext(ctx).toLowerCase()
  return 'article' in code || 'مقاله' in courseCodeFromInstanceContext(ctx)
}

export function todayIsoDate() {
  return new Date().toISOString().slice(0, 10)
}

export function resolveClassAttendanceContext(ctx = {}, extraData = {}) {
  const lms = extraData?.lms || ctx.lms || {}
  const courseCode = courseCodeFromInstanceContext(ctx)
  const lessonName = ctx.lesson_name || ctx.lesson_course_label || courseCode || '—'
  const sessionDate = ctx.session_date || todayIsoDate()
  const courseType = ctx.course_type || (isLiveSupervisionCourse(ctx)
    ? 'live_supervision'
    : isArticleWritingCourse(ctx)
      ? 'article_writing'
      : 'standard')

  const attendanceRosters = lms.lesson_attendance || {}
  const roster = attendanceRosters[courseCode] || attendanceRosters[String(courseCode)] || {}
  const sessions = mergedClassSessionsForCourse(lms, courseCode)
  const absenceCount = Number(roster.absence_count ?? 0)

  const summary = ctx.attendance_summary || {}
  const studentsAttendance = ctx.students_attendance || ctx.attendees || []

  return {
    courseCode,
    lessonName,
    sessionDate,
    courseType,
    absenceCount,
    sessions,
    studentsAttendance,
    summary,
    teachingAssistant: ctx.teaching_assistant_name || ctx.teaching_assistant || '',
    submittedAt: ctx.submitted_at || summary.recorded_at || null,
  }
}

export function ClassAttendanceFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeClassAttendanceStepIndex(currentState)
  const completed = isTerminalClassAttendanceState(currentState)

  return (
    <div
      data-testid="class-attendance-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {FLOW_STEPS.map((step, i) => {
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
          </div>
        )
      })}
    </div>
  )
}

const HINT_TONES = {
  info: { color: '#2563eb', bg: '#eff6ff' },
  warn: { color: '#d97706', bg: '#fffbeb' },
  danger: { color: '#dc2626', bg: '#fef2f2' },
}

export function ClassAttendanceHintBlock({ children, tone = 'info' }) {
  const palette = HINT_TONES[tone] || HINT_TONES.info
  return (
    <HintBlock color={palette.color} bg={palette.bg}>
      {children}
    </HintBlock>
  )
}

export function AbsenceCounterTile({ count, max = 5, label = 'غیبت در این درس' }) {
  const n = Number(count) || 0
  const danger = n >= max
  const warn = n >= max - 1 && n < max
  const tone = danger ? '#dc2626' : warn ? '#d97706' : '#16a34a'
  const bg = danger ? '#fef2f2' : warn ? '#fffbeb' : '#f0fdf4'
  return (
    <div
      data-testid="class-attendance-absence-counter"
      style={{
        padding: '0.85rem 1rem',
        marginBottom: '0.85rem',
        borderRadius: '8px',
        background: bg,
        borderRight: `4px solid ${tone}`,
      }}
    >
      <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: '0.25rem' }}>{label}</div>
      <div style={{ fontSize: '1.2rem', fontWeight: 800, color: tone }}>
        {n.toLocaleString('fa-IR')}
        <span className="muted" style={{ fontSize: '0.85rem', fontWeight: 500 }}>
          {' '}
          از
          {' '}
          {max.toLocaleString('fa-IR')}
        </span>
      </div>
    </div>
  )
}

export function labelClassSessionRowStatus(session = {}) {
  if (session.is_makeup) return 'جبرانی'
  if (session.cancelled === true || String(session.status || '').toLowerCase() === 'cancelled') {
    return 'کنسل'
  }
  if (session.attendance_locked) return 'قفل'
  return labelAttendanceSessionStatus(session.status)
}

export function mergedClassSessionsForCourse(lms = {}, courseCode = '') {
  const code = String(courseCode || '')
  const attendanceRosters = lms.lesson_attendance || {}
  const roster = attendanceRosters[code] || attendanceRosters[String(code)] || {}
  const fromRoster = Array.isArray(roster.sessions) ? roster.sessions : []
  const fromCalendar = (Array.isArray(lms.course_sessions) ? lms.course_sessions : [])
    .filter((s) => {
      if (!s || typeof s !== 'object') return false
      const sc = String(s.course_id || s.course_code || '')
      return !sc || sc === code
    })
    .map((s) => ({
      session_number: s.session_index || s.session_number,
      date: s.session_date || s.date,
      status: s.status,
      cancelled: s.cancelled,
      is_makeup: s.is_makeup,
      attendance_locked: s.attendance_locked,
      session_time: s.session_time || s.start_time,
    }))

  const seen = new Set()
  const merged = []
  for (const row of [...fromRoster, ...fromCalendar]) {
    const key = `${row.session_number}|${row.date}`
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(row)
  }
  merged.sort((a, b) => String(a.date || '').localeCompare(String(b.date || '')))
  return merged
}
