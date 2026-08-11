import React, { useCallback, useEffect, useState } from 'react'
import { processExecApi } from '../services/api'
import { notesPayload } from '../utils/decisionPayload'
import DecisionNotesBlock from './DecisionNotesBlock'
import OperatorInstanceContextSummary from './OperatorInstanceContextSummary'
import {
  canSubmitInterviewResult,
  filterInterviewResultTransitions,
} from '../utils/interviewResultAccess'
import { mergeInterviewResultFormPayload } from '../utils/interviewResultPayload'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import {
  isComprehensiveEvalTrigger,
  mergeInterviewEvaluationPayload,
  validateInterviewEvaluationForm,
} from '../utils/interviewEvaluationPayload'
import { labelProcess, labelState } from '../utils/processDisplay'

const REGISTRATION_CODES = new Set([
  'introductory_course_registration',
  'comprehensive_course_registration',
])

/**
 * ثبت نتیجهٔ مصاحبه در پنل مصاحبه‌گر (بدون ارجاع به StaffPortal).
 */
export default function InterviewerResultPanel({
  user,
  instanceId,
  onClose,
  showToast,
  onAfterTransition,
}) {
  const [loading, setLoading] = useState(true)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')
  const [interviewResultForm, setInterviewResultForm] = useState({ interviewer_notes: '' })
  const [interviewEval, setInterviewEval] = useState({
    evaluation_notes: '',
    rejection_reason: '',
    suggestion_text: '',
  })
  const [busy, setBusy] = useState(false)
  const [registrationGate, setRegistrationGate] = useState(null)

  const reload = useCallback(async () => {
    if (!instanceId) {
      setInstanceDetail(null)
      setAvailableTransitions([])
      setRegistrationGate(null)
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const dashRes = await processExecApi.dashboard(instanceId)
      setInstanceDetail(dashRes.data?.status || null)
      setAvailableTransitions(dashRes.data?.transitions || [])
      setRegistrationGate(dashRes.data?.registration_gate || null)
    } catch (e) {
      console.error(e)
      showToast?.(e.response?.data?.detail || 'خطا در بارگذاری پرونده', 'error')
      setInstanceDetail(null)
      setAvailableTransitions([])
    } finally {
      setLoading(false)
    }
  }, [instanceId, showToast])

  useEffect(() => {
    reload()
  }, [reload])

  const triggerTransition = async (transition) => {
    if (!instanceId || !instanceDetail) return
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    setBusy(true)
    try {
      let payload = notesPayload(decisionNotes)
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
      payload = mergeInterviewResultFormPayload(
        payload,
        interviewResultForm,
        toState,
        triggerEvent,
      )
      if (
        instanceDetail.process_code === 'comprehensive_course_registration'
        && isComprehensiveEvalTrigger(triggerEvent)
      ) {
        const evalError = validateInterviewEvaluationForm(interviewEval, triggerEvent)
        if (evalError) {
          showToast?.(evalError, 'error')
          return
        }
        payload = mergeInterviewEvaluationPayload(payload, interviewEval, triggerEvent)
      }
      if (toState) payload.to_state = toState
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
      })
      if (res.data.success) {
        showToast?.(`نتیجه ثبت شد: ${labelState(res.data.to_state)}`)
        await reload()
        onAfterTransition?.()
      } else {
        showToast?.(res.data.error || 'خطا', 'error')
      }
    } catch (err) {
      showToast?.(err.response?.data?.detail || 'خطا', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!instanceId) return null

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: '1.5rem' }} data-testid="interviewer-result-loading">
        <p className="muted" style={{ padding: '1.25rem', margin: 0 }}>در حال بارگذاری پرونده…</p>
      </div>
    )
  }

  if (!instanceDetail) {
    return (
      <div className="card" style={{ marginBottom: '1.5rem', borderColor: '#fecaca' }} data-testid="interviewer-result-error">
        <p style={{ padding: '1.25rem', margin: 0, color: '#b91c1c' }}>پرونده یافت نشد یا دسترسی ندارید.</p>
        {onClose && (
          <div style={{ padding: '0 1.25rem 1.25rem' }}>
            <button type="button" className="btn btn-outline btn-sm" onClick={onClose}>بستن</button>
          </div>
        )}
      </div>
    )
  }

  const instanceContext = instanceDetail.context_data || {}
  const transitionsForActions = filterInterviewResultTransitions(
    availableTransitions,
    user,
    instanceContext,
  )
  const canSubmit = canSubmitInterviewResult(user, instanceContext)
  const isIntroReg = instanceDetail.process_code === 'introductory_course_registration'
  const introGateClosed =
    isIntroReg && registrationGate && registrationGate.allowed === false
  const isCompReg = instanceDetail.process_code === 'comprehensive_course_registration'
  const showIntroResultForm =
    isIntroReg && instanceDetail.current_state === 'interview_completed' && canSubmit
  const showCompEvalForm =
    isCompReg
    && instanceDetail.current_state === 'interview_completed'
    && canSubmit
    && transitionsForActions.some((t) => isComprehensiveEvalTrigger(t.trigger_event))
  const showInterviewAdvance =
    isIntroReg && instanceDetail.current_state === 'interview_payment_confirmed'
  const interviewTimeReachedTransition = availableTransitions.find(
    (t) => t.trigger_event === 'interview_time_reached',
  )

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }} data-testid="interviewer-result-panel">
      <div className="card-header">
        <h3 className="card-title">
          ثبت نتیجه — {labelProcess(instanceDetail.process_code)}
        </h3>
        {onClose && (
          <button type="button" className="btn btn-outline btn-sm" onClick={onClose}>
            بستن
          </button>
        )}
      </div>

      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
          <div style={{ padding: '0.85rem', background: 'var(--bg)', borderRadius: '8px' }}>
            <div className="muted" style={{ fontSize: '0.72rem' }}>وضعیت</div>
            <div style={{ fontWeight: 700, color: 'var(--primary)' }}>
              {labelState(instanceDetail.current_state)}
            </div>
          </div>
          <div style={{ padding: '0.85rem', background: 'var(--bg)', borderRadius: '8px' }}>
            <div className="muted" style={{ fontSize: '0.72rem' }}>شناسه پرونده</div>
            <div dir="ltr" style={{ fontSize: '0.82rem' }}>{instanceDetail.instance_id || instanceId}</div>
          </div>
        </div>

        {introGateClosed && (
          <div
            role="status"
            data-testid="interviewer-intro-gate-closed"
            style={{
              padding: '0.85rem 1rem',
              marginBottom: '1rem',
              background: '#fffbeb',
              borderRadius: '8px',
              borderRight: '4px solid #d97706',
              fontSize: '0.88rem',
              lineHeight: 1.65,
            }}
          >
            {'ثبت‌نام دورهٔ آشنایی تا انتشار تقویم آموزشی برای دانشجو متوقف است؛ اما ثبت نتیجهٔ مصاحبه از همین‌جا امکان‌پذیر است.'}
          </div>
        )}

        {!canSubmit && REGISTRATION_CODES.has(instanceDetail.process_code) && (
          <div
            style={{
              padding: '0.85rem 1rem',
              marginBottom: '1rem',
              background: '#fffbeb',
              borderRadius: '8px',
              borderRight: '4px solid #f59e0b',
              fontSize: '0.88rem',
              lineHeight: 1.65,
            }}
          >
            ثبت نتیجه فقط برای مصاحبه‌گر همان وقت، ایجادکنندهٔ وقت، یا مدیر سیستم مجاز است. اگر این پرونده به شما
            اختصاص ندارد، با پذیرش هماهنگ کنید.
          </div>
        )}

        <OperatorInstanceContextSummary
          user={user}
          instanceDetail={instanceDetail}
          availableTransitions={availableTransitions}
          title="خلاصه پرونده"
          contextAudience="interviewer"
          showHistory={false}
        />

        {showInterviewAdvance && (
          <div
            style={{
              padding: '1rem',
              marginBottom: '1rem',
              background: '#eff6ff',
              borderRadius: '10px',
              borderRight: '4px solid #2563eb',
            }}
          >
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#1e40af' }}>
              ثبت برگزاری مصاحبه
            </h4>
            <p style={{ fontSize: '0.85rem', lineHeight: 1.65, margin: '0 0 0.75rem', color: '#334155' }}>
              پس از برگزاری مصاحبه، این دکمه را بزنید تا مرحلهٔ ثبت نتیجه باز شود.
            </p>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={busy || !interviewTimeReachedTransition}
              onClick={() => interviewTimeReachedTransition && triggerTransition(interviewTimeReachedTransition)}
            >
              ثبت برگزاری و باز کردن ثبت نتیجه
            </button>
          </div>
        )}

        {showIntroResultForm && (
          <div
            style={{
              padding: '1rem',
              marginBottom: '1rem',
              background: '#faf5ff',
              borderRadius: '10px',
              borderRight: '4px solid #7c3aed',
            }}
          >
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.75rem', color: '#5b21b6' }}>
              یادداشت محرمانه (دوره آشنایی)
            </h4>
            <label style={{ display: 'block', fontSize: '0.88rem' }}>
              <span style={{ fontWeight: 600 }}>یادداشت مصاحبه‌گر (اختیاری)</span>
              <textarea
                className="form-input"
                rows={3}
                style={{ width: '100%', marginTop: '0.35rem' }}
                dir="rtl"
                value={interviewResultForm.interviewer_notes}
                onChange={(e) =>
                  setInterviewResultForm((prev) => ({
                    ...prev,
                    interviewer_notes: e.target.value,
                  }))
                }
              />
            </label>
          </div>
        )}

        {showCompEvalForm && (
          <div
            style={{
              padding: '1rem',
              marginBottom: '1rem',
              background: '#fef2f2',
              borderRadius: '10px',
              borderRight: '4px solid #dc2626',
            }}
          >
            <h4 style={{ fontSize: '0.92rem', fontWeight: 700, marginBottom: '0.5rem', color: '#b91c1c' }}>
              فرم ارزیابی مصاحبهٔ دوره جامع (محرمانه)
            </h4>
            <label style={{ display: 'block', marginBottom: '0.6rem', fontSize: '0.85rem' }}>
              توضیحات ارزیابی (الزامی)
              <textarea
                className="psf-input psf-textarea"
                rows={3}
                style={{ width: '100%', marginTop: '0.35rem' }}
                value={interviewEval.evaluation_notes}
                onChange={(e) => setInterviewEval((prev) => ({ ...prev, evaluation_notes: e.target.value }))}
              />
            </label>
            <label style={{ display: 'block', marginBottom: '0.6rem', fontSize: '0.85rem' }}>
              دلیل رد (محرمانه — در صورت رد)
              <textarea
                className="psf-input psf-textarea"
                rows={2}
                style={{ width: '100%', marginTop: '0.35rem' }}
                value={interviewEval.rejection_reason}
                onChange={(e) => setInterviewEval((prev) => ({ ...prev, rejection_reason: e.target.value }))}
              />
            </label>
            <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.85rem' }}>
              متن پیشنهاد (برای «رد همراه با پیشنهاد»)
              <textarea
                className="psf-input psf-textarea"
                rows={2}
                style={{ width: '100%', marginTop: '0.35rem' }}
                value={interviewEval.suggestion_text}
                onChange={(e) => setInterviewEval((prev) => ({ ...prev, suggestion_text: e.target.value }))}
              />
            </label>
          </div>
        )}

        {transitionsForActions.length > 0 && (
          <div
            style={{
              padding: '1.25rem',
              background: 'var(--info-light, #eff6ff)',
              borderRadius: '10px',
              borderRight: '4px solid var(--info, #2563eb)',
            }}
          >
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem' }}>ثبت نتیجه</h4>
            <DecisionNotesBlock
              value={decisionNotes}
              onChange={setDecisionNotes}
              title="توضیح (اختیاری)"
              hint="متن همراه دکمهٔ نتیجه در پرونده ثبت می‌شود."
            />
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {transitionsForActions
                .filter((t) => !(showInterviewAdvance && t.trigger_event === 'interview_time_reached'))
                .map((t, idx) => {
                  const isApproval =
                    t.trigger_event?.includes('approved')
                    || t.trigger_event?.includes('confirm')
                    || t.trigger_event?.includes('accept')
                    || t.trigger_event?.includes('full_admission')
                    || t.trigger_event?.includes('conditional')
                    || t.trigger_event?.includes('single_course')
                  const isReject =
                    t.trigger_event?.includes('reject')
                    || t.trigger_event?.includes('decline')
                  return (
                    <button
                      key={idx}
                      type="button"
                      disabled={busy || (!canSubmit && isInterviewResultLike(t))}
                      onClick={() => triggerTransition(t)}
                      className="btn btn-sm"
                      style={{
                        background: isApproval ? 'var(--success)' : isReject ? 'var(--danger)' : 'var(--primary)',
                        color: '#fff',
                        border: 'none',
                      }}
                    >
                      {t.description || t.description_fa || t.trigger_event}
                    </button>
                  )
                })}
            </div>
          </div>
        )}

        {transitionsForActions.length === 0 && !showInterviewAdvance && (
          <p className="muted" style={{ fontSize: '0.9rem', lineHeight: 1.65, margin: 0 }}>
            در این مرحله اقدام مصاحبه‌ای برای شما تعریف نشده است.
          </p>
        )}
      </div>
    </div>
  )
}

function isInterviewResultLike(transition) {
  const te = transition?.trigger_event || ''
  return te.includes('interview_result') || te === 'interview_result_submitted'
}
