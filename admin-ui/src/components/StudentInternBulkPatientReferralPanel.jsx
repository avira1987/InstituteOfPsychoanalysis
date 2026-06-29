import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import { SlaBanner } from '../utils/earlyTerminationChainDisplay'
import {
  ReferralFlowStepper,
  PatientRowsSummary,
  computeStudentContactSla,
  resolveReferralContext,
  STUDENT_CONTACT_SLA_DAYS,
} from '../utils/internBulkPatientReferralDisplay'

const STATE_HINTS = {
  student_patient_log:
    'برای هر بیمار تیک «صحبت انجام شد» را بزنید و نتیجهٔ تماس را بنویسید. پس از تکمیل همهٔ ردیف‌ها، فرم را ثبت و دکمهٔ ادامه را بزنید.',
}

/**
 * راهنمای دانشجو — فرایند ۷۲، مرحله student_patient_log.
 */
export default function StudentInternBulkPatientReferralPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const ref = useMemo(() => resolveReferralContext(ctx), [ctx])
  const slaInfo = useMemo(() => computeStudentContactSla(ctx), [ctx])

  if (
    !active
    || !detail
    || detail.process_code !== 'intern_bulk_patient_referral'
    || currentState !== 'student_patient_log'
  ) {
    return null
  }

  return (
    <div
      className="card"
      data-testid="student-intern-bulk-referral-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">ارجاع بیماران انترن (فرایند ۷۲)</h3>
        {!compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ReferralFlowStepper currentState={currentState} compact={compact} />

        <SlaBanner
          slaInfo={slaInfo}
          title={`مهلت ثبت تماس با بیماران (${STUDENT_CONTACT_SLA_DAYS.toLocaleString('fa-IR')} روز)`}
          fallbackText="پس از ثبت شرایط ارجاع، حداکثر ۱۵ روز برای تماس با همهٔ بیماران و ثبت توضیحات فرصت دارید."
        />

        <div
          data-testid="student-referral-hint"
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
          {STATE_HINTS.student_patient_log}
        </div>

        {ref.referralConditions && (
          <div
            style={{
              marginBottom: '0.75rem',
              padding: '0.65rem 0.85rem',
              borderRadius: '8px',
              background: '#f8fafc',
              fontSize: '0.82rem',
              lineHeight: 1.65,
            }}
          >
            <strong>شرایط ارجاع (کمیته نظارت):</strong>
            <div style={{ marginTop: '0.35rem', whiteSpace: 'pre-wrap' }}>{ref.referralConditions}</div>
          </div>
        )}

        <PatientRowsSummary rows={ref.patientRows} testId="student-referral-patient-list" />
      </div>
    </div>
  )
}
