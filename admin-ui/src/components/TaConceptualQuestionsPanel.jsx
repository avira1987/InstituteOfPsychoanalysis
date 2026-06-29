import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  TaConceptualFlowStepper,
  TaConceptualSlaBanner,
  SessionInfoTiles,
  HintBlock,
  TemplateDownloadLinks,
  QuestionPdfPreview,
  InstructorReviewSummary,
  ScoreProgressBar,
  SESSION_SCORE_AWARD,
  resolveSessionContext,
  resolveUploadedQuestions,
  resolveInstructorReview,
  resolveScoreSummary,
} from '../utils/taConceptualQuestionsDisplay'

const PROCESS_TITLE_FA = 'ثبت ۳ سوال تستی‌مفهومی بعد از هر جلسه کلاس (فرایند ۴۳)'

function roleBucket(portalRole) {
  const r = (portalRole || '').toLowerCase()
  if (r === 'teaching_assistant') return 'ta'
  if (r === 'instructor') return 'instructor'
  if (r === 'admin' || r === 'staff') return 'admin'
  return 'other'
}

/**
 * داشبورد راهنمای فرایند ۴۳ — ثبت سوالات تستی‌مفهومی پس از هر جلسه کلاس.
 */
export default function TaConceptualQuestionsPanel({
  detail = null,
  active = true,
  portalRole = 'staff',
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const bucket = roleBucket(portalRole)

  const session = useMemo(() => resolveSessionContext(ctx), [ctx])
  const questions = useMemo(() => resolveUploadedQuestions(ctx), [ctx])
  const reviews = useMemo(() => resolveInstructorReview(ctx), [ctx])
  const scoreSummary = useMemo(() => resolveScoreSummary(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'ta_conceptual_questions') {
    return null
  }

  const isTaSide = bucket === 'ta' || bucket === 'admin'
  const isInstructorSide = bucket === 'instructor' || bucket === 'admin'

  const showTaUpload = ['ta_upload', 'upload_late'].includes(currentState) && isTaSide
  const showRevision = currentState === 'question_rejected' && isTaSide
  const showInstructor = currentState === 'instructor_review' && isInstructorSide
  const showApproved = currentState === 'questions_approved'
  const showPdfPreview = ['instructor_review', 'question_rejected', 'questions_approved'].includes(currentState)
  const lateViolation = currentState === 'upload_late' || ctx.upload_late_violation_reported === true

  return (
    <div
      className="card"
      data-testid="ta-conceptual-questions-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TaConceptualFlowStepper currentState={currentState} />
        <SessionInfoTiles session={session} />

        <TaConceptualSlaBanner
          ctx={ctx}
          currentState={currentState}
          startedAt={detail.started_at}
        />

        {lateViolation && isTaSide && (
          <HintBlock tone="warn">
            مهلت ۲۴ ساعتهٔ آپلود گذشته است. گزارش تخلف به کمیته نظارت ارسال شده و هشدار به معاون آموزش ثبت می‌شود.
            همچنان می‌توانید فایل‌ها را آپلود و ارسال کنید.
          </HintBlock>
        )}

        <ScoreProgressBar scoreSummary={scoreSummary} />

        {showTaUpload && (
          <>
            <TemplateDownloadLinks />
            <HintBlock tone="purple">
              سه سوال تستی‌مفهومی را طبق قالب طراحی کنید؛ هر سوال در یک فایل PDF جداگانه.
              پس از «ثبت فرم»، دکمهٔ «ثبت آپلود و ارسال به مدرس» را بزنید.
              مهلت: ۲۴ ساعت پس از پایان کلاس.
            </HintBlock>
          </>
        )}

        {showRevision && (
          <>
            <InstructorReviewSummary reviews={reviews} />
            <HintBlock tone="warn">
              سوال(های) ردشده را مطابق بازخورد مدرس اصلاح کنید و PDF جدید را در فرم زیر آپلود کنید؛
              سپس «اصلاح و ارسال مجدد» را بزنید. مهلت اصلاح: ۲۴ ساعت.
            </HintBlock>
          </>
        )}

        {showInstructor && (
          <HintBlock tone="info">
            هر سه فایل PDF را بررسی کنید. در فرم زیر برای هر سوال «قابل قبول» یا «غیر قابل قبول» ثبت کنید.
            در صورت رد، توضیح علت الزامی است. پس از ثبت فرم، اگر همه قابل قبول‌اند «تأیید همه سوالات» و
            در غیر این صورت «رد و بازگشت برای اصلاح» را بزنید. مهلت: ۴ روز.
          </HintBlock>
        )}

        {showPdfPreview && <QuestionPdfPreview questions={questions} />}

        {showApproved && (
          <HintBlock tone="success">
            هر سه سوال تأیید شدند.
            {' '}
            {SESSION_SCORE_AWARD.toLocaleString('fa-IR')}
            {' '}
            نمره به بخش «طراحی سوال تستی‌مفهومی» اضافه می‌شود و سوالات در بانک مرکز مرجع آرشیو می‌شوند.
            {scoreSummary.sessionAward != null && (
              <>
                {' '}
                (این جلسه:
                {' '}
                +
                {scoreSummary.sessionAward.toLocaleString('fa-IR')}
                {' '}
                نمره)
              </>
            )}
          </HintBlock>
        )}
      </div>
    </div>
  )
}
