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
} from '../utils/thesisDefenseRequestDisplay'

const DOSSIER_FILES = [
  { name: 'psychotic_report_file', label_fa: 'گزارش سایکوتیک', type: 'file_upload' },
  { name: 'thesis_file', label_fa: 'پایان‌نامه', type: 'file_upload' },
]

/**
 * راهنمای کمیته نظارت — فرایند ۷۰ (صدور مجوز دفاع).
 */
export default function ThesisDefenseSupervisionReviewPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const eligibility = useMemo(() => resolveEligibilityContext(ctx), [ctx])
  const files = useMemo(() => resolveUploadedFiles(ctx), [ctx])

  const isRelevant = detail?.process_code === 'thesis_defense_request'
    && currentState === 'supervision_committee_review'

  if (!active || !detail || !isRelevant) {
    return null
  }

  return (
    <div
      className="card"
      data-testid="thesis-defense-supervision-review-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">صدور مجوز دفاع — کمیته نظارت (فرایند ۷۰)</h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState) || labelThesisDefenseState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ThesisDefenseFlowStepper currentState={currentState} compact={compact} />

        <HintBlock tone="info" testId="thesis-defense-supervision-hint">
          گزارش سایکوتیک توسط کمیته پیشرفت تأیید شده است. فرم «صدور مجوز دفاع» را تکمیل کنید؛
          سپس «صدور مجوز» (permit_issued) یا «عدم مجوز» (permit_denied) را بزنید.
          در صورت مجوز، دانشجو می‌تواند پایان‌نامه را بارگذاری کند.
        </HintBlock>

        <EligibilityChecklistTiles eligibility={eligibility} />

        {(files.psychoticReport || files.thesisFile) && (
          <div style={{ marginBottom: '0.85rem' }}>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.5rem' }}>مدارک پرونده</h4>
            <UploadedDocumentsReadonlyGrid fields={DOSSIER_FILES} contextData={ctx} />
          </div>
        )}
      </div>
    </div>
  )
}
