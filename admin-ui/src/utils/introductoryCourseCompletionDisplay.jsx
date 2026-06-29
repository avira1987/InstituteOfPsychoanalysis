/** نمایش مشترک زنجیره «خاتمه دوره آشنایی» — فرایند ۳۴. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

/** مراحل اصلی (milestone) فرایند خاتمه دوره آشنایی. */
export const INTRO_COMPLETION_FLOW_STEPS = [
  {
    key: 'eligibility',
    label: 'احراز پاس شدن ۱۰ درس',
    states: ['all_courses_passed'],
  },
  {
    key: 'invitation',
    label: 'دعوت به دوره جامع',
    states: ['invitation_sent'],
  },
  {
    key: 'certificate',
    label: 'تولید و بررسی گواهی',
    states: ['certificate_draft_generated', 'certificate_review'],
  },
  {
    key: 'complete',
    label: 'صدور گواهی نهایی',
    states: ['certificate_approved', 'process_complete'],
  },
]

/** برچسب فارسی هر وضعیت فرایند ۳۴. */
export const INTRO_COMPLETION_STATE_LABELS = {
  all_courses_passed: 'قبولی در تمام دروس دوره آشنایی',
  invitation_sent: 'ارسال دعوتنامه ثبت‌نام دوره جامع',
  certificate_draft_generated: 'پیش‌نویس گواهی تولید شده',
  certificate_review: 'بررسی و تایید کمیته نظارت',
  certificate_approved: 'گواهی تایید و در پورتال بارگذاری شده',
  process_complete: 'فرایند تکمیل شد',
}

const CERTIFICATE_READY_STATES = new Set(['certificate_approved', 'process_complete'])

const INVITATION_REMINDER_STATES = new Set([
  'invitation_sent',
  'certificate_draft_generated',
  'certificate_review',
  'certificate_approved',
  'process_complete',
])

const SYSTEM_WAIT_STATES = new Set([
  'all_courses_passed',
  'invitation_sent',
  'certificate_draft_generated',
  'certificate_approved',
])

const HOURS_PER_UNIT = 13.5

export function labelIntroCompletionState(state) {
  if (!state) return '—'
  return INTRO_COMPLETION_STATE_LABELS[state] || state
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

function latestCertificateDoc(documents = []) {
  const certs = documents.filter((d) => d?.type === 'certificate')
  return certs.length > 0 ? certs[certs.length - 1] : null
}

export function activeIntroCompletionStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'process_complete') return INTRO_COMPLETION_FLOW_STEPS.length - 1
  const idx = INTRO_COMPLETION_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function hasCertificateReady(state, extraData = {}) {
  if (CERTIFICATE_READY_STATES.has(state)) return true
  const doc = latestCertificateDoc(extraData?.documents || [])
  return Boolean(doc?.portal_visible && doc?.signed)
}

export function showComprehensiveInvitationReminder(state) {
  return INVITATION_REMINDER_STATES.has(state)
}

export function isSystemWaitState(state) {
  return SYSTEM_WAIT_STATES.has(state)
}

export function resolveCompletionContext(ctx = {}, extraData = {}) {
  const documents = Array.isArray(extraData?.documents) ? extraData.documents : []
  const cert = latestCertificateDoc(documents)
  const lms = extraData?.lms || {}

  const totalUnitsRaw = ctx.total_units ?? ctx.totalUnits ?? lms.total_units ?? lms.intro_units
  const totalUnits = totalUnitsRaw != null && totalUnitsRaw !== '' ? Number(totalUnitsRaw) : null
  const totalHoursRaw = ctx.total_hours ?? ctx.totalHours ?? lms.total_hours
  const totalHours = totalHoursRaw != null && totalHoursRaw !== ''
    ? Number(totalHoursRaw)
    : (Number.isFinite(totalUnits) ? totalUnits * HOURS_PER_UNIT : null)

  return {
    comprehensiveDeadline:
      ctx.deadline_date
      ?? ctx.comprehensive_registration_deadline
      ?? ctx.comprehensive_deadline
      ?? extraData?.institute_calendar?.comprehensive_registration_deadline
      ?? null,
    totalUnits: Number.isFinite(totalUnits) ? totalUnits : null,
    totalHours: Number.isFinite(totalHours) ? totalHours : null,
    completionDate: ctx.completion_date ?? ctx.completionDate ?? null,
    certificateDoc: cert,
    certificateReady: hasCertificateReady(ctx.current_state, extraData) || Boolean(cert?.portal_visible && cert?.signed),
    certificateDraftPending: Boolean(cert && !cert.signed),
    certificateBodyFa: cert?.body_fa ?? ctx.certificate_text_fa ?? null,
  }
}

export function IntroCompletionFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeIntroCompletionStepIndex(currentState)
  const completed = currentState === 'process_complete'

  return (
    <div
      data-testid="intro-completion-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {INTRO_COMPLETION_FLOW_STEPS.map((step, i) => {
        const done = completed ? true : i < activeIdx
        const current = !completed && i === activeIdx
        const tone = done ? '#16a34a' : current ? '#0d9488' : '#94a3b8'
        const bg = done ? '#f0fdf4' : current ? '#f0fdfa' : '#f8fafc'
        return (
          <div
            key={step.key}
            style={{
              padding: compact ? '0.5rem 0.6rem' : '0.55rem 0.65rem',
              borderRadius: '8px',
              background: bg,
              borderRight: `3px solid ${tone}`,
              fontSize: compact ? '0.74rem' : '0.76rem',
              lineHeight: 1.55,
              color: done ? '#14532d' : current ? '#134e4a' : '#64748b',
            }}
          >
            <div style={{ fontWeight: 800, marginBottom: '0.15rem' }}>
              {i + 1}
              .
              {' '}
              {step.label}
            </div>
            {current && <div style={{ fontSize: '0.72rem' }}>← مرحلهٔ فعلی</div>}
            {completed && i === INTRO_COMPLETION_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
