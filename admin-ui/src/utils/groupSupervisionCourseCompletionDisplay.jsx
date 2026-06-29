/** نمایش مشترک «خاتمه هر درس سوپرویژن گروهی» — فرایند SOP ۶۲. */

import React from 'react'
import { courseCodeFromInstanceContext } from './lessonAttendanceDisplay'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'
import { resolveStateDisplayLabel } from './processDisplay'
import { HintBlock } from './attendanceChainDisplay'

export const PROCESS_CODE = 'group_supervision_course_completion'

export const PROCESS_TITLE_FA =
  'خاتمه هر درس سوپرویژن گروهی (فرایند ۶۲)'

export const HOURS_PER_PASS = 33.3333
export const HOURS_PER_PASS_DISPLAY = '۳۳.۳'
export const HOURS_CAP = 100
export const ATTENDANCE_MAX = 8
export const TA_PASS_THRESHOLD = 74

export const FLOW_STEPS = [
  { key: 'wait', label: 'منتظر جلسه ۱۸', states: ['awaiting_session_18'] },
  { key: 'pass_fail', label: 'Pass/Fail جلسه ۱۸', states: ['session_18_pass_fail_entry'] },
  { key: 'hours', label: 'اعمال ساعات', states: ['pass_fail_applied'] },
  { key: 'ta', label: 'ارزیابی TA', states: ['ta_evaluation_entry'] },
  { key: 'qual', label: 'ارزیابی کیفی', states: ['qualitative_eval_pending'] },
  { key: 'done', label: 'قفل نمرات', states: ['grades_locked'] },
  { key: 'delay', label: 'تأخیر', states: ['session_18_delay', 'qualitative_eval_delay'] },
]

export const STATE_HINTS = {
  awaiting_session_18:
    'با رسیدن تقویم به جلسه ۱۸، ثبت Pass/Fail برای دانشجویان باز می‌شود.',
  session_18_pass_fail_entry:
    'وضعیت مشارکت هر دانشجو را Pass یا Fail ثبت کنید. مهلت: ۲۴:۰۰ همان روز جلسه ۱۸. Pass → +۳۳.۳ ساعت سوپرویژن گروهی.',
  pass_fail_applied:
    'نتایج Pass/Fail اعمال شد. ساعات بالینی در پرونده دانشجویان Pass به‌روزرسانی می‌شود.',
  ta_evaluation_entry:
    'نمره حضور (۰–۸) و وظایف کمک‌مدرس را بررسی و ثبت کنید. ≥ ۷۴ PASS.',
  qualitative_eval_pending:
    'فرم ارزیابی کیفی (سوال ۷ و ۸) را ظرف ۴ روز برای تک‌تک دانشجویان تکمیل کنید.',
  grades_locked: 'نمرات و ساعات ثبت و قفل شد.',
  session_18_delay: 'مهلت ثبت Pass/Fail گذشته — گزارش به کمیته دروس ارسال شده است.',
  qualitative_eval_delay: 'تأخیر ارزیابی کیفی — گزارش تخلف ثبت شده است.',
}

const TERMINAL_STATES = new Set(['grades_locked', 'session_18_delay', 'qualitative_eval_delay'])
const SLA_HOURS_S18 = 24
const SLA_DAYS_QUAL = 4

export function isTerminalState(state) {
  return TERMINAL_STATES.has(state)
}

export function isGroupSupervisionCourseProcess(code) {
  return code === PROCESS_CODE
}

export function labelGroupSupervisionState(state, processCode = PROCESS_CODE) {
  if (!state) return '—'
  return resolveStateDisplayLabel(state, null, processCode)
}

export function fmtHours(hours) {
  if (hours == null || hours === '') return '—'
  const n = Number(hours)
  if (!Number.isFinite(n)) return String(hours)
  return n.toLocaleString('fa-IR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

export function normalizePassFail(value) {
  const raw = String(value || '').trim().toUpperCase()
  if (raw === 'PASS' || raw === 'P') return 'PASS'
  if (raw === 'FAIL' || raw === 'F') return 'FAIL'
  return raw || ''
}

export function labelPassFail(value) {
  const pf = normalizePassFail(value)
  if (pf === 'PASS') return 'PASS'
  if (pf === 'FAIL') return 'FAIL'
  return '—'
}

export function computeAttendanceScore(absenceCount) {
  const n = Number(absenceCount) || 0
  return Math.max(0, ATTENDANCE_MAX - n * 2)
}

export function computeTaTotal(attendance, duties) {
  const a = Number(attendance)
  const d = Number(duties)
  if (!Number.isFinite(a) || !Number.isFinite(d)) return null
  return a + d
}

export function labelTaPassFail(total) {
  if (total == null) return '—'
  return total >= TA_PASS_THRESHOLD ? 'PASS' : 'FAIL'
}

export function resolveGroupSupervisionContext(ctx = {}) {
  const courseCode = courseCodeFromInstanceContext(ctx)
  return {
    courseCode,
    courseName: ctx.course_name || courseCode || '—',
    courseHasTa: ctx.course_has_ta === true,
    studentsGrades: ctx.students_grades || [],
    taName: ctx.ta_name,
    taAttendance: ctx.ta_attendance_score,
    taDuties: ctx.ta_duties_score,
    taTotal: ctx.ta_total_score,
    taPassFail: ctx.ta_pass_fail,
    groupSupervisionHours: ctx.group_supervision_hours,
  }
}

export function rosterRowToPassFailRow(row, prefilledById = {}, hoursPerPass = HOURS_PER_PASS) {
  const sid = String(row.student_id || '')
  const pref = prefilledById[sid] || {}
  const hoursBefore = Number(
    pref.group_supervision_hours_before
    ?? row.group_supervision_hours_before
    ?? 0,
  )
  const pf = normalizePassFail(pref.pass_fail ?? row.pass_fail) || 'PASS'
  const hoursAdded = pf === 'PASS' ? hoursPerPass : 0
  const hoursAfter = Math.min(HOURS_CAP, hoursBefore + hoursAdded)
  return {
    student_id: sid,
    student_name: row.student_name || row.name_fa || sid,
    role: row.role || 'student',
    pass_fail: pf,
    absence_count: row.absence_count ?? pref.absence_count ?? 0,
    group_supervision_hours_before: hoursBefore,
    hours_added: hoursAdded,
    hours_after: hoursAfter,
  }
}

export function validatePassFailRow(row) {
  const pf = normalizePassFail(row.pass_fail)
  if (!pf || (pf !== 'PASS' && pf !== 'FAIL')) {
    return { ok: false, message: 'وضعیت Pass یا Fail الزامی است.' }
  }
  return { ok: true, value: pf }
}

export function buildPassFailPayload(rows, courseCode, courseName) {
  return {
    course_name: courseName || courseCode,
    course_code: courseCode,
    students_grades: rows
      .filter((r) => (r.role || 'student') !== 'teaching_assistant')
      .map((r) => ({
        student_id: r.student_id,
        student_name: r.student_name,
        pass_fail: normalizePassFail(r.pass_fail),
        hours_added: r.hours_added,
      })),
    pass_fail_submitted_before_sla: true,
  }
}

export function buildTaGradesPayload(taAttendance, taDuties, courseCode, courseName, taName) {
  return {
    course_name: courseName || courseCode,
    course_code: courseCode,
    ta_name: taName,
    ta_attendance_score: Number(taAttendance),
    ta_duties_score: Number(taDuties),
  }
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

export function GroupSupervisionFlowStepper({ currentState, compact = false }) {
  const activeIdx = stepIndexForState(FLOW_STEPS, currentState)
  const isTerminal = isTerminalState(currentState)
  const accent = '#0d9488'
  const accentBg = '#ccfbf1'
  const accentText = '#115e59'

  return (
    <div
      data-testid="group-supervision-flow-stepper"
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
            data-testid={`group-supervision-step-${step.key}`}
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
  if (currentState === 'session_18_pass_fail_entry') {
    return computeSlaRemaining(merged, SLA_HOURS_S18 / 24, 'session_18_entered_at')
      || computeSlaRemaining(merged, SLA_HOURS_S18 / 24, 'started_at')
  }
  if (currentState === 'qualitative_eval_pending') {
    return computeSlaRemaining(merged, SLA_DAYS_QUAL, 'qualitative_eval_entered_at')
      || computeSlaRemaining(merged, SLA_DAYS_QUAL, 'started_at')
  }
  return null
}

export function GroupSupervisionSlaBanner({ ctx, startedAt, currentState }) {
  const slaInfo = resolveSlaInfo(ctx, startedAt, currentState)
  if (!slaInfo) return null
  const title = currentState === 'session_18_pass_fail_entry'
    ? 'مهلت ثبت Pass/Fail (۲۴ ساعت)'
    : 'مهلت ارزیابی کیفی (۴ روز)'
  return (
    <div data-testid="group-supervision-sla-banner">
      <SlaBanner slaInfo={slaInfo} title={title} />
    </div>
  )
}

export function GroupSupervisionHintBlock({ children, title = 'راهنمای مرحله', tone = 'info' }) {
  const colors = {
    info: { color: '#0d9488', bg: '#f0fdfa' },
    warn: { color: '#d97706', bg: '#fffbeb' },
    danger: { color: '#dc2626', bg: '#fef2f2' },
  }
  const c = colors[tone] || colors.info
  return (
    <HintBlock title={title} color={c.color} bg={c.bg}>
      <span style={{ color: tone === 'danger' ? '#991b1b' : tone === 'warn' ? '#92400e' : '#115e59' }}>
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

export function hoursSummaryLabel() {
  return `هر Pass → +${HOURS_PER_PASS_DISPLAY} ساعت (حداکثر ${HOURS_CAP.toLocaleString('fa-IR')} ساعت در ۳ درس)`
}
