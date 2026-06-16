import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { processExecApi } from '../services/api'
import ProcessStepForms from './ProcessStepForms'
import { labelState } from '../utils/processDisplay'
import {
  buildStudentProcessVisitSequence,
  getPastStepsFromVisitSequence,
} from '../utils/studentProcessStepReview'

/**
 * مرور فقط-خواندنی مراحل قبلی؛ وضعیت فرایند در سرور عوض نمی‌شود.
 */
export default function StudentProcessStepReview({
  detail,
  definition,
  title = 'مرور مراحل قبلی',
  /** با کلیک روی chip رودمپ: کد وضعیت برای باز کردن مرور روی همان مرحله */
  focusStateCode = null,
  onFocusConsumed = null,
}) {
  const processCode = detail?.process_code
  const history = detail?.history
  const currentState = detail?.current_state
  const contextData = detail?.context_data || {}
  const instanceId = detail?.instance_id

  const visitFull = useMemo(
    () => buildStudentProcessVisitSequence(history, definition, currentState),
    [history, definition, currentState],
  )
  const pastSteps = useMemo(() => getPastStepsFromVisitSequence(visitFull), [visitFull])
  const canReview = pastSteps.length > 0

  const [reviewActive, setReviewActive] = useState(false)
  const [reviewIndex, setReviewIndex] = useState(0)
  const [reviewForms, setReviewForms] = useState([])
  const [reviewFormsLoading, setReviewFormsLoading] = useState(false)
  const [showEditRequestForm, setShowEditRequestForm] = useState(false)
  const [editReason, setEditReason] = useState('')
  const [editFields, setEditFields] = useState([])
  const [editBusy, setEditBusy] = useState(false)
  const [editMsg, setEditMsg] = useState(null)

  const viewedStateCode = reviewActive ? pastSteps[reviewIndex] : null

  useEffect(() => {
    if (!focusStateCode || !canReview) return
    const idx = pastSteps.indexOf(focusStateCode)
    if (idx < 0) {
      onFocusConsumed?.()
      return
    }
    setReviewActive(true)
    setReviewIndex(idx)
    onFocusConsumed?.()
  }, [focusStateCode, canReview, pastSteps, onFocusConsumed])

  useEffect(() => {
    if (!reviewActive || !processCode || !viewedStateCode) {
      setReviewForms([])
      return
    }
    let cancelled = false
    setReviewFormsLoading(true)
    processExecApi
      .getProcessFormsForState(processCode, viewedStateCode)
      .then((res) => {
        if (!cancelled) setReviewForms(res.data?.forms || [])
      })
      .catch(() => {
        if (!cancelled) setReviewForms([])
      })
      .finally(() => {
        if (!cancelled) setReviewFormsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [reviewActive, processCode, viewedStateCode])

  const stateLabel = useMemo(() => {
    if (!viewedStateCode) return ''
    const st = definition?.states?.find((s) => s.code === viewedStateCode)
    return st?.name_fa || labelState(viewedStateCode)
  }, [viewedStateCode, definition])

  const currentReviewForm = reviewForms[0] || null
  const editableFieldNames = useMemo(() => {
    const fields = currentReviewForm?.fields || []
    const out = []
    for (const f of fields) {
      const name = f?.name
      if (name && !out.includes(name)) out.push(name)
    }
    return out
  }, [currentReviewForm])

  const startReview = useCallback(() => {
    if (!canReview) return
    setReviewActive(true)
    setReviewIndex(Math.max(0, pastSteps.length - 1))
  }, [canReview, pastSteps.length])

  const exitReview = useCallback(() => {
    setReviewActive(false)
    setShowEditRequestForm(false)
  }, [])

  const toggleField = (name) => {
    setEditFields((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]))
  }

  const submitEditRequest = async () => {
    if (!instanceId || !viewedStateCode) return
    if (!editReason.trim()) {
      setEditMsg({ type: 'error', text: 'دلیل درخواست ویرایش را بنویسید.' })
      return
    }
    if (!editFields.length) {
      setEditMsg({ type: 'error', text: 'حداقل یک فیلد را انتخاب کنید.' })
      return
    }
    try {
      setEditBusy(true)
      setEditMsg(null)
      const res = await processExecApi.createEditRequest(instanceId, {
        state_code: viewedStateCode,
        form_code: currentReviewForm?.code || null,
        field_names: editFields,
        reason: editReason.trim(),
      })
      setEditMsg({
        type: 'success',
        text: `درخواست ثبت شد (کد تیکت: ${res.data?.ticket_id || '—'}).`,
      })
      setEditReason('')
      setEditFields([])
      setShowEditRequestForm(false)
    } catch (e) {
      setEditMsg({
        type: 'error',
        text: e.response?.data?.detail || 'خطا در ثبت درخواست ویرایش',
      })
    } finally {
      setEditBusy(false)
    }
  }

  if (!processCode || !detail) return null

  return (
    <div className="student-process-step-review" data-testid="student-process-step-review">
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.5rem',
          flexWrap: 'wrap',
          marginBottom: reviewActive ? '0.85rem' : 0,
        }}
      >
        <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1e293b' }}>{title}</span>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {!reviewActive && (
            <button
              type="button"
              className="btn btn-outline btn-sm student-review-btn student-review-btn-outline"
              data-testid="student-step-review-start"
              disabled={!canReview}
              onClick={startReview}
              title={!canReview ? 'هنوز مرحلهٔ قبلی در تاریخچه ثبت نشده' : undefined}
            >
              مرور مراحل قبلی
            </button>
          )}
          {reviewActive && (
            <>
              <button
                type="button"
                className="btn btn-outline btn-sm student-review-btn student-review-btn-outline"
                data-testid="student-step-review-back"
                disabled={reviewIndex <= 0}
                onClick={() => setReviewIndex((i) => Math.max(0, i - 1))}
              >
                به عقب
              </button>
              <button
                type="button"
                className="btn btn-outline btn-sm student-review-btn student-review-btn-outline"
                data-testid="student-step-review-forward"
                disabled={reviewIndex >= pastSteps.length - 1}
                onClick={() => setReviewIndex((i) => Math.min(pastSteps.length - 1, i + 1))}
              >
                به جلو
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm student-review-btn student-review-btn-primary"
                data-testid="student-step-review-current"
                onClick={exitReview}
              >
                مرحلهٔ جاری (خروج از مرور)
              </button>
            </>
          )}
        </div>
      </div>

      {reviewActive && (
        <>
          <p className="student-review-text" style={{ margin: '0 0 0.65rem', fontSize: '0.82rem', lineHeight: 1.65 }}>
            فقط مشاهده — وضعیت فرایند عوض نمی‌شود. مرحلهٔ {reviewIndex + 1} از {pastSteps.length} مرحلهٔ قبلی؛
            {' '}
            <strong>{stateLabel}</strong>
          </p>
          {reviewFormsLoading && (
            <p className="student-review-subtext" style={{ fontSize: '0.85rem' }}>در حال بارگذاری فرم این مرحله…</p>
          )}
          {!reviewFormsLoading && (
            <ProcessStepForms
              forms={reviewForms}
              values={contextData}
              onFieldChange={() => {}}
              disabled
              hasAvailableTransitions={false}
              instanceId={instanceId}
              contextData={contextData}
            />
          )}
          {!reviewFormsLoading && editableFieldNames.length > 0 && (
            <div style={{ marginTop: '0.75rem' }}>
              <button
                type="button"
                className="btn btn-outline btn-sm student-review-btn student-review-btn-outline"
                onClick={() => {
                  setShowEditRequestForm((x) => !x)
                  setEditMsg(null)
                }}
              >
                درخواست ویرایش این مرحله
              </button>
            </div>
          )}
          {showEditRequestForm && editableFieldNames.length > 0 && (
            <div style={{ marginTop: '0.65rem', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '0.75rem' }}>
              <p className="student-review-subtext" style={{ fontSize: '0.82rem', marginBottom: '0.4rem' }}>
                فیلد(های) نیازمند ویرایش را انتخاب کنید:
              </p>
              <div style={{ display: 'grid', gap: '0.35rem', marginBottom: '0.6rem' }}>
                {editableFieldNames.map((name) => (
                  <label key={name} style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                    <input type="checkbox" checked={editFields.includes(name)} onChange={() => toggleField(name)} />
                    <span>{name}</span>
                  </label>
                ))}
              </div>
              <textarea
                className="psf-input"
                rows={3}
                value={editReason}
                onChange={(e) => setEditReason(e.target.value)}
                placeholder="دلیل درخواست ویرایش را بنویسید"
              />
              <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button type="button" className="btn btn-primary btn-sm" disabled={editBusy} onClick={submitEditRequest}>
                  {editBusy ? 'در حال ثبت...' : 'ثبت درخواست ویرایش'}
                </button>
              </div>
            </div>
          )}
          {editMsg && (
            <p style={{ marginTop: '0.55rem', color: editMsg.type === 'error' ? '#b91c1c' : '#166534', fontSize: '0.83rem' }}>
              {editMsg.text}
            </p>
          )}
          {!reviewFormsLoading && (!reviewForms || reviewForms.length === 0) && (
            <p className="student-review-subtext" style={{ fontSize: '0.85rem', marginTop: '0.35rem' }}>
              برای این مرحله فرم دانشجو تعریف نشده؛ جزئیات در بخش «پرونده و سابقه» همان صفحه دیده می‌شود.
            </p>
          )}
        </>
      )}
    </div>
  )
}
