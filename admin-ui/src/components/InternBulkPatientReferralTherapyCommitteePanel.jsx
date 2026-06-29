import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import { HintBlock } from '../utils/attendanceChainDisplay'
import {
  ReferralFlowStepper,
  resolveReferralContext,
} from '../utils/internBulkPatientReferralDisplay'

const ACCENT = '#2563eb'
const ACCENT_BG = '#eff6ff'
const ACCENT_TEXT = '#1e40af'

const STATE_HINTS = {
  general_therapy_committee_review:
    'یادداشت‌های دانشجو را برای هر بیمار ببینید؛ تیک صحبت کمیته و توضیحات ارجاع را در فرم پایین ثبت کنید.',
}

/**
 * راهنمای مجری کمیته درمان عموم — فرایند ۷۲.
 */
export default function InternBulkPatientReferralTherapyCommitteePanel({
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
    || currentState !== 'general_therapy_committee_review'
  ) {
    return null
  }

  return (
    <div
      className="card"
      data-testid="intern-bulk-referral-therapy-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">ارجاع بیماران انترن — کمیته درمان عموم (فرایند ۷۲)</h3>
        {!compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ReferralFlowStepper currentState={currentState} compact={compact} />

        <HintBlock testId="intern-bulk-therapy-hint" title="راهنمای مرحله" color={ACCENT} bg={ACCENT_BG}>
          <span style={{ color: ACCENT_TEXT }}>{STATE_HINTS.general_therapy_committee_review}</span>
        </HintBlock>

        {ref.patientRows.length > 0 && (
          <div
            data-testid="therapy-committee-student-notes"
            style={{
              marginTop: '0.65rem',
              padding: '0.75rem',
              borderRadius: '8px',
              background: '#f8fafc',
              fontSize: '0.82rem',
              lineHeight: 1.65,
            }}
          >
            <strong>یادداشت‌های دانشجو (خلاصه):</strong>
            <ul style={{ margin: '0.4rem 0 0', paddingRight: '1.1rem' }}>
              {ref.patientRows.map((r) => (
                <li key={r.row_id}>
                  <strong>{r.patient_name}</strong>
                  {r.contact_notes ? ` — ${r.contact_notes}` : ' — (بدون توضیح)'}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
