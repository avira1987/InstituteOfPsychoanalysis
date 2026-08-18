import React, { useMemo } from 'react'
import {
  IntroRegFlowStepper,
  ScheduleChip,
  labelIntroRegState,
  resolveInterviewSchedule,
  resolveAdmission,
  fmtIsoDate,
  fmtRialAsToman,
  ADMISSION_TYPE_LABELS,
  INTRO_REG_TERMINAL_REJECT,
} from '../utils/introductoryCourseRegistrationDisplay'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import TuitionQuoteSummary from './TuitionQuoteSummary'
import InstituteActivityLicenseNotice from './InstituteActivityLicenseNotice'

const PROCESS_TITLE_FA = 'ثبت‌نام دوره آشنایی (فرایند ۳۱)'
const PROC_CODE = 'introductory_course_registration'

function resolveIntroRegHint(state) {
  if (!state) {
    return 'پذیرش و ثبت‌نام در دوره آشنایی — مراحل را طبق راهنمای پنل پیش ببرید.'
  }
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  const short = PROCESS_STATE_LABELS_FA[PROC_CODE]?.[state]
  return short || 'پذیرش و ثبت‌نام در دوره آشنایی — مراحل را طبق راهنمای پنل پیش ببرید.'
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
 * داشبورد راهنمای «ثبت‌نام دوره آشنایی» — فرایند ۳۱.
 * نمای متقاضی/دانشجو با مراحل، راهنمای وضعیت، و خلاصهٔ مصاحبه/پذیرش/پرداخت.
 */
export default function StudentIntroductoryCourseRegistrationPanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const interview = useMemo(() => resolveInterviewSchedule(ctx), [ctx])
  const admission = useMemo(() => resolveAdmission(ctx), [ctx])

  if (!active || !detail || detail.process_code !== PROC_CODE) {
    return null
  }

  const hint = resolveIntroRegHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelIntroRegState(currentState)) ?? ''

  const isRejected = currentState === INTRO_REG_TERMINAL_REJECT
  const isComplete = currentState === 'registration_complete'

  const showInterview = !!(interview.date || interview.time)
  const admissionLabel = admission.type ? (ADMISSION_TYPE_LABELS[admission.type] || admission.type) : null
  const showAdmission = !!admissionLabel && [
    'result_conditional_therapy', 'result_single_course', 'result_full_admission',
    'documents_upload', 'documents_incomplete', 'documents_review',
    'credentials_created', 'course_selection', 'payment', 'registration_complete', 'installment_overdue',
  ].includes(currentState)

  const interviewFeeToman = fmtRialAsToman(ctx.interview_fee_rial, ctx.interview_fee_amount)
  const showInterviewFee = ['interview_scheduled', 'interview_payment'].includes(currentState) && interviewFeeToman

  const tuitionToman = fmtRialAsToman(ctx.tuition_amount_rial, ctx.tuition_amount)
  const showTuition = ['course_selection', 'payment', 'installment_overdue'].includes(currentState) && tuitionToman

  return (
    <div className="card" data-testid="student-introductory-course-registration-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isRejected ? 'badge-danger' : isComplete ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelIntroRegState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <IntroRegFlowStepper currentState={currentState} compact={compact} />

        <InstituteActivityLicenseNotice compact={compact} />

        {!isRejected && hint && (
          <div
            data-testid="intro-reg-state-hint"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#eff6ff',
              borderRight: '4px solid #2563eb',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#1e3a8a',
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

        {(showInterviewFee || showTuition || showAdmission) && (
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
            {showAdmission && (
              <InfoTile label="نتیجه پذیرش" value={admissionLabel} tone="#16a34a" bg="#f0fdf4" />
            )}
          </div>
        )}

        {['course_selection', 'payment', 'installment_overdue'].includes(currentState) && (
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
              testId="intro-reg-interview-schedule"
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

          {admission.allowedCourseCount != null && showAdmission && (
            <ScheduleChip
              testId="intro-reg-allowed-courses"
              label="سقف انتخاب درس"
              extra={`حداکثر ${Number(admission.allowedCourseCount).toLocaleString('fa-IR')} درس`}
              tone="#7c3aed"
              bg="#f5f3ff"
            />
          )}
        </div>

        {currentState === 'installment_overdue' && (
          <div
            role="status"
            data-testid="intro-reg-overdue-note"
            style={{
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#991b1b',
            }}
          >
            توجه: تا پرداخت قسط معوق، امکان ثبت حضور شما در کلاس‌ها وجود ندارد و غیبت ثبت می‌شود.
          </div>
        )}

        {isComplete && (
          <div
            data-testid="intro-reg-complete-block"
            style={{
              marginTop: '0.5rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
              ثبت‌نام شما در دوره آشنایی نهایی شد
              {ctx.registered_at ? ` — ${fmtIsoDate(ctx.registered_at)}` : ''}
              . کلاس‌ها و لینک‌های آنلاین در پنل آموزش در دسترس قرار می‌گیرد.
            </p>
            {(ctx.intro_registration_next_step_fa || '').trim() && (
              <p style={{ margin: '0.5rem 0 0', fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
                {ctx.intro_registration_next_step_fa}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
