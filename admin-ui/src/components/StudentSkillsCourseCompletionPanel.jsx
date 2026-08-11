import React, { useMemo } from 'react'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import {
  PASS_THRESHOLD,
  PROCESS_TITLE_FA,
  STATE_HINTS,
  SkillsFlowStepper,
  SkillsHintBlock,
  SkillsSlaBanner,
  InfoTile,
  isTerminalState,
  labelPassFail,
  labelSkillsState,
  resolveSkillsCompletionContext,
  scoringSummaryLabel,
  variantLabel,
} from '../utils/skillsCourseCompletionDisplay'

const PROC_CODE = 'skills_course_completion'

function resolveSkillsHint(state) {
  if (!state) return 'خاتمه دروس تکنیک تمرین مهارت‌ها — وضعیت پرونده را در همین صفحه دنبال کنید.'
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  return STATE_HINTS[state] || 'خاتمه دروس تکنیک تمرین مهارت‌ها — وضعیت پرونده را در همین صفحه دنبال کنید.'
}

/**
 * داشبورد راهنمای «خاتمه دروس تکنیک: تمرین مهارت‌ها» — فرایند ۶۳ (دانشجو).
 */
export default function StudentSkillsCourseCompletionPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const skillsCtx = useMemo(() => resolveSkillsCompletionContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'skills_course_completion') {
    return null
  }

  const hint = resolveSkillsHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelSkillsState(currentState)) ?? ''
  const isTerminal = isTerminalState(currentState)

  const myRow = (skillsCtx.studentsGrades || []).find(
    (r) => String(r.student_id) === String(detail.student_id),
  ) || {}
  const total = myRow.total_score ?? skillsCtx.totalScore
  const passFail = myRow.pass_fail ?? skillsCtx.passFail
  const incomplete = myRow.incomplete || passFail === 'I'

  return (
    <div className="card" data-testid="student-skills-course-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelSkillsState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <SkillsFlowStepper currentState={currentState} compact={compact} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <InfoTile label="درس" value={skillsCtx.courseName} tone="#0d9488" bg="#f0fdfa" />
          <InfoTile label="نوع" value={variantLabel(skillsCtx.skillsVariant)} tone="#7c3aed" bg="#f5f3ff" />
          {total != null && (
            <InfoTile
              label="نمره نهایی"
              value={`${total.toLocaleString('fa-IR')} — ${passFail || labelPassFail(total, incomplete)}`}
              tone={total >= PASS_THRESHOLD ? '#059669' : '#dc2626'}
              bg={total >= PASS_THRESHOLD ? '#ecfdf5' : '#fef2f2'}
            />
          )}
        </div>

        <SkillsSlaBanner ctx={ctx} startedAt={detail.started_at} currentState={currentState} />

        {hint && (
          <SkillsHintBlock tone={currentState?.includes('delay') ? 'danger' : 'info'}>
            {hint}
          </SkillsHintBlock>
        )}

        <SkillsHintBlock title="بارم‌بندی" tone="info">
          {scoringSummaryLabel(skillsCtx.skillsVariant)}
        </SkillsHintBlock>

        {incomplete && (
          <SkillsHintBlock title="وضعیت Incomplete" tone="warn">
            به‌دلیل غیبت در امتحان عملی یا تستی، نمره نهایی ثبت نشده است. باید درس را دوباره بگذرانید.
            بدون امتحان مجدد.
          </SkillsHintBlock>
        )}

        {!incomplete && isTerminal && passFail === 'FAIL' && (
          <SkillsHintBlock title="مردودی" tone="warn">
            نمره شما کمتر از
            {' '}
            {PASS_THRESHOLD.toLocaleString('fa-IR')}
            {' '}
            است. بدون امتحان مجدد؛ باید درس را دوباره بگذرانید.
          </SkillsHintBlock>
        )}
      </div>
    </div>
  )
}
