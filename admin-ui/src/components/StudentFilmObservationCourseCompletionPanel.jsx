import React, { useMemo } from 'react'
import UploadedDocumentsReadonlyGrid from './UploadedDocumentsReadonlyGrid'
import FilmObservationFinalReportUploadSection from './FilmObservationFinalReportUploadSection'
import {
  BORDERLINE_SMS_FA,
  FilmCompletionFlowStepper,
  FilmCompletionHintBlock,
  FilmCompletionSlaBanner,
  FINAL_REPORT_FILE_FIELDS,
  InfoTile,
  PROCESS_TITLE_FA,
  STATE_HINTS,
  fmtIsoDate,
  isTerminalState,
  labelFilmCompletionState,
  labelPassFail,
  resolveFilmCompletionContext,
} from '../utils/filmObservationCourseCompletionDisplay'

const STUDENT_STATE_HINTS = {
  grades_entry:
    'گزارش پایانی درس را فقط به‌صورت PDF آپلود کنید. فرم از پایان جلسه ۱۷ باز و در ۲۴:۰۰ روز جلسه ۱۸ بسته می‌شود. پس از آپلود، مدرس ظرف ۵ روز گزارش را تصحیح می‌کند.',
  grades_locked:
    'نمره گزارش ثبت شد. اگر نمره نهایی شما در بازه مرزی ۶۴ تا ۷۳ باشد، می‌توانید امتحان مجدد (با پرداخت) یا دوباره گذراندن درس را انتخاب کنید.',
  delay_reported:
    'مهلت ثبت یا تصحیح گزارش گذشته است. برای پیگیری با دفتر آموزش تماس بگیرید.',
}

/**
 * داشبورد «خاتمه درس عملی کاربردی / مشاهده فیلم» — فرایند ۶۴ (دانشجو).
 */
export default function StudentFilmObservationCourseCompletionPanel({
  detail = null,
  instanceId = null,
  showToast = null,
  onRefreshInstance = null,
  stepFormValues = {},
  onFieldChange = null,
  stepFormLocked = false,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const filmCtx = useMemo(() => resolveFilmCompletionContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'film_observation_course_completion') {
    return null
  }

  const hint = STUDENT_STATE_HINTS[currentState] || STATE_HINTS[currentState]
    || 'خاتمه درس عملی کاربردی / مشاهده فیلم — وضعیت پرونده را در همین صفحه دنبال کنید.'
  const isTerminal = isTerminalState(currentState)
  const isBorderline = filmCtx.passFail === 'مرزی'
    || (filmCtx.totalScore != null && filmCtx.totalScore >= 64 && filmCtx.totalScore <= 73)
  const hasReport = !!ctx.final_report_pdf

  return (
    <div className="card" data-testid="student-film-observation-course-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelFilmCompletionState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <FilmCompletionFlowStepper currentState={currentState} compact={compact} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <InfoTile label="درس" value={filmCtx.courseName} tone="#7c3aed" bg="#f5f3ff" />
          {filmCtx.reportUploadedAt && (
            <InfoTile
              label="زمان آپلود گزارش"
              value={fmtIsoDate(filmCtx.reportUploadedAt)}
              tone="#16a34a"
              bg="#f0fdf4"
            />
          )}
          {filmCtx.totalScore != null && (
            <InfoTile
              label="نمره نهایی"
              value={`${filmCtx.totalScore.toLocaleString('fa-IR')} — ${filmCtx.passFail || labelPassFail(filmCtx.totalScore)}`}
              tone={filmCtx.totalScore >= 74 ? '#059669' : '#dc2626'}
              bg={filmCtx.totalScore >= 74 ? '#ecfdf5' : '#fef2f2'}
            />
          )}
        </div>

        <FilmCompletionSlaBanner ctx={ctx} startedAt={detail.started_at} />

        {hint && (
          <FilmCompletionHintBlock tone={currentState === 'delay_reported' ? 'danger' : 'info'}>
            {hint}
          </FilmCompletionHintBlock>
        )}

        <FilmObservationFinalReportUploadSection
          instanceId={instanceId}
          detail={detail}
          stepFormValues={stepFormValues}
          onFieldChange={onFieldChange}
          stepFormLocked={stepFormLocked}
          showToast={showToast}
          onRefreshInstance={onRefreshInstance}
          active={active}
        />

        {isTerminal && hasReport && (
          <div style={{ marginBottom: '0.85rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem' }}>گزارش آپلودشده</div>
            <UploadedDocumentsReadonlyGrid fields={FINAL_REPORT_FILE_FIELDS} contextData={ctx} />
          </div>
        )}

        {isBorderline && (
          <FilmCompletionHintBlock title="نمره مرزی" tone="warn">
            {BORDERLINE_SMS_FA}
            {' '}
            در صورت عدم پرداخت یا انتخاب «دوباره گذراندن درس»، نمره فعلی قطعی می‌شود.
          </FilmCompletionHintBlock>
        )}

        <FilmCompletionHintBlock title="نمرات مشارکت و حضور" tone="info">
          نمره مشارکت (۰–۱۰) و حضور (حداکثر ۸) توسط مدرس در فرایند ۷۵ ثبت می‌شود و در جمع نمره نهایی لحاظ می‌گردد.
        </FilmCompletionHintBlock>
      </div>
    </div>
  )
}
