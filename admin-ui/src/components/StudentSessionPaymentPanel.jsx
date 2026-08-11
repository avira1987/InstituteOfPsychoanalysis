import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { therapyApi } from '../services/api'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import { labelState } from '../utils/processDisplay'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'

const PROC_CODE = 'session_payment'

const PAYMENT_STATUS_FA = {
  pending: 'در انتظار پرداخت',
  paid: 'پرداخت‌شده',
  waived: 'معاف',
}

function fmtMoney(n) {
  if (n == null || !Number.isFinite(Number(n))) return '—'
  return Math.round(Number(n)).toLocaleString('fa-IR')
}

function fmtDate(iso) {
  if (!iso) return '—'
  return formatShamsiTehran(iso)
}

function sessionReadyLabel(session) {
  if (!session) return '—'
  if (session.payment_status === 'pending') return 'قفل — نیاز به پرداخت'
  if (session.payment_status === 'paid' || session.payment_status === 'waived') {
    if (session.links_unlocked) return 'آماده برگزاری'
    return 'پرداخت‌شده — لینک در حال آماده‌سازی'
  }
  return PAYMENT_STATUS_FA[session.payment_status] || session.payment_status || '—'
}

/** هم‌تراز بک‌اند: بدهی = pending + (completed یا تاریخ قبل از امروز تهران) */
function tehranTodayYmd() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tehran',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

function sessionCountsAsDebt(session, todayYmd = tehranTodayYmd()) {
  if (!session || session.payment_status !== 'pending') return false
  if (!['scheduled', 'completed'].includes(session.status)) return false
  if (session.status === 'completed') return true
  const d = String(session.session_date || '').slice(0, 10)
  return Boolean(d && d < todayYmd)
}

function StatTile({ label, value, tone = '#14532d', bg = '#f0fdf4' }) {
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
    </div>
  )
}

/**
 * داشبورد مالی «پرداخت جلسات آتی درمان» — فرایند ۵ (session_payment).
 * جلسات بدهکار/بستانکار، تخمین مبلغ، و وضعیت جلسات پیش‌رو.
 */
export default function StudentSessionPaymentPanel({
  detail = null,
  stepFormValues = null,
  compact = false,
  active = true,
}) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const isProcessActive = detail?.process_code === 'session_payment'
    && !detail?.is_completed
    && !detail?.is_cancelled

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await therapyApi.mySessions()
      const list = Array.isArray(res.data) ? res.data : []
      setSessions(list)
    } catch (e) {
      setSessions([])
      setError(e.response?.data?.detail || 'بارگذاری جلسات درمان ممکن نشد.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (active) load()
  }, [active, load, detail?.instance_id, detail?.current_state])

  const stats = useMemo(() => {
    const scheduledOrDone = sessions.filter((s) => ['scheduled', 'completed'].includes(s.status))
    const todayYmd = tehranTodayYmd()
    const debt = scheduledOrDone.filter((s) => sessionCountsAsDebt(s, todayYmd)).length
    const prepaid = scheduledOrDone.filter((s) => s.payment_status === 'paid' || s.payment_status === 'waived').length
    const ctxDebt = ctx.debt_sessions_count != null ? Number(ctx.debt_sessions_count) : null
    const fee = Number(
      ctx.reference_therapy_session_fee_toman
      ?? ctx.default_therapy_session_fee_toman
      ?? 0,
    )
    const credit = ctx.session_credit_balance != null ? Number(ctx.session_credit_balance) : null
    return {
      debt: Number.isFinite(ctxDebt) ? ctxDebt : debt,
      prepaid,
      fee: Number.isFinite(fee) && fee > 0 ? fee : null,
      credit: credit != null && Number.isFinite(credit) ? credit : null,
    }
  }, [sessions, ctx.debt_sessions_count, ctx.reference_therapy_session_fee_toman, ctx.default_therapy_session_fee_toman, ctx.session_credit_balance])

  const upcoming = useMemo(() => {
    const now = Date.now()
    return sessions
      .filter((s) => s.status === 'scheduled')
      .sort((a, b) => {
        const ta = Date.parse(a.session_starts_at || a.session_date || '') || 0
        const tb = Date.parse(b.session_starts_at || b.session_date || '') || 0
        return ta - tb
      })
      .filter((s) => {
        const t = Date.parse(s.session_starts_at || s.session_date || '')
        return !Number.isFinite(t) || t >= now - 86400000
      })
      .slice(0, compact ? 3 : 8)
  }, [sessions, compact])

  const formValues = stepFormValues || {}
  const sessionsToPay = Math.max(1, Number(formValues.sessions_to_pay) || Number(ctx.sessions_to_pay) || 1)
  const debtSettlement = stats.debt > 0
    ? true
    : Boolean(formValues.debt_settlement_included ?? ctx.debt_settlement_included)
  const estimatedToman = useMemo(() => {
    if (!stats.fee) return null
    let total = sessionsToPay * stats.fee
    if (debtSettlement && stats.debt > 0) total += stats.debt * stats.fee
    return total
  }, [stats.fee, stats.debt, sessionsToPay, debtSettlement])

  const invoiceRial = ctx.payment_amount_rial != null
    ? Number(ctx.payment_amount_rial)
    : ctx.invoice_amount != null
      ? Math.round(Number(ctx.invoice_amount) * 10)
      : null

  const stateHint = isProcessActive && currentState
    ? (PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[currentState] || null)
    : null

  const statusShort = currentState
    ? (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelState(currentState))
    : null

  if (compact && !isProcessActive) {
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
            background: '#eff6ff',
            borderRight: '3px solid #2563eb',
            fontSize: '0.82rem',
          }}
        >
          <strong>مرحلهٔ فرایند:</strong>{' '}
          {statusShort || labelState(currentState)}
          {stateHint && (
            <div style={{ marginTop: '0.35rem' }}>
              <div style={{ fontWeight: 600, marginBottom: '0.15rem' }}>اقدام بعدی شما</div>
              <p style={{ margin: 0, color: '#334155' }}>{stateHint}</p>
            </div>
          )}
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
          label="جلسات بدون پرداخت"
          value={stats.debt.toLocaleString('fa-IR')}
          tone={stats.debt > 0 ? '#b45309' : '#14532d'}
          bg={stats.debt > 0 ? '#fffbeb' : '#f0fdf4'}
        />
        <StatTile
          label="جلسات پرداخت‌شده / معاف"
          value={stats.prepaid.toLocaleString('fa-IR')}
          tone="#1d4ed8"
          bg="#eff6ff"
        />
        {stats.credit != null && stats.credit > 0 && (
          <StatTile
            label="اعتبار باقی‌مانده (تومان)"
            value={fmtMoney(stats.credit)}
            tone="#0d9488"
            bg="#f0fdfa"
          />
        )}
        {stats.fee != null && (
          <StatTile
            label="تعرفه هر جلسه (تومان)"
            value={fmtMoney(stats.fee)}
            tone="#475569"
            bg="#f8fafc"
          />
        )}
      </div>

      {stats.debt > 0 && (
        <div
          data-testid="session-payment-debt-banner"
          role="status"
          style={{
            marginBottom: '0.75rem',
            padding: '0.75rem 0.9rem',
            borderRadius: '8px',
            background: '#fff7ed',
            borderRight: '4px solid #ea580c',
          }}
        >
          <strong style={{ color: '#9a3412' }}>بدهی جلسات درمان</strong>
          <p style={{ margin: '0.35rem 0 0', fontSize: '0.84rem', color: '#7c2d12', lineHeight: 1.7 }}>
            {ctx.debt_notice_fa
              || `شما ${stats.debt.toLocaleString('fa-IR')} جلسهٔ درمان بدون پرداخت دارید${
                stats.fee
                  ? ` (حدود ${fmtMoney(stats.debt * stats.fee)} تومان)`
                  : ''
              }. تسویهٔ این بدهی همراه با پیش‌پرداخت جلسات آتی الزامی است و به فاکتور اضافه می‌شود.`}
          </p>
        </div>
      )}

      {currentState === 'payment_selection' && estimatedToman != null && (
        <div
          data-testid="session-payment-estimate"
          style={{
            marginBottom: '0.75rem',
            padding: '0.65rem 0.85rem',
            borderRadius: '8px',
            background: '#fefce8',
            borderRight: '3px solid #ca8a04',
            color: '#713f12',
          }}
        >
          <strong style={{ color: '#854d0e' }}>تخمین مبلغ این پرداخت:</strong>{' '}
          {fmtMoney(estimatedToman)} تومان
          <span style={{ display: 'block', fontSize: '0.8rem', color: '#713f12', marginTop: '0.2rem' }}>
            {sessionsToPay.toLocaleString('fa-IR')} جلسه پیش‌پرداخت
            {debtSettlement && stats.debt > 0
              ? ` + تسویه ${stats.debt.toLocaleString('fa-IR')} جلسه بدهکار`
              : ''}
          </span>
        </div>
      )}

      {currentState === 'awaiting_payment' && invoiceRial != null && invoiceRial >= 1000 && (
        <div
          data-testid="session-payment-invoice"
          style={{
            marginBottom: '0.75rem',
            padding: '0.65rem 0.85rem',
            borderRadius: '8px',
            background: '#ecfdf5',
            borderRight: '3px solid #16a34a',
            color: '#14532d',
          }}
        >
          <strong style={{ color: '#166534' }}>مبلغ فاکتور:</strong>{' '}
          {Math.round(invoiceRial).toLocaleString('fa-IR')} ریال
          <span style={{ marginRight: '0.5rem', color: '#64748b' }}>
            ({fmtMoney(invoiceRial / 10)} تومان)
          </span>
        </div>
      )}

      {stats.debt > 0 && currentState === 'payment_selection' && !debtSettlement && (
        <p style={{ margin: '0 0 0.75rem', fontSize: '0.82rem', color: '#b45309' }}>
          سامانه در حال اعمال تسویهٔ بدهی است؛ اگر این پیام ماند، صفحه را تازه کنید.
        </p>
      )}

      {loading && sessions.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>در حال بارگذاری جلسات…</p>
      ) : error ? (
        <p style={{ color: 'var(--danger, #b91c1c)', margin: 0 }}>{error}</p>
      ) : upcoming.length > 0 ? (
        <div className="session-payment-upcoming" data-testid="session-payment-upcoming">
          <div style={{ fontWeight: 700, marginBottom: '0.4rem', fontSize: '0.84rem', color: '#0f172a' }}>
            جلسات پیشِ رو
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="table table-sm" style={{ width: '100%', fontSize: '0.8rem', color: '#1e293b' }}>
              <thead>
                <tr>
                  <th style={{ color: '#334155' }}>شماره</th>
                  <th style={{ color: '#334155' }}>تاریخ</th>
                  <th style={{ color: '#334155' }}>پرداخت</th>
                  <th style={{ color: '#334155' }}>وضعیت برگزاری</th>
                </tr>
              </thead>
              <tbody>
                {upcoming.map((s) => (
                  <tr key={s.id}>
                    <td style={{ color: '#1e293b' }}>{s.session_number != null ? s.session_number.toLocaleString('fa-IR') : '—'}</td>
                    <td style={{ color: '#1e293b' }}>{fmtDate(s.session_starts_at || s.session_date)}</td>
                    <td style={{ color: '#1e293b' }}>{PAYMENT_STATUS_FA[s.payment_status] || s.payment_status}</td>
                    <td style={{ color: '#1e293b' }}>{sessionReadyLabel(s)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
          جلسهٔ برنامه‌ریزی‌شده‌ای در تقویم درمان یافت نشد. پس از آغاز درمان، جلسات تا پایان ترم
          باید در سامانه ثبت شوند؛ صفحه را تازه کنید یا از «پرداخت جلسات» / پشتیبانی پیگیری کنید.
        </p>
      )}
    </>
  )

  if (compact) {
    return (
      <div
        className="student-session-payment-panel"
        data-testid="student-session-payment-panel"
        style={{
          marginTop: '0.75rem',
          padding: '0.85rem 1rem',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, #f0fdf4 0%, #f8fafc 100%)',
          borderRight: '4px solid #16a34a',
          fontSize: '0.86rem',
          lineHeight: 1.75,
          color: '#0f172a',
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: '0.5rem', color: '#14532d' }}>
          وضعیت مالی جلسات درمان
        </div>
        {body}
      </div>
    )
  }

  return (
    <div className="card student-session-payment-panel" data-testid="student-session-payment-panel">
      <div className="card-header" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 className="card-title" style={{ margin: 0 }}>مالی درمان آموزشی</h3>
        <button type="button" className="btn btn-outline btn-sm" onClick={load} disabled={loading}>
          {loading ? '…' : 'تازه‌سازی'}
        </button>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem', fontSize: '0.86rem', lineHeight: 1.75 }}>
        {body}
      </div>
    </div>
  )
}
