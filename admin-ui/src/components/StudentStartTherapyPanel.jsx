import React, { useMemo } from 'react'
import SepPaymentPanel from './SepPaymentPanel'
import { labelState } from '../utils/processDisplay'

const PROCESS_TITLE_FA = 'آغاز درمان آموزشی'

const STATE_HINTS = {
  eligibility_check: 'در حال بررسی صلاحیت شما برای آغاز درمان آموزشی…',
  therapist_selection: 'از شیت وقت‌های آزاد، درمانگر و روز/ساعت جلسات هفتگی را انتخاب کنید؛ سپس فرم زیر را ثبت کنید.',
  therapist_confirmation: 'درمانگر انتخابی باید درخواست را در پنل خود بپذیرد. پس از تأیید، تاریخ شروع را ثبت می‌کنید.',
  schedule_first_session: 'تاریخ شروع اولین جلسه را ثبت کنید؛ سامانه قانون ۲۴ ساعت را اعمال می‌کند.',
  first_session_24h_check: 'در حال محاسبه تاریخ شروع…',
  payment_pending: 'هزینهٔ جلسهٔ اول را بپردازید تا درمان فعال شود و محدودیت‌های کلاس رفع گردد.',
  therapy_active: 'درمان آموزشی شما فعال است.',
  week9_blocked: 'مهلت هفتهٔ نهم گذشته است. برای رفع مسدودیت کلاس‌ها، همین فرایند را تکمیل کنید یا با پذیرش هماهنگ کنید.',
  already_completed: 'شما قبلاً این فرایند را انجام داده‌اید.',
  ineligible: 'در حال حاضر شرایط آغاز درمان آموزشی را ندارید.',
}

const STEPS = [
  { key: 'therapist_selection', label: 'انتخاب درمانگر' },
  { key: 'therapist_confirmation', label: 'تأیید درمانگر' },
  { key: 'schedule_first_session', label: 'تاریخ شروع' },
  { key: 'payment_pending', label: 'پرداخت' },
  { key: 'therapy_active', label: 'فعال' },
]

function stepIndex(state) {
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

  const hint = STATE_HINTS[currentState] || 'مراحل آغاز درمان آموزشی را در فرم زیر پیش ببرید.'
  const isComplete = currentState === 'therapy_active'
  const isBlocked = currentState === 'week9_blocked'

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

        {isBlocked && (
          <p className="psf-hint psf-hint--warn">
            دسترسی کلاس‌های آنلاین و حضور/غیاب به‌دلیل عدم آغاز درمان تا هفتهٔ نهم مسدود شده است.
            با تکمیل انتخاب درمانگر و پرداخت جلسهٔ اول، محدودیت‌ها رفع می‌شود.
          </p>
        )}

        {!isComplete && (
          <p className="psf-hint" style={{ marginTop: 0 }}>{hint}</p>
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
