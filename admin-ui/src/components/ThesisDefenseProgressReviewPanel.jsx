import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import UploadedDocumentsReadonlyGrid from './UploadedDocumentsReadonlyGrid'
import {
  ThesisDefenseFlowStepper,
  EligibilityChecklistTiles,
  HintBlock,
  labelThesisDefenseState,
  resolveEligibilityContext,
  resolveUploadedFiles,
  resolveCommitteeNotes,
} from '../utils/thesisDefenseRequestDisplay'

const FILE_FIELDS = [
  { name: 'psychotic_report_file', label_fa: 'گزارش سایکوتیک', type: 'file_upload' },
]

const STATE_HINTS = {
  progress_committee_review:
    'گزارش ۱۵۰ ساعت سایکوتیک را بررسی کنید. فرم «تعیین تکلیف گزارش» را ثبت کنید، سپس یکی از دکمه‌ها: تایید (report_approved)، نیاز به اصلاح (revision_requested)، یا رد (report_rejected).',
  report_revision:
    'دانشجو در حال اصلاح گزارش است. پس از آپلود مجدد، پرونده دوباره برای بررسی به این کمیته برمی‌گردد.',
}

/**
 * راهنمای کمیته پیشرفت — فرایند ۷۰.
 */
export default function ThesisDefenseProgressReviewPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const eligibility = useMemo(() => resolveEligibilityContext(ctx), [ctx])
  const files = useMemo(() => resolveUploadedFiles(ctx), [ctx])
  const notes = useMemo(() => resolveCommitteeNotes(ctx), [ctx])

  const isRelevant = detail?.process_code === 'thesis_defense_request'
    && ['progress_committee_review', 'report_revision'].includes(currentState)

  if (!active || !detail || !isRelevant) {
    return null
  }

  const hint = STATE_HINTS[currentState]

  return (
    <div
      className="card"
      data-testid="thesis-defense-progress-review-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">بررسی گزارش دفاع — کمیته پیشرفت (فرایند ۷۰)</h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState) || labelThesisDefenseState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ThesisDefenseFlowStepper currentState={currentState} compact={compact} />

        {hint && (
          <HintBlock tone="info" testId="thesis-defense-progress-hint">
            {hint}
          </HintBlock>
        )}

        <EligibilityChecklistTiles eligibility={eligibility} />

        {files.psychoticReport && (
          <div style={{ marginBottom: '0.85rem' }}>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.5rem' }}>گزارش بارگذاری‌شده</h4>
            <UploadedDocumentsReadonlyGrid fields={FILE_FIELDS} contextData={ctx} />
          </div>
        )}

        {notes.revisionNotes && currentState === 'report_revision' && (
          <HintBlock tone="warn">
            <strong>توضیحات قبلی برای دانشجو:</strong>
            {' '}
            {notes.revisionNotes}
          </HintBlock>
        )}
      </div>
    </div>
  )
}
