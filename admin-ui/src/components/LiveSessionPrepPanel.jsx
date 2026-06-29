import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  LiveSessionPrepFlowStepper,
  PatientSummaryTiles,
  classLabelForProcess,
  isLiveSessionPrepProcess,
  processTitleFa,
  resolvePatientReferralContext,
  resolveScheduleContext,
} from '../utils/liveSessionPrepDisplay'

const COORDINATION_STAKEHOLDERS = (classLabel) => [
  'بیمار متقاضی درمان پشت آینه',
  'درمانگر مربوطه',
  `مدرس ${classLabel}`,
  `برنامه کلاسی تمامی دانشجویان ${classLabel}`,
]

/**
 * راهنمای فرایندهای ۶۶ و ۶۸ — مقدمات جلسات زنده.
 */
export default function LiveSessionPrepPanel({
  detail = null,
  user = null,
  active = true,
  compact = false,
}) {
  const processCode = detail?.process_code || null
  const currentState = detail?.current_state || null
  const ctx = detail?.context_data || {}

  const patient = useMemo(() => resolvePatientReferralContext(ctx), [ctx])
  const schedule = useMemo(() => resolveScheduleContext(ctx), [ctx])
  const classLabel = classLabelForProcess(processCode)

  if (!active || !detail || !isLiveSessionPrepProcess(processCode)) {
    return null
  }

  const isReferral = currentState === 'patient_referral'
  const isCoordination = currentState === 'coordination_pending'
  const isScheduled = currentState === 'session_scheduled'
  const isClosed = currentState === 'coordination_closed'
  const stakeholders = COORDINATION_STAKEHOLDERS(classLabel)

  return (
    <div
      data-testid="live-session-prep-panel"
      style={{
        padding: compact ? '0.75rem' : '1rem 1.25rem',
        marginBottom: compact ? '0.75rem' : '1.25rem',
        background: isClosed ? '#f8fafc' : '#fffbeb',
        borderRadius: '10px',
        borderRight: `4px solid ${isClosed ? '#64748b' : '#d97706'}`,
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.35rem', color: isClosed ? '#334155' : '#92400e' }}>
        {processTitleFa(processCode)}
      </h4>
      {!compact && (
        <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '0 0 0.75rem' }}>
          وضعیت:
          {' '}
          <strong>{labelState(currentState)}</strong>
        </p>
      )}

      <LiveSessionPrepFlowStepper currentState={currentState} compact={compact} />

      {isReferral && (
        <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.5rem', color: '#334155' }}>
          اطلاعات پایهٔ بیمار متقاضی «درمان پشت آینه» را در فرم زیر ثبت کنید؛ سپس دکمهٔ
          {' '}
          <code style={{ fontSize: '0.8rem' }}>referral_submitted</code>
          {' '}
          را بزنید تا پرونده به مسئول هماهنگی‌های درمان و آموزش ارجاع شود.
        </p>
      )}

      {isCoordination && (
        <>
          <PatientSummaryTiles patient={patient} compact={compact} />
          <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.65rem', color: '#334155' }}>
            برای یافتن «روز و ساعت مشترک»، هماهنگی بیرون‌سیستمی با این ۴ رکن لازم است:
          </p>
          <ol style={{ fontSize: '0.82rem', lineHeight: 1.75, margin: '0 0 0.75rem', paddingRight: '1.25rem', color: '#334155' }}>
            {stakeholders.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
          <div
            style={{
              padding: '0.65rem 0.85rem',
              marginBottom: '0.75rem',
              background: '#eff6ff',
              borderRadius: '8px',
              border: '1px solid #bfdbfe',
              fontSize: '0.8rem',
              lineHeight: 1.65,
              color: '#1e40af',
            }}
          >
            پس از توافق: فرم زمان‌بندی را ذخیره کنید، سپس «ثبت زمان در LMS» را بزنید.
            پیامک فقط به مدرس، کمک‌مدرس و دانشجویان کلاس ارسال می‌شود —
            <strong> هیچ پیامکی به بیمار ارسال نمی‌شود.</strong>
          </div>
          <p style={{ fontSize: '0.82rem', lineHeight: 1.65, margin: 0, color: '#64748b' }}>
            اگر زمان مشترک پیدا نشد، «وقت خاصی هماهنگ نشد» را بزنید تا پرونده مختومه شود.
          </p>
        </>
      )}

      {isScheduled && (
        <div
          data-testid="live-session-prep-scheduled-summary"
          style={{
            padding: '0.75rem',
            background: '#ecfdf5',
            borderRadius: '8px',
            border: '1px solid #86efac',
            fontSize: '0.85rem',
            lineHeight: 1.7,
            color: '#166534',
          }}
        >
          <strong>جلسه ثبت شد.</strong>
          <br />
          زمان:
          {' '}
          {schedule.sessionLabel}
          <br />
          مدرس:
          {' '}
          {schedule.instructorName}
          {' '}
          — درمانگر:
          {' '}
          {schedule.therapistName}
        </div>
      )}

      {isClosed && (
        <div
          data-testid="live-session-prep-closed-summary"
          style={{
            padding: '0.75rem',
            background: '#f1f5f9',
            borderRadius: '8px',
            border: '1px solid #cbd5e1',
            fontSize: '0.85rem',
            lineHeight: 1.7,
            color: '#475569',
          }}
        >
          <strong>پرونده هماهنگی مختومه شد.</strong>
          {patient.fullName !== '—' && (
            <>
              <br />
              بیمار:
              {' '}
              {patient.fullName}
            </>
          )}
        </div>
      )}

      {user?.role && user.role !== 'therapy_education_coordinator' && user.role !== 'admission_officer'
        && user.role !== 'admissions_officer' && user.role !== 'admin' && isCoordination && (
        <p className="muted" style={{ margin: '0.75rem 0 0', fontSize: '0.78rem' }}>
          این مرحله معمولاً بر عهدهٔ مسئول هماهنگی‌های آموزش درمان است.
        </p>
      )}
    </div>
  )
}
