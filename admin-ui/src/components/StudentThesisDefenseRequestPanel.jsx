import React, { useMemo } from 'react'
import UploadedDocumentsReadonlyGrid from './UploadedDocumentsReadonlyGrid'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import {
  ThesisDefenseFlowStepper,
  EligibilityChecklistTiles,
  DefenseScheduleChip,
  RevisionSlaBanner,
  HintBlock,
  labelThesisDefenseState,
  resolveEligibilityContext,
  resolveDefenseSchedule,
  resolveUploadedFiles,
  resolveCommitteeNotes,
  ELIGIBILITY_ERROR_FA,
} from '../utils/thesisDefenseRequestDisplay'

const PROCESS_TITLE_FA = 'درخواست ثبت دفاع پایان‌نامه (فرایند ۷۰)'
const PROC_CODE = 'thesis_defense_request'

function resolveThesisHint(state) {
  if (!state) return 'مسیر دفاع پایان‌نامه — مراحل را طبق راهنمای این صفحه پیش ببرید.'
  if (state === 'conditions_not_met') return ELIGIBILITY_ERROR_FA
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  return 'مسیر دفاع پایان‌نامه — مراحل را طبق راهنمای این صفحه پیش ببرید.'
}

const FILE_FIELDS = [
  { name: 'psychotic_report_file', label_fa: 'گزارش سایکوتیک', type: 'file_upload' },
  { name: 'thesis_file', label_fa: 'پایان‌نامه', type: 'file_upload' },
  { name: 'revised_thesis_file', label_fa: 'پایان‌نامه اصلاح‌شده', type: 'file_upload' },
]

/**
 * داشبورد راهنمای «درخواست ثبت دفاع پایان‌نامه» — فرایند ۷۰ (دانشجو).
 */
export default function StudentThesisDefenseRequestPanel({
  detail = null,
  extraData = null,
  active = true,
  compact = false,
  onGoToProfile = null,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const eligibility = useMemo(
    () => resolveEligibilityContext(ctx, extraData || {}),
    [ctx, extraData],
  )
  const schedule = useMemo(
    () => resolveDefenseSchedule(ctx, { hideReviewers: true }),
    [ctx],
  )
  const files = useMemo(() => resolveUploadedFiles(ctx), [ctx])
  const notes = useMemo(() => resolveCommitteeNotes(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'thesis_defense_request') {
    return null
  }

  const hint = resolveThesisHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelThesisDefenseState(currentState)) ?? ''
  const isTerminal = [
    'conditions_not_met',
    'report_rejected',
    'defense_permit_denied',
    'revision_delay_violation',
    'defense_passed',
    'defense_failed',
  ].includes(currentState)
  const isSuccess = currentState === 'defense_passed'
  const showEligibility = ['eligibility_check', 'conditions_not_met'].includes(currentState)
  const showFiles = files.psychoticReport || files.thesisFile || files.revisedThesisFile
  const showSchedule = schedule.defenseDate && ![
    'eligibility_check',
    'conditions_not_met',
    'progress_committee_review',
    'report_revision',
    'supervision_committee_review',
    'thesis_upload',
  ].includes(currentState)

  let hintTone = 'info'
  if (currentState === 'conditions_not_met' || currentState === 'defense_failed') hintTone = 'error'
  if (isSuccess) hintTone = 'success'
  if (currentState === 'revision_required') hintTone = 'warn'

  return (
    <div className="card" data-testid="student-thesis-defense-request-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isSuccess ? 'badge-success' : isTerminal ? 'badge-danger' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelThesisDefenseState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ThesisDefenseFlowStepper currentState={currentState} compact={compact} />

        {hint && (
          <HintBlock tone={hintTone} testId="thesis-defense-state-hint">
            {hint}
            {currentState === 'conditions_not_met' && onGoToProfile && (
              <>
                {'\n'}
                <button
                  type="button"
                  className="btn btn-sm btn-outline"
                  style={{ marginTop: '0.5rem' }}
                  onClick={onGoToProfile}
                >
                  مشاهده کارنامه در پروفایل
                </button>
              </>
            )}
          </HintBlock>
        )}

        {showEligibility && (
          <EligibilityChecklistTiles eligibility={eligibility} />
        )}

        <RevisionSlaBanner ctx={ctx} currentState={currentState} />

        {notes.revisionNotes && currentState === 'report_revision' && (
          <HintBlock tone="warn" testId="thesis-defense-revision-notes">
            <strong>توضیحات کمیته پیشرفت:</strong>
            {' '}
            {notes.revisionNotes}
          </HintBlock>
        )}

        {(notes.permitDenialReason || notes.reportRejectionReason || notes.studentAlert) && (
          <HintBlock tone="error" testId="thesis-defense-committee-notes">
            {notes.permitDenialReason && (
              <>
                <strong>علت عدم مجوز:</strong>
                {' '}
                {notes.permitDenialReason}
              </>
            )}
            {notes.reportRejectionReason && (
              <>
                <strong>علت رد گزارش:</strong>
                {' '}
                {notes.reportRejectionReason}
              </>
            )}
            {notes.studentAlert && !notes.permitDenialReason && !notes.reportRejectionReason && notes.studentAlert}
          </HintBlock>
        )}

        {showSchedule && <DefenseScheduleChip schedule={schedule} />}

        {showFiles && (
          <div style={{ marginTop: '0.5rem' }}>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.5rem' }}>فایل‌های ثبت‌شده</h4>
            <UploadedDocumentsReadonlyGrid fields={FILE_FIELDS} contextData={ctx} />
          </div>
        )}
      </div>
    </div>
  )
}
