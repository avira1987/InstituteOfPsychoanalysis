import React, { useMemo } from 'react'
import {
  ArticleWritingFlowStepper,
  ArticleWritingSlaBanner,
  HintBlock,
  InfoTile,
  labelArticleWritingState,
  resolveArticleContext,
  isArticleViolationState,
  fmtIsoDate,
} from '../utils/articleWritingCompletionDisplay'

const PROCESS_TITLE_FA = 'خاتمه درس مقاله‌نویسی (فرایند ۶۹)'

const STUDENT_STATE_HINTS = {
  course_active:
    'کلاس مقاله‌نویسی برای شما فعال است. پس از تکمیل گزارش موردی، مدرس «تیک تکمیل» را ثبت می‌کند؛ سپس مهلت ۸ روزه برای درخواست دفاع آغاز می‌شود.',
  class_closed_student:
    'کلاس برای شما بسته شد. ظرف ۸ روز «ثبت درخواست دفاع پایان‌نامه/گزارش موردی» را در همین صفحه انجام دهید (دکمه «ادامه و ثبت مرحله»).',
  instructor_eval_pending:
    'درخواست دفاع شما ثبت شد. مدرس موظف است ظرف ۴ روز فرم ارزیابی را تکمیل کند؛ پس از آن می‌توانید فرایند دفاع (فرایند ۷۰) را آغاز کنید.',
  completed_to_defense:
    'فرایند خاتمه درس مقاله‌نویسی تکمیل شد. از بخش فرایندها، «درخواست ثبت دفاع پایان‌نامه» (فرایند ۷۰) را آغاز کنید.',
  student_delay_violation:
    'مهلت ۸ روزه ثبت درخواست دفاع گذشته است. گزارش تأخیر به کمیته نظارت ارسال شده؛ برای پیگیری با دفتر آموزش تماس بگیرید.',
  instructor_delay_violation:
    'درخواست دفاع شما ثبت شده است. تأخیر مدرس در ارزیابی گزارش شده؛ پرونده در حال پیگیری است.',
  term3_violation:
    'اخذ این درس در ترم سوم یا بعد به‌عنوان تخلف آموزشی گزارش شده است. با کمیته نظارت هماهنگ کنید.',
}

/**
 * داشبورد راهنمای «خاتمه درس مقاله‌نویسی» — فرایند ۶۹ (دانشجو).
 */
export default function StudentArticleWritingCompletionPanel({
  detail = null,
  active = true,
  compact = false,
  onOpenProcesses = null,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const article = useMemo(() => resolveArticleContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'article_writing_completion') {
    return null
  }

  const hint = STUDENT_STATE_HINTS[currentState]
    ?? 'خاتمه درس مقاله‌نویسی — وضعیت پرونده را در همین صفحه دنبال کنید.'
  const isComplete = currentState === 'completed_to_defense'
  const needsDefenseAction = currentState === 'class_closed_student'

  return (
    <div className="card" data-testid="student-article-writing-completion-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isComplete ? 'badge-success' : isArticleViolationState(currentState) ? 'badge-danger' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelArticleWritingState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ArticleWritingFlowStepper currentState={currentState} compact={compact} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <InfoTile label="درس" value={article.courseName} tone="#7c3aed" bg="#f5f3ff" />
          {article.completionTickedAt && (
            <InfoTile label="تاریخ تیک تکمیل" value={fmtIsoDate(article.completionTickedAt)} tone="#16a34a" bg="#f0fdf4" />
          )}
          {article.defenseRequestedAt && (
            <InfoTile label="تاریخ درخواست دفاع" value={fmtIsoDate(article.defenseRequestedAt)} tone="#2563eb" bg="#eff6ff" />
          )}
        </div>

        <ArticleWritingSlaBanner
          ctx={ctx}
          currentState={currentState}
          startedAt={detail.started_at}
        />

        {hint && (
          <div data-testid="article-writing-student-hint">
            <HintBlock tone={isArticleViolationState(currentState) ? 'danger' : needsDefenseAction ? 'warn' : 'info'}>
              {hint}
            </HintBlock>
          </div>
        )}

        {isComplete && onOpenProcesses && (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            style={{ marginTop: '0.5rem' }}
            onClick={() => onOpenProcesses()}
          >
            رفتن به فرایندها — شروع درخواست دفاع
          </button>
        )}
      </div>
    </div>
  )
}
