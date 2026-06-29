import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import { ReadonlyRow } from '../utils/earlyTerminationChainDisplay'
import {
  NonRegistrationFlowStepper,
  labelNonRegState,
  resolveNonRegistrationContext,
  weeksRegisterStatusFa,
  fmtMeetingDateTime,
  meetingModeLabel,
  DECISION_LABELS,
} from '../utils/studentNonRegistrationDisplay'

const ACCENT = '#d97706'
const ACCENT_BG = '#fffbeb'
const ACCENT_TEXT = '#92400e'

const STATE_HINTS = {
  list_generated: 'دانشجو بدون ثبت‌نام در مهلت قانونی شناسایی شد. فرم «تعیین جلسه» را در بخش پایین پر و ثبت کنید، سپس دکمهٔ «ثبت جلسه» را بزنید.',
  meeting_scheduled: 'دعوت‌نامه به‌صورت خودکار برای دانشجو ارسال می‌شود. پس از برگزاری جلسه، دکمهٔ «ارسال دعوت‌نامه / ثبت مرحله بعد» را بزنید تا به ثبت نتیجه بروید.',
  meeting_held: 'پس از برگزاری جلسه، فرم «ثبت نتیجه جلسه» را تکمیل کنید. سپس دقیقاً یکی از دکمه‌های تصمیم (ثبت‌نام / مرخصی / انصراف) را مطابق انتخاب فرم بزنید.',
}

/**
 * داشبورد راهنمای «عدم ثبت‌نام ترم بعد» — فرایند ۴۲ (کمیته نظارت).
 */
export default function StudentNonRegistrationReviewPanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const nr = useMemo(
    () => resolveNonRegistrationContext({ ...ctx, ...stepFormValues }),
    [ctx, stepFormValues],
  )

  if (!active || !detail || detail.process_code !== 'student_non_registration') {
    return null
  }

  const hint = STATE_HINTS[currentState]
    ?? 'پروندهٔ عدم ثبت‌نام ترم — بررسی طبق دستور کار کمیته نظارت.'
  const weeksStatus = weeksRegisterStatusFa(nr.weeksSinceStart)
  const decisionLabel = nr.decision ? (DECISION_LABELS[nr.decision] || nr.decision) : null

  return (
    <div
      className="card"
      data-testid="student-non-registration-review-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">
          عدم ثبت‌نام دانشجو برای ترم بعد (فرایند ۴۲)
        </h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState) || labelNonRegState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <NonRegistrationFlowStepper currentState={currentState} compact={compact} />

        {hint && (
          <div
            data-testid="non-reg-committee-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: ACCENT_BG,
              borderRight: `4px solid ${ACCENT}`,
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: ACCENT_TEXT,
            }}
          >
            {hint}
          </div>
        )}

        <div
          data-testid="non-reg-dossier"
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
          <strong style={{ display: 'block', marginBottom: '0.5rem' }}>خلاصهٔ پرونده</strong>
          <ReadonlyRow label="کد ترم" value={nr.termCode} testId="non-reg-term-code" />
          <ReadonlyRow
            label="هفته از شروع کلاس‌ها"
            value={nr.weeksSinceStart != null ? `${nr.weeksSinceStart.toLocaleString('fa-IR')} هفته` : null}
            testId="non-reg-weeks-since-start"
          />
          {weeksStatus && (
            <p
              data-testid="non-reg-weeks-status"
              style={{
                margin: '0 0 0.5rem',
                fontSize: '0.82rem',
                color: nr.canRegister ? '#166534' : '#991b1b',
              }}
            >
              {weeksStatus}
            </p>
          )}
          {nr.meetingAt && (
            <>
              <ReadonlyRow
                label="زمان جلسه"
                value={fmtMeetingDateTime(nr.meetingAt)}
                testId="non-reg-meeting-at"
              />
              <ReadonlyRow
                label="نحوه برگزاری"
                value={meetingModeLabel(nr.meetingMode)}
                testId="non-reg-meeting-mode"
              />
              <ReadonlyRow
                label="لینک"
                value={nr.meetingLink}
                testId="non-reg-meeting-link"
              />
              <ReadonlyRow
                label="محل"
                value={nr.meetingLocation}
                testId="non-reg-meeting-location"
              />
            </>
          )}
          {decisionLabel && (
            <ReadonlyRow label="تصمیم ثبت‌شده" value={decisionLabel} testId="non-reg-decision" />
          )}
        </div>

        {currentState === 'meeting_held' && nr.weeksSinceStart != null && !nr.canRegister && (
          <div
            data-testid="non-reg-register-blocked-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#991b1b',
            }}
          >
            گزینهٔ «قصد ثبت‌نام» در فرم باید غیرفعال در نظر گرفته شود — بیش از ۴ هفته از شروع کلاس‌ها گذشته است.
          </div>
        )}
      </div>
    </div>
  )
}
