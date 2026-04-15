import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { processExecApi } from '../services/api'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import InstanceContextSummary from './InstanceContextSummary'
import DecisionNotesBlock from './DecisionNotesBlock'
import { notesPayload } from '../utils/decisionPayload'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import { resolveUploadPublicUrl, parseStepFileUploadValue } from '../utils/uploadPublicUrl'
import UploadedDocumentsReadonlyGrid, { collectDocumentGalleryFields } from './UploadedDocumentsReadonlyGrid'

/**
 * صف بررسی مدارک ثبت‌نام دوره آشنایی — تأیید یا رد تک‌تک توسط اپراتور پذیرش.
 * @param {{ instance_id: string, student_code: string, student_id: string, process_code: string, current_state: string }[]} queue
 */
export default function DocumentsReviewPanel({ queue, onRefresh, showToast }) {
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [detail, setDetail] = useState(null)
  const [transitions, setTransitions] = useState([])
  const [forms, setForms] = useState([])
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [decisionNotes, setDecisionNotes] = useState('')
  const [acting, setActing] = useState(false)
  const [fieldDecision, setFieldDecision] = useState({})
  const [fieldNotes, setFieldNotes] = useState({})

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

  useEffect(() => {
    if (!documentFileFields.length) {
      setFieldDecision({})
      setFieldNotes({})
      return
    }
    const init = {}
    for (const f of documentFileFields) init[f.name] = 'pending'
    setFieldDecision(init)
    setFieldNotes({})
  }, [selectedInstance, documentFileFields])

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
    if (!documentFileFields.length) {
      showToast?.('فیلد مدرکی در فرم یافت نشد.', 'error')
      return
    }
    if (documentFileFields.some((f) => fieldDecision[f.name] === 'pending')) {
      showToast?.('برای هر مدرک تأیید یا رد را مشخص کنید.', 'error')
      return
    }
    if (documentFileFields.some((f) => fieldDecision[f.name] !== 'approved')) {
      showToast?.('اگر مدرکی رد شده، از دکمهٔ «رد و ارسال به دانشجو» استفاده کنید.', 'error')
      return
    }
    const status = {}
    for (const f of documentFileFields) status[f.name] = 'approved'
    const t = transitions.find((x) => x.trigger_event === 'documents_approved')
    if (!t) {
      showToast?.('ترنزیشن تأیید مدارک در دسترس نیست.', 'error')
      return
    }
    await runTransition(t, { __document_field_status: status })
  }

  const submitRejected = async () => {
    if (!documentFileFields.length) {
      showToast?.('فیلد مدرکی در فرم یافت نشد.', 'error')
      return
    }
    if (documentFileFields.some((f) => fieldDecision[f.name] === 'pending')) {
      showToast?.('برای هر مدرک تأیید یا رد را مشخص کنید.', 'error')
      return
    }
    const rejected = documentFileFields.filter((f) => fieldDecision[f.name] === 'rejected').map((f) => f.name)
    if (rejected.length === 0) {
      showToast?.('حداقل یک مدرک را رد کنید یا از تأیید کامل استفاده کنید.', 'error')
      return
    }
    const status = {}
    const rejectionNotes = {}
    for (const f of documentFileFields) {
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

  const ctxData = detail?.context_data || {}

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
                      contextData={ctxData}
                      fieldStatus={ctxData.__document_field_status}
                    />
                  </div>
                )}

                {canDecide && documentFileFields.length > 0 && (
                  <div style={{ marginBottom: '1.25rem' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.5rem' }}>
                      بررسی تک‌تک مدارک
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      {documentFileFields.map((field) => {
                        const val = ctxData[field.name]
                        const { url, mime, isLocalPlaceholder } = parseStepFileUploadValue(val)
                        const decision = fieldDecision[field.name] || 'pending'
                        const src = url ? resolveUploadPublicUrl(url) : ''
                        const showImage = url && mime.startsWith('image/')
                        const showPdf = url && mime === 'application/pdf'
                        return (
                          <div
                            key={field.name}
                            style={{
                              border: '1px solid #e5e7eb',
                              borderRadius: '10px',
                              padding: '0.85rem',
                              background: '#fafafa',
                            }}
                          >
                            <div style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                              {field.label_fa || field.name}
                            </div>
                            {isLocalPlaceholder && (
                              <p style={{ fontSize: '0.82rem', color: '#b45309', margin: '0 0 0.5rem' }}>
                                فایلی روی سرور ثبت نشده (فقط نام فایل محلی). از دانشجو بخواهید دوباره با اتصال پایدار بارگذاری کند.
                              </p>
                            )}
                            {!url && !isLocalPlaceholder && (
                              <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '0 0 0.5rem' }}>
                                این مدرک هنوز در پرونده ثبت نشده است.
                              </p>
                            )}
                            {showImage && (
                              <a href={src} target="_blank" rel="noopener noreferrer">
                                <img
                                  src={src}
                                  alt={field.label_fa || field.name}
                                  style={{
                                    maxWidth: '100%',
                                    maxHeight: '220px',
                                    borderRadius: '8px',
                                    border: '1px solid #e5e7eb',
                                    display: 'block',
                                    marginBottom: '0.5rem',
                                  }}
                                />
                              </a>
                            )}
                            {showPdf && (
                              <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline" style={{ marginBottom: '0.5rem' }}>
                                باز کردن PDF
                              </a>
                            )}
                            {url && !showImage && !showPdf && (
                              <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline" style={{ marginBottom: '0.5rem' }}>
                                باز کردن فایل
                              </a>
                            )}
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', marginTop: '0.35rem' }}>
                              <span style={{ fontSize: '0.78rem', color: '#64748b' }}>تصمیم:</span>
                              {decision === 'pending' && (
                                <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>هنوز انتخاب نشده</span>
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
                            </div>
                            {decision === 'rejected' && (
                              <label style={{ display: 'block', marginTop: '0.65rem', fontSize: '0.82rem' }}>
                                <span style={{ color: '#64748b' }}>توضیح نقص (اختیاری)</span>
                                <input
                                  type="text"
                                  className="psf-input"
                                  style={{ width: '100%', marginTop: '0.25rem', padding: '0.35rem 0.5rem' }}
                                  dir="rtl"
                                  value={fieldNotes[field.name] || ''}
                                  onChange={(e) =>
                                    setFieldNotes((prev) => ({ ...prev, [field.name]: e.target.value }))
                                  }
                                  disabled={acting}
                                />
                              </label>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                <InstanceContextSummary
                  contextData={detail.context_data}
                  history={detail.history}
                  forms={forms}
                  title="مدارک و داده‌های ثبت‌شده توسط دانشجو"
                  maxHeight="320px"
                  historyMaxHeight="180px"
                />

                {canDecide && documentFileFields.length > 0 && (
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

                {canDecide && documentFileFields.length === 0 && (
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
                    این پرونده در مرحلهٔ «مدارک ناقص» است؛ دانشجو فقط موارد رد شده را دوباره بارگذاری می‌کند. پس از ارسال، دوباره در بخش «در انتظار بررسی» ظاهر می‌شود.
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
