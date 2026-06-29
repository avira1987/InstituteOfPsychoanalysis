import React, { useMemo } from 'react'
import { HintBlock } from '../utils/attendanceChainDisplay'
import {
  getTaDutyConfig,
  isTaClassDutyProcess,
  isTaDutyTerminalState,
  resolveActorKind,
  resolveStateHint,
  resolveTaDutyContext,
  TaDutyFlowStepper,
  TaDutyInfoTile,
  TaDutySlaBanner,
  labelTaDutyState,
  fmtIsoDate,
} from '../utils/taClassDutiesDisplay'

/**
 * داشبورد راهنمای وظایف کمک‌مدرس پس از جلسه کلاس — فرایندهای SOP 43–46.
 * مخصوص پنل مدرس و کمک‌مدرس (instruction lane).
 */
export default function TaClassDutiesPanel({
  detail = null,
  user = null,
  active = true,
  compact = false,
}) {
  const processCode = detail?.process_code
  const currentState = detail?.current_state || null
  const ctx = detail?.context_data || {}

  const dutyCtx = useMemo(() => resolveTaDutyContext(ctx), [ctx])
  const cfg = useMemo(() => getTaDutyConfig(processCode), [processCode])
  const actorKind = useMemo(
    () => resolveActorKind(currentState, user?.role),
    [currentState, user?.role],
  )

  if (!active || !detail || !isTaClassDutyProcess(processCode)) {
    return null
  }

  const hint = resolveStateHint(processCode, currentState, actorKind)
    ?? (isTaDutyTerminalState(currentState)
      ? 'این پرونده به پایان رسیده است.'
      : 'وظیفهٔ کمک‌مدرس پس از جلسه کلاس — طبق راهنمای مرحله و فرم پایین اقدام کنید.')
  const isTerminal = isTaDutyTerminalState(currentState)
  const showUploadLateWarning = currentState === 'upload_late' || dutyCtx.uploadLate
  const milestoneLabel = dutyCtx.milestoneSession != null
    ? `جلسه ${dutyCtx.milestoneSession.toLocaleString('fa-IR')}`
    : null
  const sessionLabel = dutyCtx.sessionIndex != null
    ? dutyCtx.sessionIndex.toLocaleString('fa-IR')
    : null

  return (
    <div
      className="card"
      data-testid="ta-class-duties-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">
          {cfg?.titleFa || 'وظایف کمک‌مدرس پس از جلسه'}
        </h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelTaDutyState(processCode, currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TaDutyFlowStepper
          processCode={processCode}
          currentState={currentState}
          compact={compact}
        />

        <div
          data-testid="ta-duty-milestone-summary"
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <TaDutyInfoTile
            label="نام درس"
            value={dutyCtx.courseName}
            tone={cfg?.accent}
            bg={cfg?.accentBg}
          />
          {processCode === 'ta_student_consultation' && milestoneLabel && (
            <TaDutyInfoTile
              label="جلسه milestone"
              value={milestoneLabel}
              tone={cfg?.accent}
              bg={cfg?.accentBg}
            />
          )}
          {processCode !== 'ta_student_consultation' && sessionLabel && (
            <TaDutyInfoTile
              label="شماره جلسه"
              value={sessionLabel}
              tone={cfg?.accent}
              bg={cfg?.accentBg}
            />
          )}
          {dutyCtx.sessionDate && (
            <TaDutyInfoTile
              label="تاریخ جلسه"
              value={fmtIsoDate(dutyCtx.sessionDate)}
              tone="#64748b"
            />
          )}
          {dutyCtx.taScore != null && (
            <TaDutyInfoTile
              label="امتیاز ثبت‌شده"
              value={dutyCtx.taScore.toLocaleString('fa-IR')}
              tone="#059669"
              bg="#ecfdf5"
            />
          )}
        </div>

        {!isTerminal && (
          <TaDutySlaBanner
            processCode={processCode}
            currentState={currentState}
            ctx={ctx}
          />
        )}

        {showUploadLateWarning && (
          <HintBlock
            testId="ta-duty-upload-late-warning"
            title="تأخیر آپلود"
            color="#dc2626"
            bg="#fef2f2"
          >
            <span style={{ color: '#991b1b' }}>
              مهلت ۲۴ ساعت گذشته است؛ گزارش تخلف برای کمیته نظارت ثبت شده. همچنان می‌توانید ارسال کنید.
            </span>
          </HintBlock>
        )}

        {processCode === 'ta_student_consultation' && currentState === 'ta_form_fill' && (
          <HintBlock
            testId="ta-duty-consultation-milestone-hint"
            title="یادآوری milestone"
            color={cfg?.accent}
            bg={cfg?.accentBg}
          >
            <span style={{ color: cfg?.accentText }}>
              {cfg?.specialNotes?.milestone}
              {' '}
              با دکمه «افزودن دانشجو» در فرم، هر دانشجوی نیازمند تشویق یا مشورت را ثبت کنید.
            </span>
          </HintBlock>
        )}

        {processCode === 'ta_conceptual_questions' && ['ta_upload', 'question_rejected'].includes(currentState) && (
          <HintBlock
            testId="ta-duty-questions-template-hint"
            title="قالب سوال"
            color={cfg?.accent}
            bg={cfg?.accentBg}
          >
            <span style={{ color: cfg?.accentText }}>
              {cfg?.specialNotes?.template}
              {' '}
              هر سوال در یک فایل PDF جداگانه آپلود شود.
            </span>
          </HintBlock>
        )}

        {processCode === 'ta_essay_upload' && ['ta_upload', 'rejected_revision'].includes(currentState) && (
          <HintBlock
            testId="ta-duty-essay-format-hint"
            title="فرمت بارگذاری"
            color={cfg?.accent}
            bg={cfg?.accentBg}
          >
            <span style={{ color: cfg?.accentText }}>
              {cfg?.specialNotes?.formats}
              {' '}
              {cfg?.specialNotes?.template}
            </span>
          </HintBlock>
        )}

        {processCode === 'ta_blog_content' && ['ta_write', 'rejected_revision'].includes(currentState) && (
          <HintBlock
            testId="ta-duty-blog-text-hint"
            title="قوانین نگارش"
            color={cfg?.accent}
            bg={cfg?.accentBg}
          >
            <span style={{ color: cfg?.accentText }}>
              {cfg?.specialNotes?.textOnly}
            </span>
          </HintBlock>
        )}

        {currentState === 'form_locked' && (
          <HintBlock
            testId="ta-duty-form-locked"
            title="فرم قفل شد"
            color="#dc2626"
            bg="#fef2f2"
          >
            <span style={{ color: '#991b1b' }}>
              مهلت ۴ روز گذشته؛ فرم قفل و نمره صفر ثبت شده است.
            </span>
          </HintBlock>
        )}

        {hint && (
          <HintBlock
            testId="ta-duty-state-hint"
            title="راهنمای مرحله"
            color={cfg?.accent || '#2563eb'}
            bg={cfg?.accentBg || '#eff6ff'}
          >
            <span style={{ color: cfg?.accentText || '#1e40af' }}>{hint}</span>
          </HintBlock>
        )}
      </div>
    </div>
  )
}
