import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  computeSlaRemaining,
  ReadonlyRow,
  RESTART_SMS_TEXT_FA,
  SlaBanner,
  terminationReasonLabel,
} from '../utils/earlyTerminationChainDisplay'

/**
 * داشبورد راهنمای زیرفرایند الف — فرایند ۱۲ (specialized_commission_review).
 */
export default function SpecializedCommissionReviewPanel({
  detail = null,
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const restartSla = useMemo(
    () => (currentState === 'awaiting_student_restart' ? computeSlaRemaining(ctx, 5) : null),
    [currentState, ctx],
  )

  if (!active || !detail || detail.process_code !== 'specialized_commission_review') {
    return null
  }

  return (
    <div
      className="card"
      style={{ marginBottom: '1.25rem' }}
      data-testid="specialized-commission-review-panel"
    >
      <div className="card-header">
        <h3 className="card-title">کمیسیون تخصصی (فرایند ۱۲ — بخش ۲ زیرفرایند الف)</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        <div
          data-testid="commission-dossier"
          style={{
            marginBottom: '0.85rem',
            padding: '0.85rem 1rem',
            borderRadius: '10px',
            background: '#f5f3ff',
            borderRight: '4px solid #7c3aed',
            fontSize: '0.84rem',
            lineHeight: 1.75,
          }}
        >
          <strong style={{ display: 'block', marginBottom: '0.5rem' }}>پرونده ارجاعی (علت ۳)</strong>
          <ReadonlyRow
            label="علت قطع"
            value={terminationReasonLabel(ctx)}
            testId="commission-termination-reason"
          />
          <ReadonlyRow
            label="توضیحات درمانگر"
            value={(ctx.termination_note || '').trim() || null}
            testId="commission-termination-note"
          />
        </div>

        {currentState === 'commission_review' && (
          <>
            <div
              data-testid="commission-review-hint"
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
              پرونده را بررسی کرده و با دانشجو جلسه بگذارید. فرم را ثبت کنید، سپس «تأیید صلاحیت»
              یا «رد صلاحیت» را بزنید. رد → ارجاع به کمیته‌های نظارت و آموزش (فرایند ۱۳).
            </div>
            <div
              data-testid="commission-outcomes-overview"
              style={{
                display: 'grid',
                gap: '0.65rem',
                marginBottom: '0.85rem',
              }}
            >
              <div
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  background: '#f0fdf4',
                  borderRight: '4px solid #16a34a',
                  fontSize: '0.84rem',
                  lineHeight: 1.7,
                }}
              >
                <strong style={{ color: '#15803d' }}>تأیید صلاحیت</strong>
                <ul style={{ margin: '0.35rem 0 0', paddingInlineStart: '1.1rem' }}>
                  <li>باز شدن انتخاب درمانگر برای دانشجو (Unlock LMS)</li>
                  <li>مهلت ۵ روز برای آغاز دوباره درمان</li>
                  <li>عدم آغاز → ثبت تخلف آموزشی</li>
                </ul>
              </div>
              <div
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  background: '#fef2f2',
                  borderRight: '4px solid #dc2626',
                  fontSize: '0.84rem',
                  lineHeight: 1.7,
                }}
              >
                <strong style={{ color: '#b91c1c' }}>رد صلاحیت</strong>
                <ul style={{ margin: '0.35rem 0 0', paddingInlineStart: '1.1rem' }}>
                  <li>برچسب «عدم صلاحیت تخصصی»</li>
                  <li>ارجاع به زیرفرایند ب — کمیته‌های نظارت و آموزش</li>
                </ul>
              </div>
            </div>
          </>
        )}

        {currentState === 'awaiting_student_restart' && (
          <>
            <SlaBanner
              slaInfo={restartSla}
              title="مهلت ۵ روزه دانشجو"
              fallbackText="دانشجو باید ظرف ۵ روز درمان را از سر بگیرد."
            />
            <p style={{ fontSize: '0.82rem', color: '#57534e', lineHeight: 1.7 }}>
              {RESTART_SMS_TEXT_FA}
            </p>
          </>
        )}

        {currentState === 'referred_to_committees' && (
          <div
            data-testid="commission-referred"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
            }}
          >
            رد صلاحیت ثبت شد. پرونده به زیرفرایند ب (کمیته‌های نظارت و آموزش) ارجاع یافت.
          </div>
        )}

        {currentState === 'restart_completed' && (
          <div
            data-testid="commission-restart-done"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
              fontSize: '0.86rem',
            }}
          >
            دانشجو درمان را از سر گرفت.
          </div>
        )}

        {currentState === 'violation_no_restart' && (
          <div
            data-testid="commission-violation"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
            }}
          >
            دانشجو در مهلت ۵ روزه درمان را از سر نگرفت. فرایند ثبت تخلف آموزشی آغاز شده است.
          </div>
        )}
      </div>
    </div>
  )
}
