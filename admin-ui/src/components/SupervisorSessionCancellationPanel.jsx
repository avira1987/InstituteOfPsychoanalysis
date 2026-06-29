import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'

const PROCESS_TITLE_FA = 'کنسل جلسه سوپرویژن (فرایند ۲۶)'

const FLOW_STEPS = [
  { code: 'session_selection', label: 'انتخاب جلسه' },
  { code: 'makeup_choice', label: 'نوع کنسلی' },
  { code: 'makeup_proposed', label: 'پاسخ دانشجو' },
  { code: 'makeup_confirmed', label: 'جلسه جبرانی' },
  { code: 'makeup_session_completed', label: 'پایان' },
]

const TERMINAL_STATES = new Set([
  'cancelled_no_makeup',
  'makeup_session_completed',
  'student_declined_makeup',
])

const STATE_HINTS = {
  session_selection: {
    supervisor:
      'یکی از جلسات ۴ هفتهٔ آینده را در فرم انتخاب کنید؛ سپس فرم را ثبت و «ادامه و ثبت مرحله» را بزنید.',
    student: 'سوپروایزر در حال انتخاب جلسه برای لغو است.',
  },
  makeup_choice: {
    supervisor:
      'نوع کنسلی را مشخص کنید: جلسه جبرانی یا بدون جبرانی. در صورت جبرانی، تاریخ و ساعت را در فرم یا بخش تصمیم وارد کنید.',
    student: 'سوپروایزر در حال تعیین نوع کنسلی است.',
  },
  makeup_proposed: {
    supervisor: 'منتظر پاسخ دانشجو به پیشنهاد جلسه جبرانی هستید.',
    student:
      'تاریخ و ساعت پیشنهادی سوپروایزر را بررسی کنید؛ یکی از گزینه‌های فرم را انتخاب و ثبت کنید.',
  },
  supervisor_review_counter: {
    supervisor:
      'پیشنهاد جایگزین دانشجو را بخوانید؛ تاریخ و ساعت جدید را ثبت کنید و «ادامه و ثبت مرحله» را بزنید.',
    student: 'منتظر بررسی سوپروایزر برای زمان جایگزین هستید.',
  },
  payment_pending: {
    supervisor: 'دانشجو باید قبل از جلسه جبرانی پرداخت را انجام دهد.',
    student:
      'برای فعال شدن ثبت حضور، پرداخت جلسه جبرانی را از بخش سپ همین صفحه انجام دهید؛ سپس صفحه را تازه کنید.',
  },
  makeup_confirmed: {
    supervisor:
      'جلسه جبرانی ثبت شد. پس از برگزاری، دکمهٔ «جلسه برگزار شد» را بزنید تا ساعات ثبت شود.',
    student: 'جلسه جبرانی تأیید شد. لینک آنلاین در بخش جلسات آنلاین فعال می‌شود.',
  },
  cancelled_no_makeup: {
    supervisor: 'کنسلی بدون جبرانی ثبت شد. در صورت پرداخت قبلی، بستانکاری برای دانشجو اعمال می‌شود.',
    student: 'جلسه سوپرویژن بدون جلسه جبرانی لغو شد.',
  },
  student_declined_makeup: {
    supervisor: 'دانشجو جلسه جبرانی نخواست. در صورت پرداخت قبلی، بستانکاری اعمال می‌شود.',
    student: 'جلسه جبرانی لغو شد.',
  },
  makeup_session_completed: {
    supervisor: 'جلسه جبرانی برگزار شد و ساعات مطابق فرایند ۵۰ ساعته ثبت شد.',
    student: 'جلسه جبرانی سوپرویژن با موفقیت برگزار شد.',
  },
}

function FlowStepper({ currentState }) {
  const terminal = TERMINAL_STATES.has(currentState)
  const idx = FLOW_STEPS.findIndex((s) => s.code === currentState)
  const activeIdx = terminal
    ? (currentState === 'makeup_session_completed' ? FLOW_STEPS.length - 1 : 1)
    : idx

  if (idx < 0 && !terminal) return null

  return (
    <div
      data-testid="supervisor-cancel-flow-stepper"
      style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.85rem', flexWrap: 'wrap' }}
    >
      {FLOW_STEPS.map((step, i) => {
        const done = i < activeIdx
        const active = i === activeIdx && !terminal
        const terminalHere = terminal && i === activeIdx
        return (
          <div
            key={step.code}
            style={{
              flex: '1 1 5.5rem',
              padding: '0.45rem 0.55rem',
              borderRadius: '8px',
              background: terminalHere ? '#ccfbf1' : active ? '#0d9488' : done ? '#ccfbf1' : '#f1f5f9',
              color: terminalHere ? '#115e59' : active ? '#fff' : done ? '#115e59' : '#64748b',
              border: active ? '2px solid #0f766e' : '1px solid #e2e8f0',
              fontSize: '0.72rem',
              textAlign: 'center',
              fontWeight: active || terminalHere ? 700 : 500,
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

function StatTile({ label, value, sub, accent }) {
  return (
    <div
      style={{
        padding: '0.75rem 0.85rem',
        borderRadius: '10px',
        background: accent?.bg || '#f8fafc',
        borderRight: `4px solid ${accent?.color || '#94a3b8'}`,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{label}</div>
      <div style={{ fontSize: '1.1rem', fontWeight: 800, color: accent?.color || '#0f172a' }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: '0.76rem', color: '#78716c', marginTop: '0.2rem' }}>{sub}</div>
      )}
    </div>
  )
}

function formatPaidStatus(ctx) {
  const paid = ctx.supervision_session_paid ?? ctx.session_paid
  if (paid === true) return { text: 'پرداخت شده', color: '#166534', bg: '#f0fdf4' }
  if (paid === false) return { text: 'پرداخت نشده', color: '#991b1b', bg: '#fef2f2' }
  return { text: 'نامشخص', color: '#64748b', bg: '#f8fafc' }
}

/**
 * داشبورد «کنسل جلسه سوپرویژن توسط سوپروایزر» — فرایند ۲۶.
 * با `portalRole="student"` در پورتال دانشجو نیز استفاده می‌شود.
 */
export default function SupervisorSessionCancellationPanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
  portalRole = 'supervisor',
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const isSupervisor = portalRole === 'supervisor' || portalRole === 'admin'

  const sessions = Array.isArray(ctx.supervisor_sessions_next_4_weeks)
    ? ctx.supervisor_sessions_next_4_weeks
    : []

  const selectedId = stepFormValues?.selected_session || ctx.selected_session || null

  const selectedSession = useMemo(() => {
    if (!selectedId) return null
    const fromList = sessions.find((s) => String(s.value) === String(selectedId))
    if (fromList) return fromList
    if (ctx.selected_session_date) {
      return {
        session_date: ctx.selected_session_date,
        session_time: ctx.selected_session_time || '—',
        paid: ctx.supervision_session_paid ?? ctx.session_paid,
      }
    }
    return null
  }, [selectedId, sessions, ctx])

  const paidTone = formatPaidStatus(ctx)

  if (!active || !detail || detail.process_code !== 'supervisor_session_cancellation') {
    return null
  }

  const hint = STATE_HINTS[currentState]?.[isSupervisor ? 'supervisor' : 'student']
  const isTerminal = TERMINAL_STATES.has(currentState)

  const proposedDate = ctx.proposed_date || stepFormValues?.proposed_date
  const proposedTime = ctx.proposed_time || stepFormValues?.proposed_time

  return (
    <div className="card" data-testid="supervisor-session-cancellation-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        {!compact && <FlowStepper currentState={currentState} />}

        {!isTerminal && hint && (
          <div
            data-testid="supervisor-cancel-state-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: isSupervisor ? '#f0fdfa' : '#eff6ff',
              borderRight: `4px solid ${isSupervisor ? '#0d9488' : '#2563eb'}`,
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: isSupervisor ? '#134e4a' : '#1e3a8a',
            }}
          >
            {hint}
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.85rem',
          }}
        >
          <StatTile
            label="جلسات قابل انتخاب"
            value={sessions.length.toLocaleString('fa-IR')}
            sub="۴ هفتهٔ آینده — حداکثر ۱ جلسه"
            accent={{ color: '#0d9488', bg: '#f0fdfa' }}
          />
          {selectedSession && (
            <StatTile
              label="جلسه انتخاب‌شده"
              value={selectedSession.session_date || '—'}
              sub={`ساعت ${selectedSession.session_time || '—'}`}
              accent={{ color: '#7c3aed', bg: '#f5f3ff' }}
            />
          )}
          {(selectedSession || ctx.supervision_session_paid != null) && (
            <StatTile
              label="وضعیت پرداخت جلسه"
              value={paidTone.text}
              accent={{ color: paidTone.color, bg: paidTone.bg }}
            />
          )}
        </div>

        {selectedSession && currentState !== 'session_selection' && (
          <div
            data-testid="supervisor-cancel-selected-session-summary"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#f8fafc',
              borderRight: '4px solid #64748b',
              fontSize: '0.84rem',
              lineHeight: 1.7,
            }}
          >
            <strong>جلسهٔ لغو:</strong>
            {' '}
            مورخ
            {' '}
            {selectedSession.session_date}
            {' '}
            ساعت
            {' '}
            {selectedSession.session_time}
            {selectedSession.student_name && (
              <>
                {' '}
                —
                {' '}
                {selectedSession.student_name}
              </>
            )}
          </div>
        )}

        {(proposedDate || proposedTime) && ['makeup_proposed', 'payment_pending', 'makeup_confirmed'].includes(currentState) && (
          <div
            data-testid="supervisor-cancel-makeup-proposal"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#92400e',
            }}
          >
            <strong>زمان پیشنهادی جلسه جبرانی:</strong>
            {' '}
            {proposedDate || '—'}
            {' '}
            —
            {' '}
            ساعت
            {' '}
            {proposedTime || '—'}
          </div>
        )}

        {currentState === 'supervisor_review_counter' && (ctx.counter_proposal_text || '').trim() && (
          <div
            data-testid="supervisor-cancel-counter-proposal"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fff7ed',
              borderRight: '4px solid #ea580c',
              fontSize: '0.84rem',
              lineHeight: 1.7,
            }}
          >
            <strong>پیشنهاد دانشجو:</strong>
            <div style={{ marginTop: '0.35rem', whiteSpace: 'pre-wrap' }}>
              {ctx.counter_proposal_text.trim()}
            </div>
          </div>
        )}

        {currentState === 'makeup_choice' && isSupervisor && (
          <div
            style={{
              marginBottom: '0.65rem',
              fontSize: '0.82rem',
              color: '#64748b',
              lineHeight: 1.65,
            }}
          >
            <strong>مسیر بدون جبرانی:</strong>
            {' '}
            اطلاع‌رسانی به دانشجو؛ در صورت پرداخت، بستانکاری.
            <br />
            <strong>مسیر جبرانی:</strong>
            {' '}
            پیشنهاد تاریخ/ساعت و انتظار برای پاسخ دانشجو.
          </div>
        )}

        {isTerminal && hint && (
          <div
            data-testid="supervisor-cancel-terminal-note"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#14532d',
            }}
          >
            {hint}
          </div>
        )}

        {sessions.length === 0 && currentState === 'session_selection' && isSupervisor && (
          <p style={{ margin: 0, fontSize: '0.82rem', color: '#b45309', lineHeight: 1.6 }}>
            جلسهٔ سوپرویژن برنامه‌ریزی‌شده‌ای در ۴ هفتهٔ آینده نیست.
            ابتدا مطمئن شوید فرایند تکمیل ۵۰ ساعته برای دانشجو فعال است.
          </p>
        )}
      </div>
    </div>
  )
}
