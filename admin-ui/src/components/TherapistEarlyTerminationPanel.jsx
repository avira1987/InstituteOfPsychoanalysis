import React, { useMemo } from 'react'
import { labelProcess, labelState } from '../utils/processDisplay'
import {
  computeSlaRemaining,
  parseReasonCode,
  TERMINATION_REASONS,
} from '../utils/earlyTerminationChainDisplay'

const PATH_INFO = {
  standard: {
    title: 'مسیر استاندارد (علت ۱ یا ۲)',
    items: [
      'خاتمه رابطه درمانی و آزادسازی وقت درمانگر',
      'ثبت قطع در پرونده دانشجو و اطلاع‌رسانی',
      'مهلت ۵ روز برای آغاز دوباره درمان توسط دانشجو',
      'در صورت عدم آغاز: ثبت تخلف آموزشی',
    ],
    color: '#2563eb',
  },
  scientific: {
    title: 'مسیر علمی (علت ۳)',
    items: [
      'خاتمه رابطه درمانی و آزادسازی وقت درمانگر',
      'ارجاع به زیرفرایند کمیسیون تخصصی',
    ],
    color: '#7c3aed',
  },
  disciplinary: {
    title: 'مسیر انضباطی (علت ۴)',
    items: [
      'خاتمه رابطه درمانی و آزادسازی وقت درمانگر',
      'تغییر وضعیت دانشجو به Pending Investigation',
      'ارجاع به زیرفرایند بررسی کمیته‌ها',
    ],
    color: '#dc2626',
  },
}

function PathCard({ pathKey }) {
  const info = PATH_INFO[pathKey]
  if (!info) return null
  return (
    <div
      data-testid={`early-termination-path-${pathKey}`}
      style={{
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: '#f8fafc',
        borderRight: `4px solid ${info.color}`,
        fontSize: '0.84rem',
        lineHeight: 1.7,
      }}
    >
      <strong style={{ display: 'block', marginBottom: '0.35rem', color: info.color }}>
        {info.title}
      </strong>
      <ul style={{ margin: 0, paddingInlineStart: '1.1rem' }}>
        {info.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

function SubprocessStatusBlock({ ctx, currentState }) {
  const childCode = ctx.last_child_process_code
  const childId = ctx.last_child_process_instance_id
  const childState = ctx.last_child_current_state

  if (!childCode && currentState !== 'scientific_referred' && currentState !== 'disciplinary_referred') {
    return null
  }

  const expectedCode = currentState === 'scientific_referred'
    ? 'specialized_commission_review'
    : currentState === 'disciplinary_referred'
      ? 'committees_review'
      : childCode

  return (
    <div
      data-testid="early-termination-subprocess-status"
      style={{
        marginBottom: '0.85rem',
        padding: '0.85rem 1rem',
        borderRadius: '10px',
        background: '#f0fdf4',
        borderRight: '4px solid #16a34a',
        fontSize: '0.86rem',
        lineHeight: 1.75,
        color: '#14532d',
      }}
    >
      <strong style={{ display: 'block', marginBottom: '0.35rem' }}>وضعیت زیرفرایند</strong>
      {expectedCode && (
        <p style={{ margin: '0 0 0.35rem' }}>
          فرایند فعال:
          {' '}
          {labelProcess(expectedCode || childCode)}
        </p>
      )}
      {childState && (
        <p style={{ margin: '0 0 0.35rem' }}>
          مرحله:
          {' '}
          {labelState(childState)}
        </p>
      )}
      {childId && (
        <p style={{ margin: 0, fontSize: '0.78rem', color: '#166534' }}>
          شناسه پرونده زیرفرایند:
          {' '}
          {childId}
        </p>
      )}
      {!childCode && (
        <p style={{ margin: 0 }}>
          {currentState === 'scientific_referred'
            ? 'ارجاع به کمیسیون تخصصی (فرایند ۱۲) در حال پردازش است.'
            : 'ارجاع به کمیته‌های نظارت و آموزش (فرایند ۱۳) در حال پردازش است.'}
        </p>
      )}
    </div>
  )
}

/**
 * داشبورد راهنمای «قطع زودرس درمان آموزشی» — فرایند ۱۱ (therapy_early_termination).
 */
export default function TherapistEarlyTerminationPanel({
  detail = null,
  stepFormValues = {},
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const selectedReason = useMemo(() => {
    const fromForm = parseReasonCode(stepFormValues?.termination_reason_code)
    if (fromForm != null) return fromForm
    return parseReasonCode(ctx.termination_reason_code)
  }, [stepFormValues, ctx.termination_reason_code])

  const selectedMeta = selectedReason != null ? TERMINATION_REASONS[selectedReason] : null
  const slaInfo = useMemo(
    () => (currentState === 'awaiting_student_restart' ? computeSlaRemaining(ctx, 5) : null),
    [currentState, ctx],
  )

  if (!active || !detail || detail.process_code !== 'therapy_early_termination') {
    return null
  }

  return (
    <div className="card" data-testid="therapist-early-termination-panel">
      <div className="card-header">
        <h3 className="card-title">قطع زودرس درمان آموزشی (فرایند ۱۱ — بخش ۱)</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        {currentState === 'reason_selection' && (
          <div
            data-testid="early-termination-init-hint"
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
            یکی از چهار علت قطع را در فرم زیر انتخاب کنید، فرم را ثبت کنید، سپس دکمهٔ
            {' '}
            «ثبت تصمیم» را بزنید. مسیر فرایند بر اساس علت انتخابی تعیین می‌شود.
          </div>
        )}

        {currentState === 'reason_selection' && (
          <div
            data-testid="early-termination-paths-overview"
            style={{
              display: 'grid',
              gap: '0.65rem',
              marginBottom: '0.85rem',
            }}
          >
            <PathCard pathKey="standard" />
            <PathCard pathKey="scientific" />
            <PathCard pathKey="disciplinary" />
          </div>
        )}

        {selectedMeta && currentState === 'reason_selection' && (
          <div
            data-testid="early-termination-selected-preview"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: selectedMeta.bg,
              borderRight: `4px solid ${selectedMeta.color}`,
              fontSize: '0.86rem',
              lineHeight: 1.75,
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.25rem', color: selectedMeta.color }}>
              پیش‌نمایش مسیر:
              {' '}
              {selectedMeta.pathLabel}
            </strong>
            <span>{selectedMeta.label}</span>
          </div>
        )}

        {currentState === 'awaiting_student_restart' && (
          <div
            data-testid="early-termination-restart-wait"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: slaInfo?.expired ? '#fef2f2' : '#fffbeb',
              borderRight: `4px solid ${slaInfo?.expired ? '#dc2626' : '#d97706'}`,
              fontSize: '0.86rem',
              lineHeight: 1.75,
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>
              در انتظار آغاز دوباره توسط دانشجو
            </strong>
            {slaInfo ? (
              slaInfo.expired ? (
                <span style={{ color: '#991b1b' }}>
                  مهلت ۵ روزه به پایان رسیده است. سیستم تخلف آموزشی را ثبت می‌کند.
                </span>
              ) : (
                <span style={{ color: '#92400e' }}>
                  {slaInfo.daysLeft.toLocaleString('fa-IR')}
                  {' '}
                  روز تا پایان مهلت ۵ روزه باقی مانده
                  {slaInfo.deadline && (
                    <>
                      {' '}
                      (مهلت:
                      {' '}
                      {slaInfo.deadline.toLocaleDateString('fa-IR')}
                      )
                    </>
                  )}
                </span>
              )
            ) : (
              <span style={{ color: '#92400e' }}>
                دانشجو باید ظرف ۵ روز درمان را از سر بگیرد؛ در غیر این صورت تخلف ثبت می‌شود.
              </span>
            )}
          </div>
        )}

        {(currentState === 'scientific_referred' || currentState === 'disciplinary_referred') && (
          <>
            <div
              data-testid="early-termination-referred"
              style={{
                marginBottom: '0.85rem',
                padding: '0.85rem 1rem',
                borderRadius: '10px',
                background: '#f0fdf4',
                borderRight: '4px solid #16a34a',
                fontSize: '0.86rem',
                lineHeight: 1.75,
                color: '#14532d',
              }}
            >
              {currentState === 'scientific_referred'
                ? 'پرونده به کمیسیون تخصصی ارجاع شد. پیگیری از طریق زیرفرایند مربوطه انجام می‌شود.'
                : 'پرونده به کمیته‌های نظارت و آموزش ارجاع شد. وضعیت دانشجو Pending Investigation است.'}
            </div>
            <SubprocessStatusBlock ctx={ctx} currentState={currentState} />
          </>
        )}

        {(ctx.termination_note || '').trim() && (
          <p
            data-testid="early-termination-note-display"
            style={{ margin: 0, fontSize: '0.82rem', color: '#57534e', lineHeight: 1.7 }}
          >
            <strong>توضیحات درمانگر:</strong>
            {' '}
            {ctx.termination_note}
          </p>
        )}
      </div>
    </div>
  )
}
