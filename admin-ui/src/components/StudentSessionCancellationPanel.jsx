import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'

function normalizeSelectedSessions(raw) {
  if (Array.isArray(raw)) {
    return raw.filter((x) => x != null && String(x).trim() !== '').map(String)
  }
  if (raw == null || raw === '') return []
  if (typeof raw === 'string') {
    const s = raw.trim()
    if (s.startsWith('[')) {
      try {
        const p = JSON.parse(s)
        return Array.isArray(p) ? p.map(String) : []
      } catch {
        return []
      }
    }
    return s.split(/[,،\s]+/).filter(Boolean).map(String)
  }
  return [String(raw)]
}

function percentTone(pct) {
  if (pct == null || Number.isNaN(pct)) return { color: '#64748b', bg: '#f8fafc', label: '—' }
  if (pct > 12) return { color: '#991b1b', bg: '#fef2f2', label: 'تخلف (>۱۲٪)' }
  if (pct >= 10) return { color: '#92400e', bg: '#fffbeb', label: 'هشدار (۱۰–۱۲٪)' }
  return { color: '#166534', bg: '#f0fdf4', label: 'مجاز (<۱۰٪)' }
}

function StatTile({ label, value, sub, accent }) {
  return (
    <div
      style={{
        padding: '0.85rem',
        borderRadius: '10px',
        background: accent?.bg || '#f8fafc',
        borderRight: `4px solid ${accent?.color || '#94a3b8'}`,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{label}</div>
      <div style={{ fontSize: '1.2rem', fontWeight: 800, color: accent?.color || '#0f172a' }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: '0.78rem', color: '#78716c', marginTop: '0.25rem' }}>{sub}</div>
      )}
    </div>
  )
}

/**
 * داشبورد «کنسل جلسات درمان آموزشی» — فرایند ۱۷ (student_session_cancellation).
 */
export default function StudentSessionCancellationPanel({
  detail = null,
  stepFormValues = {},
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const selectedIds = useMemo(() => {
    const fromForm = normalizeSelectedSessions(stepFormValues?.selected_sessions)
    if (fromForm.length) return fromForm
    return normalizeSelectedSessions(ctx.selected_sessions)
  }, [stepFormValues, ctx.selected_sessions])

  const percentNow = ctx.cancellation_percent_now != null ? Number(ctx.cancellation_percent_now) : null
  const percentAfter = ctx.cancellation_percent_after != null
    ? Number(ctx.cancellation_percent_after)
    : null
  const completed = ctx.completed_sessions != null ? Number(ctx.completed_sessions) : null
  const cancelled = ctx.cancelled_sessions != null ? Number(ctx.cancelled_sessions) : null
  const upcoming = Array.isArray(ctx.upcoming_cancellation_sessions)
    ? ctx.upcoming_cancellation_sessions
    : []
  const wouldExceed = Boolean(ctx.would_exceed_consecutive_weeks)
  const tone = percentTone(percentAfter ?? percentNow)

  const isTerminal = [
    'cancellation_applied',
    'warning_and_applied',
    'violation_and_applied',
    'consecutive_blocked',
  ].includes(currentState)

  if (!active || !detail || detail.process_code !== 'student_session_cancellation') {
    return null
  }

  return (
    <div className="card" data-testid="student-session-cancellation-panel">
      <div className="card-header">
        <h3 className="card-title">کنسل جلسات درمان آموزشی (فرایند ۱۷)</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        {currentState === 'calendar_displayed' && (
          <div
            data-testid="session-cancellation-init-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#eff6ff',
              borderRight: '4px solid #2563eb',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#1e3a8a',
            }}
          >
            تقویم فقط ۳ هفتهٔ آینده را نشان می‌دهد. جلسات را تیک بزنید، فرم را ثبت کنید،
            سپس «ادامه و ثبت مرحله» را بزنید. برای وقفهٔ بیش از ۳ هفته متوالی از
            {' '}
            <strong>وقفه در درمان آموزشی</strong>
            {' '}
            استفاده کنید.
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.85rem',
          }}
        >
          {completed != null && cancelled != null && (
            <StatTile
              label="سوابق جلسات"
              value={`${cancelled.toLocaleString('fa-IR')} کنسل / ${completed.toLocaleString('fa-IR')} برگزار`}
              sub="از ابتدای درمان"
              accent={{ color: '#475569', bg: '#f8fafc' }}
            />
          )}
          {percentNow != null && (
            <StatTile
              label="درصد کنسلی فعلی"
              value={`${percentNow.toLocaleString('fa-IR')}٪`}
              accent={percentTone(percentNow)}
            />
          )}
          {(currentState === 'sessions_selected' || selectedIds.length > 0) && percentAfter != null && (
            <StatTile
              label="درصد پس از این کنسلی"
              value={`${percentAfter.toLocaleString('fa-IR')}٪`}
              sub={tone.label}
              accent={tone}
            />
          )}
          <StatTile
            label="جلسات قابل انتخاب"
            value={upcoming.length.toLocaleString('fa-IR')}
            sub="۳ هفتهٔ آینده"
            accent={{ color: '#ea580c', bg: '#fff7ed' }}
          />
        </div>

        {selectedIds.length > 0 && !isTerminal && (
          <div
            data-testid="session-cancellation-selection-summary"
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
            <strong>{selectedIds.length.toLocaleString('fa-IR')}</strong>
            {' '}
            جلسه برای کنسل انتخاب شده است.
          </div>
        )}

        {wouldExceed && !isTerminal && (
          <div
            role="alert"
            data-testid="session-cancellation-consecutive-block"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#991b1b',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>محدودیت ۳ هفته متوالی</strong>
            {(ctx.consecutive_block_message_fa || '').trim() || (
              <>
                کنسل بیش از ۳ هفته متوالی از این مسیر مجاز نیست.
                برای وقفهٔ طولانی‌تر فرایند «وقفه در درمان آموزشی» را اجرا کنید.
              </>
            )}
          </div>
        )}

        {currentState === 'sessions_selected' && percentAfter != null && percentAfter >= 10 && percentAfter <= 12 && (
          <div
            role="status"
            data-testid="session-cancellation-warning-10-12"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#92400e',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>هشدار پیشگیری از تخلف</strong>
            با این کنسلی، مجموع کنسلی‌های شما به بازهٔ ۱۰ تا ۱۲ درصد می‌رسد و گزارش
            «هشدار پیشگیری از تخلف» برای کمیته ارسال می‌شود.
          </div>
        )}

        {((currentState === 'sessions_selected' && percentAfter != null && percentAfter > 12)
          || ctx.requires_violation_ack) && (
          <div
            role="alert"
            data-testid="session-cancellation-violation-popup"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#7f1d1d',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>هشدار تخلف آموزشی</strong>
            {(ctx.violation_warning_message_fa || '').trim() || (
              <>
                با ثبت این جلسات، کنسلی‌های شما از ۱۲٪ فراتر می‌رود و تخلف آموزشی
                به کمیته نظارت گزارش می‌شود. چک‌باکس تأیید را در فرم زیر بزنید.
              </>
            )}
          </div>
        )}

        {currentState === 'consecutive_blocked' && (
          <div
            data-testid="session-cancellation-blocked-done"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#991b1b',
            }}
          >
            فرایند به‌دلیل نقض قانون ۳ هفته متوالی متوقف شد. برای وقفهٔ طولانی‌تر
            از فرایند «وقفه در درمان آموزشی» (فرایند ۱۶) استفاده کنید.
          </div>
        )}

        {currentState === 'cancellation_applied' && (
          <div
            data-testid="session-cancellation-applied"
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
            کنسلی ثبت شد. برای هر جلسه، فرایند تعیین تکلیف مالی به‌صورت خودکار اجرا می‌شود.
          </div>
        )}

        {currentState === 'warning_and_applied' && (
          <div
            data-testid="session-cancellation-warning-applied"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#92400e',
            }}
          >
            کنسلی ثبت شد. گزارش «هشدار پیشگیری از تخلف» برای کمیته ارسال شد و
            تعیین تکلیف مالی برای جلسات آغاز شده است.
          </div>
        )}

        {currentState === 'violation_and_applied' && (
          <div
            data-testid="session-cancellation-violation-applied"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#7f1d1d',
            }}
          >
            کنسلی ثبت شد. تخلف آموزشی به کمیته نظارت گزارش شد و تعیین تکلیف مالی
            برای جلسات در حال اجراست.
          </div>
        )}

        {upcoming.length === 0 && currentState === 'calendar_displayed' && (
          <p style={{ margin: 0, fontSize: '0.82rem', color: '#b45309', lineHeight: 1.6 }}>
            جلسهٔ برنامه‌ریزی‌شده‌ای در ۳ هفتهٔ آینده نیست.
          </p>
        )}
      </div>
    </div>
  )
}
