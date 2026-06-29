import React, { useMemo } from 'react'
import UploadedDocumentsReadonlyGrid from './UploadedDocumentsReadonlyGrid'
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

const STATE_HINTS = {
  eligibility_check:
    'وضعیت چهار شرط زیر را بررسی کنید. در صورت احراز همهٔ شروط، فایل PDF گزارش ۱۵۰ ساعت بیماران سایکوتیک را در فرم پایین بارگذاری و «ادامه و ثبت مرحله» را بزنید.',
  conditions_not_met: ELIGIBILITY_ERROR_FA,
  progress_committee_review:
    'گزارش شما در کمیته پیشرفت در حال بررسی است. پس از اعلام نتیجه، این صفحه به‌روز می‌شود.',
  report_revision:
    'کمیته پیشرفت نیاز به اصلاح گزارش سایکوتیک اعلام کرده است. توضیحات را در باکس زیر ببینید؛ فایل اصلاح‌شده را بارگذاری کنید.',
  supervision_committee_review:
    'پرونده در کمیته نظارت است. پس از صدور مجوز یا رد، وضعیت اینجا نمایش داده می‌شود.',
  defense_permit_denied:
    'کمیته نظارت مجوز دفاع صادر نکرده است. توضیحات در باکس زیر آمده است.',
  thesis_upload:
    'مجوز دفاع صادر شد. فایل پایان‌نامه / گزارش موردی (PDF) را در فرم پایین بارگذاری کنید.',
  education_committee_scheduling:
    'پایان‌نامه ثبت شد. کمیته آموزش در حال تعیین زمان و داوران است؛ جزئیات جلسه (بدون نام داور) پس از ثبت اینجا نمایش داده می‌شود.',
  first_defense_held:
    'زمان دفاع ثبت شده است. در روز مقرر طبق اعلام کمیته حاضر شوید. پس از برگزاری، نتیجه در همین صفحه اعلام می‌شود.',
  revision_required:
    'حداقل یک داور نمره C/D/F داده است. حداکثر ۲ هفته فرصت دارید فایل اصلاح‌شده را بارگذاری کنید.',
  revision_upload:
    'فایل اصلاح‌شده ثبت شد. کمیته آموزش زمان دفاع مجدد را هماهنگ می‌کند.',
  second_defense_held:
    'دفاع مجدد برنامه‌ریزی شده است. در روز مقرر حاضر شوید؛ نتیجه نهایی پس از داوری اعلام می‌شود.',
  defense_passed: 'تبریک — دفاع با موفقیت (PASS) به پایان رسید.',
  defense_failed: 'نتیجه نهایی دفاع: مردود (FAIL). در صورت پرسش با کمیته پیشرفت تماس بگیرید.',
  report_rejected: 'گزارش سایکوتیک توسط کمیته پیشرفت رد شد و فرایند خاتمه یافته است.',
  revision_delay_violation:
    'مهلت ۲ هفته برای آپلود اصلاحات به پایان رسید. پرونده به کمیته نظارت برای بررسی تخلف ارجاع شده است.',
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

  const hint = STATE_HINTS[currentState]
    ?? 'مسیر دفاع پایان‌نامه — مراحل را طبق راهنمای این صفحه پیش ببرید.'
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
