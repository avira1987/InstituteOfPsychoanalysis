/** نمایش مشترک «خاتمه درس مشاهده زنده درمان — گزارش PDF و نمره نهایی» — فرایند SOP ۶۵. */

export {
  REPORT_MAX,
  PARTICIPATION_MAX,
  ATTENDANCE_MAX,
  PASS_THRESHOLD,
  BORDERLINE_MIN,
  BORDERLINE_MAX,
  TOTAL_MAX,
  BORDERLINE_SMS_FA,
  FINAL_REPORT_FILE_FIELDS,
  FINAL_REPORT_MAX_MB,
  isTerminalState,
  fmtIsoDate,
  validateReportGrade,
  computeTotalScore,
  labelPassFail,
  labelBorderlineStatus,
  resolveReportFileFromRow,
  resolveSlaInfo,
  InfoTile,
  ReportPdfLink,
  rosterRowToReportGradeRow,
  buildStudentsGradesPayload,
  labelReportGrade,
  resolveUploadWindowStatus,
} from './filmObservationCourseCompletionDisplay'

import React from 'react'
import { resolveStateDisplayLabel } from './processDisplay'
import {
  FilmCompletionFlowStepper,
  FilmCompletionHintBlock,
  FilmCompletionSlaBanner,
  FilmCompletionUploadBanner,
  resolveFilmCompletionContext,
} from './filmObservationCourseCompletionDisplay'

export const PROCESS_CODE = 'live_therapy_observation_course_completion'

export const PROCESS_TITLE_FA =
  'خاتمه درس مشاهده زنده درمان — آپلود گزارش پایانی (فرایند ۶۵)'

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
    'نمرات گزارش ثبت و قفل شد. برای نمرات مرزی ۶۴–۷۳، دانشجو می‌تواند امتحان مجدد را انتخاب کند.',
  delay_reported:
    'مهلت ثبت نمرات گذشته است؛ گزارش تأخیر به کمیته ارسال شده است.',
}

export function isLiveTherapyObservationCourseProcess(code) {
  return code === PROCESS_CODE
}

export function labelLiveTherapyCompletionState(state, processCode = PROCESS_CODE) {
  if (!state) return '—'
  return resolveStateDisplayLabel(state, null, processCode)
}

export function resolveLiveTherapyCompletionContext(ctx = {}) {
  return resolveFilmCompletionContext(ctx)
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

export function LiveTherapyCompletionFlowStepper({ currentState, compact = false }) {
  const activeIdx = stepIndexForState(FLOW_STEPS, currentState)
  const isTerminal = currentState === 'grades_locked' || currentState === 'delay_reported'
  const accent = '#0d9488'
  const accentBg = '#ccfbf1'
  const accentText = '#0f766e'

  return (
    <div
      data-testid="live-therapy-observation-course-flow-stepper"
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
            data-testid={`live-therapy-observation-course-step-${step.key}`}
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

export function LiveTherapyCompletionSlaBanner({ ctx, startedAt }) {
  const slaInfo = resolveSlaInfo(ctx, startedAt)
  if (!slaInfo) return null
  return (
    <div data-testid="live-therapy-observation-course-sla-banner">
      <FilmCompletionSlaBanner ctx={ctx} startedAt={startedAt} />
    </div>
  )
}

export function LiveTherapyCompletionHintBlock(props) {
  return <FilmCompletionHintBlock {...props} />
}

export function LiveTherapyCompletionUploadBanner({ ctx }) {
  return <FilmCompletionUploadBanner ctx={ctx} />
}
