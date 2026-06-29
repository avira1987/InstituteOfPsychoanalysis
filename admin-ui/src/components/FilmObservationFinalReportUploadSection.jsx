import React, { useState } from 'react'
import { processExecApi } from '../services/api'
import UploadedDocumentsReadonlyGrid from './UploadedDocumentsReadonlyGrid'
import {
  FilmCompletionHintBlock,
  FilmCompletionUploadBanner,
  FINAL_REPORT_FILE_FIELDS,
  FINAL_REPORT_MAX_MB,
  REPORT_MAX,
  fmtIsoDate,
  ReportPdfLink,
} from '../utils/filmObservationCourseCompletionDisplay'
import { parseStepFileUploadValue } from '../utils/uploadPublicUrl'

/**
 * بخش آپلود گزارش پایانی PDF — فرایند ۶۴ (دانشجو).
 */
export default function FilmObservationFinalReportUploadSection({
  instanceId = null,
  detail = null,
  stepFormValues = {},
  onFieldChange = null,
  stepFormLocked = false,
  showToast = null,
  onRefreshInstance = null,
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const [uploading, setUploading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [uploadErr, setUploadErr] = useState(null)

  if (!active || currentState !== 'grades_entry') {
    return null
  }

  const fileValue = stepFormValues?.final_report_pdf ?? ctx.final_report_pdf
  const hasFile = !!parseStepFileUploadValue(fileValue).url
    || !!parseStepFileUploadValue(fileValue).fileName
  const uploadedAt = ctx.final_report_uploaded_at || ctx.report_uploaded_at
  const courseName = stepFormValues?.course_name ?? ctx.course_name ?? ctx.lesson_name

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    setUploadErr(null)
    if (!file) {
      onFieldChange?.('final_report_pdf', null)
      return
    }
    if (file.size > FINAL_REPORT_MAX_MB * 1024 * 1024) {
      const msg = `حداکثر حجم فایل ${FINAL_REPORT_MAX_MB} مگابایت است.`
      setUploadErr(msg)
      showToast?.(msg, 'error')
      return
    }
    const isPdf = file.type === 'application/pdf' || /\.pdf$/i.test(file.name)
    if (!isPdf) {
      const msg = 'فقط فایل PDF مجاز است.'
      setUploadErr(msg)
      showToast?.(msg, 'error')
      return
    }
    if (!instanceId) {
      onFieldChange?.('final_report_pdf', { file_name: file.name, size: file.size, mime: file.type })
      return
    }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('field_name', 'final_report_pdf')
      const res = await processExecApi.uploadStudentStepFile(instanceId, fd)
      onFieldChange?.('final_report_pdf', res.data)
      showToast?.('فایل آپلود شد؛ برای ثبت نهایی دکمه «ثبت گزارش» را بزنید.')
    } catch (err) {
      const d = err?.response?.data?.detail
      const msg = typeof d === 'string' ? d : (err.message || 'خطا در آپلود فایل')
      setUploadErr(msg)
      showToast?.(msg, 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleRegister = async () => {
    if (!instanceId) {
      showToast?.('شناسه پرونده یافت نشد.', 'error')
      return
    }
    if (!hasFile) {
      showToast?.('ابتدا فایل PDF گزارش را آپلود کنید.', 'error')
      return
    }
    setSubmitting(true)
    try {
      const formValues = {
        ...stepFormValues,
        final_report_pdf: fileValue,
        ...(courseName ? { course_name: courseName } : {}),
      }
      await processExecApi.registerStudentStepForms(instanceId, { form_values: formValues })
      showToast?.('گزارش پایانی ثبت شد.')
      onRefreshInstance?.()
    } catch (err) {
      const d = err?.response?.data?.detail
      if (d && typeof d === 'object' && Array.isArray(d.missing)) {
        showToast?.(`موارد ناقص: ${d.missing.join('، ')}`, 'error')
      } else {
        showToast?.(typeof d === 'string' ? d : (err.message || 'خطا در ثبت'), 'error')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (stepFormLocked && hasFile) {
    return (
      <div
        data-testid="film-observation-final-report-upload-section"
        style={{ marginBottom: '0.85rem' }}
      >
        <FilmCompletionUploadBanner ctx={ctx} />
        <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem' }}>
          گزارش ثبت‌شده
          {uploadedAt && (
            <span style={{ fontWeight: 400, color: '#64748b', marginRight: '0.5rem' }}>
              —
              {' '}
              {fmtIsoDate(uploadedAt)}
            </span>
          )}
        </div>
        <UploadedDocumentsReadonlyGrid fields={FINAL_REPORT_FILE_FIELDS} contextData={ctx} />
        <FilmCompletionHintBlock tone="info">
          گزارش ثبت شده است. برای ویرایش، مسئول مربوط باید امکان ویرایش را باز کند.
        </FilmCompletionHintBlock>
      </div>
    )
  }

  return (
    <div
      data-testid="film-observation-final-report-upload-section"
      style={{
        marginBottom: '0.85rem',
        padding: '1rem 1.1rem',
        borderRadius: '10px',
        background: '#faf5ff',
        border: '1px solid #e9d5ff',
        borderRight: '4px solid #7c3aed',
      }}
    >
      <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.92rem', fontWeight: 700, color: '#5b21b6' }}>
        آپلود گزارش پایانی
      </h4>

      <FilmCompletionUploadBanner ctx={ctx} />

      <FilmCompletionHintBlock tone="warn">
        گزارش را فقط به‌صورت PDF آپلود کنید. سقف نمره گزارش برای مدرس:
        {' '}
        {REPORT_MAX.toLocaleString('fa-IR')}
        {' '}
        از ۱۰۰.
      </FilmCompletionHintBlock>

      {courseName && (
        <p className="muted" style={{ fontSize: '0.82rem', margin: '0 0 0.65rem' }}>
          درس:
          {' '}
          <strong>{courseName}</strong>
        </p>
      )}

      {uploadErr && (
        <div className="psf-warning" role="alert" style={{ marginBottom: '0.65rem' }}>
          {uploadErr}
        </div>
      )}

      {hasFile ? (
        <div style={{ marginBottom: '0.75rem' }}>
          <ReportPdfLink fileValue={fileValue} label="پیش‌نمایش گزارش" />
          {fileValue?.file_name && (
            <span style={{ display: 'block', fontSize: '0.8rem', color: '#64748b', marginTop: '0.35rem' }}>
              {fileValue.file_name}
            </span>
          )}
        </div>
      ) : (
        <p className="muted" style={{ fontSize: '0.82rem', margin: '0 0 0.65rem' }}>
          هنوز گزارشی آپلود نشده است.
        </p>
      )}

      {!stepFormLocked && (
        <>
          <div className="psf-field" style={{ marginBottom: '0.75rem' }}>
            <span className="psf-label">گزارش پایانی PDF *</span>
            <input
              type="file"
              accept=".pdf,application/pdf"
              className="psf-file"
              disabled={uploading || submitting}
              onChange={handleFileChange}
              data-testid="film-observation-final-report-file-input"
            />
          </div>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            data-testid="film-observation-final-report-submit"
            disabled={submitting || uploading || !hasFile}
            onClick={handleRegister}
          >
            {submitting ? 'در حال ثبت…' : uploading ? 'در حال آپلود…' : 'ثبت گزارش پایانی'}
          </button>
        </>
      )}
    </div>
  )
}
