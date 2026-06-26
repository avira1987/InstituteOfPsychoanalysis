import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

const BLOCK_SIZE = 50

const PROCESS_TITLE_FA =
  'آغاز سوپرویژن فردی دوم یا سوم یا چهارم یا پنجم (فرایند ۱۹)'

const PAYMENT_FLOW_STEPS = [
  { key: 'select', label: 'انتخاب سوپروایزر و زمان' },
  { key: 'pay_new', label: 'پرداخت جلسه اول بلوک بعد' },
  { key: 'pay_50th', label: 'پرداخت جلسه ۵۰ام (پس از باز شدن قفل)' },
  { key: 'done', label: 'تکمیل و اطلاع‌رسانی' },
]

const MANDATORY_LOCK_MSG =
  'دانشجوی گرامی، برای پرداخت جهت حضور در ۵۰مین جلسه سوپرویژن باید اول زمان و سوپرویژن بعدی خود را انتخاب کنید تا قادر به پرداخت برای حضور در ۵۰مین جلسه سوپرویژن باشید.'

const CHANGE_PATHS = [
  {
    key: 'supervisor_change',
    title: 'تغییر سوپروایزر',
    color: '#2563eb',
    bg: '#eff6ff',
    items: [
      'سوپروایزر فعلی به فهرست گذشته منتقل می‌شود (با ساعات گذرانده‌شده).',
      'سوپروایزر و زمان جدید جایگزین برنامه فعلی می‌شود.',
      'وقت آزاد سوپروایزر قبلی دوباره در شیت وقت‌ها قرار می‌گیرد.',
    ],
  },
  {
    key: 'restart',
    title: 'آغاز مجدد سوپرویژن',
    color: '#16a34a',
    bg: '#f0fdf4',
    items: [
      'برای شروع اولین بلوک یا از سرگیری پس از وقفه.',
      'روز، ساعت و نام سوپروایزر در پرونده ثبت می‌شود.',
      'لینک آنلاین و امکان حضور/غیاب فعال می‌شود.',
    ],
  },
  {
    key: 'schedule_change',
    title: 'تغییر ساعت (همان سوپروایزر)',
    color: '#d97706',
    bg: '#fffbeb',
    items: [
      'ساعات جدید جایگزین برنامه فعلی می‌شود.',
      'زمان‌های قبلی به شیت وقت‌های آزاد سوپروایزر برمی‌گردد.',
      'قانون ۲۴ ساعت برای تاریخ شروع اعمال می‌شود.',
    ],
  },
]

function fmtDate(iso) {
  if (!iso) return '—'
  return formatShamsiTehran(iso)
}

function StatTile({ label, value, sub, tone = '#7c3aed', bg = '#f5f3ff' }) {
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
      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: tone }}>{value}</div>
      {sub && <div style={{ fontSize: '0.76rem', color: '#78716c', marginTop: '0.2rem' }}>{sub}</div>}
    </div>
  )
}

function blockOrdinalFa(n) {
  if (n == null || !Number.isFinite(n)) return null
  const map = { 2: 'دوم', 3: 'سوم', 4: 'چهارم', 5: 'پنجم' }
  return map[n] || n.toLocaleString('fa-IR')
}

function PaymentFlowStepper({ currentState, paymentUnlocked }) {
  const activeIdx = (() => {
    if (currentState === 'both_paid_completed') return 3
    if (currentState === 'new_block_first_paid') return 2
    if (currentState === 'slot_selected') return 1
    if (currentState === 'supervisor_slots_displayed') return 0
    if (paymentUnlocked) return 2
    return 0
  })()

  return (
    <div
      data-testid="supervision-block-payment-flow"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: '0.45rem',
        marginBottom: '0.85rem',
      }}
    >
      {PAYMENT_FLOW_STEPS.map((step, i) => {
        const done = i < activeIdx
        const current = i === activeIdx
        const tone = done ? '#16a34a' : current ? '#7c3aed' : '#94a3b8'
        const bg = done ? '#f0fdf4' : current ? '#f5f3ff' : '#f8fafc'
        return (
          <div
            key={step.key}
            style={{
              padding: '0.55rem 0.65rem',
              borderRadius: '8px',
              background: bg,
              borderRight: `3px solid ${tone}`,
              fontSize: '0.76rem',
              lineHeight: 1.55,
              color: done ? '#14532d' : current ? '#5b21b6' : '#64748b',
            }}
          >
            <div style={{ fontWeight: 800, marginBottom: '0.15rem' }}>
              {i + 1}
              .
              {' '}
              {step.label}
            </div>
            {current && <div style={{ fontSize: '0.72rem' }}>← مرحلهٔ فعلی</div>}
          </div>
        )
      })}
    </div>
  )
}

function PathCard({ path, active }) {
  const isActive = active === path.key
  return (
    <div
      data-testid={`supervision-block-path-${path.key}`}
      style={{
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: isActive ? path.bg : '#f8fafc',
        borderRight: `4px solid ${path.color}`,
        fontSize: '0.84rem',
        lineHeight: 1.7,
        opacity: active && !isActive ? 0.55 : 1,
      }}
    >
      <strong style={{ display: 'block', marginBottom: '0.35rem', color: path.color }}>
        {path.title}
        {isActive && (
          <span style={{ marginInlineStart: '0.4rem', fontSize: '0.75rem' }}>← مسیر انتخابی</span>
        )}
      </strong>
      <ul style={{ margin: 0, paddingInlineStart: '1.1rem' }}>
        {path.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

function normalizeHistory(rawBlocks, ctx) {
  const fromCtx = ctx.supervision_history ?? ctx.supervision_blocks ?? ctx.past_supervision_blocks
  const source = Array.isArray(fromCtx) && fromCtx.length ? fromCtx : rawBlocks
  if (!Array.isArray(source)) return []
  return source.map((b, i) => {
    if (!b || typeof b !== 'object') {
      return { key: String(i), block: i + 1, supervisor: String(b), hours: null, status: null }
    }
    return {
      key: b.id || String(i),
      block: b.block_number ?? b.block_index ?? i + 1,
      supervisor: b.supervisor_name_fa ?? b.supervisor_name ?? b.supervisor_id ?? '—',
      hours: b.hours ?? b.completed_hours ?? b.attendance_hours ?? null,
      status: b.status ?? null,
    }
  })
}

function normalizeSlots(raw) {
  if (!raw) return []
  if (Array.isArray(raw)) return raw
  if (typeof raw === 'object') {
    return Object.entries(raw).flatMap(([supervisor, slots]) => {
      const list = Array.isArray(slots) ? slots : [slots]
      return list.map((s) => ({
        supervisor,
        ...(typeof s === 'object' ? s : { slot: s }),
      }))
    })
  }
  return []
}

/**
 * داشبورد «آغاز سوپرویژن فردی دوم…» — فرایند ۱۹ (supervision_block_transition).
 * راهنمای بصری؛ ورود داده از ProcessStepForms انجام می‌شود.
 */
export default function StudentSupervisionBlockTransitionPanel({
  detail = null,
  stepFormValues = {},
  extraData = null,
  compact = false,
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const isProcessActive = detail?.process_code === 'supervision_block_transition'
    && !detail?.is_completed
    && !detail?.is_cancelled

  const attendance = ctx.current_supervision_block_attendance != null
    ? Number(ctx.current_supervision_block_attendance)
    : null
  const at50th = attendance != null && attendance >= BLOCK_SIZE
  const sessionsTo50 = attendance != null ? Math.max(0, BLOCK_SIZE - attendance) : null

  const changeType = stepFormValues?.change_type ?? ctx.change_type ?? null

  const historyRows = useMemo(
    () => normalizeHistory(extraData?.lms?.supervision_blocks, ctx),
    [extraData?.lms?.supervision_blocks, ctx],
  )

  const nextBlockNumber = useMemo(() => {
    const fromCtx = ctx.next_supervision_block_number ?? ctx.target_supervision_block_number
    if (fromCtx != null && Number.isFinite(Number(fromCtx))) return Number(fromCtx)
    const completed = historyRows.filter((r) => r.status === 'completed' || r.status === 'done').length
    if (completed > 0) return completed + 1
    if (historyRows.length > 0) return historyRows.length + 1
    return 2
  }, [ctx.next_supervision_block_number, ctx.target_supervision_block_number, historyRows])

  const slots = useMemo(
    () => normalizeSlots(
      ctx.available_supervisor_slots
      ?? ctx.supervisor_slots
      ?? ctx.displayed_supervisor_slots,
    ),
    [ctx.available_supervisor_slots, ctx.supervisor_slots, ctx.displayed_supervisor_slots],
  )

  const selectedSupervisor = stepFormValues?.new_supervisor_id
    ?? stepFormValues?.supervisor_id
    ?? ctx.new_supervisor_id
    ?? ctx.supervisor_id
    ?? ctx.selected_supervisor_id
  const selectedDay = stepFormValues?.supervision_day ?? stepFormValues?.selected_day ?? ctx.supervision_day ?? ctx.selected_day
  const selectedTime = stepFormValues?.supervision_time ?? stepFormValues?.selected_time ?? ctx.supervision_time ?? ctx.selected_time
  const startDate = ctx.calculated_start_date ?? ctx.start_date ?? ctx.supervision_start_date
  const paymentUnlocked = Boolean(ctx.payment_unlocked_for_50th_session)
  const mandatoryMsg = ctx.mandatory_message_fa || MANDATORY_LOCK_MSG

  const stateHint = isProcessActive && currentState
    ? ({
      payment_intent_50th: at50th
        ? 'به جلسه ۵۰ رسیده‌اید. «ادامه و ثبت مرحله» را بزنید تا سوابق و وقت‌های آزاد نمایش داده شود.'
        : 'اگر هنوز به جلسه ۵۰ نرسیده‌اید، پس از «ادامه» به پرداخت عادی سوپرویژن هدایت می‌شوید؛ در غیر این صورت مسیر انتقال بلوک باز می‌شود.',
      not_at_50th: 'هنوز به جلسه ۵۰ نرسیده‌اید — از فرایند پرداخت جلسات یا تکمیل بلوک ۵۰ ساعته ادامه دهید.',
      supervisor_slots_displayed: 'سوابق و شیت وقت‌های آزاد را در باکس‌های زیر ببینید؛ سپس در فرم، سوپروایزر و یک زمان (حداکثر ۱ جلسه در هفته) را انتخاب کنید.',
      slot_selected: 'تاریخ شروع با قانون ۲۴ ساعت محاسبه شده است. ابتدا هزینهٔ جلسه اول دوره جدید را بپردازید.',
      new_block_first_paid: 'پرداخت جلسه اول دوره جدید انجام شد — اکنون می‌توانید جلسه ۵۰ام دوره فعلی را پرداخت کنید.',
      both_paid_completed: 'هر دو پرداخت انجام شد. جزئیات جلسه جدید از طریق پیامک به شما و سوپروایزر ارسال می‌شود.',
    }[currentState] || null)
    : null

  if (!active || !detail || detail.process_code !== 'supervision_block_transition') {
    return null
  }

  const body = (
    <>
      {isProcessActive && currentState && (
        <div
          style={{
            marginBottom: '0.75rem',
            padding: '0.5rem 0.75rem',
            borderRadius: '8px',
            background: '#f5f3ff',
            borderRight: '3px solid #7c3aed',
            fontSize: '0.82rem',
          }}
        >
          <strong>مرحلهٔ فرایند:</strong>{' '}
          {labelState(currentState)}
          {stateHint && <p style={{ margin: '0.35rem 0 0', color: '#334155' }}>{stateHint}</p>}
        </div>
      )}

      {!compact && isProcessActive && (
        <PaymentFlowStepper currentState={currentState} paymentUnlocked={paymentUnlocked} />
      )}

      {nextBlockNumber >= 2 && nextBlockNumber <= 5 && (
        <div
          data-testid="supervision-block-target"
          style={{
            marginBottom: '0.85rem',
            padding: '0.65rem 0.85rem',
            borderRadius: '8px',
            background: '#faf5ff',
            borderRight: '3px solid #9333ea',
            fontSize: '0.84rem',
            color: '#581c87',
          }}
        >
          <strong>بلوک هدف:</strong>
          {' '}
          سوپرویژن فردی
          {' '}
          {blockOrdinalFa(nextBlockNumber)}
        </div>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: compact ? 'repeat(2, minmax(0, 1fr))' : 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: '0.65rem',
          marginBottom: '0.85rem',
        }}
      >
        <StatTile
          label="حضور در بلوک فعلی"
          value={attendance != null ? attendance.toLocaleString('fa-IR') : '—'}
          sub={attendance != null ? `از ${BLOCK_SIZE.toLocaleString('fa-IR')} جلسه` : 'پس از ثبت حضور پر می‌شود'}
          tone={at50th ? '#16a34a' : '#7c3aed'}
          bg={at50th ? '#f0fdf4' : '#f5f3ff'}
        />
        <StatTile
          label="تا جلسه ۵۰"
          value={sessionsTo50 != null ? sessionsTo50.toLocaleString('fa-IR') : '—'}
          sub={at50th ? 'آماده انتقال بلوک' : 'جلسه مانده'}
          tone={at50th ? '#16a34a' : '#b45309'}
          bg={at50th ? '#ecfdf5' : '#fffbeb'}
        />
        {(currentState === 'new_block_first_paid' || currentState === 'both_paid_completed' || paymentUnlocked) && (
          <StatTile
            label="قفل پرداخت جلسه ۵۰"
            value={paymentUnlocked || currentState === 'new_block_first_paid' || currentState === 'both_paid_completed' ? 'باز' : 'قفل'}
            sub="پس از پرداخت جلسه اول بلوک بعد"
            tone={paymentUnlocked ? '#16a34a' : '#dc2626'}
            bg={paymentUnlocked ? '#f0fdf4' : '#fef2f2'}
          />
        )}
      </div>

      {(currentState === 'payment_intent_50th' || changeType) && !compact && (
        <div style={{ display: 'grid', gap: '0.65rem', marginBottom: '0.85rem' }}>
          <div style={{ fontWeight: 700, fontSize: '0.84rem', color: '#475569' }}>
            انواع تغییر (راهنما)
          </div>
          {CHANGE_PATHS.map((p) => (
            <PathCard key={p.key} path={p} active={changeType} />
          ))}
        </div>
      )}

      {(currentState === 'supervisor_slots_displayed'
        || currentState === 'slot_selected'
        || at50th) && (
        <div
          data-testid="supervision-block-mandatory-msg"
          role="alert"
          style={{
            marginBottom: '0.85rem',
            padding: '0.75rem 1rem',
            borderRadius: '10px',
            background: '#fff7ed',
            borderRight: '4px solid #ea580c',
            fontSize: '0.86rem',
            lineHeight: 1.75,
            color: '#9a3412',
          }}
        >
          <strong style={{ display: 'block', marginBottom: '0.35rem' }}>الزام انتقال بلوک</strong>
          {mandatoryMsg}
        </div>
      )}

      {historyRows.length > 0 && (
        <div style={{ marginBottom: '0.85rem' }} data-testid="supervision-block-history">
          <div style={{ fontWeight: 700, marginBottom: '0.4rem', fontSize: '0.84rem' }}>
            سوابق بلوک‌های ۵۰ ساعته
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="table table-sm" style={{ width: '100%', fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  <th>بلوک</th>
                  <th>سوپروایزر</th>
                  <th>ساعت</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {historyRows.map((row) => (
                  <tr key={row.key}>
                    <td>{row.block != null ? row.block.toLocaleString('fa-IR') : '—'}</td>
                    <td>{row.supervisor || '—'}</td>
                    <td>
                      {row.hours != null && Number.isFinite(Number(row.hours))
                        ? Number(row.hours).toLocaleString('fa-IR')
                        : '—'}
                    </td>
                    <td>{row.status || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {slots.length > 0 && (currentState === 'supervisor_slots_displayed' || currentState === 'slot_selected') && (
        <div style={{ marginBottom: '0.85rem' }} data-testid="supervision-block-slots">
          <div style={{ fontWeight: 700, marginBottom: '0.4rem', fontSize: '0.84rem' }}>
            وقت‌های آزاد سوپروایزرها
            <span style={{ fontWeight: 400, color: '#64748b', marginInlineStart: '0.35rem' }}>
              (حداکثر ۱ جلسه در هفته)
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="table table-sm" style={{ width: '100%', fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  <th>سوپروایزر</th>
                  <th>روز</th>
                  <th>ساعت</th>
                </tr>
              </thead>
              <tbody>
                {slots.slice(0, compact ? 4 : 12).map((s, i) => (
                  <tr key={s.id || i}>
                    <td>{s.supervisor_name_fa ?? s.supervisor_name ?? s.supervisor ?? '—'}</td>
                    <td>{s.day_fa ?? s.day ?? s.weekday ?? '—'}</td>
                    <td dir="ltr">{s.time ?? s.slot ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(selectedSupervisor || selectedDay || selectedTime) && (
        <div
          data-testid="supervision-block-selection-preview"
          style={{
            marginBottom: '0.85rem',
            padding: '0.85rem 1rem',
            borderRadius: '10px',
            background: '#eff6ff',
            borderRight: '4px solid #2563eb',
            fontSize: '0.86rem',
            lineHeight: 1.75,
            color: '#1e3a8a',
          }}
        >
          <strong style={{ display: 'block', marginBottom: '0.35rem' }}>انتخاب شما</strong>
          {selectedSupervisor && <div>سوپروایزر: {String(selectedSupervisor)}</div>}
          {selectedDay && <div>روز: {String(selectedDay)}</div>}
          {selectedTime && <div>ساعت: {String(selectedTime)}</div>}
        </div>
      )}

      {startDate && (
        <div
          data-testid="supervision-block-start-date"
          style={{
            marginBottom: '0.85rem',
            padding: '0.75rem 1rem',
            borderRadius: '10px',
            background: '#f0fdf4',
            borderRight: '4px solid #16a34a',
            fontSize: '0.86rem',
            lineHeight: 1.75,
            color: '#14532d',
          }}
        >
          <strong>تاریخ آغاز (قانون ۲۴ ساعت):</strong>{' '}
          {fmtDate(startDate)}
          <p style={{ margin: '0.35rem 0 0', fontSize: '0.8rem', color: '#166534' }}>
            اگر فاصله تا اولین جلسه کمتر از ۲۴ ساعت باشد، شروع به هفته بعد موکول می‌شود.
          </p>
        </div>
      )}

      {currentState === 'new_block_first_paid' && (
        <div
          data-testid="supervision-block-pay-50th-hint"
          style={{
            marginBottom: '0.85rem',
            padding: '0.75rem 1rem',
            borderRadius: '10px',
            background: '#ecfdf5',
            borderRight: '4px solid #059669',
            fontSize: '0.86rem',
            lineHeight: 1.75,
            color: '#065f46',
          }}
        >
          قفل پرداخت جلسه ۵۰ام باز شد. از بخش پرداخت همین صفحه برای جلسه پنجاهم دوره فعلی استفاده کنید.
        </div>
      )}

      {currentState === 'both_paid_completed' && (
        <div
          data-testid="supervision-block-completed"
          style={{
            marginBottom: '0.85rem',
            padding: '0.75rem 1rem',
            borderRadius: '10px',
            background: '#f0fdf4',
            borderRight: '4px solid #16a34a',
            fontSize: '0.86rem',
            lineHeight: 1.75,
            color: '#14532d',
          }}
        >
          انتقال بلوک و هر دو پرداخت با موفقیت انجام شد.
          {(ctx.new_supervisor_name || selectedSupervisor) && (
            <>
              {' '}
              سوپروایزر جدید:
              {' '}
              {ctx.new_supervisor_name || selectedSupervisor}
            </>
          )}
          {startDate && (
            <>
              {' '}
              — آغاز:
              {' '}
              {fmtDate(startDate)}
            </>
          )}
        </div>
      )}

      {!compact && (
        <div
          style={{
            padding: '0.65rem 0.85rem',
            borderRadius: '8px',
            background: '#f8fafc',
            borderRight: '3px solid #94a3b8',
            fontSize: '0.8rem',
            lineHeight: 1.7,
            color: '#475569',
          }}
        >
          <strong>قوانین:</strong>
          {' '}
          حداکثر ۱ جلسه سوپرویژن در هفته؛ انتخاب سوپروایزر متناسب با شماره بلوک (هیئت علمی ۱–۵ برای بلوک اول و دوم، ۶+ برای بلوک سوم به بعد).
        </div>
      )}
    </>
  )

  if (compact) {
    return (
      <div
        className="student-supervision-block-panel"
        data-testid="student-supervision-block-panel"
        style={{
          marginTop: '0.75rem',
          padding: '0.85rem 1rem',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, #f5f3ff 0%, #f8fafc 100%)',
          borderRight: '4px solid #7c3aed',
          fontSize: '0.86rem',
          lineHeight: 1.75,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: '0.5rem', color: '#5b21b6' }}>
          {PROCESS_TITLE_FA}
        </div>
        {body}
      </div>
    )
  }

  return (
    <div className="card student-supervision-block-panel" data-testid="student-supervision-block-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>
      <div style={{ padding: '0 1rem 1rem', fontSize: '0.86rem', lineHeight: 1.75 }}>
        {body}
      </div>
    </div>
  )
}
