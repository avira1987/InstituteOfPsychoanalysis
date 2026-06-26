import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  ATTENDANCE_STATES,
  computeSlaRemaining,
  formatSessionContext,
  HintBlock,
  ReadonlyRow,
  SlaBanner,
} from '../utils/attendanceChainDisplay'

const FLOW_STEPS = [
  { code: 'session_scheduled', label: 'جلسه برنامه‌ریزی' },
  { code: 'therapist_recording', label: 'ثبت درمانگر' },
  { code: 'site_manager_pending', label: 'پیگیری سایت' },
  { code: 'session_completed', label: 'تکمیل/غیبت' },
]

function FlowStepper({ currentState }) {
  const idx = FLOW_STEPS.findIndex((s) => s.code === currentState)
  const terminalStates = [
    'session_completed',
    'excused_absence',
    'unexcused_absence',
    'quota_exceeded',
    'recording_closed',
    'auto_absence_unpaid',
    'deputy_escalated',
  ]
  const terminalIdx = terminalStates.includes(currentState) ? FLOW_STEPS.length : idx

  if (idx < 0 && !terminalStates.includes(currentState)) return null

  return (
    <div
      data-testid="attendance-tracking-stepper"
      style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.85rem', flexWrap: 'wrap' }}
    >
      {FLOW_STEPS.map((step, i) => {
        const done = i < terminalIdx
        const active = i === terminalIdx && idx >= 0
        return (
          <div
            key={step.code}
            style={{
              flex: '1 1 6rem',
              padding: '0.45rem 0.55rem',
              borderRadius: '8px',
              background: active ? '#2563eb' : done ? '#dbeafe' : '#f1f5f9',
              color: active ? '#fff' : done ? '#1e40af' : '#64748b',
              border: active ? '2px solid #1d4ed8' : '1px solid #e2e8f0',
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
 * داشبورد راهنمای «تکمیل ساعات درمان آموزشی» — فرایند ۶ (attendance_tracking).
 */
export default function AttendanceTrackingPanel({
  detail = null,
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const siteManagerSla = useMemo(
    () => (currentState === 'site_manager_pending' ? computeSlaRemaining(ctx, 2, 'site_manager_pending_entered_at') : null),
    [currentState, ctx],
  )

  const stateMeta = ATTENDANCE_STATES[currentState]

  if (!active || !detail || detail.process_code !== 'attendance_tracking') {
    return null
  }

  const sessionLines = formatSessionContext(ctx)

  return (
    <div className="card" data-testid="attendance-tracking-panel" style={{ marginBottom: '1.25rem' }}>
      <div className="card-header">
        <h3 className="card-title">تکمیل ساعات درمان آموزشی (فرایند ۶ — حضور و غیاب)</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        <FlowStepper currentState={currentState} />

        {sessionLines.length > 0 && (
          <div
            data-testid="attendance-tracking-session-context"
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
            testId={`attendance-tracking-hint-${currentState}`}
            title={stateMeta.title}
            color={stateMeta.color}
            bg={stateMeta.bg}
          >
            {stateMeta.hint}
          </HintBlock>
        )}

        {currentState === 'site_manager_pending' && (
          <SlaBanner
            slaInfo={siteManagerSla}
            title="مهلت پیگیری مسئول سایت (۲ روز)"
            fallbackText="پس از ۲ روز بدون پیگیری، پرونده به معاون مدیر آموزش اسکیت می‌شود."
          />
        )}

        {currentState === 'therapist_recording' && (
          <HintBlock
            testId="attendance-tracking-therapist-actions-hint"
            title="راهنمای ثبت"
            color="#f59e0b"
            bg="#fffbeb"
          >
            <ul style={{ margin: 0, paddingInlineStart: '1.1rem' }}>
              <li>حاضر: +۱ ساعت به فیلد مناسب (۱×/۲× هفتگی یا مجموع)</li>
              <li>غایب موجه: بدون افزایش ساعت</li>
              <li>غایب غیرموجه: تعیین تکلیف هزینه و احتمال ارجاع به فرایند ۷</li>
            </ul>
          </HintBlock>
        )}

        {(currentState === 'unexcused_absence' || currentState === 'quota_exceeded') && (
          <HintBlock
            testId="attendance-tracking-absence-outcome"
            title={currentState === 'quota_exceeded' ? 'سهمیه غیبت تمام شد' : 'غیبت غیرموجه ثبت شد'}
            color="#7c3aed"
            bg="#f5f3ff"
          >
            {currentState === 'quota_exceeded'
              ? 'سهمیه غیبت غیرموجه پر شده است. کمیته مطلع می‌شود و فرایند تعیین تکلیف هزینه اجرا می‌شود.'
              : 'غیبت غیرموجه ثبت شد. فرایند تعیین تکلیف هزینه جلسه (فرایند ۷) آغاز می‌شود.'}
          </HintBlock>
        )}

        <ReadonlyRow label="وضعیت پرداخت جلسه" value={ctx.session_paid === false ? 'پرداخت نشده' : ctx.session_paid === true ? 'پرداخت شده' : null} />
        <ReadonlyRow label="ساعات ۱× هفتگی" value={ctx.therapy_hours_1x_weekly != null ? String(ctx.therapy_hours_1x_weekly) : null} />
        <ReadonlyRow label="ساعات ۲× هفتگی" value={ctx.therapy_hours_2x_weekly != null ? String(ctx.therapy_hours_2x_weekly) : null} />
        <ReadonlyRow label="مجموع ساعات درمان" value={ctx.therapy_hours_total != null ? String(ctx.therapy_hours_total) : null} />
      </div>
    </div>
  )
}
