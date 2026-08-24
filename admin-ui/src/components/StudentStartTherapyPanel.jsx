import React, { useMemo } from 'react'
import SepPaymentPanel from './SepPaymentPanel'
import { labelState } from '../utils/processDisplay'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import {
  isSingleCourseAdmission,
  isConditionalTherapyAdmission,
  CONDITIONAL_THERAPY_TERM2_NOTICE_FA,
} from '../utils/studentProcessAccess'

const PROCESS_TITLE_FA = 'آغاز درمان آموزشی'
const PROC_CODE = 'start_therapy'

function resolveStartTherapyHint(state) {
  if (!state) {
    return 'مراحل آغاز درمان آموزشی را در فرم زیر پیش ببرید.'
  }
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  const short = PROCESS_STATE_LABELS_FA[PROC_CODE]?.[state]
  return short || 'مراحل آغاز درمان آموزشی را در فرم زیر پیش ببرید.'
}

const STEPS = [
  { key: 'therapist_selection', label: 'انتخاب از شیت' },
  { key: 'first_session_24h_check', label: 'زمان‌بندی' },
  { key: 'payment_pending', label: 'پرداخت' },
  { key: 'therapy_active', label: 'فعال' },
]

function stepIndex(state) {
  if (state === 'first_session_24h_check') return 1
  const order = STEPS.map((s) => s.key)
  const idx = order.indexOf(state)
  return idx >= 0 ? idx : 0
}

function FlowStepper({ currentState }) {
  const active = stepIndex(currentState)
  return (
    <ol className="return-flow-stepper" style={{ margin: '0 0 1rem', padding: 0, listStyle: 'none', display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
      {STEPS.map((s, i) => {
        const done = i < active || currentState === 'therapy_active'
        const current = s.key === currentState
        return (
          <li
            key={s.key}
            style={{
              padding: '0.25rem 0.55rem',
              borderRadius: 6,
              fontSize: '0.78rem',
              background: current ? '#dbeafe' : done ? '#dcfce7' : '#f1f5f9',
              color: current ? '#1d4ed8' : done ? '#15803d' : '#64748b',
            }}
          >
            {s.label}
          </li>
        )
      })}
    </ol>
  )
}

export default function StudentStartTherapyPanel({
  detail = null,
  studentProfile = null,
  active = true,
  compact = false,
  onPaymentDone,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const courseType = studentProfile?.course_type || ctx.course_type || 'introductory'
  const weeklyHint = courseType === 'comprehensive' ? 'دقیقاً ۲ جلسه در هفته' : '۱ یا ۲ جلسه در هفته'
  const slotsSummary = ctx.selected_slots_summary_fa

  const unlockRequired = useMemo(() => {
    const flags = studentProfile?.extra_data?.lms?.access_flags || {}
    return flags.therapist_selection_unlocked === true
  }, [studentProfile])

  if (!active || !detail || detail.process_code !== 'start_therapy') {
    return null
  }

  const hint = resolveStartTherapyHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelState(currentState)) ?? ''
  const isComplete = currentState === 'therapy_active'
  const isBlocked = currentState === 'week9_blocked'
  const singleCourse = isSingleCourseAdmission(studentProfile, ctx)
  const isConditional = isConditionalTherapyAdmission(studentProfile, ctx)

  if (singleCourse) {
    return (
      <div
        className="card"
        data-testid="student-start-therapy-panel-single-course"
        style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
      >
        <div className="card-header">
          <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        </div>
        <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
          <p className="psf-hint psf-hint--warn">
            پذیرش شما به‌صورت تک‌درس است و برنامهٔ شروع درمان آموزشی برای این نوع پذیرش موضوعیت ندارد.
            این فرم را تکمیل نکنید؛ مسیر شما از پنل دروس و کلاس‌ها ادامه دارد.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div
      className="card"
      data-testid="student-start-therapy-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span className={`badge ${isComplete ? 'badge-success' : isBlocked ? 'badge-danger' : 'badge-info'}`} style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <FlowStepper currentState={currentState} />

        {unlockRequired && currentState === 'therapist_selection' && (
          <p className="psf-hint" style={{ background: '#f0fdf4', padding: '0.5rem 0.65rem', borderRadius: 6 }}>
            دسترسی انتخاب درمانگر پس از بررسی کمیته برای شما باز شده است.
          </p>
        )}

        {(isConditional) && !isComplete && (
          <p
            className="psf-hint psf-hint--warn"
            data-testid="start-therapy-conditional-banner"
            style={{ marginBottom: '0.75rem' }}
          >
            {CONDITIONAL_THERAPY_TERM2_NOTICE_FA}
          </p>
        )}

        {isBlocked && courseType === 'comprehensive' && (
          <p className="psf-hint psf-hint--warn">
            دسترسی کلاس‌های آنلاین و حضور/غیاب به‌دلیل عدم آغاز درمان تا هفتهٔ نهم مسدود شده است.
            با تکمیل انتخاب درمانگر و پرداخت جلسهٔ اول، محدودیت‌ها رفع می‌شود.
          </p>
        )}

        {isBlocked && courseType !== 'comprehensive' && (
          <p className="psf-hint psf-hint--warn">
            شما درمانگر فعالی ندارید و امکان ثبت‌نام شما برای ترم دوم ممکن نیست.
            با تکمیل انتخاب درمانگر و پرداخت جلسهٔ اول، محدودیت‌ها رفع می‌شود.
          </p>
        )}

        {!isComplete && hint && (
          <div
            data-testid="start-therapy-state-hint"
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

        {isComplete && (
          <p className="psf-hint" style={{ background: '#f0fdf4', padding: '0.5rem 0.65rem', borderRadius: 6 }}>
            درمان آموزشی فعال است. می‌توانید جلسات آتی را از بخش پرداخت جلسات پیگیری کنید.
          </p>
        )}

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
          <span className="badge badge-outline">محدودیت ساعات: {weeklyHint}</span>
          {ctx.therapist_id && <span className="badge badge-outline">درمانگر انتخاب‌شده</span>}
          {slotsSummary?.length > 0 && (
            <span className="badge badge-outline">{slotsSummary.join(' · ')}</span>
          )}
        </div>

        {currentState === 'payment_pending' && detail?.instance_id && (
          <SepPaymentPanel
            instanceId={detail.instance_id}
            studentId={studentProfile?.id || detail.student_id}
            onPaid={onPaymentDone}
          />
        )}
      </div>
    </div>
  )
}
