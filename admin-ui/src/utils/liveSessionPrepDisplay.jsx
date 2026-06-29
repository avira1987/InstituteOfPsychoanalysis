/** نمایش مشترک فرایندهای ۶۶ و ۶۸ — مقدمات جلسات زنده */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

export const LIVE_SESSION_PREP_PROCESS_CODES = new Set([
  'live_therapy_observation_session_prep',
  'live_supervision_session_prep',
])

export const LIVE_SESSION_PREP_FLOW_STEPS = [
  { key: 'referral', label: 'ارجاع بیمار', states: ['patient_referral'] },
  { key: 'coordination', label: 'هماهنگی زمان', states: ['coordination_pending'] },
  { key: 'scheduled', label: 'ثبت در LMS', states: ['session_scheduled'] },
  { key: 'closed', label: 'مختومه', states: ['coordination_closed'] },
]

const PROCESS_TITLES = {
  live_therapy_observation_session_prep: 'مقدمات برگزاری جلسات مشاهده زنده درمان (فرایند ۶۶)',
  live_supervision_session_prep: 'مقدمات برگزاری جلسات سوپرویژن زنده (فرایند ۶۸)',
}

const PROCESS_NUMBERS = {
  live_therapy_observation_session_prep: 66,
  live_supervision_session_prep: 68,
}

const CLASS_LABEL_BY_PROCESS = {
  live_therapy_observation_session_prep: 'درس مشاهده زنده درمان',
  live_supervision_session_prep: 'درس سوپرویژن زنده',
}

export function isLiveSessionPrepProcess(processCode) {
  return LIVE_SESSION_PREP_PROCESS_CODES.has(processCode)
}

export function processTitleFa(processCode) {
  return PROCESS_TITLES[processCode] || processCode || '—'
}

export function processNumber(processCode) {
  return PROCESS_NUMBERS[processCode] ?? null
}

export function classLabelForProcess(processCode) {
  return CLASS_LABEL_BY_PROCESS[processCode] || 'کلاس'
}

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

export function fmtSessionDateTime(dateVal, timeVal) {
  const datePart = dateVal ? fmtIsoDate(dateVal) : ''
  const timePart = str(timeVal)
  if (datePart && timePart) return `${datePart} — ساعت ${timePart}`
  if (datePart) return datePart
  if (timePart) return `ساعت ${timePart}`
  return '—'
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function resolvePatientReferralContext(ctx = {}) {
  const first = str(ctx.patient_first_name)
  const last = str(ctx.patient_last_name)
  const fullName = [first, last].filter(Boolean).join(' ') || '—'
  return {
    firstName: first,
    lastName: last,
    fullName,
    phone: str(ctx.patient_phone) || '—',
    notes: str(ctx.referral_notes) || str(ctx.notes) || null,
  }
}

export function resolveScheduleContext(ctx = {}) {
  return {
    instructorId: str(ctx.instructor_id) || null,
    instructorName: str(ctx.instructor_name) || str(ctx.instructor_id) || '—',
    therapistId: str(ctx.therapist_id) || null,
    therapistName: str(ctx.therapist_name) || str(ctx.therapist_id) || '—',
    sessionDate: ctx.session_date || null,
    sessionTime: str(ctx.session_time) || null,
    sessionLabel: fmtSessionDateTime(ctx.session_date, ctx.session_time),
  }
}

export function activeLiveSessionPrepStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'session_scheduled') return 2
  if (currentState === 'coordination_closed') return 3
  const idx = LIVE_SESSION_PREP_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function LiveSessionPrepFlowStepper({ currentState, compact = false, testId = 'live-session-prep-stepper' }) {
  const activeIdx = activeLiveSessionPrepStepIndex(currentState)
  const isTerminalSuccess = currentState === 'session_scheduled'
  const isTerminalClosed = currentState === 'coordination_closed'

  return (
    <div
      data-testid={testId}
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.35rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {LIVE_SESSION_PREP_FLOW_STEPS.map((step, idx) => {
        let done = idx < activeIdx
        let current = idx === activeIdx
        if (isTerminalSuccess && idx <= 2) done = true
        if (isTerminalClosed && idx === 3) current = true
        if (isTerminalClosed && idx < 3) done = idx < 2
        const tone = done ? '#16a34a' : current ? '#d97706' : '#94a3b8'
        const bg = done ? '#ecfdf5' : current ? '#fffbeb' : '#f8fafc'
        return (
          <div
            key={step.key}
            data-testid={`live-session-prep-step-${step.key}`}
            style={{
              flex: compact ? '1 1 42%' : '1 1 7rem',
              minWidth: compact ? '6.5rem' : '7rem',
              padding: compact ? '0.45rem 0.55rem' : '0.55rem 0.7rem',
              borderRadius: '8px',
              background: bg,
              borderRight: `3px solid ${tone}`,
              fontSize: compact ? '0.74rem' : '0.8rem',
              fontWeight: current ? 700 : 500,
              color: done ? '#166534' : current ? '#92400e' : '#64748b',
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

export function PatientSummaryTiles({ patient, compact = false }) {
  if (!patient) return null
  const tileStyle = {
    flex: '1 1 10rem',
    padding: compact ? '0.5rem 0.65rem' : '0.6rem 0.75rem',
    background: '#fff',
    borderRadius: '8px',
    border: '1px solid #fde68a',
  }
  return (
    <div
      data-testid="live-session-prep-patient-summary"
      style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}
    >
      <div style={tileStyle}>
        <div style={{ fontSize: '0.72rem', color: '#92400e', marginBottom: '0.2rem' }}>بیمار</div>
        <strong style={{ fontSize: '0.85rem' }}>{patient.fullName}</strong>
      </div>
      <div style={tileStyle}>
        <div style={{ fontSize: '0.72rem', color: '#92400e', marginBottom: '0.2rem' }}>تماس</div>
        <strong style={{ fontSize: '0.85rem' }}>{patient.phone}</strong>
      </div>
      {patient.notes && (
        <div style={{ ...tileStyle, flex: '1 1 100%' }}>
          <div style={{ fontSize: '0.72rem', color: '#92400e', marginBottom: '0.2rem' }}>یادداشت پذیرش</div>
          <span style={{ fontSize: '0.82rem', lineHeight: 1.6 }}>{patient.notes}</span>
        </div>
      )}
    </div>
  )
}
