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
 * داشبورد «کنسل جلسات سوپرویژن» — فرایند ۲۵ (student_supervision_cancellation).
 */
export default function StudentSupervisionCancellationPanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
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
  const allowedCap = ctx.allowed_cancellation_cap_count != null
    ? Number(ctx.allowed_cancellation_cap_count)
    : null
  const upcoming = Array.isArray(ctx.upcoming_cancellation_sessions)
    ? ctx.upcoming_cancellation_sessions
    : []
  const groups = Array.isArray(ctx.supervision_cancellation_groups)
    ? ctx.supervision_cancellation_groups
    : []
  const wouldExceed = Boolean(ctx.would_exceed_consecutive_weeks)
  const tone = percentTone(percentAfter ?? percentNow)

  const isTerminal = [
    'cancellation_applied',
    'warning_and_applied',
    'violation_and_applied',
    'consecutive_blocked',
  ].includes(currentState)

  if (!active || !detail || detail.process_code !== 'student_supervision_cancellation') {
    return null
  }

  return (
    <div className="card" data-testid="student-supervision-cancellation-panel">
      {!compact && (
        <div className="card-header">
          <h3 className="card-title">کنسل جلسات سوپرویژن (فرایند ۲۵)</h3>
          {currentState && (
            <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
              {labelState(currentState)}
            </span>
          )}
        </div>
      )}

      <div style={{ padding: compact ? '0' : '0 1rem 1rem' }}>
        {currentState === 'calendar_displayed' && !compact && (
          <div
            data-testid="supervision-cancellation-init-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#f0fdfa',
              borderRight: '4px solid #0d9488',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#134e4a',
            }}
          >
            تقویم فقط ۳ هفتهٔ آینده را نشان می‌دهد. اگر دو سوپروایزر فعال دارید، جلسات هر دو
            {' '}
            نمایش داده می‌شوند. جلسات را تیک بزنید، فرم را ثبت کنید، سپس «ادامه و ثبت مرحله»
            را بزنید. برای وقفهٔ بیش از ۳ هفته متوالی از
            {' '}
            <strong>وقفه در سوپرویژن فردی</strong>
            {' '}
            استفاده کنید.
          </div>
        )}

        {(ctx.cancellation_status_summary_fa || '').trim() && !isTerminal && (
          <div
            data-testid="supervision-cancellation-status-summary"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#f8fafc',
              borderRight: '4px solid #64748b',
              fontSize: '0.84rem',
              lineHeight: 1.75,
              color: '#334155',
            }}
          >
            {ctx.cancellation_status_summary_fa}
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.5rem' : '0.85rem',
          }}
        >
          {completed != null && cancelled != null && (
            <StatTile
              label="سوابق جلسات"
              value={`${cancelled.toLocaleString('fa-IR')} کنسل / ${completed.toLocaleString('fa-IR')} برگزار`}
              sub="مبنای ساعات ۵۰ساعتی"
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
          {allowedCap != null && (
            <StatTile
              label="سقف مجاز کنسلی (۱۲٪)"
              value={allowedCap.toLocaleString('fa-IR')}
              sub="Round Up"
              accent={{ color: '#0f766e', bg: '#f0fdfa' }}
            />
          )}
          <StatTile
            label="جلسات قابل انتخاب"
            value={upcoming.length.toLocaleString('fa-IR')}
            sub="۳ هفتهٔ آینده"
            accent={{ color: '#ea580c', bg: '#fff7ed' }}
          />
        </div>

        {!compact && groups.length > 1 && currentState === 'calendar_displayed' && (
          <div style={{ marginBottom: '0.85rem' }}>
            {groups.map((g) => (
              <div
                key={g.supervisor_id || g.supervisor_name_fa}
                data-testid={`supervision-cancel-group-${g.supervisor_id || 'default'}`}
                style={{
                  marginBottom: '0.65rem',
                  padding: '0.65rem 0.85rem',
                  borderRadius: '8px',
                  background: '#f0fdfa',
                  border: '1px solid #99f6e4',
                  fontSize: '0.82rem',
                }}
              >
                <strong>{g.supervisor_name_fa}</strong>
                {' — '}
                {(g.sessions || []).length.toLocaleString('fa-IR')}
                {' '}
                جلسه در ۳ هفتهٔ آینده
              </div>
            ))}
          </div>
        )}

        {selectedIds.length > 0 && !isTerminal && (
          <div
            data-testid="supervision-cancellation-selection-summary"
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
            جلسه سوپرویژن برای کنسل انتخاب شده است.
          </div>
        )}

        {wouldExceed && !isTerminal && (
          <div
            role="alert"
            data-testid="supervision-cancellation-consecutive-block"
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
                برای وقفهٔ طولانی‌تر فرایند «وقفه در سوپرویژن فردی» را اجرا کنید.
              </>
            )}
          </div>
        )}

        {currentState === 'sessions_selected' && percentAfter != null && percentAfter >= 10 && percentAfter <= 12 && (
          <div
            role="status"
            data-testid="supervision-cancellation-warning-10-12"
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
            data-testid="supervision-cancellation-violation-popup"
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

        {percentAfter != null && percentAfter > 12 && !isTerminal && (
          <div
            role="alert"
            data-testid="supervision-cancellation-over-cap-warning"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #b91c1c',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#7f1d1d',
            }}
          >
            <strong>! هشدار:</strong>
            {' '}
            دانشجوی گرامی، تعداد کنسلی‌های شما از حد مجاز (۱۲ درصد) فراتر رفته است.
            این مورد به کمیته نظارت گزارش خواهد شد.
          </div>
        )}

        {currentState === 'consecutive_blocked' && (
          <div
            data-testid="supervision-cancellation-blocked-done"
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
            از فرایند «وقفه در سوپرویژن فردی» استفاده کنید.
          </div>
        )}

        {currentState === 'cancellation_applied' && (
          <div
            data-testid="supervision-cancellation-applied"
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
            کنسلی ثبت شد. ثبت حضور سوپروایزر برای تاریخ‌های انتخاب‌شده بسته شد.
            برای هر جلسه، فرایند تعیین تکلیف مالی به‌صورت خودکار اجرا می‌شود.
          </div>
        )}

        {currentState === 'warning_and_applied' && (
          <div
            data-testid="supervision-cancellation-warning-applied"
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
            {ctx.violation_registration_instance_id && (
              <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: '#78716c' }}>
                فرایند ثبت تخلف:
                {' '}
                <code dir="ltr" style={{ fontSize: '0.78rem' }}>
                  {String(ctx.violation_registration_instance_id)}
                </code>
              </p>
            )}
          </div>
        )}

        {currentState === 'violation_and_applied' && (
          <div
            data-testid="supervision-cancellation-violation-applied"
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
            {ctx.violation_registration_instance_id && (
              <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: '#78716c' }}>
                فرایند ثبت تخلف:
                {' '}
                <code dir="ltr" style={{ fontSize: '0.78rem' }}>
                  {String(ctx.violation_registration_instance_id)}
                </code>
              </p>
            )}
          </div>
        )}

        {upcoming.length === 0 && currentState === 'calendar_displayed' && !compact && (
          <p style={{ margin: 0, fontSize: '0.82rem', color: '#b45309', lineHeight: 1.6 }}>
            جلسهٔ برنامه‌ریزی‌شده‌ای در ۳ هفتهٔ آینده نیست.
          </p>
        )}
      </div>
    </div>
  )
}
