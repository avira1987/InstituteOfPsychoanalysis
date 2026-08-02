import React, { useCallback, useMemo, useState } from 'react'
import { processExecApi } from '../services/api'
import { resolveCompletionContext } from '../utils/introductoryCourseCompletionDisplay'
import { formatStudentCodeDisplay } from '../utils/processDisplay'

/**
 * راهنمای کمیته نظارت برای بررسی گواهی — فرایند ۳۴، state certificate_review.
 */
export default function IntroductoryCourseCompletionReviewPanel({
  detail = null,
  user = null,
  extraData = null,
  studentId = null,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState(null)

  const completion = useMemo(
    () => resolveCompletionContext(ctx, extraData || {}),
    [ctx, extraData],
  )

  const resolvedStudentId = studentId || detail?.student_id || null
  const certDoc = completion.certificateDoc

  const downloadDraftPdf = useCallback(async () => {
    if (!resolvedStudentId || !certDoc?.id) return
    setDownloading(true)
    setDownloadError(null)
    try {
      await processExecApi.downloadStudentDocumentPdf(
        resolvedStudentId,
        certDoc.id,
        'certificate-draft.pdf',
      )
    } catch (_) {
      setDownloadError('دانلود پیش‌نویس PDF ممکن نشد.')
    } finally {
      setDownloading(false)
    }
  }, [resolvedStudentId, certDoc?.id])

  if (
    !detail
    || detail.process_code !== 'introductory_course_completion'
    || currentState !== 'certificate_review'
  ) {
    return null
  }

  const studentLabel = detail.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : null

  const fmtNum = (v) => {
    if (!Number.isFinite(v)) return null
    return v.toLocaleString('fa-IR', { maximumFractionDigits: 1 })
  }

  return (
    <div
      data-testid="intro-completion-certificate-review-panel"
      style={{
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
        background: '#fffbeb',
        borderRadius: '10px',
        borderRight: '4px solid #d97706',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#92400e' }}>
        بررسی گواهی پایان دوره آشنایی (فرایند ۳۴)
      </h4>

      <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
        پیش‌نویس گواهی پایان دوره آشنایی را بررسی کنید. در صورت صحت، انتقال
        {' '}
        <code style={{ fontSize: '0.8rem' }}>committee_approved_certificate</code>
        {' '}
        را بزنید تا مهر و امضای الکترونیکی اعمال و گواهی در پورتال دانشجو قرار گیرد.
        در صورت نیاز به اصلاح، انتقال
        {' '}
        <code style={{ fontSize: '0.8rem' }}>committee_requested_revision</code>
        {' '}
        را انجام دهید.
      </p>

      {studentLabel && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          پروندهٔ دانشجو:
          {' '}
          <strong>{studentLabel}</strong>
        </p>
      )}

      {(completion.totalUnits != null || completion.totalHours != null) && (
        <div
          data-testid="intro-completion-review-units-hours"
          style={{
            marginBottom: '0.75rem',
            padding: '0.65rem 0.85rem',
            borderRadius: '8px',
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            fontSize: '0.82rem',
            lineHeight: 1.65,
            color: '#334155',
          }}
        >
          {fmtNum(completion.totalUnits) && (
            <div>
              <strong>تعداد واحد:</strong>
              {' '}
              {fmtNum(completion.totalUnits)}
            </div>
          )}
          {fmtNum(completion.totalHours) && (
            <div>
              <strong>ساعات آموزشی:</strong>
              {' '}
              {fmtNum(completion.totalHours)}
              {' '}
              (هر واحد ۱۳٫۵ ساعت)
            </div>
          )}
        </div>
      )}

      {certDoc?.id && (
        <div
          data-testid="intro-completion-review-certificate-download"
          style={{ marginBottom: '0.75rem' }}
        >
          <button
            type="button"
            className="btn btn-sm btn-outline"
            disabled={downloading}
            onClick={downloadDraftPdf}
          >
            {downloading ? 'در حال دانلود…' : 'دانلود پیش‌نویس PDF گواهی'}
          </button>
          {downloadError && (
            <p style={{ margin: '0.4rem 0 0', color: '#b91c1c', fontSize: '0.82rem' }}>{downloadError}</p>
          )}
        </div>
      )}

      {completion.certificateDraftPending && !certDoc?.id && (
        <p className="muted" style={{ margin: '0 0 0.5rem', fontSize: '0.82rem' }}>
          پیش‌نویس گواهی در پرونده ثبت شده است؛ جزئیات را در بخش «پرونده و سابقه» بررسی کنید.
        </p>
      )}

      {user?.role && user.role !== 'supervision_committee' && user.role !== 'admin' && (
        <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
          این مرحله معمولاً بر عهدهٔ کمیته نظارت است.
        </p>
      )}
    </div>
  )
}
