import React, { useMemo, useState } from 'react'
import { processExecApi } from '../services/api'
import {
  BORDERLINE_HINT_FA,
  EXAM_MAX,
  PROCESS_TITLE_FA,
  STATE_HINTS,
  TheoryFlowStepper,
  TheoryHintBlock,
  TheorySlaBanner,
  InfoTile,
  buildExamCompletedPayload,
  buildRetakeCompletedPayload,
  isTerminalState,
  labelPassFail,
  labelTheoryState,
  resolveTheoryCompletionContext,
  scoringSummaryLabel,
} from '../utils/theoryCourseCompletionDisplay'

const STUDENT_STATE_HINTS = {
  awaiting_session_18:
    'درس شما در انتظار جلسه ۱۸ است. پس از برگزاری جلسه، مدرس مشارکت را ثبت می‌کند.',
  session_18_entry:
    'جلسه ۱۸ — مدرس در حال ثبت مشارکت و انتخاب پک آزمون است.',
  final_exam_open:
    'آزمون تستی آنلاین (۸۲ نمره) آماده است. غیبت در آزمون → Incomplete.',
  grades_computed: 'نمرات در حال نهایی‌سازی است.',
  borderline_student_choice: BORDERLINE_HINT_FA,
  retake_exam_open:
    'امتحان مجدد فعال شد. پس از پرداخت، در زمان مقرر آزمون را بگذرانید.',
  qualitative_eval_pending: 'مدرس فرم ارزیابی کیفی را تکمیل می‌کند.',
  grades_locked: 'نمره نهایی ثبت و قفل شد.',
  session_18_delay: 'مهلت ثبت جلسه ۱۸ گذشته است. با دفتر آموزش تماس بگیرید.',
  qualitative_eval_delay: 'تأخیر در ارزیابی کیفی. با دفتر آموزش تماس بگیرید.',
}

/**
 * داشبورد «خاتمه دروس تئوری» — فرایند ۶۱ (دانشجو).
 */
export default function StudentTheoryCourseCompletionPanel({
  detail = null,
  instanceId = null,
  availableTransitions = [],
  showToast = null,
  onRefreshInstance = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const theoryCtx = useMemo(() => resolveTheoryCompletionContext(ctx), [ctx])
  const [submitting, setSubmitting] = useState(false)
  const [demoTestScore, setDemoTestScore] = useState('')

  if (!active || !detail || detail.process_code !== 'theory_course_completion') {
    return null
  }

  const hint = STUDENT_STATE_HINTS[currentState] || STATE_HINTS[currentState]
    || 'خاتمه دروس تئوری — وضعیت پرونده را در همین صفحه دنبال کنید.'
  const isTerminal = isTerminalState(currentState)

  const myRow = (theoryCtx.studentsGrades || []).find(
    (r) => String(r.student_id) === String(detail.student_id),
  ) || {}
  const total = myRow.total_score ?? theoryCtx.totalScore
  const passFail = myRow.pass_fail ?? theoryCtx.passFail
  const incomplete = myRow.incomplete || passFail === 'I'
  const isBorderline = passFail === 'مرزی' || theoryCtx.borderlinePending

  const findTransition = (event) => availableTransitions.find((t) => t.trigger_event === event)

  const triggerTransition = async (event, payload = {}) => {
    const tr = findTransition(event)
    if (!tr || !instanceId) {
      showToast?.('این اقدام در دسترس نیست.', 'error')
      return
    }
    setSubmitting(true)
    try {
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: tr.trigger_event,
        payload,
        ...(tr.to_state ? { to_state: tr.to_state } : {}),
      })
      if (res.data?.success) {
        showToast?.('ثبت شد')
        onRefreshInstance?.()
      } else {
        showToast?.(res.data?.error || 'خطا', 'error')
      }
    } catch (e) {
      showToast?.(e?.response?.data?.detail || e.message || 'خطا', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const handleExamComplete = () => {
    const score = demoTestScore === '' ? 75 : Number(demoTestScore)
    const payload = buildExamCompletedPayload(score, false)
    triggerTransition('exam_completed', payload)
  }

  const handleRetakeComplete = () => {
    const score = demoTestScore === '' ? 78 : Number(demoTestScore)
    const payload = buildRetakeCompletedPayload(score, false)
    triggerTransition('retake_exam_completed', payload)
  }

  return (
    <div className="card" data-testid="student-theory-course-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelTheoryState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TheoryFlowStepper currentState={currentState} compact={compact} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <InfoTile label="درس" value={theoryCtx.courseName} tone="#7c3aed" bg="#f5f3ff" />
          <InfoTile label="بارم" value={scoringSummaryLabel()} tone="#7c3aed" bg="#ede9fe" />
          {theoryCtx.participationScore != null && (
            <InfoTile label="مشارکت" value={theoryCtx.participationScore.toLocaleString('fa-IR')} />
          )}
          {theoryCtx.attendanceScore != null && (
            <InfoTile label="حضور" value={theoryCtx.attendanceScore.toLocaleString('fa-IR')} />
          )}
          {theoryCtx.testScore != null && (
            <InfoTile
              label="آزمون"
              value={`${theoryCtx.testScore.toLocaleString('fa-IR')} / ${EXAM_MAX.toLocaleString('fa-IR')}`}
            />
          )}
          {total != null && (
            <InfoTile
              label="نمره نهایی"
              value={`${total.toLocaleString('fa-IR')} — ${passFail || labelPassFail(total)}`}
              tone={total >= 74 ? '#059669' : '#dc2626'}
              bg={total >= 74 ? '#ecfdf5' : '#fef2f2'}
            />
          )}
        </div>

        <TheorySlaBanner ctx={ctx} startedAt={detail.started_at} currentState={currentState} />

        {hint && (
          <TheoryHintBlock tone={currentState?.includes('delay') ? 'danger' : 'info'}>
            {hint}
          </TheoryHintBlock>
        )}

        {incomplete && (
          <TheoryHintBlock tone="danger">
            به‌دلیل غیبت در آزمون، نمره نهایی ثبت نشده است. باید درس را دوباره بگذرانید.
          </TheoryHintBlock>
        )}

        {currentState === 'final_exam_open' && (
          <div
            style={{
              padding: '1rem',
              marginTop: '0.75rem',
              background: '#f5f3ff',
              borderRadius: '10px',
              borderRight: '4px solid #7c3aed',
            }}
          >
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#5b21b6' }}>
              آزمون تستی آنلاین
            </h4>
            <p style={{ fontSize: '0.85rem', lineHeight: 1.65, margin: '0 0 0.75rem', color: '#334155' }}>
              اتصال LMS در حال تکمیل است. برای تست، نمره آزمون را وارد و دکمه زیر را بزنید.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="number"
                className="form-input"
                min={0}
                max={EXAM_MAX}
                value={demoTestScore}
                onChange={(e) => setDemoTestScore(e.target.value)}
                placeholder={`۰–${EXAM_MAX}`}
                style={{ width: '5rem' }}
              />
              <button
                type="button"
                className="btn btn-primary btn-sm"
                data-testid="theory-student-exam-complete"
                disabled={submitting || !findTransition('exam_completed')}
                onClick={handleExamComplete}
              >
                {submitting ? 'در حال ثبت…' : 'ثبت اتمام آزمون'}
              </button>
            </div>
          </div>
        )}

        {currentState === 'borderline_student_choice' && isBorderline && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem' }}>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              data-testid="theory-student-retake"
              disabled={submitting || !findTransition('retake_selected')}
              onClick={() => triggerTransition('retake_selected', { retake_payment_ack: true })}
            >
              امتحان مجدد (پرداخت)
            </button>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              data-testid="theory-student-repeat-course"
              disabled={submitting || !findTransition('repeat_course_selected')}
              onClick={() => triggerTransition('repeat_course_selected')}
            >
              می‌خواهم درس را دوباره بگذرانم
            </button>
          </div>
        )}

        {currentState === 'retake_exam_open' && (
          <div
            style={{
              padding: '1rem',
              marginTop: '0.75rem',
              background: '#fffbeb',
              borderRadius: '10px',
              borderRight: '4px solid #d97706',
            }}
          >
            <p style={{ fontSize: '0.85rem', margin: '0 0 0.75rem' }}>
              امتحان مجدد — پک جدید:
              {' '}
              {theoryCtx.retakeExamPackId || '—'}
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="number"
                className="form-input"
                min={0}
                max={EXAM_MAX}
                value={demoTestScore}
                onChange={(e) => setDemoTestScore(e.target.value)}
                placeholder="نمره مجدد"
                style={{ width: '5rem' }}
              />
              <button
                type="button"
                className="btn btn-primary btn-sm"
                data-testid="theory-student-retake-complete"
                disabled={submitting || !findTransition('retake_exam_completed')}
                onClick={handleRetakeComplete}
              >
                ثبت اتمام امتحان مجدد
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
