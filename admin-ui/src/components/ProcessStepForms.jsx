import React, { useState, useEffect, useRef, useMemo } from 'react'
import {
  filterFormsForStudent,
  validateStepForms,
} from '../utils/processFormsStudent'
import { applyInstallmentPolicyToForms } from '../utils/installmentPolicyForms'
import { isStepOtpAlreadyVerified } from '../utils/stepOtpVerified'
import { listDocumentResubmitFeedback } from '../utils/documentReviewStates'
import { withStudentAdmissionContext } from '../utils/resolveCourseFieldOptions'
import { studentFormToSchemaJson } from '../utils/formFieldTypes'
import { processExecApi, publicApi } from '../services/api'
import UnifiedFormRenderer from './UnifiedFormRenderer'
import InstallmentPlanTable from './InstallmentPlanTable'
import { previewInstallmentPlan } from '../utils/installmentSchedulePreview'

/**
 * فرم‌های مرحلهٔ دانشجو — پوستهٔ نازک روی UnifiedFormRenderer.
 */
export default function ProcessStepForms({
  forms,
  values,
  onFieldChange,
  disabled,
  onRegisterSubmit,
  hasAvailableTransitions = true,
  instanceId = null,
  resubmitFieldNames = null,
  contextData: contextDataProp = null,
  studentProfile = null,
  extraData = null,
  currentState = null,
}) {
  const contextData = useMemo(
    () => withStudentAdmissionContext(
      contextDataProp,
      studentProfile || (extraData ? { extra_data: extraData } : null),
    ),
    [contextDataProp, studentProfile, extraData],
  )
  const [uploadErr, setUploadErr] = useState(null)
  const [installmentPolicy, setInstallmentPolicy] = useState({ installment_enabled: true })
  const onFieldChangeRef = useRef(onFieldChange)
  onFieldChangeRef.current = onFieldChange

  useEffect(() => {
    let active = true
    publicApi
      .installmentPolicy()
      .then((r) => {
        if (active) setInstallmentPolicy(r.data || { installment_enabled: true })
      })
      .catch(() => {
        if (active) setInstallmentPolicy({ installment_enabled: true })
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    const debt = Number(contextData?.debt_sessions_count)
    if (!Number.isFinite(debt) || debt <= 0) return
    if (values?.debt_settlement_included === true) return
    const hasField = (forms || []).some(
      (f) => Array.isArray(f?.fields) && f.fields.some((ff) => ff?.name === 'debt_settlement_included'),
    )
    const setField = onFieldChangeRef.current
    if (hasField && typeof setField === 'function') {
      setField('debt_settlement_included', true)
    }
  }, [contextData?.debt_sessions_count, values?.debt_settlement_included, forms])

  const list = applyInstallmentPolicyToForms(
    filterFormsForStudent(forms || []),
    installmentPolicy,
    contextData,
  )
  const flatFieldsEarly = list.flatMap((form) => form.fields || [])
  const rulesGateFieldEarly = flatFieldsEarly.find((f) => f.type === 'checkbox' && f.rules_link_href)
  const gateKeyEarly = rulesGateFieldEarly?.name
  const rulesAccepted = !!(gateKeyEarly && values?.[gateKeyEarly])
  const hasStepOtpField = flatFieldsEarly.some((f) => (f.type || '') === 'step_otp')
  const otpAlreadyVerified = isStepOtpAlreadyVerified(values, contextData, currentState)

  useEffect(() => {
    if (!hasStepOtpField || !otpAlreadyVerified) return
    if (values?.step_otp_verified === true) return
    const setField = onFieldChangeRef.current
    if (typeof setField === 'function') setField('step_otp_verified', true)
  }, [hasStepOtpField, otpAlreadyVerified, values?.step_otp_verified])

  useEffect(() => {
    if (!hasStepOtpField || !gateKeyEarly || rulesAccepted) return
    if (isStepOtpAlreadyVerified({}, contextData, currentState)) return
    if (values?.step_otp_verified && typeof onFieldChangeRef.current === 'function') {
      onFieldChangeRef.current('step_otp_verified', false)
    }
  }, [hasStepOtpField, gateKeyEarly, rulesAccepted, values?.step_otp_verified, contextData, currentState])

  useEffect(() => {
    if (installmentPolicy.installment_enabled !== false) return
    if ((contextData || {}).payment_method === 'installment') return
    const setField = onFieldChangeRef.current
    if (typeof setField !== 'function') return
    if (values?.payment_method === 'installment') setField('payment_method', '')
    if (values?.installment_count != null && values.installment_count !== '') setField('installment_count', '')
  }, [
    installmentPolicy.installment_enabled,
    contextData?.payment_method,
    values?.payment_method,
    values?.installment_count,
  ])

  if (list.length === 0) return null

  const validateOpts = {
    resubmitFieldNames: Array.isArray(resubmitFieldNames) && resubmitFieldNames.length
      ? resubmitFieldNames
      : undefined,
    contextData: contextData || undefined,
  }
  const { ok, missing } = validateStepForms(list, values, validateOpts)

  const handleRegisterClick = () => {
    const result = validateStepForms(list, values, validateOpts)
    if (onRegisterSubmit) onRegisterSubmit(result)
  }

  const handleField = (name, v) => {
    onFieldChange(name, v)
    if (name === 'payment_method' && v !== 'installment') {
      if (values?.installment_count != null && values.installment_count !== '') {
        onFieldChange('installment_count', '')
      }
    }
  }

  const handleUploadFile = async (fieldName, file) => {
    if (!instanceId) {
      return { file_name: file.name, size: file.size, mime: file.type }
    }
    const fd = new FormData()
    fd.append('file', file)
    fd.append('field_name', fieldName)
    try {
      const res = await processExecApi.uploadStudentStepFile(instanceId, fd)
      setUploadErr(null)
      return res.data
    } catch (err) {
      const d = err.response?.data?.detail
      const msg = typeof d === 'string' ? d : 'خطا در آپلود فایل'
      setUploadErr(msg)
      throw new Error(msg)
    }
  }

  const partialMode = Array.isArray(resubmitFieldNames) && resubmitFieldNames.length > 0
  const resubmitSet = partialMode ? new Set(resubmitFieldNames) : null
  const lockedInPartial = (field) => {
    if (!partialMode || !resubmitSet) return false
    const t = field?.type || 'text'
    if (t === 'step_otp') return otpAlreadyVerified
    if (t === 'checkbox' && field?.rules_link_href) return !!values?.[field.name]
    return !resubmitSet.has(field?.name)
  }

  const flatFields = list.flatMap((form) => form.fields || [])
  const fieldLabelByName = Object.fromEntries(
    flatFields.filter((f) => f?.name).map((f) => [f.name, f.label_fa || f.name]),
  )
  const rejectionFeedback = listDocumentResubmitFeedback(contextData || {}, fieldLabelByName)
  const rejectionNoteByField = Object.fromEntries(
    rejectionFeedback.items.filter((item) => item.note).map((item) => [item.fieldName, item.note]),
  )
  const showRejectionSummary = partialMode && (
    rejectionFeedback.items.length > 0 || !!rejectionFeedback.generalNote
  )
  const rulesGateField = flatFields.find((f) => f.type === 'checkbox' && f.rules_link_href)
  const gateKey = rulesGateField?.name
  const uploadsBlockedByRules = !!(gateKey && !values?.[gateKey])
  const editableFieldNames = partialMode
    ? flatFields.filter((f) => !lockedInPartial(f)).map((f) => f.name).filter(Boolean)
    : null

  const leadText = partialMode
    ? 'مدارک تأییدشده در زیر برای مرور شما مانده‌اند؛ فقط مواردی که پذیرش برای اصلاح اعلام کرده دوباره بارگذاری کنید؛ سپس «ثبت اطلاعات این مرحله» را بزنید.'
    : hasAvailableTransitions
      ? 'فیلدها را تکمیل کنید، «ثبت اطلاعات این مرحله» را بزنید؛ سپس در صورت وجود، دکمهٔ «ادامه و ثبت مرحله» را بزنید تا به مرحلهٔ بعد بروید (پرداخت یا پیامک در صورت نیاز توسط سامانه انجام می‌شود).'
      : 'فیلدها را تکمیل و ثبت کنید. ادامهٔ مسیر در این مرحله توسط اداری/سیستم انجام می‌شود؛ بعداً صفحه را تازه کنید.'

  const submitHint = !ok
    ? 'موارد الزام را پر کنید و دوباره ثبت کنید.'
    : hasAvailableTransitions
      ? 'پس از ثبت، در صورت وجود دکمهٔ «ادامه و ثبت مرحله»، همان را بزنید.'
      : 'ثبت انجام شد؛ اقدام بعدی از سمت اداری است.'

  const renderFieldAddon = (field, { value: fieldValue }) => {
    if (field.name !== 'installment_count' || !fieldValue) return null
    const tuitionRial = contextData?.tuition_total_rial != null
      ? Number(contextData.tuition_total_rial)
      : (contextData?.invoice_amount != null
        ? Math.round(Number(contextData.invoice_amount) * 10)
        : null)
    const n = parseInt(fieldValue, 10)
    if (!tuitionRial || tuitionRial <= 0 || !(n > 1)) return null
    const registered = Array.isArray(contextData?.installment_plan) ? contextData.installment_plan : []
    const registeredMatches = registered.length === n
      && String(contextData?.installment_count ?? '') === String(n)
    const plan = registeredMatches
      ? registered
      : previewInstallmentPlan({
        totalRial: tuitionRial,
        paymentMethod: 'installment',
        count: n,
        gapDays: installmentPolicy?.term2_installment_gap_days ?? 25,
        baseDueDate: contextData?.term_start_date || null,
      })
    return <InstallmentPlanTable plan={plan} compact title="سررسید و مبلغ هر قسط" />
  }

  return (
    <div className="process-step-forms">
      <h4 className="psf-title">این مرحله</h4>
      <p className="psf-lead">{leadText}</p>
      {showRejectionSummary && (
        <div className="psf-warning" role="status" data-testid="doc-rejection-summary">
          <strong>پذیرش این مدارک را ناقص اعلام کرده است:</strong>
          {rejectionFeedback.items.length > 0 && (
            <ul className="psf-doc-reject-list">
              {rejectionFeedback.items.map((item) => (
                <li key={item.fieldName}>
                  {item.label}
                  {item.note ? ` — ${item.note}` : ''}
                </li>
              ))}
            </ul>
          )}
          {rejectionFeedback.generalNote ? (
            <p className="psf-doc-reject-general">یادداشت پذیرش: {rejectionFeedback.generalNote}</p>
          ) : null}
        </div>
      )}
      {uploadErr && (
        <div className="psf-warning" role="alert">{uploadErr}</div>
      )}
      {uploadsBlockedByRules && (
        <p className="psf-hint psf-hint--warn" style={{ marginTop: 0 }}>
          ابتدا بالای همین فرم، پذیرش قوانین انستیتو را با تیک زدن تأیید کنید؛ سپس بارگذاری فایل فعال می‌شود.
        </p>
      )}
      {list.map((form) => {
        const fields = form.fields || []
        if (partialMode && fields.length && !fields.some((f) => resubmitFieldNames.includes(f.name))) {
          return (
            <div key={form.code || form.name_fa} className="psf-card">
              <p className="psf-note">موردی برای اصلاح در این فرم نیست؛ با پذیرش هماهنگ کنید.</p>
            </div>
          )
        }
        return (
          <div key={form.code || form.name_fa} className="psf-card">
            <div className="psf-card-head">
              <span className="psf-card-title">{form.name_fa || form.code}</span>
            </div>
            {form.note_fa && <p className="psf-note">{form.note_fa}</p>}
            <UnifiedFormRenderer
              audience="student"
              schemaJson={studentFormToSchemaJson(form)}
              values={values || {}}
              onFieldChange={handleField}
              role="student"
              roles={['student']}
              disabled={disabled}
              instanceId={instanceId}
              contextData={contextData}
              onUploadFile={handleUploadFile}
              showToast={(msg) => setUploadErr(msg || null)}
              editableFieldNames={editableFieldNames}
              studentUi={{
                autoRequestOtp: rulesAccepted && !otpAlreadyVerified,
                fileUploadBlocked: uploadsBlockedByRules,
                rejectionNotes: rejectionNoteByField,
                forceChecked: {
                  debt_settlement_included: Number(contextData?.debt_sessions_count) > 0,
                },
                renderFieldAddon,
                previewMode: 'lightbox',
                allowTherapistManualFallback: true,
              }}
            />
          </div>
        )
      })}
      {!ok && (
        <div className="psf-warning" role="status">
          <strong>ناقص:</strong>
          {' '}
          {missing.join('، ')}
        </div>
      )}
      <div className="psf-submit-row">
        <button
          type="button"
          data-testid="quest-step-form-submit"
          className="btn btn-primary psf-submit-btn"
          disabled={disabled}
          onClick={handleRegisterClick}
        >
          ثبت اطلاعات این مرحله
        </button>
        <span className="psf-submit-hint">{submitHint}</span>
      </div>
    </div>
  )
}
