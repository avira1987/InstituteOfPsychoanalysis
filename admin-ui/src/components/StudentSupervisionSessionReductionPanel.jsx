import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  ELIGIBILITY_BLOCKED_MESSAGE_FA,
  SUPERVISION_REDUCTION_PATH_A_STEPS,
  SUPERVISION_REDUCTION_PATH_B_STEPS,
  SupervisionReductionFlowStepper,
  StructurePreviewChip,
  ThresholdRow,
  buildThresholdRows,
  normalizeSelectedSessions,
  parseWeeklyCount,
  resolveFrequencyStructure,
  resolveSupervisorRejectionNote,
} from '../utils/supervisionSessionReductionDisplay'

const PROCESS_TITLE_FA =
  'درخواست کاهش جلسات هفتگی سوپرویژن (فرایند ۲۳)'

const STATE_HINTS = {
  initiated: {
    student: 'دکمهٔ «ادامه و ثبت مرحله» را بزنید. اگر ۲ جلسه یا بیشتر در هفته دارید، جلسات مازاد را حذف می‌کنید؛ اگر ۱ جلسه دارید، مسیر کاهش تواتر (با احراز ساعات) بررسی می‌شود.',
    supervisor: 'دانشجو در حال شروع درخواست کاهش جلسات سوپرویژن است.',
  },
  session_selection: {
    student: 'جلسات سوپرویژنی که می‌خواهید حذف کنید را در فرم تیک بزنید؛ حداقل یک جلسه در هفته باید باقی بماند.',
    supervisor: 'دانشجو در حال انتخاب جلسات برای حذف است.',
  },
  structure_selection: {
    student: 'ابتدا با سوپروایزر هماهنگ کنید؛ سپس توالی (۲/۳/۴ هفته یک‌بار)، روز و ساعت را در فرم وارد کنید.',
    supervisor: 'دانشجو در حال ثبت ساختار جدید جلسات است.',
  },
  supervisor_review: {
    student: 'سوپروایزر در حال بررسی درخواست شماست؛ پس از اعلام نتیجه همین صفحه را تازه کنید.',
    supervisor: 'درخواست کاهش تواتر را ببینید؛ در صورت موافقت تأیید کنید، در غیر این صورت رد با توضیح.',
  },
  multi_reduction_completed: {
    student: 'کاهش جلسات هفتگی سوپرویژن اعمال شد. جزئیات از طریق پیامک اطلاع‌رسانی می‌شود.',
    supervisor: 'دانشجو جلسات مازاد سوپرویژن را حذف کرد.',
  },
  frequency_reduction_completed: {
    student: 'درخواست کاهش تواتر تأیید شد و ساختار جدید در برنامهٔ شما ثبت می‌شود.',
    supervisor: 'کاهش تواتر جلسات سوپرویژن تأیید و ثبت شد.',
  },
  eligibility_blocked: {
    student: ELIGIBILITY_BLOCKED_MESSAGE_FA,
    supervisor: 'دانشجو شرایط کاهش تواتر را ندارد.',
  },
}

function StatTile({ label, value, sub, tone = '#7c3aed', bg = '#f5f3ff', testId }) {
  return (
    <div
      data-testid={testId}
      style={{
        padding: '0.75rem 0.85rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: tone }}>{value}</div>
      {sub && <div style={{ fontSize: '0.76rem', color: '#78716c', marginTop: '0.2rem' }}>{sub}</div>}
    </div>
  )
}

/**
 * داشبورد راهنمای «کاهش جلسات هفتگی سوپرویژن» — فرایند ۲۳.
 */
export default function StudentSupervisionSessionReductionPanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
  portalRole = 'student',
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const isSupervisor = portalRole === 'supervisor' || portalRole === 'admin'

  const weeklyCount = useMemo(
    () => parseWeeklyCount(
      ctx.supervision_weekly_sessions
      ?? ctx.weekly_supervision_sessions
      ?? ctx.supervision_weekly_sessions_before,
    ),
    [ctx],
  )

  const upcomingSessions = Array.isArray(ctx.upcoming_supervision_sessions)
    ? ctx.upcoming_supervision_sessions
    : []

  const thresholdRows = useMemo(() => buildThresholdRows(ctx), [ctx])
  const evaluableThresholds = thresholdRows.filter((r) => r.threshold > 0)
  const allThresholdsMet = evaluableThresholds.length > 0
    && evaluableThresholds.every((r) => r.hours >= r.threshold)

  const selectedIds = normalizeSelectedSessions(stepFormValues?.selected_sessions)
  const remainingAfter = weeklyCount != null && selectedIds.length > 0
    ? weeklyCount - selectedIds.length
    : null
  const wouldRemoveAll = weeklyCount != null && selectedIds.length >= weeklyCount

  const structure = useMemo(
    () => resolveFrequencyStructure(ctx, stepFormValues),
    [ctx, stepFormValues],
  )
  const rejectionNote = useMemo(() => resolveSupervisorRejectionNote(ctx), [ctx])

  const isMultiSessionPath = weeklyCount != null && weeklyCount >= 2
  const isFrequencyPath = weeklyCount != null && weeklyCount < 2

  if (!active || !detail || detail.process_code !== 'supervision_session_reduction') {
    return null
  }

  const hint = STATE_HINTS[currentState]?.[isSupervisor ? 'supervisor' : 'student']
  const isTerminal = [
    'multi_reduction_completed',
    'frequency_reduction_completed',
    'eligibility_blocked',
  ].includes(currentState)

  const flowSteps = isMultiSessionPath
    || currentState === 'session_selection'
    || currentState === 'multi_reduction_completed'
    ? SUPERVISION_REDUCTION_PATH_B_STEPS
    : SUPERVISION_REDUCTION_PATH_A_STEPS

  return (
    <div className="card" data-testid="student-supervision-session-reduction-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        {!isTerminal && currentState !== 'initiated' && (
          <SupervisionReductionFlowStepper
            steps={flowSteps}
            currentState={currentState}
            compact={compact}
            testId={`supervision-reduction-flow-${isMultiSessionPath ? 'multi' : 'frequency'}`}
          />
        )}

        {hint && !compact && (
          <div
            data-testid="supervision-reduction-state-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: currentState === 'eligibility_blocked' ? '#fef2f2' : '#eff6ff',
              borderRight: `4px solid ${currentState === 'eligibility_blocked' ? '#dc2626' : '#2563eb'}`,
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: currentState === 'eligibility_blocked' ? '#991b1b' : '#1e3a8a',
            }}
          >
            {hint}
          </div>
        )}

        {currentState === 'initiated' && weeklyCount != null && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '0.65rem',
              marginBottom: '0.85rem',
            }}
          >
            <StatTile
              testId="supervision-reduction-weekly-count"
              label="برنامهٔ فعلی"
              value={`${weeklyCount.toLocaleString('fa-IR')} جلسه در هفته`}
              sub={isMultiSessionPath ? 'مسیر حذف جلسات مازاد' : 'مسیر کاهش تواتر (یک جلسه در هفته)'}
              tone={isMultiSessionPath ? '#7c3aed' : '#0d9488'}
              bg={isMultiSessionPath ? '#f5f3ff' : '#f0fdfa'}
            />
          </div>
        )}

        {isFrequencyPath && thresholdRows.length > 0 && currentState !== 'eligibility_blocked' && (
          <div
            data-testid="supervision-reduction-thresholds"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #f5f3ff 0%, #f8fafc 100%)',
              borderRight: '4px solid #7c3aed',
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.5rem',
              marginBottom: '0.55rem',
            }}
            >
              <span style={{ fontWeight: 700, color: '#5b21b6', fontSize: '0.88rem' }}>
                وضعیت ساعات آموزشی (۱۵۰ / ۲۵۰ / ۷۵۰)
              </span>
              {evaluableThresholds.length > 0 && (
                <span
                  data-testid="supervision-reduction-threshold-status"
                  style={{
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    padding: '0.15rem 0.6rem',
                    borderRadius: '999px',
                    background: allThresholdsMet ? '#dcfce7' : '#fef3c7',
                    color: allThresholdsMet ? '#166534' : '#92400e',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {allThresholdsMet ? 'همهٔ حدنصاب‌ها کامل است' : 'حدنصاب‌ها هنوز کامل نیست'}
                </span>
              )}
            </div>
            <div style={{ display: 'grid', gap: '0.6rem' }}>
              {thresholdRows.map((row) => (
                <ThresholdRow key={row.key} row={row} />
              ))}
            </div>
          </div>
        )}

        {currentState === 'session_selection' && weeklyCount != null && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '0.65rem',
              marginBottom: '0.85rem',
            }}
          >
            <StatTile
              testId="supervision-reduction-current-schedule"
              label="جلسات فعلی در هفته"
              value={weeklyCount.toLocaleString('fa-IR')}
              sub={`${upcomingSessions.length.toLocaleString('fa-IR')} جلسه در لیست`}
              tone="#7c3aed"
            />
            {remainingAfter != null && (
              <StatTile
                testId="supervision-reduction-remaining-preview"
                label="پس از حذف (پیش‌نمایش)"
                value={remainingAfter.toLocaleString('fa-IR')}
                sub={`${selectedIds.length.toLocaleString('fa-IR')} جلسه برای حذف انتخاب شده`}
                tone={remainingAfter >= 1 ? '#16a34a' : '#dc2626'}
                bg={remainingAfter >= 1 ? '#f0fdf4' : '#fef2f2'}
              />
            )}
          </div>
        )}

        {currentState === 'session_selection' && wouldRemoveAll && (
          <div
            role="alert"
            data-testid="supervision-reduction-remove-all-warning"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#991b1b',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>حداقل یک جلسه باید باقی بماند</strong>
            نمی‌توانید تمام جلسات هفتگی سوپرویژن را حذف کنید. تعداد انتخاب‌شده را کاهش دهید.
          </div>
        )}

        {currentState === 'structure_selection' && !isSupervisor && (
          <div
            data-testid="supervision-reduction-coordination-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fefce8',
              borderRight: '4px solid #ca8a04',
              fontSize: '0.84rem',
              lineHeight: 1.75,
              color: '#713f12',
            }}
          >
            دانشجوی گرامی، لطفاً ابتدا با سوپروایزر خود روز و ساعت جلسات سوپرویژن را هماهنگ کنید
            و سپس فرم زیر را تکمیل نمایید.
          </div>
        )}

        {(currentState === 'structure_selection' || currentState === 'supervisor_review') && (
          <div style={{ marginBottom: '0.85rem' }}>
            <StructurePreviewChip structure={structure} />
          </div>
        )}

        {currentState === 'structure_selection' && rejectionNote && (
          <div
            data-testid="supervision-reduction-supervisor-rejection-note"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#78350f',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>توضیح سوپروایزر</strong>
            {rejectionNote}
          </div>
        )}

        {currentState === 'eligibility_blocked' && (
          <div
            role="alert"
            data-testid="supervision-reduction-eligibility-blocked"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#991b1b',
            }}
          >
            {ELIGIBILITY_BLOCKED_MESSAGE_FA}
          </div>
        )}

        {isTerminal && currentState !== 'eligibility_blocked' && (
          <div
            data-testid="supervision-reduction-terminal-success"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#14532d',
            }}
          >
            {STATE_HINTS[currentState]?.[isSupervisor ? 'supervisor' : 'student']}
          </div>
        )}

        {upcomingSessions.length === 0 && currentState === 'session_selection' && (
          <p
            style={{
              margin: '0.85rem 0 0',
              fontSize: '0.8rem',
              color: '#b45309',
              lineHeight: 1.6,
            }}
          >
            جلسهٔ هفتگی سوپرویژنی در لیست نیست؛ در صورت نیاز با پشتیبانی تماس بگیرید.
          </p>
        )}
      </div>
    </div>
  )
}
