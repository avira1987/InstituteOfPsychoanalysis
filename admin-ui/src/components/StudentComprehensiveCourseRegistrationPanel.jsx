import React, { useMemo } from 'react'
import {
  CompRegFlowStepper,
  ScheduleChip,
  labelCompRegState,
  resolveInterviewSchedule,
  fmtIsoDate,
  fmtRialAsToman,
  isCompRegRejected,
} from '../utils/comprehensiveCourseRegistrationDisplay'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import TuitionQuoteSummary from './TuitionQuoteSummary'
import InstituteActivityLicenseNotice from './InstituteActivityLicenseNotice'

const PROCESS_TITLE_FA = 'ثبت‌نام دوره جامع (فرایند ۳۵)'
const PROC_CODE = 'comprehensive_course_registration'

function resolveCompRegHint(state) {
  if (!state) {
    return 'ثبت‌نام در دوره جامع — مراحل را طبق راهنمای پنل پیش ببرید.'
  }
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  const short = PROCESS_STATE_LABELS_FA[PROC_CODE]?.[state]
  return short || 'ثبت‌نام در دوره جامع — مراحل را طبق راهنمای پنل پیش ببرید.'
}

function InfoTile({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
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

/**
 * داشبورد راهنمای «ثبت‌نام دوره جامع» — فرایند ۳۵.
 * نمای دانشجو با مراحل، راهنمای وضعیت، و خلاصهٔ مصاحبه/پذیرش/پرداخت.
 */
export default function StudentComprehensiveCourseRegistrationPanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const interview = useMemo(() => resolveInterviewSchedule(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'comprehensive_course_registration') {
    return null
  }

  const hint = resolveCompRegHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelCompRegState(currentState)) ?? ''

  const isRejected = isCompRegRejected(currentState)
  const isComplete = currentState === 'registration_complete'

  const showInterview = !!(interview.date || interview.time)
    && ['interview_scheduled', 'interview_payment', 'interview_completed', 'result_accepted'].includes(currentState)

  const interviewFeeToman = fmtRialAsToman(ctx.interview_fee_rial, ctx.interview_fee_amount)
  const showInterviewFee = ['interview_scheduled', 'interview_payment'].includes(currentState) && interviewFeeToman

  const tuitionToman = fmtRialAsToman(ctx.tuition_amount_rial, ctx.tuition_amount)
  const showTuition = ['course_display', 'payment'].includes(currentState) && tuitionToman

  const showAcceptance = ['result_accepted', 'course_display', 'payment', 'registration_complete'].includes(currentState)

  return (
    <div className="card" data-testid="student-comprehensive-course-registration-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isRejected ? 'badge-danger' : isComplete ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelCompRegState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <CompRegFlowStepper currentState={currentState} compact={compact} />

        <InstituteActivityLicenseNotice compact={compact} />

        {hint && (
          <div
            data-testid="comp-reg-state-hint"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: isRejected ? '#fef2f2' : '#eff6ff',
              borderRight: isRejected ? '4px solid #dc2626' : '4px solid #2563eb',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: isRejected ? '#991b1b' : '#1e3a8a',
            }}
          >
            {statusShort && (
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.25rem' }}>
                وضعیت فعلی: {statusShort}
              </div>
            )}
            <div style={{ fontWeight: 600, marginBottom: '0.2rem' }}>اقدام بعدی شما</div>
            {hint}
          </div>
        )}

        {(showInterviewFee || showTuition) && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '0.65rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            {showInterviewFee && (
              <InfoTile label="هزینه مصاحبه" value={interviewFeeToman} tone="#b45309" bg="#fffbeb" />
            )}
            {showTuition && (
              <InfoTile label="شهریه دوره" value={tuitionToman} tone="#b45309" bg="#fffbeb" />
            )}
          </div>
        )}

        {['course_display', 'payment'].includes(currentState) && (
          <TuitionQuoteSummary contextData={ctx} compact={compact} />
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.5rem' : '0.75rem',
          }}
        >
          {showInterview && (
            <ScheduleChip
              testId="comp-reg-interview-schedule"
              label="زمان مصاحبه"
              date={interview.date}
              time={interview.time}
              extra={interview.type
                ? `نوع مصاحبه: ${interview.type === 'online' ? 'آنلاین' : 'حضوری'}`
                : null}
              tone="#2563eb"
              bg="#eff6ff"
            />
          )}
        </div>

        {showAcceptance && !isComplete && (
          <div
            data-testid="comp-reg-acceptance-block"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#166534',
            }}
          >
            <strong>شرایط پذیرش:</strong>
            {' '}
            حداقل ۲ بار در هفته درمان شخصی الزامی است و تمامی دروس ترم جامع اجباری هستند.
          </div>
        )}

        {isComplete && (
          <div
            data-testid="comp-reg-complete-block"
            style={{
              marginTop: '0.5rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
              ثبت‌نام شما در دوره جامع نهایی شد
              {ctx.registered_at ? ` — ${fmtIsoDate(ctx.registered_at)}` : ''}
              . کلاس‌ها و لینک‌های آنلاین در پنل آموزش در دسترس قرار می‌گیرد.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
