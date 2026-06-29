/** نمایش مشترک «خاتمه دروس تکنیک: تمرین مهارت‌ها» — فرایند SOP ۶۳. */

import React from 'react'
import { courseCodeFromInstanceContext } from './lessonAttendanceDisplay'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'
import { resolveStateDisplayLabel } from './processDisplay'
import { formatShamsiTehran } from './shamsiDateTime'
import { HintBlock } from './attendanceChainDisplay'

export const PROCESS_CODE = 'skills_course_completion'

export const PROCESS_TITLE_FA =
  'خاتمه دروس تکنیک: تمرین مهارت‌ها (فرایند ۶۳)'

export const PARTICIPATION_MAX = 10
export const ATTENDANCE_MAX = 8
export const PASS_THRESHOLD = 74
export const TOTAL_MAX = 100
export const PRACTICAL_MAX_NORMAL = 60
export const PRACTICAL_MAX_SKILLS_4 = 42
export const TEST_MAX_NORMAL = 22
export const TEST_MAX_SKILLS_4 = 40

export const PRACTICAL_REFERENCE_HINT =
  'امتحان عملی مطابق جدول مرجع (تحویلی از آقای صالحی) نمره‌دهی می‌شود.'

export const FLOW_STEPS = [
  { key: 's17_wait', label: 'منتظر جلسه ۱۷', states: ['awaiting_session_17'] },
  { key: 's17', label: 'جلسه ۱۷ — عملی', states: ['session_17_grades_entry'] },
  { key: 's18_wait', label: 'منتظر جلسه ۱۸', states: ['awaiting_session_18'] },
  { key: 's18', label: 'جلسه ۱۸ — تستی', states: ['session_18_grades_entry', 'grades_computed'] },
  { key: 'ta', label: 'ارزیابی TA', states: ['ta_evaluation_entry'] },
  { key: 'qual', label: 'ارزیابی کیفی', states: ['qualitative_eval_pending'] },
  { key: 'done', label: 'قفل نمرات', states: ['grades_locked'] },
  { key: 'delay', label: 'تأخیر', states: ['session_17_delay', 'qualitative_eval_delay'] },
]

export const STATE_HINTS = {
  awaiting_session_17:
    'با رسیدن تقویم به جلسه ۱۷، فیلدهای نمره‌دهی باز می‌شود.',
  session_17_grades_entry:
    'مشارکت (۰–۱۰) و امتحان عملی را برای هر دانشجو ثبت کنید. مهلت: ۲۴:۰۰ همان روز جلسه ۱۷.',
  awaiting_session_18:
    'نمرات جلسه ۱۷ ثبت شد. پس از جلسه ۱۸، آزمون تستی را ثبت کنید.',
  session_18_grades_entry:
    'نمره آزمون تستی را ثبت کنید. حضور و غیاب خودکار محاسبه می‌شود. غیبت در عملی یا تست → Incomplete.',
  grades_computed:
    'نمرات نهایی محاسبه شد. در صورت وجود کمک‌مدرس، ارزیابی TA انجام دهید.',
  ta_evaluation_entry:
    'نمره حضور (۰–۸) و وظایف کمک‌مدرس را بررسی و ثبت کنید. ≥ ۷۴ PASS.',
  qualitative_eval_pending:
    'فرم ارزیابی کیفی (سوال ۷ و ۸) را ظرف ۴ روز برای تک‌تک دانشجویان تکمیل کنید.',
  grades_locked: 'نمرات ثبت و قفل شد. بدون امتحان مجدد.',
  session_17_delay: 'مهلت ثبت جلسه ۱۷ گذشته — گزارش به کمیته ارسال شده است.',
  qualitative_eval_delay: 'تأخیر ارزیابی کیفی — گزارش تخلف ثبت شده است.',
}

const TERMINAL_STATES = new Set(['grades_locked', 'session_17_delay', 'qualitative_eval_delay'])
const SLA_HOURS_S17 = 24
const SLA_DAYS_QUAL = 4

export function isTerminalState(state) {
  return TERMINAL_STATES.has(state)
}

export function isSkillsCourseProcess(code) {
  return code === PROCESS_CODE
}

export function practicalMax(variant) {
  return variant === 'skills_4' ? PRACTICAL_MAX_SKILLS_4 : PRACTICAL_MAX_NORMAL
}

export function testMax(variant) {
  return variant === 'skills_4' ? TEST_MAX_SKILLS_4 : TEST_MAX_NORMAL
}

export function labelSkillsState(state, processCode = PROCESS_CODE) {
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
  if (row.session_17_absent || row.session_18_absent) return true
  if (row.practical_absent || row.test_absent) return true
  return false
}

export function computeTotalScore(participation, practical, test, attendance, incomplete = false) {
  if (incomplete) return null
  const p = Number(participation)
  const pr = Number(practical)
  const t = Number(test)
  const a = Number(attendance)
  const sum = (Number.isFinite(p) ? p : 0)
    + (Number.isFinite(pr) ? pr : 0)
    + (Number.isFinite(t) ? t : 0)
    + (Number.isFinite(a) ? a : 0)
  return Math.min(TOTAL_MAX, Math.max(0, sum))
}

export function labelPassFail(total, incomplete = false) {
  if (incomplete) return 'I'
  if (total == null || total === '') return '—'
  const n = Number(total)
  if (!Number.isFinite(n)) return String(total)
  if (n >= PASS_THRESHOLD) return 'PASS'
  return 'FAIL'
}

export function validateParticipation(value) {
  if (value === '' || value == null) return { ok: false, message: 'نمره مشارکت الزامی است.' }
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0 || n > PARTICIPATION_MAX) {
    return { ok: false, message: `مشارکت باید بین ۰ تا ${PARTICIPATION_MAX} باشد.` }
  }
  return { ok: true, value: n }
}

export function validatePracticalGrade(value, variant) {
  const max = practicalMax(variant)
  if (value === '' || value == null) return { ok: false, message: 'نمره عملی الزامی است.' }
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0 || n > max) {
    return { ok: false, message: `نمره عملی باید بین ۰ تا ${max} باشد.` }
  }
  return { ok: true, value: n }
}

export function validateTestGrade(value, variant) {
  const max = testMax(variant)
  if (value === '' || value == null) return { ok: false, message: 'نمره تستی الزامی است.' }
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0 || n > max) {
    return { ok: false, message: `نمره تستی باید بین ۰ تا ${max} باشد.` }
  }
  return { ok: true, value: n }
}

export function resolveSkillsCompletionContext(ctx = {}) {
  const courseCode = courseCodeFromInstanceContext(ctx)
  const variant = ctx.skills_variant
    || (String(ctx.course_name || courseCode || '').includes('۴') ? 'skills_4' : 'normal')
  const studentsGrades = Array.isArray(ctx.students_grades) ? ctx.students_grades : []

  return {
    courseCode: courseCode || null,
    courseName: ctx.course_name || ctx.lesson_name || courseCode || null,
    skillsVariant: variant,
    practicalMax: practicalMax(variant),
    testMax: testMax(variant),
    courseHasTa: ctx.course_has_ta ?? null,
    taName: ctx.ta_name || null,
    taTotalScore: ctx.ta_total_score != null ? Number(ctx.ta_total_score) : null,
    taPassFail: ctx.ta_pass_fail || null,
    studentsGrades,
    totalScore: ctx.total_score != null ? Number(ctx.total_score) : null,
    passFail: ctx.pass_fail || null,
    incomplete: ctx.incomplete === true,
    sessionIndex: ctx.session_index ?? null,
  }
}

export function rosterRowToSession17Row(entry, prefilled = {}, variant = 'normal') {
  const sid = String(entry.student_id || '')
  const pref = prefilled[sid] || {}
  const participation = pref.participation_score ?? entry.participation_score ?? ''
  const practical = pref.practical_score ?? entry.practical_score ?? ''
  const s17Absent = pref.session_17_absent ?? entry.session_17_absent ?? false
  const incomplete = s17Absent || pref.incomplete

  return {
    student_id: sid,
    student_name: entry.name_fa || entry.student_name || entry.student_code || sid,
    student_code: entry.student_code || sid,
    role: entry.role || 'student',
    participation_score: participation,
    practical_score: practical,
    session_17_absent: s17Absent,
    absence_count: entry.absence_count ?? pref.absence_count ?? 0,
    incomplete,
    practical_max: practicalMax(variant),
  }
}

export function rosterRowToSession18Row(entry, prefilled = {}, variant = 'normal') {
  const sid = String(entry.student_id || '')
  const pref = prefilled[sid] || {}
  const participation = Number(pref.participation_score ?? entry.participation_score ?? 0) || 0
  const practical = Number(pref.practical_score ?? entry.practical_score ?? 0) || 0
  const test = pref.test_score ?? entry.test_score ?? ''
  const s17Absent = pref.session_17_absent ?? entry.session_17_absent ?? false
  const s18Absent = pref.session_18_absent ?? entry.session_18_absent ?? false
  const absence = pref.absence_count ?? entry.absence_count ?? 0
  const attendance = computeAttendanceScore(absence)
  const incomplete = s17Absent || s18Absent || pref.incomplete
  const total = incomplete
    ? null
    : computeTotalScore(participation, practical, test, attendance, false)

  return {
    student_id: sid,
    student_name: entry.name_fa || entry.student_name || entry.student_code || sid,
    student_code: entry.student_code || sid,
    role: entry.role || 'student',
    participation_score: participation,
    practical_score: practical,
    test_score: test,
    attendance_score: attendance,
    absence_count: absence,
    session_17_absent: s17Absent,
    session_18_absent: s18Absent,
    incomplete,
    total_score: total,
    pass_fail: labelPassFail(total, incomplete),
    test_max: testMax(variant),
  }
}

export function buildSession17Payload(rows, courseCode, courseName, variant) {
  return {
    course_name: courseName || courseCode,
    course_code: courseCode,
    skills_variant: variant,
    students_grades: rows
      .filter((r) => (r.role || 'student') !== 'teaching_assistant')
      .map((r) => ({
        student_id: r.student_id,
        student_name: r.student_name,
        participation_score: Number(r.participation_score),
        practical_score: Number(r.practical_score),
        session_17_absent: !!r.session_17_absent,
        practical_absent: !!r.session_17_absent,
      })),
    session_17_submitted_before_sla: true,
  }
}

export function buildSession18Payload(rows, courseCode, courseName, testExamId) {
  return {
    course_name: courseName || courseCode,
    course_code: courseCode,
    test_exam_id: testExamId || undefined,
    students_grades: rows
      .filter((r) => (r.role || 'student') !== 'teaching_assistant')
      .map((r) => ({
        student_id: r.student_id,
        student_name: r.student_name,
        test_score: r.session_18_absent ? undefined : Number(r.test_score),
        session_18_absent: !!r.session_18_absent,
        test_absent: !!r.session_18_absent,
        participation_score: r.participation_score,
        practical_score: r.practical_score,
        absence_count: r.absence_count,
        session_17_absent: r.session_17_absent,
      })),
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
  if (currentState === 'session_17_delay' || currentState === 'qualitative_eval_delay') {
    return flowSteps.findIndex((s) => s.key === 'delay')
  }
  if (currentState === 'grades_locked') {
    return flowSteps.findIndex((s) => s.key === 'done')
  }
  const idx = flowSteps.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function SkillsFlowStepper({ currentState, compact = false }) {
  const activeIdx = stepIndexForState(FLOW_STEPS, currentState)
  const isTerminal = isTerminalState(currentState)
  const accent = '#0d9488'
  const accentBg = '#ccfbf1'
  const accentText = '#115e59'

  return (
    <div
      data-testid="skills-course-flow-stepper"
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
            data-testid={`skills-course-step-${step.key}`}
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
  if (currentState === 'session_17_grades_entry') {
    return computeSlaRemaining(merged, SLA_HOURS_S17 / 24, 'session_17_entered_at')
      || computeSlaRemaining(merged, SLA_HOURS_S17 / 24, 'started_at')
  }
  if (currentState === 'qualitative_eval_pending') {
    return computeSlaRemaining(merged, SLA_DAYS_QUAL, 'qualitative_eval_entered_at')
      || computeSlaRemaining(merged, SLA_DAYS_QUAL, 'started_at')
  }
  return null
}

export function SkillsSlaBanner({ ctx, startedAt, currentState }) {
  const slaInfo = resolveSlaInfo(ctx, startedAt, currentState)
  if (!slaInfo) return null
  const title = currentState === 'session_17_grades_entry'
    ? 'مهلت ثبت جلسه ۱۷ (۲۴ ساعت)'
    : 'مهلت ارزیابی کیفی (۴ روز)'
  return (
    <div data-testid="skills-course-sla-banner">
      <SlaBanner slaInfo={slaInfo} title={title} />
    </div>
  )
}

export function SkillsHintBlock({ children, title = 'راهنمای مرحله', tone = 'info' }) {
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

export function variantLabel(variant) {
  return variant === 'skills_4' ? 'مهارت‌های ۴' : 'مهارت عادی'
}

export function scoringSummaryLabel(variant) {
  return `مشارکت ${PARTICIPATION_MAX.toLocaleString('fa-IR')} + عملی ${practicalMax(variant).toLocaleString('fa-IR')} + تست ${testMax(variant).toLocaleString('fa-IR')} + حضور ${ATTENDANCE_MAX.toLocaleString('fa-IR')} = ${TOTAL_MAX.toLocaleString('fa-IR')}`
}
