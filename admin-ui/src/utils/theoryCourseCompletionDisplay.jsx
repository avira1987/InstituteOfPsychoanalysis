/** نمایش مشترک «خاتمه دروس تئوری» — فرایند SOP ۶۱. */

import React from 'react'
import { courseCodeFromInstanceContext } from './lessonAttendanceDisplay'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'
import { resolveStateDisplayLabel } from './processDisplay'
import { formatShamsiTehran } from './shamsiDateTime'
import { HintBlock } from './attendanceChainDisplay'

export const PROCESS_CODE = 'theory_course_completion'

export const PROCESS_TITLE_FA = 'خاتمه دروس تئوری (فرایند ۶۱)'

export const PARTICIPATION_MAX = 10
export const ATTENDANCE_MAX = 8
export const EXAM_MAX = 82
export const PASS_THRESHOLD = 74
export const BORDERLINE_MIN = 64
export const BORDERLINE_MAX = 73
export const TOTAL_MAX = 100

export const BORDERLINE_HINT_FA =
  'نمره شما در بازه مرزی (۶۴ تا ۷۳) است. می‌توانید امتحان مجدد (با پرداخت) یا دوباره گذراندن درس را انتخاب کنید.'

export const FLOW_STEPS = [
  { key: 's18_wait', label: 'منتظر جلسه ۱۸', states: ['awaiting_session_18'] },
  { key: 's18', label: 'جلسه ۱۸ — مشارکت', states: ['session_18_entry'] },
  { key: 'exam', label: 'آزمون تستی', states: ['final_exam_open', 'grades_computed'] },
  { key: 'borderline', label: 'مرزی / مجدد', states: ['borderline_student_choice', 'retake_exam_open'] },
  { key: 'qual', label: 'ارزیابی کیفی', states: ['qualitative_eval_pending'] },
  { key: 'done', label: 'قفل نمرات', states: ['grades_locked'] },
  { key: 'delay', label: 'تأخیر', states: ['session_18_delay', 'qualitative_eval_delay'] },
]

export const STATE_HINTS = {
  awaiting_session_18:
    'با رسیدن تقویم به جلسه ۱۸، ثبت مشارکت و انتخاب پک آزمون باز می‌شود.',
  session_18_entry:
    'مشارکت (۰–۱۰) را برای هر دانشجو ثبت کنید و پک آزمون تستی (۸۲ نمره) را تأیید کنید. مهلت: ۲۴:۰۰ همان روز جلسه ۱۸. حضور خودکار محاسبه می‌شود.',
  final_exam_open:
    'آزمون تستی آنلاین (۸۲ نمره) در پورتال برگزار می‌شود. غیبت در آزمون → Incomplete.',
  grades_computed:
    'نمرات نهایی محاسبه شد. جمع: مشارکت (۱۰) + حضور (۸) + آزمون (۸۲) = ۱۰۰.',
  borderline_student_choice: BORDERLINE_HINT_FA,
  retake_exam_open:
    'پس از پرداخت، امتحان مجدد با پک جدید در همان ساعت (۴ روز بعد) برگزار می‌شود.',
  qualitative_eval_pending:
    'فرم ارزیابی کیفی (سوال ۷ و ۸) را ظرف ۴ روز برای تک‌تک دانشجویان تکمیل کنید.',
  grades_locked: 'نمرات ثبت و قفل شد.',
  session_18_delay: 'مهلت ثبت جلسه ۱۸ گذشته — گزارش به کمیته ارسال شده است.',
  qualitative_eval_delay: 'تأخیر ارزیابی کیفی — گزارش تخلف ثبت شده است.',
}

const TERMINAL_STATES = new Set(['grades_locked', 'session_18_delay', 'qualitative_eval_delay'])
const SLA_HOURS_S18 = 24
const SLA_DAYS_QUAL = 4

export function isTerminalState(state) {
  return TERMINAL_STATES.has(state)
}

export function isTheoryCourseProcess(code) {
  return code === PROCESS_CODE
}

export function labelTheoryState(state, processCode = PROCESS_CODE) {
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

export function computeAttendanceScore(absenceCount) {
  const n = Number(absenceCount) || 0
  return Math.max(0, ATTENDANCE_MAX - n * 2)
}

export function isIncompleteRow(row = {}) {
  if (row.incomplete) return true
  if (row.exam_absent || row.test_absent) return true
  return false
}

export function computeTotalScore(participation, test, attendance, incomplete = false) {
  if (incomplete) return null
  const p = Number(participation)
  const t = Number(test)
  const a = Number(attendance)
  const sum = (Number.isFinite(p) ? p : 0)
    + (Number.isFinite(t) ? t : 0)
    + (Number.isFinite(a) ? a : 0)
  return Math.min(TOTAL_MAX, Math.max(0, sum))
}

export function isBorderlineTotal(total) {
  if (total == null || total === '') return false
  const n = Number(total)
  return Number.isFinite(n) && n >= BORDERLINE_MIN && n <= BORDERLINE_MAX
}

export function labelPassFail(total, incomplete = false) {
  if (incomplete) return 'I'
  if (total == null || total === '') return '—'
  const n = Number(total)
  if (!Number.isFinite(n)) return String(total)
  if (n >= PASS_THRESHOLD) return 'PASS'
  if (isBorderlineTotal(n)) return 'مرزی'
  return 'FAIL'
}

export function labelBorderlineStatus(total) {
  if (!isBorderlineTotal(total)) return null
  return 'امتحان مجدد یا دوباره گذراندن درس'
}

export function validateParticipation(value) {
  if (value === '' || value == null) return { ok: false, message: 'نمره مشارکت الزامی است.' }
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0 || n > PARTICIPATION_MAX) {
    return { ok: false, message: `مشارکت باید بین ۰ تا ${PARTICIPATION_MAX} باشد.` }
  }
  return { ok: true, value: n }
}

export function validateExamPackId(value) {
  if (!value || !String(value).trim()) {
    return { ok: false, message: 'انتخاب پک آزمون الزامی است.' }
  }
  return { ok: true, value: String(value).trim() }
}

export function resolveTheoryCompletionContext(ctx = {}) {
  const courseCode = courseCodeFromInstanceContext(ctx)
  const studentsGrades = Array.isArray(ctx.students_grades) ? ctx.students_grades : []

  return {
    courseCode: courseCode || null,
    courseName: ctx.course_name || ctx.lesson_name || courseCode || null,
    examPackId: ctx.exam_pack_id || null,
    retakeExamPackId: ctx.retake_exam_pack_id || null,
    courseHasTa: ctx.course_has_ta ?? null,
    taName: ctx.ta_name || null,
    taPassFail: ctx.ta_pass_fail || null,
    studentsGrades,
    totalScore: ctx.total_score != null ? Number(ctx.total_score) : null,
    passFail: ctx.pass_fail || null,
    borderlinePending: ctx.borderline_pending === true,
    testScore: ctx.test_score != null ? Number(ctx.test_score) : null,
    participationScore: ctx.participation_score != null ? Number(ctx.participation_score) : null,
    attendanceScore: ctx.attendance_score != null ? Number(ctx.attendance_score) : null,
    incomplete: ctx.incomplete === true,
    sessionIndex: ctx.session_index ?? 18,
  }
}

export function rosterRowToSession18Row(entry, prefilled = {}) {
  const sid = String(entry.student_id || '')
  const pref = prefilled[sid] || {}
  const participation = pref.participation_score ?? entry.participation_score ?? ''
  const absence = pref.absence_count ?? entry.absence_count ?? 0
  const attendance = pref.attendance_score ?? computeAttendanceScore(absence)

  return {
    student_id: sid,
    student_name: entry.name_fa || entry.student_name || entry.student_code || sid,
    student_code: entry.student_code || sid,
    role: entry.role || 'student',
    participation_score: participation,
    attendance_score: attendance,
    absence_count: absence,
    test_score: pref.test_score ?? entry.test_score ?? '',
    exam_absent: pref.exam_absent ?? entry.exam_absent ?? false,
    total_score: pref.total_score ?? entry.total_score ?? null,
    pass_fail: pref.pass_fail ?? entry.pass_fail ?? null,
  }
}

export function buildSession18Payload(rows, courseCode, courseName, examPackId) {
  return {
    course_name: courseName || courseCode,
    course_code: courseCode,
    exam_pack_id: examPackId,
    students_grades: rows
      .filter((r) => (r.role || 'student') !== 'teaching_assistant')
      .map((r) => ({
        student_id: r.student_id,
        student_name: r.student_name,
        participation_score: Number(r.participation_score),
        attendance_score: r.attendance_score ?? computeAttendanceScore(r.absence_count),
        absence_count: r.absence_count ?? 0,
      })),
    session_18_submitted_before_sla: true,
  }
}

export function buildExamCompletedPayload(testScore, examAbsent = false) {
  const payload = { exam_absent: !!examAbsent }
  if (!examAbsent && testScore !== '' && testScore != null) {
    payload.test_score = Number(testScore)
  }
  return payload
}

export function buildRetakeCompletedPayload(retakeScore, examAbsent = false) {
  const payload = { exam_absent: !!examAbsent }
  if (!examAbsent && retakeScore !== '' && retakeScore != null) {
    payload.retake_test_score = Number(retakeScore)
    payload.test_score = Number(retakeScore)
  }
  return payload
}

function stepIndexForState(flowSteps, currentState) {
  if (!currentState || !flowSteps?.length) return 0
  if (currentState === 'session_18_delay' || currentState === 'qualitative_eval_delay') {
    return flowSteps.findIndex((s) => s.key === 'delay')
  }
  if (currentState === 'grades_locked') {
    return flowSteps.findIndex((s) => s.key === 'done')
  }
  const idx = flowSteps.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function TheoryFlowStepper({ currentState, compact = false }) {
  const activeIdx = stepIndexForState(FLOW_STEPS, currentState)
  const isTerminal = isTerminalState(currentState)
  const accent = '#7c3aed'
  const accentBg = '#ede9fe'
  const accentText = '#5b21b6'

  return (
    <div
      data-testid="theory-course-flow-stepper"
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
            data-testid={`theory-course-step-${step.key}`}
            style={{
              flex: compact ? '1 1 100%' : '1 1 auto',
              minWidth: compact ? 0 : '4.5rem',
              padding: compact ? '0.45rem 0.6rem' : '0.55rem 0.75rem',
              borderRadius: '8px',
              border: `1px solid ${border}`,
              borderRight: `4px solid ${border}`,
              background: bg,
              fontSize: compact ? '0.75rem' : '0.8rem',
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

export function resolveSlaInfo(ctx = {}, startedAt = null, currentState = null) {
  const merged = { ...ctx }
  if (startedAt && !merged.started_at) merged.started_at = startedAt
  if (currentState === 'session_18_entry') {
    return computeSlaRemaining(merged, SLA_HOURS_S18 / 24, 'session_18_entered_at')
      || computeSlaRemaining(merged, SLA_HOURS_S18 / 24, 'started_at')
  }
  if (currentState === 'qualitative_eval_pending') {
    return computeSlaRemaining(merged, SLA_DAYS_QUAL, 'qualitative_eval_entered_at')
      || computeSlaRemaining(merged, SLA_DAYS_QUAL, 'started_at')
  }
  return null
}

export function TheorySlaBanner({ ctx, startedAt, currentState }) {
  const slaInfo = resolveSlaInfo(ctx, startedAt, currentState)
  if (!slaInfo) return null
  const title = currentState === 'session_18_entry'
    ? 'مهلت ثبت جلسه ۱۸ (۲۴ ساعت)'
    : 'مهلت ارزیابی کیفی (۴ روز)'
  return (
    <div data-testid="theory-course-sla-banner">
      <SlaBanner slaInfo={slaInfo} title={title} />
    </div>
  )
}

export function TheoryHintBlock({ children, title = 'راهنمای مرحله', tone = 'info' }) {
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

export function labelGrade(value) {
  if (value === '' || value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  return n.toLocaleString('fa-IR')
}

export function scoringSummaryLabel() {
  return `مشارکت ${PARTICIPATION_MAX.toLocaleString('fa-IR')} + حضور ${ATTENDANCE_MAX.toLocaleString('fa-IR')} + آزمون ${EXAM_MAX.toLocaleString('fa-IR')} = ${TOTAL_MAX.toLocaleString('fa-IR')}`
}
