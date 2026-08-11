import React, { useMemo } from 'react'
import SepPaymentPanel from './SepPaymentPanel'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import {
  CompTermStartFlowStepper,
  labelCompTermStartState,
  resolveCompTermContext,
  COMP_TERM_START_TERMINAL_STOP,
  COMP_TERM_START_STOP_MESSAGES,
  PAYMENT_METHOD_LABELS,
  fmtIsoDate,
} from '../utils/comprehensiveTermStartDisplay'

const PROCESS_TITLE_FA = 'آغاز ترم‌های دوره جامع (فرایند ۴۰)'
const PROC_CODE = 'comprehensive_term_start'

function resolveCompTermStartHint(state) {
  if (!state) return 'ثبت‌نام ترم جدید دوره جامع — مراحل را طبق راهنمای پنل پیش ببرید.'
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  return 'ثبت‌نام ترم جدید دوره جامع — مراحل را طبق راهنمای پنل پیش ببرید.'
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

function courseStatusLabel(course) {
  if (course.is_remedial || course.remedial) return 'جبرانی'
  return course.status_fa || course.status || 'ثابت'
}

/**
 * داشبورد راهنمای «آغاز ترم‌های دوره جامع» — فرایند ۴۰.
 * نمای دانشجو با مراحل، راهنمای وضعیت، و خلاصهٔ شهریه/پرداخت/اقساط.
 */
export default function StudentComprehensiveTermStartPanel({
  detail = null,
  studentProfile = null,
  studentId = null,
  stepFormValues = {},
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const termCtx = useMemo(
    () => resolveCompTermContext(ctx, stepFormValues),
    [ctx, stepFormValues],
  )

  if (!active || !detail || detail.process_code !== 'comprehensive_term_start') {
    return null
  }

  const resolvedStudentId = studentProfile?.id ?? studentId ?? null
  const isStop = COMP_TERM_START_TERMINAL_STOP.has(currentState)
  const isComplete = currentState === 'registration_complete'

  const hint = resolveCompTermStartHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelCompTermStartState(currentState)) ?? ''

  const termLabel = termCtx.termNumber
    ? `ترم ${Number(termCtx.termNumber).toLocaleString('fa-IR')}`
    : null

  const showTerm = !!termLabel && [
    'course_display', 'payment_choice', 'payment_processing', 'registration_complete',
  ].includes(currentState)

  const showTuition = ['course_display', 'payment_choice', 'payment_processing', 'registration_complete'].includes(currentState)
    && termCtx.tuitionToman

  const paymentLabel = termCtx.paymentMethod ? (PAYMENT_METHOD_LABELS[termCtx.paymentMethod] || termCtx.paymentMethod) : null
  const paymentValue = paymentLabel
    ? (termCtx.paymentMethod === 'installment' && termCtx.installmentCount
      ? `${paymentLabel} — ${Number(termCtx.installmentCount).toLocaleString('fa-IR')} قسط`
      : paymentLabel)
    : null
  const showPayment = !!paymentValue && [
    'payment_choice', 'payment_processing', 'registration_complete',
  ].includes(currentState)

  const showInstallmentInfo = currentState === 'registration_complete' && termCtx.paymentMethod === 'installment'
  const nextDue = showInstallmentInfo && termCtx.nextInstallmentDueAt ? fmtIsoDate(termCtx.nextInstallmentDueAt) : null
  const remaining = showInstallmentInfo && termCtx.pendingInstallmentsRemaining != null
    ? `${Number(termCtx.pendingInstallmentsRemaining).toLocaleString('fa-IR')} قسط`
    : null

  const showCourses = ['course_display', 'payment_choice'].includes(currentState) && termCtx.courses.length > 0
  const hasRemedial = termCtx.remedialCourses.length > 0

  const paymentAmountRial = ctx.payable_amount_rial != null
    ? Number(ctx.payable_amount_rial)
    : ctx.payment_amount_rial != null
      ? Number(ctx.payment_amount_rial)
      : Math.round(Number(ctx.invoice_amount || ctx.tuition_amount || 0) * 10)

  const paymentMethodChosen = Boolean(ctx.payment_method || termCtx.paymentMethod)
  const showSep = ['payment_processing', 'installment_overdue'].includes(currentState) && paymentMethodChosen

  return (
    <div className="card" data-testid="student-comprehensive-term-start-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isStop ? 'badge-danger' : isComplete ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelCompTermStartState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <CompTermStartFlowStepper currentState={currentState} compact={compact} />

        {isStop && (
          <div
            role="status"
            data-testid="comp-term-start-stop-message"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#991b1b',
            }}
          >
            {COMP_TERM_START_STOP_MESSAGES[currentState]}
          </div>
        )}

        {!isStop && hint && (
          <div
            data-testid="comp-term-start-state-hint"
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

        {(showTerm || showTuition || showPayment || nextDue || remaining) && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '0.65rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            {showTerm && (
              <InfoTile label="ترم ثبت‌نام" value={termLabel} tone="#16a34a" bg="#f0fdf4" />
            )}
            {showTuition && (
              <InfoTile label="شهریه ترم" value={termCtx.tuitionToman} tone="#b45309" bg="#fffbeb" />
            )}
            {showPayment && (
              <InfoTile label="روش پرداخت" value={paymentValue} tone="#7c3aed" bg="#f5f3ff" />
            )}
            {nextDue && (
              <InfoTile label="سررسید قسط بعدی" value={nextDue} tone="#2563eb" bg="#eff6ff" />
            )}
            {remaining && (
              <InfoTile label="اقساط باقی‌مانده" value={remaining} tone="#2563eb" bg="#eff6ff" />
            )}
          </div>
        )}

        {showCourses && (
          <div
            data-testid="comp-term-start-courses-table"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              overflowX: 'auto',
            }}
          >
            <div style={{ fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.45rem', color: '#334155' }}>
              {hasRemedial ? 'دروس ترم (الزامی + جبرانی)' : 'دروس ثابت ترم (الزامی)'}
            </div>
            <table className="table" style={{ fontSize: '0.82rem', marginBottom: 0 }}>
              <thead>
                <tr>
                  <th>نام درس</th>
                  <th>واحد</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {termCtx.courses.map((course, idx) => (
                  <tr key={course.code || course.name || idx}>
                    <td>{course.name_fa || course.name || course.label_fa || '—'}</td>
                    <td>{course.units ?? course.credit ?? '—'}</td>
                    <td>{courseStatusLabel(course)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {showSep && resolvedStudentId && (
          <div style={{ marginBottom: compact ? '0.65rem' : '0.85rem' }} data-testid="comp-term-start-sep-payment">
            {currentState === 'payment_processing' && !paymentMethodChosen && (
              <p style={{ margin: '0 0 0.5rem', fontSize: '0.86rem', color: '#1e3a8a', lineHeight: 1.7 }}>
                ابتدا روش پرداخت را در فرم بالا انتخاب و ثبت کنید؛ سپس درگاه پرداخت فعال می‌شود.
              </p>
            )}
            {ctx.payment_method === 'installment' && paymentAmountRial > 0 && (
              <p style={{ margin: '0 0 0.5rem', fontSize: '0.86rem', color: '#1e3a8a' }}>
                مبلغ قابل پرداخت الان (قسط {Number(ctx.current_installment_index || 1).toLocaleString('fa-IR')}):
                {' '}
                <strong>{Math.round(paymentAmountRial / 10).toLocaleString('fa-IR')} تومان</strong>
              </p>
            )}
            <SepPaymentPanel
              instanceId={detail.instance_id}
              studentId={resolvedStudentId}
              amountRial={paymentAmountRial > 0 ? paymentAmountRial : undefined}
              description="پرداخت شهریه ترم دوره جامع"
            />
          </div>
        )}

        {isComplete && (
          <div
            data-testid="comp-term-start-complete-block"
            style={{
              marginTop: '0.5rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
              ثبت‌نام شما در ترم جدید دوره جامع نهایی شد و لینک کلاس‌های آنلاین فعال است.
              {termCtx.paymentMethod === 'installment' ? ' اقساط بعدی را در سررسید پرداخت کنید.' : ''}
              {termCtx.registeredAt ? ` — ${fmtIsoDate(termCtx.registeredAt)}` : ''}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
