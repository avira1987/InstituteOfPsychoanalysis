/** نمایش مشترک فرایند ۷۲ — ارجاع کلیه بیماران انترن */

import React from 'react'
import { computeSlaRemaining } from './earlyTerminationChainDisplay'

export const STUDENT_CONTACT_SLA_DAYS = 15
export const COORDINATION_SLA_DAYS = 3

export const REFERRAL_FLOW_STEPS = [
  { key: 'supervision', label: 'جلسه نظارت', states: ['supervision_start', 'referral_conditions_set'] },
  { key: 'student', label: 'تماس دانشجو', states: ['student_patient_log'] },
  { key: 'therapy', label: 'کمیته درمان', states: ['general_therapy_committee_review'] },
  { key: 'coordination', label: 'هماهنگی', states: ['coordination_followup'] },
  { key: 'done', label: 'پایان', states: ['completed'] },
]

export const REFERRAL_STATE_LABELS = {
  supervision_start: 'ثبت جلسه و شرایط ارجاع',
  referral_conditions_set: 'همگام‌سازی پورتال',
  student_patient_log: 'تماس با بیماران',
  general_therapy_committee_review: 'تکمیل کمیته درمان عموم',
  coordination_followup: 'پیگیری نهایی',
  completed: 'پایان فرایند',
}

export function labelReferralState(state) {
  if (!state) return '—'
  return REFERRAL_STATE_LABELS[state] || state
}

export function activeReferralStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'completed') return REFERRAL_FLOW_STEPS.length - 1
  const idx = REFERRAL_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function normalizeReferralRows(raw) {
  if (!Array.isArray(raw)) return []
  return raw
    .filter((r) => r && typeof r === 'object')
    .map((row, i) => ({
      row_id: String(row.row_id || `row-${i + 1}`),
      patient_name: String(row.patient_name || '').trim(),
      patient_phone: String(row.patient_phone || '').trim(),
      contacted: Boolean(row.contacted),
      contact_notes: String(row.contact_notes || '').trim(),
      committee_contacted: Boolean(row.committee_contacted),
      referral_notes: String(row.referral_notes || '').trim(),
      replacement_therapist: String(row.replacement_therapist || '').trim(),
      followup_done: Boolean(row.followup_done),
    }))
    .filter((r) => r.patient_name)
}

export function resolveReferralContext(ctx = {}) {
  const rows = normalizeReferralRows(ctx.patient_referral_rows)
  return {
    meetingDatetime: ctx.meeting_datetime || null,
    meetingHeld: ctx.meeting_held,
    referralConditions: String(ctx.referral_conditions || '').trim(),
    conditionsSetAt: ctx.referral_conditions_set_at || null,
    studentLogEnteredAt: ctx.student_patient_log_entered_at || null,
    committeeEnteredAt: ctx.general_therapy_committee_review_entered_at || null,
    coordinationEnteredAt: ctx.coordination_followup_entered_at || null,
    patientRows: rows,
    patientCount: rows.length,
  }
}

export function computeStudentContactSla(ctx = {}) {
  const ref = resolveReferralContext(ctx)
  return computeSlaRemaining(
    {
      ...ctx,
      student_patient_log_entered_at: ref.studentLogEnteredAt || ref.conditionsSetAt,
    },
    STUDENT_CONTACT_SLA_DAYS,
    'student_patient_log_entered_at',
  )
}

export function computeCoordinationSla(ctx = {}) {
  const ref = resolveReferralContext(ctx)
  return computeSlaRemaining(
    { ...ctx, coordination_followup_entered_at: ref.coordinationEnteredAt },
    COORDINATION_SLA_DAYS,
    'coordination_followup_entered_at',
  )
}

export function ReferralFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeReferralStepIndex(currentState)
  return (
    <div
      data-testid="intern-bulk-referral-stepper"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.35rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {REFERRAL_FLOW_STEPS.map((step, idx) => {
        const done = idx < activeIdx
        const current = idx === activeIdx
        const tone = done ? '#16a34a' : current ? '#d97706' : '#94a3b8'
        const bg = done ? '#ecfdf5' : current ? '#fffbeb' : '#f8fafc'
        return (
          <div
            key={step.key}
            data-testid={`referral-step-${step.key}`}
            style={{
              flex: compact ? '1 1 45%' : '1 1 8rem',
              minWidth: compact ? '7rem' : '8rem',
              padding: compact ? '0.45rem 0.55rem' : '0.55rem 0.7rem',
              borderRadius: '8px',
              background: bg,
              borderRight: `3px solid ${tone}`,
              fontSize: compact ? '0.74rem' : '0.8rem',
            }}
          >
            <div style={{ fontWeight: 700, color: tone }}>{step.label}</div>
            {current && <div style={{ fontSize: '0.72rem', color: '#64748b' }}>← مرحلهٔ فعلی</div>}
            {done && <div style={{ fontSize: '0.72rem', color: '#64748b' }}>✓</div>}
          </div>
        )
      })}
    </div>
  )
}

export function PatientRowsSummary({ rows = [], testId = 'referral-patient-summary' }) {
  if (!rows.length) {
    return (
      <p className="muted" style={{ fontSize: '0.82rem', margin: 0 }}>
        هنوز بیماری در لیست ثبت نشده است.
      </p>
    )
  }
  return (
    <div data-testid={testId} style={{ fontSize: '0.82rem', lineHeight: 1.65 }}>
      <strong>
        {rows.length.toLocaleString('fa-IR')}
        {' '}
        بیمار
      </strong>
      <ul style={{ margin: '0.35rem 0 0', paddingRight: '1.1rem' }}>
        {rows.map((r) => (
          <li key={r.row_id}>
            {r.patient_name}
            {r.patient_phone ? ` — ${r.patient_phone}` : ''}
          </li>
        ))}
      </ul>
    </div>
  )
}
