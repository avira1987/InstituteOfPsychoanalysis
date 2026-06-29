/** نمایش مشترک فرایند ۷۰ — درخواست ثبت دفاع پایان‌نامه */

import React from 'react'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'
import { formatShamsiTehran } from './shamsiDateTime'
import { STATE_LABELS_FA } from './processMetadataLabels'

export const REVISION_SLA_DAYS = 14

export const ELIGIBILITY_ERROR_FA =
  'دانشجوی گرامی، بر اساس بررسی خودکار پرونده شما در اتوماسیون، شروط پیش‌نیاز جهت ثبت درخواست دفاع تکمیل نگردیده است. لطفاً جهت مشاهده جزئیات نقص پرونده به کارنامه خود مراجعه فرمایید.\n'
  + 'شروط: ۱) ۶۷ واحد با معدل B؛ ۲) ۷۵۰ ساعت تجربه بالینی؛ ۳) ۱۵۰ ساعت سوپرویژن فردی؛ ۴) ۲۵۰ ساعت درمان آموزشی.'

export const THESIS_DEFENSE_FLOW_STEPS = [
  {
    key: 'eligibility',
    label: 'غربالگری',
    states: ['eligibility_check', 'conditions_not_met', 'report_revision'],
  },
  {
    key: 'committees',
    label: 'کمیته‌ها',
    states: [
      'progress_committee_review',
      'supervision_committee_review',
      'defense_permit_denied',
      'report_rejected',
    ],
  },
  {
    key: 'defense',
    label: 'دفاع',
    states: [
      'thesis_upload',
      'education_committee_scheduling',
      'first_defense_held',
    ],
  },
  {
    key: 'revision',
    label: 'اصلاح / نتیجه',
    states: [
      'revision_required',
      'revision_upload',
      'second_defense_held',
      'revision_delay_violation',
      'defense_passed',
      'defense_failed',
    ],
  },
]

const TERMINAL_STATES = new Set([
  'conditions_not_met',
  'report_rejected',
  'defense_permit_denied',
  'revision_delay_violation',
  'defense_passed',
  'defense_failed',
])

export function labelThesisDefenseState(state) {
  if (!state) return '—'
  return STATE_LABELS_FA.thesis_defense_request?.[state] || state
}

export function activeThesisDefenseStepIndex(currentState) {
  if (!currentState) return 0
  if (TERMINAL_STATES.has(currentState)) {
    if (['defense_passed', 'defense_failed'].includes(currentState)) {
      return THESIS_DEFENSE_FLOW_STEPS.length - 1
    }
    if (currentState === 'conditions_not_met') return 0
    if (['report_rejected', 'defense_permit_denied'].includes(currentState)) return 1
    return THESIS_DEFENSE_FLOW_STEPS.length - 1
  }
  const idx = THESIS_DEFENSE_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function resolveEligibilityContext(ctx = {}, extraData = {}) {
  const ex = extraData && typeof extraData === 'object' ? extraData : {}
  const lms = ex.lms && typeof ex.lms === 'object' ? ex.lms : {}
  const num = (v, fallback = 0) => {
    const n = Number(v)
    return Number.isFinite(n) ? n : fallback
  }
  const totalUnits = num(ctx.total_units ?? ex.total_units ?? lms.total_units)
  const cumulativeGpa = num(ctx.cumulative_gpa ?? ex.cumulative_gpa ?? lms.cumulative_gpa)
  const therapyHours = num(ctx.therapy_hours ?? ctx.therapy_hours_2x)
  const clinicalHours = num(ctx.clinical_hours)
  const supervisionHours = num(ctx.supervision_hours)
  const unitsRequired = num(ctx.units_required, 67)
  const therapyThreshold = num(ctx.therapy_threshold, 250)
  const clinicalThreshold = num(ctx.clinical_threshold, 750)
  const supervisionThreshold = num(ctx.supervision_threshold, 150)

  const units67BMet = ctx.units_67_b_met != null
    ? Boolean(ctx.units_67_b_met)
    : totalUnits >= unitsRequired && cumulativeGpa >= num(ctx.gpa_min_b, 14)
  const clinical750Met = ctx.clinical_750_met != null
    ? Boolean(ctx.clinical_750_met)
    : clinicalHours >= clinicalThreshold
  const supervision150Met = ctx.supervision_150_met != null
    ? Boolean(ctx.supervision_150_met)
    : supervisionHours >= supervisionThreshold
  const therapy250Met = ctx.therapy_250_met != null
    ? Boolean(ctx.therapy_250_met)
    : therapyHours >= therapyThreshold
  const allMet = ctx.all_conditions_met != null
    ? Boolean(ctx.all_conditions_met)
    : units67BMet && clinical750Met && supervision150Met && therapy250Met

  return {
    totalUnits,
    cumulativeGpa,
    therapyHours,
    clinicalHours,
    supervisionHours,
    unitsRequired,
    therapyThreshold,
    clinicalThreshold,
    supervisionThreshold,
    units67BMet,
    clinical750Met,
    supervision150Met,
    therapy250Met,
    allConditionsMet: allMet,
    previewFa: ctx.thesis_defense_eligibility_preview_fa || null,
  }
}

function parseDefenseDate(defenseDate) {
  if (!defenseDate) return null
  const s = String(defenseDate).slice(0, 10)
  const t = Date.parse(s)
  return Number.isNaN(t) ? null : new Date(t)
}

export function shouldRevealReviewers(defenseDate) {
  const d = parseDefenseDate(defenseDate)
  if (!d) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  d.setHours(0, 0, 0, 0)
  return d.getTime() <= today.getTime()
}

export function resolveDefenseSchedule(ctx = {}, options = {}) {
  const hideReviewers = options.hideReviewers !== false
  const defenseDate = ctx.defense_date ?? null
  const defenseTime = ctx.defense_time ?? null
  const reveal = !hideReviewers || shouldRevealReviewers(defenseDate)
  return {
    defenseDate,
    defenseTime,
    reviewer1Name: reveal ? (ctx.reviewer_1_name || ctx.reviewer_1_label_fa) : null,
    reviewer2Name: reveal ? (ctx.reviewer_2_name || ctx.reviewer_2_label_fa) : null,
    reviewersHidden: hideReviewers && !reveal,
    isSecondDefense: Boolean(ctx.second_defense_date || ctx.defense_type === 'دفاع مجدد'),
  }
}

export function computeRevisionSlaRemaining(ctx = {}) {
  return computeSlaRemaining(ctx, REVISION_SLA_DAYS, 'revision_required_entered_at')
    || computeSlaRemaining(ctx, REVISION_SLA_DAYS, 'first_defense_date')
}

export function resolveUploadedFiles(ctx = {}) {
  return {
    psychoticReport: ctx.psychotic_report_file ?? null,
    thesisFile: ctx.thesis_file ?? null,
    revisedThesisFile: ctx.revised_thesis_file ?? null,
  }
}

export function resolveCommitteeNotes(ctx = {}) {
  return {
    revisionNotes: (ctx.revision_notes || '').trim() || null,
    permitDenialReason: (ctx.permit_denial_reason || '').trim() || null,
    reportRejectionReason: (ctx.report_rejection_reason || ctx.rejection_reason || '').trim() || null,
    studentAlert: (ctx.student_portal_alert_fa || '').trim() || null,
  }
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function ThesisDefenseFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeThesisDefenseStepIndex(currentState)
  const completed = ['defense_passed', 'defense_failed'].includes(currentState)

  return (
    <div
      data-testid="thesis-defense-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(110px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {THESIS_DEFENSE_FLOW_STEPS.map((step, i) => {
        const done = completed ? true : i < activeIdx
        const current = !completed && i === activeIdx
        const tone = done ? '#16a34a' : current ? '#7c3aed' : '#94a3b8'
        const bg = done ? '#f0fdf4' : current ? '#f5f3ff' : '#f8fafc'
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
              color: done ? '#14532d' : current ? '#5b21b6' : '#64748b',
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

function CheckTile({ label, met, detail }) {
  return (
    <div
      style={{
        padding: '0.75rem 0.85rem',
        borderRadius: '10px',
        background: met ? '#f0fdf4' : '#fef2f2',
        borderRight: `4px solid ${met ? '#16a34a' : '#dc2626'}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontSize: '0.92rem', fontWeight: 700, color: met ? '#14532d' : '#991b1b' }}>
        {met ? '✓ احراز شد' : '✗ احراز نشد'}
      </div>
      {detail && (
        <div style={{ fontSize: '0.78rem', color: '#475569', marginTop: '0.25rem' }}>{detail}</div>
      )}
    </div>
  )
}

export function EligibilityChecklistTiles({ eligibility }) {
  if (!eligibility) return null
  const fmt = (v) => (Number.isFinite(v) ? v.toLocaleString('fa-IR', { maximumFractionDigits: 1 }) : '—')
  return (
    <div
      data-testid="thesis-defense-eligibility-tiles"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: '0.65rem',
        marginBottom: '0.85rem',
      }}
    >
      <CheckTile
        label="۶۷ واحد با معدل B"
        met={eligibility.units67BMet}
        detail={`${fmt(eligibility.totalUnits)} واحد — معدل ${fmt(eligibility.cumulativeGpa)}`}
      />
      <CheckTile
        label="۷۵۰ ساعت بالینی"
        met={eligibility.clinical750Met}
        detail={`${fmt(eligibility.clinicalHours)} / ${fmt(eligibility.clinicalThreshold)}`}
      />
      <CheckTile
        label="۱۵۰ ساعت سوپرویژن"
        met={eligibility.supervision150Met}
        detail={`${fmt(eligibility.supervisionHours)} / ${fmt(eligibility.supervisionThreshold)}`}
      />
      <CheckTile
        label="۲۵۰ ساعت درمان"
        met={eligibility.therapy250Met}
        detail={`${fmt(eligibility.therapyHours)} / ${fmt(eligibility.therapyThreshold)}`}
      />
    </div>
  )
}

export function DefenseScheduleChip({ schedule }) {
  if (!schedule?.defenseDate && !schedule?.defenseTime) return null
  return (
    <div
      data-testid="thesis-defense-schedule-chip"
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: '#eff6ff',
        borderRight: '4px solid #2563eb',
        fontSize: '0.86rem',
        lineHeight: 1.75,
        color: '#1e3a8a',
      }}
    >
      <strong>زمان جلسه دفاع:</strong>
      {' '}
      {fmtIsoDate(schedule.defenseDate)}
      {schedule.defenseTime ? ` — ساعت ${schedule.defenseTime}` : ''}
      {schedule.reviewersHidden && (
        <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem', color: '#475569' }}>
          نام داوران تا روز دفاع در پورتال نمایش داده نمی‌شود.
        </p>
      )}
      {schedule.reviewer1Name && (
        <p style={{ margin: '0.35rem 0 0', fontSize: '0.82rem' }}>
          داور اول:
          {' '}
          {schedule.reviewer1Name}
          {schedule.reviewer2Name ? ` — داور دوم: ${schedule.reviewer2Name}` : ''}
        </p>
      )}
    </div>
  )
}

export function RevisionSlaBanner({ ctx, currentState }) {
  if (!['revision_required', 'revision_upload'].includes(currentState)) return null
  const slaInfo = computeRevisionSlaRemaining(ctx)
  if (!slaInfo) return null
  return (
    <SlaBanner
      slaInfo={slaInfo}
      title="مهلت آپلود اصلاحات (۲ هفته پس از دفاع اول)"
    />
  )
}

export function HintBlock({ children, tone = 'info', testId }) {
  const styles = {
    info: { bg: '#eff6ff', border: '#2563eb', color: '#1e3a8a' },
    warn: { bg: '#fffbeb', border: '#d97706', color: '#92400e' },
    error: { bg: '#fef2f2', border: '#dc2626', color: '#991b1b' },
    success: { bg: '#f0fdf4', border: '#16a34a', color: '#14532d' },
  }
  const s = styles[tone] || styles.info
  return (
    <div
      data-testid={testId}
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: s.bg,
        borderRight: `4px solid ${s.border}`,
        fontSize: '0.86rem',
        lineHeight: 1.75,
        color: s.color,
        whiteSpace: 'pre-line',
      }}
    >
      {children}
    </div>
  )
}
