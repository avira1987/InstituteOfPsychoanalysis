import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  computeSlaRemaining,
  formatSupervisionAbsenceContext,
  HintBlock,
  OptionCard,
  ReadonlyRow,
  SlaBanner,
  UNANNOUNCED_SUPERVISION_EXECUTOR_OPTIONS,
  UNANNOUNCED_SUPERVISION_SITE_MANAGER_OPTIONS,
} from '../utils/attendanceChainDisplay'

const ACCENT = '#0d9488'
const ACCENT_DARK = '#0f766e'
const ACCENT_LIGHT = '#ccfbf1'
const ACCENT_TEXT = '#115e59'

const PHASE_STEPS = [
  { code: 'identified', label: 'شناسایی' },
  { code: 'site_manager_review', label: 'مدیر داخلی' },
  { code: 'ambiguous_3week_wait', label: 'تایمر ۳ هفته' },
  { code: 'committee_pending', label: 'کمیته درمان و سوپرویژن' },
  { code: 'committee_executor_review', label: 'مجری کمیته' },
]

function PhaseStepper({ currentState }) {
  const terminalStates = [
    'stopped_on_leave',
    'first_absence_handled',
    'option_1_violation',
    'student_returned',
    'violation_reported',
  ]
  if (terminalStates.includes(currentState)) {
    return (
      <div
        data-testid="unannounced-supervision-absence-terminal"
        style={{
          marginBottom: '0.85rem',
          padding: '0.65rem 0.85rem',
          borderRadius: '8px',
          background: '#f0fdf4',
          borderRight: '4px solid #16a34a',
          fontSize: '0.84rem',
        }}
      >
        پرونده در مرحلهٔ پایانی است:
        {' '}
        {labelState(currentState)}
      </div>
    )
  }

  const stateToStep = {
    identified: 0,
    site_manager_review: 1,
    ambiguous_3week_wait: 2,
    committee_pending: 3,
    committee_executor_review: 4,
  }
  const activeIdx = stateToStep[currentState] ?? -1
  if (activeIdx < 0) return null

  return (
    <div
      data-testid="unannounced-supervision-absence-stepper"
      style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.85rem', flexWrap: 'wrap' }}
    >
      {PHASE_STEPS.map((step, i) => {
        const done = i < activeIdx
        const active = i === activeIdx
        return (
          <div
            key={step.code}
            style={{
              flex: '1 1 5.5rem',
              padding: '0.45rem 0.55rem',
              borderRadius: '8px',
              background: active ? ACCENT : done ? ACCENT_LIGHT : '#f1f5f9',
              color: active ? '#fff' : done ? ACCENT_TEXT : '#64748b',
              border: active ? `2px solid ${ACCENT_DARK}` : '1px solid #e2e8f0',
              fontSize: '0.7rem',
              textAlign: 'center',
              fontWeight: active ? 700 : 500,
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

/**
 * داشبورد راهنمای «واکنش به غیبت بدون اطلاع سوپرویژن» — فرایند ۲۷ (unannounced_supervision_absence_reaction).
 */
export default function UnannouncedSupervisionAbsenceReactionPanel({
  detail = null,
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const ambiguousSla = useMemo(
    () => (currentState === 'ambiguous_3week_wait' ? computeSlaRemaining(ctx, 21, 'ambiguous_3week_wait_entered_at') : null),
    [currentState, ctx],
  )

  if (!active || !detail || detail.process_code !== 'unannounced_supervision_absence_reaction') {
    return null
  }

  const sessionLines = formatSupervisionAbsenceContext(ctx)

  return (
    <div
      className="card"
      data-testid="unannounced-supervision-absence-reaction-panel"
      style={{ marginBottom: '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">واکنش به غیبت بدون اطلاع سوپرویژن (فرایند ۲۷ — No-Show)</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        <PhaseStepper currentState={currentState} />

        {sessionLines.length > 0 && (
          <div
            data-testid="unannounced-supervision-absence-session-context"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#f8fafc',
              fontSize: '0.84rem',
              lineHeight: 1.7,
            }}
          >
            {sessionLines.map((line) => (
              <p key={line} style={{ margin: '0 0 0.25rem' }}>{line}</p>
            ))}
          </div>
        )}

        {currentState === 'identified' && (
          <HintBlock
            testId="unannounced-supervision-absence-identified-hint"
            title="غیبت بدون اطلاع سوپرویژن شناسایی شد"
            color={ACCENT}
            bg="#f0fdfa"
          >
            سیستم بر اساس تعداد غیبت‌های پیوسته مسیر را تعیین می‌کند: غیبت اول (SMS)،
            دو جلسه پیوسته (ارجاع به مدیر داخلی)، یا توقف در صورت وقفهٔ سوپرویژن فردی.
          </HintBlock>
        )}

        {currentState === 'site_manager_review' && (
          <>
            <HintBlock
              testId="unannounced-supervision-absence-site-manager-hint"
              title="بررسی مدیر داخلی — دو جلسه پیوسته No-Show سوپرویژن"
              color="#dc2626"
              bg="#fef2f2"
            >
              یکی از سه گزینه را در بخش «تصمیم شما» انتخاب کنید. هر گزینه اثرات متفاوتی دارد:
            </HintBlock>
            <div
              data-testid="unannounced-supervision-absence-site-manager-options"
              style={{ display: 'grid', gap: '0.65rem', marginBottom: '0.85rem' }}
            >
              {UNANNOUNCED_SUPERVISION_SITE_MANAGER_OPTIONS.map((opt) => (
                <OptionCard key={opt.key} option={opt} testIdPrefix="unannounced-supervision-absence-sm" />
              ))}
            </div>
          </>
        )}

        {currentState === 'ambiguous_3week_wait' && (
          <>
            <HintBlock
              testId="unannounced-supervision-absence-ambiguous-hint"
              title="وضعیت مبهم — تایمر ۳ هفته"
              color="#d97706"
              bg="#fffbeb"
            >
              وقت سوپروایزر آزاد شده است. اگر دانشجو ظرف ۳ هفته فرایند آغاز یا تغییر دوبارهٔ
              سوپرویژن فردی را آغاز کند، پرونده به «بازگشت دانشجو» می‌رسد؛ در غیر این صورت به
              کمیته درمان آموزشی و سوپرویژن ارجاع می‌شود.
            </HintBlock>
            <SlaBanner
              slaInfo={ambiguousSla}
              title="مهلت ۳ هفته برای بازگشت به سوپرویژن"
              fallbackText="پس از ۳ هفته بدون بازگشت، پرونده به رئیس کمیته درمان آموزشی و سوپرویژن ارجاع می‌شود."
            />
          </>
        )}

        {currentState === 'committee_pending' && (
          <HintBlock
            testId="unannounced-supervision-absence-chair-hint"
            title="در انتظار رئیس کمیته درمان آموزشی و سوپرویژن"
            color="#2563eb"
            bg="#eff6ff"
          >
            رئیس کمیته پرونده را بررسی کرده و با دکمهٔ «واگذار کردم» پیگیری را به مجری کمیته
            واگذار می‌کند.
          </HintBlock>
        )}

        {currentState === 'committee_executor_review' && (
          <>
            <HintBlock
              testId="unannounced-supervision-absence-executor-hint"
              title="پیگیری مجری کمیته درمان آموزشی و سوپرویژن"
              color={ACCENT}
              bg="#f0fdfa"
            >
              یکی از دو گزینه را انتخاب کنید. در هر دو حالت تخلف آموزشی ثبت می‌شود:
            </HintBlock>
            <div
              data-testid="unannounced-supervision-absence-executor-options"
              style={{ display: 'grid', gap: '0.65rem', marginBottom: '0.85rem' }}
            >
              {UNANNOUNCED_SUPERVISION_EXECUTOR_OPTIONS.map((opt) => (
                <OptionCard key={opt.key} option={opt} testIdPrefix="unannounced-supervision-absence-ex" />
              ))}
            </div>
          </>
        )}

        <ReadonlyRow
          label="علت ورود"
          value={
            ctx.reason === 'two_consecutive_supervision_no_show'
              ? 'دو جلسه پیوسته No-Show سوپرویژن'
              : ctx.reason || null
          }
          testId="unannounced-supervision-absence-reason"
        />
        <ReadonlyRow
          label="نتیجهٔ ثبت‌شده در پرونده"
          value={
            ctx.portal_result === 'definitive_supervision_stop'
              ? 'قطع سوپرویژن قطعی'
              : ctx.portal_result === 'agreed_to_return_supervision'
                ? 'پذیرفته بازگشت به سوپرویژن'
                : ctx.portal_result || null
          }
          testId="unannounced-supervision-absence-portal-result"
        />
      </div>
    </div>
  )
}
