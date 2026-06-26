import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  BlockProgressBar,
  computeSlaRemaining,
  formatPaymentStatus,
  formatSupervisionSessionContext,
  HintBlock,
  ReadonlyRow,
  REMINDER_45_48_SMS_EXCERPT_FA,
  resolveBlockHours,
  resolveBlockNumber,
  SlaBanner,
  SUPERVISION_50H_STATES,
} from '../utils/supervision50hChainDisplay'

const FLOW_STEPS = [
  { code: 'session_scheduled', label: 'برنامه‌ریزی' },
  { code: 'supervisor_recording', label: 'ثبت سوپروایزر' },
  { code: 'evaluation_pending', label: 'ارزیابی ۵۰س' },
  { code: 'session_completed', label: 'پایان جلسه' },
]

const TERMINAL_STATES = new Set([
  'session_completed',
  'evaluation_completed',
  'evaluation_sla_breach',
  'recording_closed',
  'auto_absence_unpaid',
  'deputy_escalated',
  'absence_recorded',
])

function FlowStepper({ currentState }) {
  const idx = FLOW_STEPS.findIndex((s) => s.code === currentState)
  const onEvaluation = currentState === 'evaluation_pending' || currentState === 'evaluation_completed'
  const terminalIdx = TERMINAL_STATES.has(currentState)
    ? (onEvaluation ? 2 : FLOW_STEPS.length - 1)
    : idx

  if (idx < 0 && !TERMINAL_STATES.has(currentState)) return null

  return (
    <div
      data-testid="supervision-50h-stepper"
      style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.85rem', flexWrap: 'wrap' }}
    >
      {FLOW_STEPS.map((step, i) => {
        const done = i < terminalIdx
        const active = i === terminalIdx && (idx >= 0 || onEvaluation)
        return (
          <div
            key={step.code}
            style={{
              flex: '1 1 6rem',
              padding: '0.45rem 0.55rem',
              borderRadius: '8px',
              background: active ? '#0d9488' : done ? '#ccfbf1' : '#f1f5f9',
              color: active ? '#fff' : done ? '#115e59' : '#64748b',
              border: active ? '2px solid #0f766e' : '1px solid #e2e8f0',
              fontSize: '0.72rem',
              textAlign: 'center',
              fontWeight: active ? 700 : 500,
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

/**
 * داشبورد راهنمای «تکمیل ۵۰ ساعت سوپرویژن فردی» — فرایند ۲۰ (supervision_50h_completion).
 */
export default function Supervision50hCompletionPanel({
  detail = null,
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const siteManagerSla = useMemo(
    () => (currentState === 'site_manager_pending'
      ? computeSlaRemaining(ctx, 2, 'site_manager_pending_entered_at')
      : null),
    [currentState, ctx],
  )

  const evaluationSla = useMemo(
    () => (currentState === 'evaluation_pending'
      ? computeSlaRemaining(ctx, 3, 'evaluation_pending_entered_at')
      : null),
    [currentState, ctx],
  )

  const stateMeta = SUPERVISION_50H_STATES[currentState]
  const blockHours = resolveBlockHours(ctx)
  const blockNumber = resolveBlockNumber(ctx)
  const sessionLines = formatSupervisionSessionContext(ctx)
  const paymentStatus = formatPaymentStatus(ctx)
  const unpaid = ctx.supervision_session_paid === false || ctx.session_paid === false
  const blockFive = blockNumber === 5

  if (!active || !detail || detail.process_code !== 'supervision_50h_completion') {
    return null
  }

  return (
    <div className="card" data-testid="supervision-50h-panel" style={{ marginBottom: '1.25rem' }}>
      <div className="card-header">
        <h3 className="card-title">تکمیل ۵۰ ساعت سوپرویژن فردی (فرایند ۲۰)</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        <FlowStepper currentState={currentState} />

        {blockHours != null && (
          <BlockProgressBar hours={blockHours} max={50} blockNumber={blockNumber} />
        )}

        {sessionLines.length > 0 && (
          <div
            data-testid="supervision-50h-session-context"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#f8fafc',
              fontSize: '0.84rem',
              lineHeight: 1.7,
            }}
          >
            {sessionLines.map((line) => (
              <p key={line} style={{ margin: '0 0 0.25rem' }}>{line}</p>
            ))}
          </div>
        )}

        {stateMeta && (
          <HintBlock
            testId={`supervision-50h-hint-${currentState}`}
            title={stateMeta.title}
            color={stateMeta.color}
            bg={stateMeta.bg}
          >
            {stateMeta.hint}
          </HintBlock>
        )}

        {currentState === 'supervisor_recording' && (
          <HintBlock
            testId="supervision-50h-recording-actions-hint"
            title="راهنمای ثبت"
            color="#0d9488"
            bg="#f0fdfa"
          >
            <ul style={{ margin: 0, paddingInlineStart: '1.1rem' }}>
              <li>حاضر: +۱ ساعت به بلوک فعلی</li>
              <li>غایب: ارجاع به تعیین تکلیف هزینه (فرایند ۷)</li>
              {unpaid && (
                <li style={{ color: '#b45309' }}>
                  پرداخت نشده — فقط «غایب» قابل ثبت است؛ «حاضر» غیرفعال است.
                </li>
              )}
              {(blockHours === 48 || blockHours === 49) && !blockFive && (
                <li>SMS یادآوری ۴۵/۴۸: {REMINDER_45_48_SMS_EXCERPT_FA}</li>
              )}
            </ul>
          </HintBlock>
        )}

        {currentState === 'site_manager_pending' && (
          <SlaBanner
            slaInfo={siteManagerSla}
            title="مهلت پیگیری مسئول سایت (۲ روز)"
            fallbackText="پس از ۲ روز بدون پیگیری، پرونده به معاون مدیر آموزش اسکیت می‌شود."
          />
        )}

        {currentState === 'evaluation_pending' && (
          <SlaBanner
            slaInfo={evaluationSla}
            title="مهلت تکمیل فرم ارزیابی (۳ روز)"
            fallbackText="پس از ۳ روز بدون تکمیل فرم، گزارش تخلف به کمیته نظارت ارسال می‌شود."
          />
        )}

        {blockFive && blockHours != null && blockHours >= 45 && (
          <HintBlock
            testId="supervision-50h-block-five-note"
            title="دوره پنجم"
            color="#64748b"
            bg="#f1f5f9"
          >
            در دوره پنجم سوپرویژن، SMS یادآوری ساعات ۴۵ و ۴۸ ارسال نمی‌شود.
          </HintBlock>
        )}

        <ReadonlyRow label="وضعیت پرداخت جلسه" value={paymentStatus} />
        <ReadonlyRow
          label="وقفه سوپرویژن"
          value={ctx.student_on_supervision_leave === true ? 'بله — ثبت بسته' : ctx.student_on_supervision_leave === false ? 'خیر' : null}
        />
        <ReadonlyRow
          label="قفل پرداخت جلسه ۵۰"
          value={ctx.payment_unlocked_for_50th_session ? 'باز شده' : ctx.payment_unlocked_for_50th_session === false ? 'قفل' : null}
        />
        <ReadonlyRow
          label="شمارنده بلوک"
          value={ctx.block_counter_locked ? 'قفل (دوره تکمیل)' : null}
        />
      </div>
    </div>
  )
}
