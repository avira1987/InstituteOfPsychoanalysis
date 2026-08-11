import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  PROCESS_STATE_LABELS_FA,
  PROCESS_STUDENT_TASK_LABELS_FA,
} from '../utils/processMetadataLabels'

/**
 * پنل خاتمه درمان آموزشی — ساعات و راهنمای اقدام تا therapy_completed.
 */
export default function StudentTherapyCompletionPanel({
  detail = null,
  compact = false,
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const isActive = detail?.process_code === 'therapy_completion'
    && !detail?.is_completed
    && !detail?.is_cancelled

  const rows = useMemo(() => {
    const th = ctx.therapy_hours_2x != null ? Number(ctx.therapy_hours_2x) : null
    const tt = ctx.therapy_threshold != null ? Number(ctx.therapy_threshold) : null
    const ch = ctx.clinical_hours != null ? Number(ctx.clinical_hours) : null
    const ct = ctx.clinical_threshold != null ? Number(ctx.clinical_threshold) : null
    const sh = ctx.supervision_hours != null ? Number(ctx.supervision_hours) : null
    const st = ctx.supervision_threshold != null ? Number(ctx.supervision_threshold) : null
    return [
      { key: 'therapy', label: 'درمان آموزشی', hours: th, threshold: tt, color: '#a21caf' },
      { key: 'clinical', label: 'تجربه بالینی', hours: ch, threshold: ct, color: '#0ea5e9' },
      { key: 'supervision', label: 'سوپرویژن', hours: sh, threshold: st, color: '#f59e0b' },
    ].filter((r) => r.hours != null && r.threshold != null)
  }, [ctx])

  if (!active || !detail || detail.process_code !== 'therapy_completion') {
    return null
  }
  if (compact && !isActive && !detail.is_completed) {
    return null
  }

  const evaluable = rows.filter((r) => r.threshold > 0)
  const allMet = evaluable.length > 0 && evaluable.every((r) => r.hours >= r.threshold)
  const preview = (ctx.therapy_completion_preview_fa || '').trim()
  const nextStep = (ctx.therapy_completion_next_step_fa || '').trim()
  const taskFa = currentState
    ? (PROCESS_STUDENT_TASK_LABELS_FA.therapy_completion?.[currentState] || null)
    : null
  const stateFa = currentState
    ? (PROCESS_STATE_LABELS_FA.therapy_completion?.[currentState] || labelState(currentState))
    : null

  const body = (
    <>
      {stateFa && (
        <p style={{ margin: '0 0 0.65rem', fontSize: '0.82rem' }}>
          <strong>وضعیت:</strong>
          {' '}
          {stateFa}
        </p>
      )}
      {taskFa && isActive && (
        <p style={{ margin: '0 0 0.75rem', fontSize: '0.84rem', lineHeight: 1.7, color: '#334155' }}>
          {taskFa}
        </p>
      )}
      {preview && (
        <p style={{ margin: '0 0 0.75rem', fontSize: '0.82rem', color: '#475569' }}>{preview}</p>
      )}

      {rows.length > 0 && (
        <div style={{ display: 'grid', gap: '0.55rem', marginBottom: '0.75rem' }}>
          {rows.map((r) => {
            const pct = r.threshold > 0
              ? Math.min(100, Math.round((r.hours / r.threshold) * 100))
              : 100
            const met = r.threshold <= 0 || r.hours >= r.threshold
            const remaining = Math.max(0, r.threshold - r.hours)
            return (
              <div key={r.key} data-testid={`therapy-completion-row-${r.key}`}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: 4 }}>
                  <span>
                    <strong>{r.label}</strong>
                    {met
                      ? <span style={{ color: '#16a34a', marginInlineStart: 6 }}>احراز شد</span>
                      : (
                        <span style={{ color: '#b45309', marginInlineStart: 6 }}>
                          {remaining.toLocaleString('fa-IR')}
                          {' '}
                          ساعت مانده
                        </span>
                      )}
                  </span>
                  <span dir="ltr">
                    {Number(r.hours).toLocaleString('fa-IR')}
                    /
                    {Number(r.threshold).toLocaleString('fa-IR')}
                  </span>
                </div>
                <div style={{ height: 8, borderRadius: 999, background: '#e2e8f0', overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${pct}%`,
                      height: '100%',
                      background: r.color,
                      borderRadius: 999,
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {evaluable.length > 0 && (
        <div
          data-testid="therapy-completion-gate-status"
          style={{
            fontSize: '0.8rem',
            fontWeight: 700,
            marginBottom: nextStep ? '0.5rem' : 0,
            color: allMet ? '#166534' : '#92400e',
          }}
        >
          {allMet ? 'همهٔ شرایط احراز شد — می‌توانید مرحله را ثبت کنید.' : 'شرایط هنوز کامل نیست.'}
        </div>
      )}

      {nextStep && detail.is_completed && (
        <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem', lineHeight: 1.7 }}>{nextStep}</p>
      )}
    </>
  )

  if (compact) {
    return (
      <div
        className="student-therapy-completion-panel"
        data-testid="student-therapy-completion-panel"
        style={{
          marginTop: '0.75rem',
          padding: '0.85rem 1rem',
          borderRadius: 10,
          background: 'linear-gradient(135deg, #fdf4ff 0%, #f8fafc 100%)',
          borderRight: '4px solid #a21caf',
          fontSize: '0.86rem',
          lineHeight: 1.75,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: '0.5rem', color: '#701a75' }}>
          ایست بازرسی خاتمه درمان
        </div>
        {body}
      </div>
    )
  }

  return (
    <div className="card" data-testid="student-therapy-completion-panel" style={{ marginBottom: '1rem' }}>
      <div className="card-header">
        <h3 className="card-title" style={{ margin: 0 }}>خاتمه درمان آموزشی</h3>
      </div>
      <div style={{ padding: '0 1rem 1rem' }}>{body}</div>
    </div>
  )
}
