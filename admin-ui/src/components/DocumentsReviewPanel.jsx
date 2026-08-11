import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { processExecApi } from '../services/api'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import { useAuth } from '../contexts/AuthContext'
import OperatorInstanceContextSummary from './OperatorInstanceContextSummary'
import DecisionNotesBlock from './DecisionNotesBlock'
import { notesPayload } from '../utils/decisionPayload'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import { resolveUploadPublicUrl, parseStepFileUploadValue } from '../utils/uploadPublicUrl'
import UploadedDocumentsReadonlyGrid, { collectDocumentGalleryFields } from './UploadedDocumentsReadonlyGrid'
import DocumentPreviewLightbox, { buildDocumentPreviewItems } from './DocumentPreviewLightbox'

/** آیا برای فیلد file_upload محتوایی (آپلود واقعی یا placeholder) ثبت شده؟ */
function fieldHasUploadedContent(val) {
  const { url, isLocalPlaceholder, fileName } = parseStepFileUploadValue(val)
  return !!(url || isLocalPlaceholder || (fileName && String(fileName).trim()))
}

/**
 * مدارک اجباری همیشه نیاز به تصمیم دارند.
 * مدارک اختیاری فقط وقتی محتوا آپلود شده باشد تأیید/رد می‌خواهند.
 */
function fieldNeedsReviewDecision(field, ctxData) {
  if (field?.required) return true
  return fieldHasUploadedContent((ctxData || {})[field?.name])
}

/**
 * صف بررسی مدارک ثبت‌نام دوره آشنایی — تأیید یا رد تک‌تک توسط اپراتور پذیرش.
 * @param {{ instance_id: string, student_code: string, student_id: string, process_code: string, current_state: string }[]} queue
 */
export default function DocumentsReviewPanel({ queue, onRefresh, showToast }) {
  const { user } = useAuth()
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [detail, setDetail] = useState(null)
  const [transitions, setTransitions] = useState([])
  const [forms, setForms] = useState([])
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [decisionNotes, setDecisionNotes] = useState('')
  const [acting, setActing] = useState(false)
  const [fieldDecision, setFieldDecision] = useState({})
  const [fieldNotes, setFieldNotes] = useState({})
  const [lightboxIndex, setLightboxIndex] = useState(null)

  const loadDetail = useCallback(
    async (instanceId) => {
      if (!instanceId) {
        setDetail(null)
        setTransitions([])
        setForms([])
        return
      }
      setLoadingDetail(true)
      try {
        const dashRes = await processExecApi.dashboard(instanceId)
        setDetail(dashRes.data?.status || null)
        setTransitions(dashRes.data?.transitions || [])
        setForms(dashRes.data?.forms || [])
      } catch (e) {
        const d = e.response?.data?.detail
        showToast?.(typeof d === 'string' ? d : 'خطا در بارگذاری جزئیات پرونده', 'error')
        setDetail(null)
        setTransitions([])
        setForms([])
      } finally {
        setLoadingDetail(false)
      }
    },
    [showToast],
  )

  useEffect(() => {
    if (selectedInstance) loadDetail(selectedInstance)
    else {
      setDetail(null)
      setTransitions([])
      setForms([])
      setLightboxIndex(null)
    }
  }, [selectedInstance, loadDetail])

  const documentFileFields = useMemo(() => {
    const out = []
    for (const f of forms || []) {
      for (const field of f.fields || []) {
        if ((field.type || '') === 'file_upload' && field.name) out.push(field)
      }
    }
    return out
  }, [forms])

  const documentGalleryFields = useMemo(() => collectDocumentGalleryFields(forms || []), [forms])

  const ctxDataForInit =
    detail?.context_data && typeof detail.context_data === 'object' ? detail.context_data : null

  const reviewableDocumentFields = useMemo(
    () => documentFileFields.filter((f) => fieldNeedsReviewDecision(f, ctxDataForInit)),
    [documentFileFields, ctxDataForInit],
  )

  useEffect(() => {
    if (!documentFileFields.length) {
      setFieldDecision({})
      setFieldNotes({})
      return
    }
    // پس از ارسال مجدد، وضعیت «تأیید شده» برای مدارک قبلی حفظ می‌شود؛
    // فقط موارد جدید/رد شده دوباره pending می‌مانند تا دکمهٔ تأیید/رد معنا داشته باشد.
    // مدارک اختیاری بدون آپلود: skipped — نیاز به تأیید/رد ندارند.
    const prevStatus =
      ctxDataForInit && typeof ctxDataForInit === 'object'
        ? ctxDataForInit.__document_field_status
        : null
    const init = {}
    for (const f of documentFileFields) {
      if (!fieldNeedsReviewDecision(f, ctxDataForInit)) {
        init[f.name] = 'skipped'
        continue
      }
      init[f.name] =
        prevStatus && typeof prevStatus === 'object' && prevStatus[f.name] === 'approved'
          ? 'approved'
          : 'pending'
    }
    setFieldDecision(init)
    setFieldNotes({})
  }, [selectedInstance, documentFileFields, detail?.current_state, ctxDataForInit])

  const runTransition = async (transition, extraPayload = {}) => {
    if (!selectedInstance) return
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    setActing(true)
    try {
      let payload = { ...notesPayload(decisionNotes), ...extraPayload }
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
      if (toState) payload.to_state = toState
      const res = await processExecApi.trigger(selectedInstance, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
      })
      if (res.data.success) {
        showToast?.(`ثبت شد — وضعیت جدید: ${labelState(res.data.to_state)}`)
        setDecisionNotes('')
        setSelectedInstance(null)
        await onRefresh?.()
      } else {
        showToast?.(res.data.error || 'ترنزیشن انجام نشد', 'error')
      }
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در ثبت تصمیم', 'error')
    } finally {
      setActing(false)
    }
  }

  const submitAllApproved = async () => {
    if (!reviewableDocumentFields.length) {
      showToast?.('فیلد مدرکی قابل بررسی در فرم یافت نشد.', 'error')
      return
    }
    if (reviewableDocumentFields.some((f) => fieldDecision[f.name] === 'pending')) {
      showToast?.('برای هر مدرک آپلودشده (و همهٔ مدارک اجباری) تأیید یا رد را مشخص کنید.', 'error')
      return
    }
    if (reviewableDocumentFields.some((f) => fieldDecision[f.name] !== 'approved')) {
      showToast?.('اگر مدرکی رد شده، از دکمهٔ «رد و ارسال به دانشجو» استفاده کنید.', 'error')
      return
    }
    const status = {}
    for (const f of reviewableDocumentFields) status[f.name] = 'approved'
    const t = transitions.find((x) => x.trigger_event === 'documents_approved')
    if (!t) {
      showToast?.('ترنزیشن تأیید مدارک در دسترس نیست.', 'error')
      return
    }
    await runTransition(t, { __document_field_status: status })
  }

  const submitRejected = async () => {
    if (!reviewableDocumentFields.length) {
      showToast?.('فیلد مدرکی قابل بررسی در فرم یافت نشد.', 'error')
      return
    }
    if (reviewableDocumentFields.some((f) => fieldDecision[f.name] === 'pending')) {
      showToast?.('برای هر مدرک آپلودشده (و همهٔ مدارک اجباری) تأیید یا رد را مشخص کنید.', 'error')
      return
    }
    const rejected = reviewableDocumentFields
      .filter((f) => fieldDecision[f.name] === 'rejected')
      .map((f) => f.name)
    if (rejected.length === 0) {
      showToast?.('حداقل یک مدرک را رد کنید یا از تأیید کامل استفاده کنید.', 'error')
      return
    }
    const status = {}
    const rejectionNotes = {}
    for (const f of reviewableDocumentFields) {
      status[f.name] = fieldDecision[f.name] === 'rejected' ? 'rejected' : 'approved'
      if (fieldDecision[f.name] === 'rejected') {
        const n = (fieldNotes[f.name] || '').trim()
        if (n) rejectionNotes[f.name] = n
      }
    }
    const t = transitions.find((x) => x.trigger_event === 'documents_rejected')
    if (!t) {
      showToast?.('ترنزیشن رد مدارک در دسترس نیست.', 'error')
      return
    }
    const extra = {
      __documents_resubmit_fields: rejected,
      __document_field_status: status,
      ...(Object.keys(rejectionNotes).length ? { __document_field_rejection_notes: rejectionNotes } : {}),
    }
    await runTransition(t, extra)
  }

  const waitingReview = queue.filter((q) => q.current_state === 'documents_review')
  const waitingResubmit = queue.filter((q) => q.current_state === 'documents_incomplete')

  const canDecide =
    detail &&
    detail.current_state === 'documents_review' &&
    transitions.some(
      (t) =>
        t.trigger_event === 'documents_approved' || t.trigger_event === 'documents_rejected',
    )

  const ctxData = detail?.context_data && typeof detail.context_data === 'object' ? detail.context_data : null

  const reviewPreviewItems = useMemo(
    () => buildDocumentPreviewItems(documentFileFields, ctxData || {}, resolveUploadPublicUrl, parseStepFileUploadValue),
    [documentFileFields, ctxData],
  )

  const openReviewPreview = (fieldName) => {
    const idx = reviewPreviewItems.findIndex((p) => p.fieldName === fieldName || p.id === fieldName)
    if (idx >= 0) setLightboxIndex(idx)
  }

  const decidedCount = reviewableDocumentFields.filter(
    (f) => fieldDecision[f.name] && fieldDecision[f.name] !== 'pending',
  ).length
  const approvedCount = reviewableDocumentFields.filter((f) => fieldDecision[f.name] === 'approved').length
  const rejectedCount = reviewableDocumentFields.filter((f) => fieldDecision[f.name] === 'rejected').length

  return (
    <div>
      <div className="card" style={{ marginBottom: '1.25rem' }}>
        <div className="card-header">
          <h3 className="card-title">بررسی مدارک ثبت‌نام (دوره آشنایی)</h3>
          <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.92rem', lineHeight: 1.65, maxWidth: '48rem' }}>
            برای هر مدرک تصویر را ببینید و جداگانه تأیید یا رد کنید. در صورت رد، دانشجو فقط همان موارد را دوباره بارگذاری می‌کند.
          </p>
        </div>
      </div>

      <div className="stats-grid" style={{ marginBottom: '1.25rem' }}>
        <div className="stat-card">
          <div className="stat-icon warning">📋</div>
          <div>
            <div className="stat-value">{waitingReview.length}</div>
            <div className="stat-label">در انتظار بررسی</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon info">⏳</div>
          <div>
            <div className="stat-value">{waitingResubmit.length}</div>
            <div className="stat-label">مدارک ناقص — انتظار ارسال مجدد</div>
          </div>
        </div>
      </div>

      {waitingReview.length === 0 && waitingResubmit.length === 0 && (
        <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
          <p className="muted" style={{ margin: 0 }}>پرونده‌ای در این صف نیست.</p>
        </div>
      )}

      {(waitingReview.length > 0 || waitingResubmit.length > 0) && (
        <div className="card" style={{ marginBottom: '1.25rem' }}>
          <div className="card-header">
            <h4 className="card-title" style={{ fontSize: '1rem' }}>فهرست پرونده‌ها</h4>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.88rem' }}>
              <thead>
                <tr>
                  <th>کد دانشجویی</th>
                  <th>وضعیت</th>
                  <th>فرایند</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {queue.map((row) => (
                  <tr key={row.instance_id}>
                    <td>{formatStudentCodeDisplay(row.student_code)}</td>
                    <td>{labelState(row.current_state)}</td>
                    <td>{labelProcess(row.process_code)}</td>
                    <td>
                      <button
                        type="button"
                        className={`btn btn-sm ${selectedInstance === row.instance_id ? 'btn-primary' : 'btn-outline'}`}
                        onClick={() =>
                          setSelectedInstance(
                            selectedInstance === row.instance_id ? null : row.instance_id,
                          )
                        }
                      >
                        {selectedInstance === row.instance_id ? 'بستن جزئیات' : 'مشاهده و تصمیم'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedInstance && (
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
            <h4 className="card-title" style={{ fontSize: '1rem', margin: 0 }}>جزئیات پرونده</h4>
            {loadingDetail && <span className="muted" style={{ fontSize: '0.85rem' }}>در حال بارگذاری…</span>}
          </div>
          <div style={{ padding: '0 1.25rem 1.25rem' }}>
            {detail && !loadingDetail && (
              <>
                <p style={{ fontSize: '0.88rem', marginBottom: '0.75rem' }}>
                  <strong>مرحله فعلی:</strong> {labelState(detail.current_state)}
                </p>

                {!canDecide && documentGalleryFields.length > 0 && (
                  <div style={{ marginBottom: '1.25rem' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.5rem' }}>
                      مدارک بارگذاری‌شده توسط دانشجو
                    </div>
                    <UploadedDocumentsReadonlyGrid
                      fields={documentGalleryFields}
                      contextData={ctxData || {}}
                      fieldStatus={ctxData?.__document_field_status}
                    />
                  </div>
                )}

                {canDecide && documentFileFields.length > 0 && (
                  <div style={{ marginBottom: '1.25rem' }}>
                    <div className="doc-review-toolbar">
                      <div>
                        <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#1e293b' }}>
                          بررسی تک‌تک مدارک
                        </div>
                        <p className="muted" style={{ margin: '0.25rem 0 0', fontSize: '0.82rem' }}>
                          روی تصویر کلیک کنید تا بزرگ شود؛ سپس تأیید یا رد را مشخص کنید.
                          مدارک اختیاری فقط در صورت آپلود نیاز به تصمیم دارند.
                        </p>
                      </div>
                      <div className="doc-review-progress">
                        <span>{decidedCount} از {reviewableDocumentFields.length} تصمیم‌گرفته</span>
                        {approvedCount > 0 && <span className="doc-review-progress__ok">{approvedCount} تأیید</span>}
                        {rejectedCount > 0 && <span className="doc-review-progress__bad">{rejectedCount} رد</span>}
                      </div>
                    </div>
                    <div className="doc-review-list">
                      {documentFileFields.map((field) => {
                        const val = (ctxData || {})[field.name]
                        const { url, mime, isLocalPlaceholder, fileName } = parseStepFileUploadValue(val)
                        const decision = fieldDecision[field.name] || 'pending'
                        const needsDecision = decision !== 'skipped' && fieldNeedsReviewDecision(field, ctxData)
                        const src = url ? resolveUploadPublicUrl(url) : ''
                        const showImage = url && mime.startsWith('image/')
                        const showPdf = url && mime === 'application/pdf'
                        const label = field.label_fa || field.name
                        const isOptional = !field.required
                        return (
                          <div
                            key={field.name}
                            className={`doc-review-card ${decision === 'approved' ? 'is-approved' : ''} ${decision === 'rejected' ? 'is-rejected' : ''} ${decision === 'skipped' ? 'is-skipped' : ''}`}
                          >
                            <div className="doc-review-card__preview">
                              {showImage && (
                                <button
                                  type="button"
                                  className="doc-gallery__thumb doc-gallery__thumb--lg"
                                  onClick={() => openReviewPreview(field.name)}
                                  aria-label={`پیش‌نمایش ${label}`}
                                >
                                  <img src={src} alt={label} />
                                  <span className="doc-gallery__thumb-overlay">
                                    <span>بزرگ‌نمایی</span>
                                  </span>
                                </button>
                              )}
                              {showPdf && (
                                <button
                                  type="button"
                                  className="doc-gallery__file-tile doc-gallery__file-tile--lg"
                                  onClick={() => openReviewPreview(field.name)}
                                >
                                  <span className="doc-gallery__file-icon">PDF</span>
                                  <span>پیش‌نمایش PDF</span>
                                </button>
                              )}
                              {url && !showImage && !showPdf && (
                                <button
                                  type="button"
                                  className="doc-gallery__file-tile doc-gallery__file-tile--lg"
                                  onClick={() => openReviewPreview(field.name)}
                                >
                                  <span className="doc-gallery__file-icon">فایل</span>
                                  <span>مشاهده فایل</span>
                                </button>
                              )}
                              {isLocalPlaceholder && (
                                <p className="doc-gallery__hint doc-gallery__hint--warn">
                                  فایلی روی سرور ثبت نشده (فقط نام فایل محلی). از دانشجو بخواهید دوباره با اتصال پایدار بارگذاری کند.
                                </p>
                              )}
                              {!url && !isLocalPlaceholder && (
                                <p className="doc-gallery__hint">
                                  {isOptional
                                    ? 'اختیاری — فایل آپلود نشده؛ نیاز به تأیید/رد ندارد.'
                                    : 'این مدرک هنوز در پرونده ثبت نشده است.'}
                                </p>
                              )}
                            </div>

                            <div className="doc-review-card__body">
                              <div className="doc-review-card__title">
                                {label}
                                {isOptional && (
                                  <span className="doc-review-card__optional-badge"> اختیاری</span>
                                )}
                              </div>
                              {fileName && <div className="doc-gallery__filename" title={fileName}>{fileName}</div>}

                              {needsDecision ? (
                                <>
                                  <div className="doc-review-card__actions">
                                    <span className="doc-review-card__decision-label">تصمیم:</span>
                                    {decision === 'pending' && (
                                      <span className="doc-review-card__pending">هنوز انتخاب نشده</span>
                                    )}
                                    <button
                                      type="button"
                                      className={`btn btn-sm ${decision === 'approved' ? 'btn-primary' : 'btn-outline'}`}
                                      disabled={acting}
                                      onClick={() => setFieldDecision((prev) => ({ ...prev, [field.name]: 'approved' }))}
                                    >
                                      تأیید
                                    </button>
                                    <button
                                      type="button"
                                      className={`btn btn-sm ${decision === 'rejected' ? 'btn-primary' : 'btn-outline'}`}
                                      style={
                                        decision === 'rejected'
                                          ? { borderColor: 'var(--danger, #dc2626)', color: '#fff', background: 'var(--danger, #dc2626)' }
                                          : { borderColor: 'var(--danger, #dc2626)', color: 'var(--danger, #dc2626)' }
                                      }
                                      disabled={acting}
                                      onClick={() => setFieldDecision((prev) => ({ ...prev, [field.name]: 'rejected' }))}
                                    >
                                      رد
                                    </button>
                                    {url && (
                                      <button
                                        type="button"
                                        className="btn btn-sm btn-outline"
                                        onClick={() => openReviewPreview(field.name)}
                                      >
                                        پیش‌نمایش
                                      </button>
                                    )}
                                  </div>

                                  {decision === 'rejected' && (
                                    <label className="doc-review-card__note">
                                      <span>توضیح نقص (اختیاری)</span>
                                      <input
                                        type="text"
                                        className="psf-input"
                                        dir="rtl"
                                        value={fieldNotes[field.name] || ''}
                                        onChange={(e) =>
                                          setFieldNotes((prev) => ({ ...prev, [field.name]: e.target.value }))
                                        }
                                        disabled={acting}
                                        placeholder="مثلاً تصویر تار است یا ناقص است"
                                      />
                                    </label>
                                  )}
                                </>
                              ) : (
                                <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '0.82rem' }}>
                                  آپلود نشده — از صف تأیید/رد خارج است.
                                </p>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                <OperatorInstanceContextSummary
                  user={user}
                  instanceDetail={detail}
                  availableTransitions={transitions}
                  forms={forms}
                  studentCode={detail?.student_code}
                  title="مدارک و داده‌های ثبت‌شده توسط دانشجو"
                  maxHeight="320px"
                  historyMaxHeight="180px"
                />

                {canDecide && reviewableDocumentFields.length > 0 && (
                  <>
                    <div style={{ marginTop: '1.25rem' }}>
                      <DecisionNotesBlock
                        value={decisionNotes}
                        onChange={setDecisionNotes}
                        title="یادداشت پذیرش (اختیاری)"
                        hint="در صورت رد یا تأیید، می‌توانید توضیح کوتاه ثبت کنید؛ همراه تصمیم در پرونده ذخیره می‌شود."
                      />
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginTop: '1rem' }}>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={acting}
                        onClick={submitAllApproved}
                      >
                        تأیید همهٔ مدارک و ادامه
                      </button>
                      <button
                        type="button"
                        className="btn btn-outline"
                        style={{ borderColor: 'var(--danger, #dc2626)', color: 'var(--danger, #dc2626)' }}
                        disabled={acting}
                        onClick={submitRejected}
                      >
                        رد موارد انتخاب‌شده و ارسال به دانشجو
                      </button>
                    </div>
                  </>
                )}

                {canDecide && reviewableDocumentFields.length === 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginTop: '1rem' }}>
                    {transitions
                      .filter((t) =>
                        ['documents_approved', 'documents_rejected'].includes(t.trigger_event),
                      )
                      .map((t, idx) => (
                        <button
                          key={`${t.trigger_event}-${idx}`}
                          type="button"
                          className={
                            t.trigger_event === 'documents_approved' ? 'btn btn-primary' : 'btn btn-outline'
                          }
                          style={
                            t.trigger_event === 'documents_rejected'
                              ? { borderColor: 'var(--danger, #dc2626)', color: 'var(--danger, #dc2626)' }
                              : undefined
                          }
                          disabled={acting}
                          onClick={() => runTransition(t)}
                        >
                          {t.description_fa || t.trigger_event}
                        </button>
                      ))}
                  </div>
                )}

                {detail.current_state === 'documents_incomplete' && (
                  <p style={{ marginTop: '1rem', fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                    این پرونده در مرحلهٔ «مدارک ناقص» است؛ دانشجو فقط موارد رد شده را دوباره بارگذاری می‌کند.
                    پس از ثبت مدارک جدید توسط دانشجو، پرونده به‌صورت خودکار به «در انتظار بررسی» برمی‌گردد و دکمه‌های تأیید/رد دوباره ظاهر می‌شوند.
                    اگر دانشجو قبلاً بارگذاری کرده ولی هنوز اینجا مانده، صفحه را تازه کنید یا از او بخواهید پس از باز شدن ویرایش، دوباره «ثبت» را بزند.
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      )}

      <DocumentPreviewLightbox
        open={lightboxIndex != null}
        items={reviewPreviewItems}
        index={lightboxIndex ?? 0}
        onClose={() => setLightboxIndex(null)}
        onIndexChange={setLightboxIndex}
      />
    </div>
  )
}
