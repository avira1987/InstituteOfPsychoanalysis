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

function parseWeeklyCount(raw) {
  if (raw == null || raw === '') return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

function ThresholdRow({ row }) {
  const pct = row.threshold > 0
    ? Math.min(100, Math.round((row.hours / row.threshold) * 100))
    : 100
  const met = row.threshold <= 0 || row.hours >= row.threshold
  const remaining = Math.max(0, row.threshold - row.hours)

  return (
    <div data-testid={`therapy-reduction-threshold-${row.key}`}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        gap: '0.5rem',
        fontSize: '0.82rem',
      }}
      >
        <span>
          <strong>{row.label}</strong>
          {met
            ? <span style={{ color: '#16a34a', marginInlineStart: '0.4rem' }}>✓ احراز شد</span>
            : (
              <span style={{ color: '#b45309', marginInlineStart: '0.4rem' }}>
                {remaining.toLocaleString('fa-IR')} ساعت مانده
              </span>
            )}
        </span>
        <span dir="ltr" style={{ fontVariantNumeric: 'tabular-nums', color: '#475569' }}>
          {row.hours.toLocaleString('fa-IR')} / {row.threshold.toLocaleString('fa-IR')}
        </span>
      </div>
      <div
        style={{
          marginTop: '0.25rem',
          height: '7px',
          borderRadius: '999px',
          background: '#e2e8f0',
          overflow: 'hidden',
        }}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label={`${row.label}: ${pct}%`}
      >
        <div style={{
          width: `${pct}%`,
          height: '100%',
          background: met ? '#16a34a' : row.color,
          transition: 'width 0.4s ease',
        }}
        />
      </div>
    </div>
  )
}

/**
 * داشبورد راهنمای «کاهش جلسات هفتگی درمان» — فرایند ۱۰ (therapy_session_reduction).
 * نمایشی/راهنما؛ ورود داده از ProcessStepForms انجام می‌شود.
 */
export default function StudentTherapyReductionPanel({
  detail = null,
  stepFormValues = {},
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const weeklyBefore = ctx.student_weekly_sessions_before != null
    ? Number(ctx.student_weekly_sessions_before)
    : null
  const upcomingSessions = Array.isArray(ctx.upcoming_therapy_sessions)
    ? ctx.upcoming_therapy_sessions
    : []

  const thresholdRows = useMemo(() => {
    const th = ctx.therapy_hours_2x != null ? Number(ctx.therapy_hours_2x) : null
    const tt = ctx.therapy_threshold != null ? Number(ctx.therapy_threshold) : null
    const ch = ctx.clinical_hours != null ? Number(ctx.clinical_hours) : null
    const ct = ctx.clinical_threshold != null ? Number(ctx.clinical_threshold) : null
    const sh = ctx.supervision_hours != null ? Number(ctx.supervision_hours) : null
    const st = ctx.supervision_threshold != null ? Number(ctx.supervision_threshold) : null
    return [
      { key: 'therapy', label: 'درمان آموزشی', hours: th, threshold: tt, color: '#ea580c' },
      { key: 'clinical', label: 'تجربه بالینی', hours: ch, threshold: ct, color: '#0ea5e9' },
      { key: 'supervision', label: 'سوپرویژن', hours: sh, threshold: st, color: '#f59e0b' },
    ].filter((r) => r.hours != null && r.threshold != null)
  }, [ctx])

  const evaluableThresholds = thresholdRows.filter((r) => r.threshold > 0)
  const allThresholdsMet = evaluableThresholds.length > 0
    && evaluableThresholds.every((r) => r.hours >= r.threshold)

  const newWeekly = parseWeeklyCount(stepFormValues?.remaining_sessions_after_reduction)
  const selectedIds = normalizeSelectedSessions(stepFormValues?.selected_sessions)
  const requiredCancel = weeklyBefore != null && newWeekly != null
    ? Math.max(1, weeklyBefore - newWeekly)
    : null

  const wouldViolate = newWeekly === 1 && !allThresholdsMet
  const selectionMismatch = requiredCancel != null && selectedIds.length > 0
    && selectedIds.length < requiredCancel

  if (!active || !detail || detail.process_code !== 'therapy_session_reduction') {
    return null
  }

  if (weeklyBefore == null && thresholdRows.length === 0) {
    return null
  }

  return (
    <div className="card" data-testid="student-therapy-reduction-panel">
      <div className="card-header">
        <h3 className="card-title">کاهش جلسات هفتگی درمان آموزشی (فرایند ۱۰)</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        {currentState === 'initiated' && (
          <div
            data-testid="therapy-reduction-init-hint"
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
            برای شروع، دکمهٔ «ادامه و ثبت مرحله» را بزنید. اگر کمتر از ۲ جلسه در هفته دارید،
            در همین مسیر اعلام می‌شود و باید از فرایند وقفهٔ درمان استفاده کنید.
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.85rem',
          }}
        >
          {weeklyBefore != null && (
            <div
              data-testid="therapy-reduction-current-schedule"
              style={{
                padding: '0.85rem',
                borderRadius: '10px',
                background: '#fff7ed',
                borderRight: '4px solid #ea580c',
              }}
            >
              <div style={{ fontSize: '0.78rem', color: '#64748b' }}>برنامهٔ فعلی</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#9a3412' }}>
                {weeklyBefore.toLocaleString('fa-IR')}
                <span style={{ fontSize: '0.85rem', fontWeight: 500 }}> جلسه در هفته</span>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#78716c', marginTop: '0.25rem' }}>
                {upcomingSessions.length.toLocaleString('fa-IR')} جلسهٔ آتی در تقویم
              </div>
            </div>
          )}

          {newWeekly != null && weeklyBefore != null && currentState === 'session_selection' && (
            <div
              data-testid="therapy-reduction-preview-weekly"
              style={{
                padding: '0.85rem',
                borderRadius: '10px',
                background: wouldViolate ? '#fffbeb' : '#f0fdf4',
                borderRight: `4px solid ${wouldViolate ? '#d97706' : '#16a34a'}`,
              }}
            >
              <div style={{ fontSize: '0.78rem', color: '#64748b' }}>پس از کاهش (پیش‌نمایش)</div>
              <div style={{
                fontSize: '1.25rem',
                fontWeight: 800,
                color: wouldViolate ? '#92400e' : '#14532d',
              }}
              >
                {newWeekly.toLocaleString('fa-IR')}
                <span style={{ fontSize: '0.85rem', fontWeight: 500 }}> جلسه در هفته</span>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#78716c', marginTop: '0.25rem' }}>
                {selectedIds.length.toLocaleString('fa-IR')} جلسه برای لغو انتخاب شده
                {requiredCancel != null ? ` (حداقل ${requiredCancel.toLocaleString('fa-IR')})` : ''}
              </div>
            </div>
          )}
        </div>

        {thresholdRows.length > 0 && (
          <div
            data-testid="therapy-reduction-thresholds"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #fff7ed 0%, #f8fafc 100%)',
              borderRight: '4px solid #ea580c',
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.5rem',
              marginBottom: '0.55rem',
            }}
            >
              <span style={{ fontWeight: 700, color: '#9a3412', fontSize: '0.88rem' }}>
                وضعیت ساعات آموزشی
              </span>
              {evaluableThresholds.length > 0 && (
                <span
                  data-testid="therapy-reduction-threshold-status"
                  style={{
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    padding: '0.15rem 0.6rem',
                    borderRadius: '999px',
                    background: allThresholdsMet ? '#dcfce7' : '#fef3c7',
                    color: allThresholdsMet ? '#166534' : '#92400e',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {allThresholdsMet ? 'همهٔ حدنصاب‌ها کامل است' : 'حدنصاب‌ها هنوز کامل نیست'}
                </span>
              )}
            </div>
            <div style={{ display: 'grid', gap: '0.6rem' }}>
              {thresholdRows.map((row) => (
                <ThresholdRow key={row.key} row={row} />
              ))}
            </div>
          </div>
        )}

        {currentState === 'session_selection' && wouldViolate && (
          <div
            role="alert"
            data-testid="therapy-reduction-violation-warning"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #fffbeb 0%, #fff7ed 100%)',
              borderRight: '4px solid #d97706',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#78350f',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>هشدار تخلف آموزشی</strong>
            کاهش جلسات به یک بار در هفته پیش از تکمیل ساعات مصوب، تخلف آموزشی محسوب می‌شود.
            ساعات گذرانده‌شده در حالت یک جلسه در هفته ممکن است جزو ۲۵۰ ساعت درمان آموزشی
            (دو بار در هفته) برای فارغ‌التحصیلی محاسبه نشود. پس از ثبت، گزارش به کمیتهٔ نظارت
            ارسال می‌شود و باید مرحلهٔ تأیید را تکمیل کنید.
          </div>
        )}

        {currentState === 'session_selection' && selectionMismatch && (
          <div
            role="status"
            data-testid="therapy-reduction-selection-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.7rem 0.9rem',
              borderRadius: '8px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#991b1b',
            }}
          >
            تعداد جلسات انتخاب‌شده برای لغو با کاهش برنامه هم‌خوان نیست.
            {' '}
            حداقل
            {' '}
            {requiredCancel.toLocaleString('fa-IR')}
            {' '}
            جلسهٔ آتی را انتخاب کنید.
          </div>
        )}

        {currentState === 'violation_warning' && (
          <div
            role="alert"
            data-testid="therapy-reduction-violation-ack"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #fef2f2 0%, #fff7ed 100%)',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#7f1d1d',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>تأیید با علم به تبعات آموزشی</strong>
            با ادامهٔ این مسیر، کاهش در برنامه اعمال می‌شود و فرایند ثبت تخلف آموزشی نیز باز می‌شود.
            چک‌باکس را در فرم زیر بزنید و سپس «ادامه و ثبت مرحله» را انتخاب کنید.
          </div>
        )}

        {(ctx.therapy_reduction_next_step_fa || '').trim() && (
          <p
            data-testid="therapy-reduction-next-step"
            style={{ margin: 0, fontSize: '0.82rem', color: '#57534e', lineHeight: 1.7 }}
          >
            {ctx.therapy_reduction_next_step_fa}
          </p>
        )}

        {upcomingSessions.length === 0 && currentState === 'session_selection' && (
          <p
            style={{
              margin: '0.85rem 0 0',
              fontSize: '0.8rem',
              color: '#b45309',
              lineHeight: 1.6,
            }}
          >
            جلسهٔ آتی برنامه‌ریزی‌شده‌ای در تقویم نیست؛ در صورت نیاز با پشتیبانی تماس بگیرید.
          </p>
        )}
      </div>
    </div>
  )
}
