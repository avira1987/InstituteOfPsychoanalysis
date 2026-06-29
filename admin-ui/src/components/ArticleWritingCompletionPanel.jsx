import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  ArticleWritingFlowStepper,
  ArticleWritingSlaBanner,
  EvaluationSummaryBlock,
  HintBlock,
  InfoTile,
  labelArticleWritingState,
  resolveArticleContext,
  resolveEvaluationSummary,
  isArticleViolationState,
  fmtIsoDate,
} from '../utils/articleWritingCompletionDisplay'

const PROCESS_TITLE_FA = 'خاتمه درس مقاله‌نویسی جهت گزارش موردی (فرایند ۶۹)'

const INSTRUCTOR_STATE_HINTS = {
  course_active:
    'برای هر دانشجویی که پایان‌نامه/گزارش موردی خود را تکمیل کرده، تیک «تکمیل شد» را در فرم پایین بزنید؛ سپس «تیک تکمیل — کلاس بسته شد» را ثبت کنید. حداکثر ۲ ترم برای این درس مجاز است.',
  instructor_eval_pending:
    'فرم ارزیابی کیفی (سوال ۷ و ۸) را برای این دانشجو تکمیل کنید. در صورت «بله»، حداقل یک ویژگی انتخاب کنید. مهلت: ۴ روز.',
  completed_to_defense:
    'ارزیابی ثبت شد. دانشجو به فاز «درخواست دفاع پایان‌نامه» (فرایند ۷۰) هدایت می‌شود.',
  student_delay_violation: 'تأخیر دانشجو در ثبت درخواست دفاع — گزارش به کمیته نظارت ارسال شده است.',
  instructor_delay_violation: 'تأخیر در تکمیل فرم ارزیابی — گزارش تخلف به کمیته نظارت ارسال شده است.',
  term3_violation: 'اخذ درس در ترم سوم یا بعد — گزارش تخلف آموزشی ثبت شده است.',
}

function roleBucket(portalRole) {
  const r = (portalRole || '').toLowerCase()
  if (r === 'instructor') return 'instructor'
  if (r === 'admin' || r === 'staff') return 'admin'
  return 'other'
}

/**
 * داشبورد راهنمای فرایند ۶۹ — پنل مدرس/اپراتور.
 */
export default function ArticleWritingCompletionPanel({
  detail = null,
  active = true,
  portalRole = 'staff',
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const bucket = roleBucket(portalRole)

  const article = useMemo(() => resolveArticleContext(ctx), [ctx])
  const evalSummary = useMemo(() => resolveEvaluationSummary(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'article_writing_completion') {
    return null
  }

  const isInstructorSide = bucket === 'instructor' || bucket === 'admin'
  if (!isInstructorSide) return null

  const hint = INSTRUCTOR_STATE_HINTS[currentState]
    ?? 'خاتمه درس مقاله‌نویسی — طبق راهنمای مرحله و فرم پایین اقدام کنید.'
  const isTerminal = currentState === 'completed_to_defense' || isArticleViolationState(currentState)
  const termNum = article.enrollmentTerm != null ? Number(article.enrollmentTerm) : null
  const termWarning = termNum != null && termNum >= 3

  return (
    <div
      className="card"
      data-testid="article-writing-completion-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelArticleWritingState(currentState) || labelState(currentState)}
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
          {article.enrollmentTerm != null && (
            <InfoTile
              label="ترم اخذ"
              value={String(article.enrollmentTerm)}
              tone={termWarning ? '#dc2626' : '#2563eb'}
              bg={termWarning ? '#fef2f2' : '#eff6ff'}
            />
          )}
          {article.studentName && (
            <InfoTile label="دانشجو" value={article.studentName} tone="#0d9488" bg="#f0fdfa" />
          )}
          {article.completionTickedAt && (
            <InfoTile label="زمان تیک تکمیل" value={fmtIsoDate(article.completionTickedAt)} tone="#16a34a" bg="#f0fdf4" />
          )}
        </div>

        <ArticleWritingSlaBanner
          ctx={ctx}
          currentState={currentState}
          startedAt={detail.started_at}
        />

        {termWarning && currentState === 'course_active' && (
          <HintBlock tone="danger">
            این دانشجو در ترم {String(termNum)} این درس را اخذ کرده است. اخذ ترم سوم و بعد تخلف آموزشی است و گزارش به کمیته نظارت دارد.
          </HintBlock>
        )}

        {currentState === 'course_active' && (
          <HintBlock tone="warn">
            کلاس مقاله‌نویسی حداکثر ۲ ترم (یک سال) ادامه دارد. اگر در ترم اول تکمیل نشد، دانشجو در ترم دوم دوباره اخذ می‌کند؛ در ترم سوم گزارش تخلف ثبت می‌شود.
          </HintBlock>
        )}

        {hint && <HintBlock tone={isArticleViolationState(currentState) ? 'danger' : 'info'}>{hint}</HintBlock>}

        <EvaluationSummaryBlock summary={evalSummary} />
      </div>
    </div>
  )
}
