import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  HintBlock,
  InfoTile,
  resolveFullLeaveContext,
} from '../utils/fullEducationLeaveDisplay'

const PROCESS_TITLE_FA = 'تعیین تکلیف درمانگر — مرخصی از کل آموزش (فرایند ۵۹)'

/**
 * پنل مسئول هماهنگی درمان — فرایند ۵۹.
 */
export default function TherapistAssignmentReviewPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const leave = useMemo(() => resolveFullLeaveContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'full_education_leave') {
    return null
  }

  if (currentState !== 'therapist_assignment') {
    return null
  }

  return (
    <div
      className="card"
      data-testid="therapist-assignment-review-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {!compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <HintBlock tone="#dc2626" bg="#fef2f2">
          مهلت اقدام: ۴ روز از تاریخ ارسال به کارتابل. در صورت عدم ثبت، وقت درمانگر به‌صورت خودکار آزاد می‌شود.
        </HintBlock>

        <HintBlock tone="#2563eb" bg="#eff6ff">
          یکی از دو حالت را در فرم انتخاب کنید: ادامه درمان در قالب «درمان عموم» (پس از تماس دانشجو) یا آزادسازی وقت درمانگر.
        </HintBlock>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '0.65rem',
          }}
        >
          <InfoTile label="نام دانشجو" value={ctx.student_name_display || '—'} />
          <InfoTile label="درمانگر فعلی" value={leave.therapistName || '—'} tone="#7c3aed" bg="#f5f3ff" />
          <InfoTile label="زمان جلسات" value={ctx.current_session_times_display || '—'} />
          <InfoTile
            label="مهلت اقدام"
            value={ctx.therapist_deadline_display || '۴ روز از تاریخ ارجاع'}
            tone="#d97706"
            bg="#fffbeb"
          />
        </div>
      </div>
    </div>
  )
}
