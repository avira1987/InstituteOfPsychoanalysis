import React, { useMemo } from 'react'
import { SlaBanner } from '../utils/earlyTerminationChainDisplay'
import {
  ReferralFlowStepper,
  computeCoordinationSla,
  resolveReferralContext,
  COORDINATION_SLA_DAYS,
} from '../utils/internBulkPatientReferralDisplay'
import { formatStudentCodeDisplay } from '../utils/processDisplay'

/**
 * راهنمای مسئول هماهنگی — فرایند ۷۲، state coordination_followup.
 */
export default function InternBulkPatientReferralCoordinationPanel({
  detail = null,
  user = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const ref = useMemo(() => resolveReferralContext(ctx), [ctx])
  const slaInfo = useMemo(() => computeCoordinationSla(ctx), [ctx])

  if (
    !active
    || !detail
    || detail.process_code !== 'intern_bulk_patient_referral'
    || currentState !== 'coordination_followup'
  ) {
    return null
  }

  const studentLabel = detail.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : null

  return (
    <div
      data-testid="intern-bulk-referral-coordination-panel"
      style={{
        padding: compact ? '0.75rem' : '1rem 1.25rem',
        marginBottom: compact ? '0.75rem' : '1.25rem',
        background: '#fffbeb',
        borderRadius: '10px',
        borderRight: '4px solid #d97706',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#92400e' }}>
        پیگیری ارجاع بیماران انترن (فرایند ۷۲)
      </h4>

      <ReferralFlowStepper currentState={currentState} compact />

      <SlaBanner
        slaInfo={slaInfo}
        title={`مهلت پیگیری (${COORDINATION_SLA_DAYS.toLocaleString('fa-IR')} روز)`}
        fallbackText="حداکثر ۳ روز برای تیک پیگیری همهٔ بیماران فرصت دارید؛ در صورت تأخیر هشدار به معاون مدیر داخلی ارسال می‌شود."
      />

      <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
        برای هر بیمار تیک «پیگیری انجام شد» را در فرم زیر بزنید؛ سپس دکمهٔ
        {' '}
        <code style={{ fontSize: '0.8rem' }}>coordination_followup_complete</code>
        {' '}
        را بزنید.
      </p>

      {studentLabel && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          پروندهٔ دانشجو:
          {' '}
          <strong>{studentLabel}</strong>
          {' '}
          —
          {' '}
          {ref.patientCount.toLocaleString('fa-IR')}
          {' '}
          بیمار
        </p>
      )}

      {user?.role && user.role !== 'therapy_education_coordinator' && user.role !== 'admin' && (
        <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
          این مرحله معمولاً بر عهدهٔ مسئول هماهنگی‌های آموزش درمان است.
        </p>
      )}
    </div>
  )
}
