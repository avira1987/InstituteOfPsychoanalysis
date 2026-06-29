/** نمایش مشترک زنجیره «کاهش جلسات هفتگی سوپرویژن» — فرایند ۲۳. */

import React from 'react'

export const SUPERVISION_REDUCTION_PATH_B_STEPS = [
  { key: 'session_selection', state: 'session_selection', label: 'انتخاب جلسات برای حذف' },
  { key: 'multi_reduction_completed', state: 'multi_reduction_completed', label: 'کاهش انجام شد' },
]

export const SUPERVISION_REDUCTION_PATH_A_STEPS = [
  { key: 'structure_selection', state: 'structure_selection', label: 'تعیین توالی و زمان' },
  { key: 'supervisor_review', state: 'supervisor_review', label: 'بررسی سوپروایزر' },
  { key: 'frequency_reduction_completed', state: 'frequency_reduction_completed', label: 'ثبت نهایی' },
]

export const ELIGIBILITY_BLOCKED_MESSAGE_FA =
  'دانشجوی گرامی، زمانی می‌توانید جلسات سوپرویژن خود را به کمتر از یک بار در هفته برسانید که ساعات ۱۵۰، ۲۵۰ و ۷۵۰ به ترتیب برای سوپرویژن فردی، درمان آموزشی و تجربه بالینی را گذرانده باشید.'

export const FREQUENCY_LABELS_FA = {
  2: 'دو هفته یک‌بار',
  3: 'سه هفته یک‌بار',
  4: 'چهار هفته یک‌بار',
}

export const WEEKDAY_LABELS_FA = {
  saturday: 'شنبه',
  sunday: 'یکشنبه',
  monday: 'دوشنبه',
  tuesday: 'سه‌شنبه',
  wednesday: 'چهارشنبه',
  thursday: 'پنج‌شنبه',
  friday: 'جمعه',
}

export function parseWeeklyCount(raw) {
  if (raw == null || raw === '') return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

export function normalizeSelectedSessions(raw) {
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

export function resolveFrequencyStructure(ctx = {}, stepFormValues = {}) {
  const freqRaw = stepFormValues.frequency ?? ctx.frequency ?? null
  const freqNum = freqRaw != null ? Number(freqRaw) : null
  const dayKey = (stepFormValues.day ?? ctx.day ?? '').trim()
  const time = (stepFormValues.time ?? ctx.time ?? '').trim()
  const note = (stepFormValues.structure_note ?? ctx.structure_note ?? '').trim()
  return {
    frequency: freqNum,
    frequencyLabel: freqNum != null ? (FREQUENCY_LABELS_FA[freqNum] || `${freqNum} هفته یک‌بار`) : null,
    dayKey,
    dayLabel: WEEKDAY_LABELS_FA[dayKey] || dayKey || null,
    time,
    note,
  }
}

export function resolveSupervisorRejectionNote(ctx = {}) {
  return (
    ctx.supervisor_rejection_note
    ?? ctx.supervisor_rejection_reason_fa
    ?? ctx.rejection_reason_fa
    ?? ctx.supervisor_notes_fa
    ?? ''
  ).trim()
}

export function buildThresholdRows(ctx = {}) {
  const th = ctx.therapy_hours_2x != null ? Number(ctx.therapy_hours_2x) : null
  const tt = ctx.therapy_threshold != null ? Number(ctx.therapy_threshold) : null
  const ch = ctx.clinical_hours != null ? Number(ctx.clinical_hours) : null
  const ct = ctx.clinical_threshold != null ? Number(ctx.clinical_threshold) : null
  const sh = ctx.supervision_hours != null ? Number(ctx.supervision_hours) : null
  const st = ctx.supervision_threshold != null ? Number(ctx.supervision_threshold) : null
  return [
    { key: 'supervision', label: 'سوپرویژن فردی', hours: sh, threshold: st, color: '#f59e0b' },
    { key: 'therapy', label: 'درمان آموزشی', hours: th, threshold: tt, color: '#ea580c' },
    { key: 'clinical', label: 'تجربه بالینی', hours: ch, threshold: ct, color: '#0ea5e9' },
  ].filter((r) => r.hours != null && r.threshold != null)
}

export function ThresholdRow({ row }) {
  const pct = row.threshold > 0
    ? Math.min(100, Math.round((row.hours / row.threshold) * 100))
    : 100
  const met = row.threshold <= 0 || row.hours >= row.threshold
  const remaining = Math.max(0, row.threshold - row.hours)

  return (
    <div data-testid={`supervision-reduction-threshold-${row.key}`}>
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

function activeStepIndex(steps, currentState) {
  if (!currentState) return 0
  const idx = steps.findIndex((s) => s.state === currentState)
  if (idx >= 0) return idx
  const terminal = steps[steps.length - 1]?.state
  if (currentState === terminal) return steps.length - 1
  return 0
}

export function SupervisionReductionFlowStepper({
  steps,
  currentState,
  compact = false,
  testId = 'supervision-reduction-flow-stepper',
}) {
  const activeIdx = activeStepIndex(steps, currentState)
  const terminalState = steps[steps.length - 1]?.state
  const completed = currentState === terminalState

  return (
    <div
      data-testid={testId}
      style={{
        display: 'grid',
        gridTemplateColumns: compact
          ? '1fr'
          : 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {steps.map((step, i) => {
        const done = completed ? true : i < activeIdx
        const current = !completed && i === activeIdx
        const tone = done ? '#16a34a' : current ? '#7c3aed' : '#94a3b8'
        const bg = done ? '#f0fdf4' : current ? '#f5f3ff' : '#f8fafc'
        return (
          <div
            key={step.key}
            style={{
              padding: compact ? '0.5rem 0.6rem' : '0.55rem 0.65rem',
              borderRadius: '8px',
              background: bg,
              borderRight: `3px solid ${tone}`,
              fontSize: compact ? '0.74rem' : '0.76rem',
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
            {completed && i === steps.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function StructurePreviewChip({ structure, testId = 'supervision-reduction-structure-preview' }) {
  if (!structure.frequencyLabel && !structure.dayLabel && !structure.time) return null
  return (
    <div
      data-testid={testId}
      style={{
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: '#f5f3ff',
        borderRight: '4px solid #7c3aed',
        fontSize: '0.84rem',
        lineHeight: 1.7,
      }}
    >
      <div style={{ fontWeight: 700, color: '#5b21b6', marginBottom: '0.35rem', fontSize: '0.82rem' }}>
        ساختار پیشنهادی جدید
      </div>
      {structure.frequencyLabel && (
        <div>
          <strong>توالی:</strong>
          {' '}
          {structure.frequencyLabel}
        </div>
      )}
      {structure.dayLabel && (
        <div>
          <strong>روز:</strong>
          {' '}
          {structure.dayLabel}
        </div>
      )}
      {structure.time && (
        <div>
          <strong>ساعت:</strong>
          {' '}
          <span dir="ltr" style={{ fontVariantNumeric: 'tabular-nums' }}>{structure.time}</span>
        </div>
      )}
      {structure.note && (
        <div style={{ marginTop: '0.35rem', color: '#64748b', fontSize: '0.8rem' }}>
          {structure.note}
        </div>
      )}
    </div>
  )
}
