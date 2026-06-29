/** نمایش مشترک «خاتمه درس عملی کاربردی / مشاهده فیلم — گزارش PDF و نمره نهایی» — فرایند SOP ۶۴. */

import React from 'react'
import { courseCodeFromInstanceContext } from './lessonAttendanceDisplay'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'
import { resolveStateDisplayLabel } from './processDisplay'
import { formatShamsiTehran } from './shamsiDateTime'
import { HintBlock } from './attendanceChainDisplay'
import { parseStepFileUploadValue, resolveUploadPublicUrl } from './uploadPublicUrl'

export const PROCESS_CODE = 'film_observation_course_completion'

export const PROCESS_TITLE_FA =
  'خاتمه هر درس عملی کاربردی و مشاهده فیلم‌ها (فرایند ۶۴)'

export const REPORT_MAX = 82
export const PARTICIPATION_MAX = 10
export const ATTENDANCE_MAX = 8
export const PASS_THRESHOLD = 74
export const BORDERLINE_MIN = 64
export const BORDERLINE_MAX = 73
export const TOTAL_MAX = 100

export const BORDERLINE_SMS_FA =
  'دانشجوی گرامی، نمره نهایی شما در محدوده مرزی قرار گرفته است. شما دقیقاً ۲۴ ساعت از زمان دریافت این پیامک مهلت دارید تا در صورت تمایل، جهت فعال‌سازی فرصت بارگذاری مجدد گزارش، نسبت به پرداخت هزینه در پورتال خود اقدام فرمایید. در غیر این صورت، نمره فعلی قطعی خواهد شد.'

export const FINAL_REPORT_FILE_FIELDS = [
  { name: 'final_report_pdf', label_fa: 'گزارش پایانی PDF', type: 'file_upload' },
]

export const FINAL_REPORT_MAX_MB = 25

export const FLOW_STEPS = [
  { key: 'upload_open', label: 'باز شدن آپلود (جلسه ۱۷)', states: ['grades_entry'] },
  { key: 'upload_deadline', label: 'مهلت آپلود (جلسه ۱۸)', states: ['grades_entry'] },
  { key: 'grading', label: 'تصحیح اولیه (۵ روز)', states: ['grades_entry'] },
  { key: 'total', label: 'جمع نمره', states: ['grades_entry', 'grades_locked'] },
  { key: 'borderline', label: 'مرزی / امتحان مجدد', states: ['grades_entry', 'grades_locked'] },
  { key: 'qual_eval', label: 'ارزیابی کیفی (۴ روز)', states: ['grades_entry', 'grades_locked'] },
  { key: 'done', label: 'قفل نمرات', states: ['grades_locked'] },
  { key: 'delay', label: 'تأخیر', states: ['delay_reported'] },
]

export const STATE_HINTS = {
  grades_entry:
    'گزارش‌های PDF آپلودشده را بررسی و نمره گزارش (۰ تا ۸۲) را برای هر دانشجو ثبت کنید. جمع نمره: مشارکت (۱۰) + حضور (۸) + گزارش (۸۲) = ۱۰۰. مهلت تصحیح اولیه: ۵ روز از ۲۴:۰۰ روز جلسه ۱۸.',
  grades_locked:
    'نمرات گزارش ثبت و قفل شد. برای نمرات مرزی ۶۴–۷۳، دانشجو می‌تواند امتحان مجدد را انتخاب کند. ارزیابی کیفی (۴ روز پس از جلسه ۱۸) را در فرم پایین تکمیل کنید.',
  delay_reported:
    'مهلت ثبت نمرات گذشته است؛ گزارش تأخیر به کمیته ارسال شده است.',
}

const TERMINAL_STATES = new Set(['grades_locked', 'delay_reported'])
const SLA_DAYS = 7

export function isTerminalState(state) {
  return TERMINAL_STATES.has(state)
}

export function isFilmObservationCourseProcess(code) {
  return code === PROCESS_CODE
}

export function labelFilmCompletionState(state, processCode = PROCESS_CODE) {
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

export function validateReportGrade(value) {
  if (value === '' || value == null) return { ok: false, message: 'نمره گزارش الزامی است.' }
  const n = Number(value)
  if (!Number.isFinite(n)) return { ok: false, message: 'نمره گزارش باید عدد باشد.' }
  if (n < 0 || n > REPORT_MAX) {
    return { ok: false, message: `نمره گزارش باید بین ۰ تا ${REPORT_MAX} باشد.` }
  }
  return { ok: true, value: n }
}

export function computeTotalScore(participation, attendance, report) {
  const p = Number(participation)
  const a = Number(attendance)
  const r = Number(report)
  const sum = (Number.isFinite(p) ? p : 0)
    + (Number.isFinite(a) ? a : 0)
    + (Number.isFinite(r) ? r : 0)
  return Math.min(TOTAL_MAX, Math.max(0, sum))
}

export function labelPassFail(total) {
  if (total == null || total === '') return '—'
  const n = Number(total)
  if (!Number.isFinite(n)) return String(total)
  if (n >= PASS_THRESHOLD) return 'PASS'
  if (n < BORDERLINE_MIN) return 'FAIL'
  return 'مرزی'
}

export function labelBorderlineStatus(total) {
  const n = Number(total)
  if (!Number.isFinite(n)) return null
  if (n >= BORDERLINE_MIN && n <= BORDERLINE_MAX) return 'امتحان مجدد یا دوباره گذراندن درس'
  return null
}

export function resolveReportFileFromRow(row = {}) {
  return row.final_report_pdf
    ?? row.report_file
    ?? row.report_pdf
    ?? row.final_report
    ?? null
}

export function resolveFilmCompletionContext(ctx = {}) {
  const courseCode = courseCodeFromInstanceContext(ctx)
  const participation =
    ctx.participation_score != null ? Number(ctx.participation_score) : null
  const attendance =
    ctx.attendance_score != null ? Number(ctx.attendance_score) : null
  const reportGrade =
    ctx.report_grade != null
      ? Number(ctx.report_grade)
      : ctx.grade != null
        ? Number(ctx.grade)
        : null
  const total =
    ctx.total_score != null
      ? Number(ctx.total_score)
      : (participation != null || attendance != null || reportGrade != null)
        ? computeTotalScore(
          participation ?? 0,
          attendance ?? 0,
          reportGrade ?? 0,
        )
        : null

  return {
    courseCode: courseCode || null,
    courseName: ctx.course_name || ctx.lesson_name || courseCode || null,
    sessionIndex: ctx.session_index ?? ctx.session_number ?? 18,
    participationScore: participation,
    attendanceScore: attendance,
    reportGrade,
    totalScore: total,
    passFail: ctx.pass_fail || (total != null ? labelPassFail(total) : null),
    borderline: total != null ? labelBorderlineStatus(total) : null,
    finalReportPdf: ctx.final_report_pdf ?? null,
    studentsGrades: Array.isArray(ctx.students_grades) ? ctx.students_grades : [],
    reportUploadedAt: ctx.final_report_uploaded_at ?? ctx.report_uploaded_at ?? null,
    retakeEligible: ctx.retake_eligible ?? null,
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

export function FilmCompletionFlowStepper({ currentState, compact = false }) {
  const activeIdx = stepIndexForState(FLOW_STEPS, currentState)
  const isTerminal = isTerminalState(currentState)
  const accent = '#7c3aed'
  const accentBg = '#ede9fe'
  const accentText = '#5b21b6'

  return (
    <div
      data-testid="film-observation-course-flow-stepper"
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
            data-testid={`film-observation-course-step-${step.key}`}
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

export function FilmCompletionSlaBanner({ ctx, startedAt }) {
  const slaInfo = resolveSlaInfo(ctx, startedAt)
  if (!slaInfo) return null
  return (
    <div data-testid="film-observation-course-sla-banner">
      <SlaBanner slaInfo={slaInfo} title="مهلت ثبت نمرات گزارش (۷ روز)" />
    </div>
  )
}

export function FilmCompletionHintBlock({ children, title = 'راهنمای مرحله', tone = 'info' }) {
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

export function ReportPdfLink({ fileValue, label = 'گزارش PDF' }) {
  const { url, mime } = parseStepFileUploadValue(fileValue)
  const src = url ? resolveUploadPublicUrl(url) : ''
  if (!src) {
    return <span style={{ color: '#94a3b8', fontSize: '0.82rem' }}>آپلود نشده</span>
  }
  const isPdf = (mime || '').includes('pdf') || /\.pdf($|\?)/i.test(src)
  return (
    <a
      href={src}
      target="_blank"
      rel="noopener noreferrer"
      style={{ fontSize: '0.82rem', color: '#2563eb' }}
    >
      {isPdf ? `📄 ${label}` : label}
    </a>
  )
}

export function rosterRowToReportGradeRow(entry, prefilled = {}, ctxDefaults = {}) {
  const sid = String(entry.student_id || '')
  const pref = prefilled[sid] || {}
  const participation =
    pref.participation_score
    ?? entry.participation_score
    ?? ctxDefaults.participationScore
    ?? ''
  const attendance =
    pref.attendance_score
    ?? entry.attendance_score
    ?? ctxDefaults.attendanceScore
    ?? 8
  const reportGrade =
    pref.report_grade
    ?? pref.grade
    ?? entry.report_grade
    ?? entry.grade
    ?? ''
  const reportFile = resolveReportFileFromRow(pref) || resolveReportFileFromRow(entry)
  const total = computeTotalScore(participation, attendance, reportGrade)

  return {
    student_id: sid,
    student_name: entry.name_fa || entry.student_name || entry.student_code || sid,
    student_code: entry.student_code || sid,
    role: entry.role || 'student',
    participation_score: participation,
    attendance_score: Number(attendance) || 0,
    report_grade: reportGrade,
    report_file: reportFile,
    total_score: Number.isFinite(total) ? total : null,
    pass_fail: labelPassFail(total),
    borderline: labelBorderlineStatus(total),
  }
}

export function buildStudentsGradesPayload(rows) {
  return rows
    .filter((r) => (r.role || 'student') !== 'teaching_assistant')
    .map((r) => {
      const report = Number(r.report_grade)
      const participation = Number(r.participation_score) || 0
      const attendance = Number(r.attendance_score) || 0
      const total = computeTotalScore(participation, attendance, report)
      return {
        student_id: r.student_id,
        student_name: r.student_name,
        report_grade: report,
        participation_score: participation || undefined,
        attendance_score: attendance || undefined,
        total_score: total,
        grade: report,
        pass_fail: labelPassFail(total),
      }
    })
}

export function labelReportGrade(value) {
  if (value === '' || value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  return n.toLocaleString('fa-IR')
}

/** وضعیت پنجره آپلود گزارش (جلسه ۱۷–۱۸) — نمایشی؛ بدون بلاک سخت اگر فیلد نباشد. */
export function resolveUploadWindowStatus(ctx = {}) {
  const openAt = ctx.upload_window_open_at || ctx.report_upload_open_at
  const closeAt = ctx.upload_window_close_at || ctx.report_upload_close_at
  const sessionIndex = ctx.session_index ?? ctx.session_number ?? null
  if (openAt || closeAt) {
    return {
      label: 'مهلت آپلود گزارش',
      detail: [
        openAt ? `شروع: ${fmtIsoDate(openAt)}` : null,
        closeAt ? `پایان: ${fmtIsoDate(closeAt)}` : null,
      ].filter(Boolean).join(' — ') || 'طبق تقویم کلاس',
      tone: 'info',
    }
  }
  if (sessionIndex != null) {
    const sn = Number(sessionIndex)
    if (Number.isFinite(sn) && sn >= 17) {
      return {
        label: 'پنجره آپلود',
        detail: sn >= 18
          ? 'مهلت آپلود تا ۲۴:۰۰ روز جلسه ۱۸'
          : 'آپلود از پایان جلسه ۱۷ فعال است',
        tone: sn >= 18 ? 'warn' : 'info',
      }
    }
  }
  return {
    label: 'مهلت آپلود',
    detail: 'از پایان جلسه ۱۷ تا ۲۴:۰۰ روز جلسه ۱۸',
    tone: 'info',
  }
}

export function FilmCompletionUploadBanner({ ctx }) {
  const status = resolveUploadWindowStatus(ctx)
  const colors = {
    info: { color: '#2563eb', bg: '#eff6ff', border: '#93c5fd' },
    warn: { color: '#d97706', bg: '#fffbeb', border: '#fcd34d' },
  }
  const c = colors[status.tone] || colors.info
  return (
    <div
      data-testid="film-observation-upload-window-banner"
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: c.bg,
        borderRight: `4px solid ${c.border}`,
        fontSize: '0.84rem',
        lineHeight: 1.7,
        color: c.color,
      }}
    >
      <strong>{status.label}:</strong>
      {' '}
      {status.detail}
    </div>
  )
}
