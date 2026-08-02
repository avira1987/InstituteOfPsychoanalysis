import React, { useMemo } from 'react'
import UploadedDocumentsReadonlyGrid from './UploadedDocumentsReadonlyGrid'
import LiveTherapyObservationFinalReportUploadSection from './LiveTherapyObservationFinalReportUploadSection'
import {
  BORDERLINE_SMS_FA,
  LiveTherapyCompletionFlowStepper,
  LiveTherapyCompletionHintBlock,
  LiveTherapyCompletionSlaBanner,
  FINAL_REPORT_FILE_FIELDS,
  InfoTile,
  PROCESS_TITLE_FA,
  STATE_HINTS,
  fmtIsoDate,
  isTerminalState,
  labelLiveTherapyCompletionState,
  labelPassFail,
  resolveLiveTherapyCompletionContext,
} from '../utils/liveTherapyObservationCourseCompletionDisplay'

const STUDENT_STATE_HINTS = {
  grades_entry:
    'گزارش پایانی درس را فقط به‌صورت PDF آپلود کنید. فرم از پایان جلسه ۱۷ باز و در ۲۴:۰۰ روز جلسه ۱۸ بسته می‌شود. پس از آپلود، مدرس ظرف ۵ روز گزارش را تصحیح می‌کند.',
  grades_locked:
    'نمره گزارش ثبت شد. اگر نمره نهایی شما در بازه مرزی ۶۴ تا ۷۳ باشد، می‌توانید امتحان مجدد (با پرداخت) یا دوباره گذراندن درس را انتخاب کنید.',
  delay_reported:
    'مهلت ثبت یا تصحیح گزارش گذشته است. برای پیگیری با دفتر آموزش تماس بگیرید.',
}

/**
 * داشبورد «خاتمه درس مشاهده زنده درمان» — فرایند ۶۵ (دانشجو).
 */
export default function StudentLiveTherapyObservationCourseCompletionPanel({
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

  const therapyCtx = useMemo(() => resolveLiveTherapyCompletionContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'live_therapy_observation_course_completion') {
    return null
  }

  const hint = STUDENT_STATE_HINTS[currentState] || STATE_HINTS[currentState]
    || 'خاتمه درس مشاهده زنده درمان — وضعیت پرونده را در همین صفحه دنبال کنید.'
  const isTerminal = isTerminalState(currentState)
  const isBorderline = therapyCtx.passFail === 'مرزی'
    || (therapyCtx.totalScore != null && therapyCtx.totalScore >= 64 && therapyCtx.totalScore <= 73)
  const hasReport = !!ctx.final_report_pdf

  return (
    <div className="card" data-testid="student-live-therapy-observation-course-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelLiveTherapyCompletionState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <LiveTherapyCompletionFlowStepper currentState={currentState} compact={compact} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <InfoTile label="درس" value={therapyCtx.courseName} tone="#0d9488" bg="#f0fdfa" />
          {therapyCtx.reportUploadedAt && (
            <InfoTile
              label="زمان آپلود گزارش"
              value={fmtIsoDate(therapyCtx.reportUploadedAt)}
              tone="#16a34a"
              bg="#f0fdf4"
            />
          )}
          {therapyCtx.totalScore != null && (
            <InfoTile
              label="نمره نهایی"
              value={`${therapyCtx.totalScore.toLocaleString('fa-IR')} — ${therapyCtx.passFail || labelPassFail(therapyCtx.totalScore)}`}
              tone={therapyCtx.totalScore >= 74 ? '#059669' : '#dc2626'}
              bg={therapyCtx.totalScore >= 74 ? '#ecfdf5' : '#fef2f2'}
            />
          )}
        </div>

        <LiveTherapyCompletionSlaBanner ctx={ctx} startedAt={detail.started_at} />

        {hint && (
          <LiveTherapyCompletionHintBlock tone={currentState === 'delay_reported' ? 'danger' : 'info'}>
            {hint}
          </LiveTherapyCompletionHintBlock>
        )}

        <LiveTherapyObservationFinalReportUploadSection
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
          <LiveTherapyCompletionHintBlock title="نمره مرزی" tone="warn">
            {BORDERLINE_SMS_FA}
            {' '}
            در صورت عدم پرداخت یا انتخاب «دوباره گذراندن درس»، نمره فعلی قطعی می‌شود.
          </LiveTherapyCompletionHintBlock>
        )}

        <LiveTherapyCompletionHintBlock title="نمرات مشارکت و حضور" tone="info">
          نمره مشارکت (۰–۱۰) و حضور (حداکثر ۸) توسط مدرس در فرایند ۷۴ ثبت می‌شود و در جمع نمره نهایی لحاظ می‌گردد.
        </LiveTherapyCompletionHintBlock>
      </div>
    </div>
  )
}
