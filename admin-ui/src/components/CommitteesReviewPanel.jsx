import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  computeSlaRemaining,
  formatCommissionOpinion,
  formatNezaratRecommendation,
  ReadonlyRow,
  resolveEntrySource,
  SlaBanner,
  terminationReasonLabel,
} from '../utils/earlyTerminationChainDisplay'

const STEPS = [
  { code: 'supervision_review', label: 'کمیته نظارت', sla: 3 },
  { code: 'education_review', label: 'کمیته آموزش', sla: 6 },
  { code: 'awaiting_student_restart', label: 'مهلت دانشجو', sla: 5 },
]

function Stepper({ currentState }) {
  const idx = STEPS.findIndex((s) => s.code === currentState)
  if (idx < 0 && !['restart_completed', 'violation_no_restart', 'education_terminated'].includes(currentState)) {
    return null
  }
  const terminalIdx = ['restart_completed', 'violation_no_restart', 'education_terminated'].includes(currentState)
    ? STEPS.length
    : idx

  return (
    <div
      data-testid="committees-review-stepper"
      style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.85rem', flexWrap: 'wrap' }}
    >
      {STEPS.map((step, i) => {
        const done = i < terminalIdx
        const active = i === terminalIdx && idx >= 0
        return (
          <div
            key={step.code}
            style={{
              flex: '1 1 7rem',
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
            <span style={{ display: 'block', opacity: 0.85, marginTop: '0.15rem' }}>
              SLA
              {' '}
              {step.sla}
              {' '}
              روز
            </span>
          </div>
        )
      })}
    </div>
  )
}

/**
 * داشبورد راهنمای زیرفرایند ب — فرایند ۱۳ (committees_review).
 */
export default function CommitteesReviewPanel({
  detail = null,
  stepFormValues = {},
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const supervisionSla = useMemo(
    () => (currentState === 'supervision_review' ? computeSlaRemaining(ctx, 3) : null),
    [currentState, ctx],
  )
  const educationSla = useMemo(
    () => (currentState === 'education_review' ? computeSlaRemaining(ctx, 6) : null),
    [currentState, ctx],
  )
  const restartSla = useMemo(
    () => (currentState === 'awaiting_student_restart' ? computeSlaRemaining(ctx, 5) : null),
    [currentState, ctx],
  )

  const nezaratPreview = formatNezaratRecommendation(ctx, stepFormValues)

  if (!active || !detail || detail.process_code !== 'committees_review') {
    return null
  }

  return (
    <div
      className="card"
      style={{ marginBottom: '1.25rem' }}
      data-testid="committees-review-panel"
    >
      <div className="card-header">
        <h3 className="card-title">بررسی کمیته‌ها (فرایند ۱۳ — بخش ۳ زیرفرایند ب)</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        <Stepper currentState={currentState} />

        <div
          data-testid="committees-review-dossier"
          style={{
            marginBottom: '0.85rem',
            padding: '0.85rem 1rem',
            borderRadius: '10px',
            background: '#f8fafc',
            borderRight: '4px solid #64748b',
            fontSize: '0.84rem',
            lineHeight: 1.75,
          }}
        >
          <strong style={{ display: 'block', marginBottom: '0.5rem' }}>پرونده ورودی</strong>
          <ReadonlyRow label="منبع ورود" value={resolveEntrySource(ctx)} testId="committees-entry-source" />
          <ReadonlyRow
            label="علت قطع درمانگر"
            value={terminationReasonLabel(ctx)}
            testId="committees-termination-reason"
          />
          <ReadonlyRow
            label="توضیحات درمانگر"
            value={(ctx.termination_note || '').trim() || null}
            testId="committees-termination-note"
          />
          <ReadonlyRow
            label="نظر کمیسیون تخصصی"
            value={formatCommissionOpinion(ctx)}
            testId="committees-commission-opinion"
          />
        </div>

        {currentState === 'supervision_review' && (
          <>
            <div
              data-testid="committees-supervision-hint"
              style={{
                marginBottom: '0.85rem',
                padding: '0.75rem 1rem',
                borderRadius: '10px',
                background: '#fffbeb',
                borderRight: '4px solid #d97706',
                fontSize: '0.86rem',
                lineHeight: 1.75,
              }}
            >
              کمیته نظارت فقط پیشنهاد مشورتی ثبت می‌کند (ادامه یا قطع). حکم نهایی با کمیته آموزش است.
              فرم را ثبت کنید، سپس «ثبت پیشنهاد» را بزنید.
            </div>
            <SlaBanner
              slaInfo={supervisionSla}
              title="مهلت بررسی کمیته نظارت (۳ روز)"
              fallbackText="ظرف ۳ روز پیشنهاد ثبت شود؛ در غیر این صورت معاون آموزش مطلع می‌شود."
            />
            {nezaratPreview !== '—' && (
              <div
                data-testid="committees-nezarat-preview"
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  background: '#eff6ff',
                  borderRight: '4px solid #2563eb',
                  fontSize: '0.84rem',
                }}
              >
                <strong>پیش‌نمایش پیشنهاد:</strong>
                {' '}
                {nezaratPreview}
              </div>
            )}
          </>
        )}

        {currentState === 'education_review' && (
          <>
            <div
              data-testid="committees-education-hint"
              style={{
                marginBottom: '0.85rem',
                padding: '0.75rem 1rem',
                borderRadius: '10px',
                background: '#eff6ff',
                borderRight: '4px solid #2563eb',
                fontSize: '0.86rem',
                lineHeight: 1.75,
              }}
            >
              پیش از حکم نهایی، سه منبع را بررسی کنید: علت درمانگر، نظر کمیسیون (در صورت وجود)، پیشنهاد نظارت.
            </div>
            <SlaBanner
              slaInfo={educationSla}
              title="مهلت تصمیم کمیته آموزش (۶ روز)"
              fallbackText="ظرف ۶ روز حکم نهایی صادر شود."
            />
            <ReadonlyRow
              label="پیشنهاد ثبت‌شده نظارت"
              value={nezaratPreview}
              testId="committees-supervision-rec-display"
            />
          </>
        )}

        {currentState === 'awaiting_student_restart' && (
          <div data-testid="committees-awaiting-restart">
            <SlaBanner
              slaInfo={restartSla}
              title="مهلت ۵ روزه دانشجو برای آغاز دوباره درمان"
              fallbackText="دانشجو باید ظرف ۵ روز درمان را از سر بگیرد؛ در غیر این صورت تخلف ثبت می‌شود."
            />
            <p style={{ fontSize: '0.82rem', color: '#57534e', lineHeight: 1.7, margin: 0 }}>
              LMS برای دانشجو باز شده است. پیامک استاندارد ارسال شده است.
            </p>
          </div>
        )}

        {currentState === 'education_terminated' && (
          <div
            data-testid="committees-terminated"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
            }}
          >
            <strong>حکم قطع قطعی صادر شد.</strong>
            {' '}
            حساب غیرفعال، جلسات آینده لغو، نامه رسمی صادر و در پرونده بایگانی می‌شود.
            برای انترن، فرایند ارجاع بیماران نیز آغاز می‌شود.
          </div>
        )}

        {currentState === 'restart_completed' && (
          <div
            data-testid="committees-restart-done"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
              fontSize: '0.86rem',
            }}
          >
            دانشجو در مهلت مقرر درمان را از سر گرفت. فرایند مختومه است.
          </div>
        )}
      </div>
    </div>
  )
}
