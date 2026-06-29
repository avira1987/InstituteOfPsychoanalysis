import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import UploadedDocumentsReadonlyGrid from './UploadedDocumentsReadonlyGrid'
import {
  ThesisDefenseFlowStepper,
  DefenseScheduleChip,
  HintBlock,
  labelThesisDefenseState,
  resolveDefenseSchedule,
  resolveUploadedFiles,
} from '../utils/thesisDefenseRequestDisplay'

const THESIS_FILES = [
  { name: 'thesis_file', label_fa: 'پایان‌نامه', type: 'file_upload' },
  { name: 'revised_thesis_file', label_fa: 'پایان‌نامه اصلاح‌شده', type: 'file_upload' },
]

/**
 * راهنمای کمیته آموزش — فرایند ۷۰ (تعیین داوران و زمان دفاع).
 */
export default function ThesisDefenseEducationSchedulePanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const merged = useMemo(() => ({ ...ctx, ...stepFormValues }), [ctx, stepFormValues])

  const schedule = useMemo(
    () => resolveDefenseSchedule(merged, { hideReviewers: false }),
    [merged],
  )
  const files = useMemo(() => resolveUploadedFiles(ctx), [ctx])

  const isScheduling = detail?.process_code === 'thesis_defense_request'
    && currentState === 'education_committee_scheduling'
  const isReschedule = detail?.process_code === 'thesis_defense_request'
    && currentState === 'revision_upload'

  if (!active || !detail || (!isScheduling && !isReschedule)) {
    return null
  }

  return (
    <div
      className="card"
      data-testid="thesis-defense-education-schedule-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">
          {isReschedule
            ? 'زمان‌بندی دفاع مجدد — کمیته آموزش (فرایند ۷۰)'
            : 'تعیین داوران و زمان دفاع — کمیته آموزش (فرایند ۷۰)'}
        </h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState) || labelThesisDefenseState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ThesisDefenseFlowStepper currentState={currentState} compact={compact} />

        {isScheduling && (
          <HintBlock tone="info" testId="thesis-defense-education-hint">
            داور اول و دوم، تاریخ و ساعت جلسه را در فرم «تعیین داوران و زمان» ثبت کنید.
            نام داوران تا روز دفاع در پورتال دانشجو نمایش داده نمی‌شود.
            پس از ثبت فرم، دکمه «ثبت زمان‌بندی» (schedule_registered) را بزنید.
          </HintBlock>
        )}

        {isReschedule && (
          <HintBlock tone="warn" testId="thesis-defense-reschedule-hint">
            دانشجو پایان‌نامه اصلاح‌شده را بارگذاری کرده است.
            زمان دفاع مجدد را با همان داوران ثبت کنید و دکمه «ثبت دفاع مجدد»
            (second_defense_scheduled) را بزنید.
          </HintBlock>
        )}

        {(files.thesisFile || files.revisedThesisFile) && (
          <div style={{ marginBottom: '0.85rem' }}>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.5rem' }}>فایل پایان‌نامه</h4>
            <UploadedDocumentsReadonlyGrid fields={THESIS_FILES} contextData={ctx} />
          </div>
        )}

        {schedule.defenseDate && isReschedule && (
          <DefenseScheduleChip schedule={schedule} />
        )}
      </div>
    </div>
  )
}
