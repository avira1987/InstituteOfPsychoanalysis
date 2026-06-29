import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import { HintBlock, ReadonlyRow } from '../utils/attendanceChainDisplay'
import {
  AgreedTimeRow,
  InternHoursFlowStepper,
  labelDisciplinaryStatus,
  resolveAgreedTimes,
  resolveMilestoneInfo,
} from '../utils/internHoursIncreaseDisplay'

const ACCENT = '#d97706'
const ACCENT_BG = '#fffbeb'
const ACCENT_TEXT = '#92400e'

const STATE_HINTS = {
  deadline_reached: 'سیستم سررسید افزایش ساعت را شناسایی کرده است. پس از هشدار به کمیته، پرونده به مرحلهٔ بررسی منتقل می‌شود.',
  supervision_review: 'وضعیت انضباطی انترن را در فرم پایین بررسی کنید. اگر «فاقد تخلف» است دکمهٔ تأیید را بزنید؛ در صورت «دارای تخلف» پرونده به کمیته تخلفات ارجاع می‌شود.',
  approved_time_coordination: 'زمان‌های توافق‌شده با انترن را در فرم ثبت کنید و در شیت وقت‌های آزاد مرکز وارد کنید؛ سپس دکمهٔ «ثبت زمان‌ها» را بزنید تا ظرفیت به‌صورت خودکار افزایش یابد.',
  rejected_referral: 'افزایش ظرفیت تأیید نشد. پرونده به فرایند ثبت تخلف ارجاع شده و پیامک به دانشجو ارسال می‌شود.',
  hours_increased: 'ظرفیت ارائه درمان انترن افزایش یافت. زمان‌های جدید در شیت وقت‌های آزاد ثبت شده و پیامک تأیید به دانشجو ارسال می‌شود.',
}

/**
 * داشبورد راهنمای «افزایش حداکثر ساعت‌های ارائه درمان انترن» — فرایند ۳۹.
 * مخصوص پورتال کمیته نظارت.
 */
export default function InternHoursIncreasePanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const milestone = useMemo(() => resolveMilestoneInfo(ctx), [ctx])
  const agreedTimes = useMemo(
    () => resolveAgreedTimes(ctx, stepFormValues),
    [ctx, stepFormValues],
  )

  if (!active || !detail || detail.process_code !== 'intern_hours_increase') {
    return null
  }

  const hint = STATE_HINTS[currentState]
    ?? 'پروندهٔ افزایش ظرفیت ارائه درمان انترن — بررسی طبق دستور کار کمیته نظارت.'
  const isTerminal = currentState === 'rejected_referral' || currentState === 'hours_increased'
  const disciplinaryLabel = labelDisciplinaryStatus(
    ctx.disciplinary_status ?? stepFormValues.disciplinary_status,
  )

  return (
    <div
      className="card"
      data-testid="intern-hours-increase-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">
          اضافه شدن حداکثر ساعت‌های ارائه درمان انترن (فرایند ۳۹)
        </h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <InternHoursFlowStepper currentState={currentState} compact={compact} />

        {!isTerminal && hint && (
          <HintBlock
            testId="intern-hours-state-hint"
            title="راهنمای مرحله"
            color={ACCENT}
            bg={ACCENT_BG}
          >
            <span style={{ color: ACCENT_TEXT }}>{hint}</span>
          </HintBlock>
        )}

        <div
          data-testid="intern-hours-milestone-summary"
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          {milestone.month != null && (
            <div
              style={{
                padding: '0.75rem 0.85rem',
                borderRadius: '10px',
                background: '#f8fafc',
                borderRight: '4px solid #64748b',
              }}
            >
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>
                ماه سررسید انترنشیپ
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#334155' }}>
                ماه
                {' '}
                {milestone.month.toLocaleString('fa-IR')}
              </div>
            </div>
          )}

          {milestone.hoursIncrease != null && (
            <div
              data-testid="intern-hours-increase-amount"
              style={{
                padding: '0.75rem 0.85rem',
                borderRadius: '10px',
                background: ACCENT_BG,
                borderRight: `4px solid ${ACCENT}`,
              }}
            >
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>
                ساعت اضافهٔ پیش‌بینی‌شده
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: ACCENT_TEXT }}>
                +
                {milestone.hoursIncrease.toLocaleString('fa-IR')}
                {' '}
                ساعت
              </div>
              <div style={{ fontSize: '0.76rem', color: '#78716c', marginTop: '0.2rem' }}>
                {milestone.patternLabel}
              </div>
            </div>
          )}
        </div>

        {currentState === 'supervision_review' && (
          <div
            data-testid="intern-hours-review-options"
            style={{
              display: 'grid',
              gap: '0.65rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
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
              <strong>فاقد تخلف:</strong>
              {' '}
              تأیید صلاحیت — پرونده به مرحلهٔ هماهنگی زمان‌های جدید می‌رود.
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
              <strong>دارای تخلف:</strong>
              {' '}
              ارجاع به کمیته تخلفات — افزایش ظرفیت به‌تعویق می‌افتد.
            </div>
          </div>
        )}

        {currentState === 'approved_time_coordination' && (
          <HintBlock
            testId="intern-hours-coordination-note"
            title="ثبت در شیت وقت‌های آزاد"
            color="#2563eb"
            bg="#eff6ff"
          >
            پس از هماهنگی با انترن، روز و بازهٔ زمانی هر جلسه را در فرم پایین وارد کنید.
            سپس با دکمهٔ «ثبت زمان‌ها» ظرفیت به‌صورت خودکار افزایش می‌یابد.
          </HintBlock>
        )}

        {disciplinaryLabel && (
          <ReadonlyRow
            label="وضعیت انضباطی ثبت‌شده"
            value={disciplinaryLabel}
            testId="intern-hours-disciplinary-status"
          />
        )}

        {agreedTimes.length > 0 && (
          <div
            data-testid="intern-hours-agreed-times-block"
            style={{ marginBottom: compact ? '0.5rem' : '0.75rem' }}
          >
            <div
              style={{
                fontSize: '0.82rem',
                fontWeight: 700,
                color: '#334155',
                marginBottom: '0.45rem',
              }}
            >
              زمان‌های توافق‌شده
            </div>
            <div style={{ display: 'grid', gap: '0.45rem' }}>
              {agreedTimes.map((row, i) => (
                <AgreedTimeRow key={`${row.day}-${row.start_time}-${i}`} row={row} index={i} />
              ))}
            </div>
          </div>
        )}

        {currentState === 'hours_increased' && (
          <div
            data-testid="intern-hours-success-block"
            style={{
              marginTop: '0.5rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#166534',
            }}
          >
            ظرفیت ارائه درمان انترن افزایش یافت
            {milestone.hoursIncrease != null && (
              <>
                {' '}
                (
                +
                {milestone.hoursIncrease.toLocaleString('fa-IR')}
                {' '}
                ساعت)
              </>
            )}
            . زمان‌های جدید در شیت وقت‌های آزاد ثبت شده‌اند.
          </div>
        )}

        {currentState === 'rejected_referral' && (
          <div
            data-testid="intern-hours-rejected-block"
            style={{
              marginTop: '0.5rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#991b1b',
            }}
          >
            افزایش ظرفیت تأیید نشد. پرونده به فرایند ثبت تخلف ارجاع شده است.
          </div>
        )}
      </div>
    </div>
  )
}
