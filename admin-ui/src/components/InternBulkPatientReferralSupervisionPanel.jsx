import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import { HintBlock, ReadonlyRow } from '../utils/attendanceChainDisplay'
import {
  ReferralFlowStepper,
  PatientRowsSummary,
  resolveReferralContext,
} from '../utils/internBulkPatientReferralDisplay'

const ACCENT = '#d97706'
const ACCENT_BG = '#fffbeb'
const ACCENT_TEXT = '#92400e'

const STATE_HINTS = {
  supervision_start:
    'تاریخ جلسه، وضعیت برگزاری، شرایط ارجاع و لیست همهٔ بیماران انترن را در فرم پایین ثبت کنید؛ سپس «ثبت جلسه و شرایط» را بزنید.',
}

/**
 * راهنمای کمیته نظارت — فرایند ۷۲، مرحله supervision_start.
 */
export default function InternBulkPatientReferralSupervisionPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const ref = useMemo(() => resolveReferralContext(ctx), [ctx])

  if (
    !active
    || !detail
    || detail.process_code !== 'intern_bulk_patient_referral'
    || currentState !== 'supervision_start'
  ) {
    return null
  }

  const hint = STATE_HINTS[currentState]
    ?? 'ارجاع کلیه بیماران انترن — ثبت جلسه و شرایط طبق SOP.'

  return (
    <div
      className="card"
      data-testid="intern-bulk-referral-supervision-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">
          ارجاع بیماران انترن (فرایند ۷۲)
        </h3>
        {!compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ReferralFlowStepper currentState={currentState} compact={compact} />

        <HintBlock testId="intern-bulk-supervision-hint" title="راهنمای مرحله" color={ACCENT} bg={ACCENT_BG}>
          <span style={{ color: ACCENT_TEXT }}>{hint}</span>
        </HintBlock>

        {ref.referralConditions && (
          <ReadonlyRow label="شرایط ارجاع (ثبت‌شده)" value={ref.referralConditions} />
        )}
        {ref.patientCount > 0 && (
          <div style={{ marginTop: '0.65rem' }}>
            <PatientRowsSummary rows={ref.patientRows} />
          </div>
        )}
      </div>
    </div>
  )
}
