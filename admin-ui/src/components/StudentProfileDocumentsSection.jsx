import React, { useEffect, useMemo, useState } from 'react'
import { processExecApi } from '../services/api'
import { filterFormsForStudent } from '../utils/processFormsStudent'
import UploadedDocumentsReadonlyGrid, { collectDocumentGalleryFields } from './UploadedDocumentsReadonlyGrid'
import { parseStepFileUploadValue } from '../utils/uploadPublicUrl'

/**
 * تب پروفایل: مدارک بارگذاری‌شدهٔ مسیر اصلی (از context نمونهٔ فرایند) حتی پس از تأیید پذیرش.
 */
export default function StudentProfileDocumentsSection({ instanceId }) {
  const [loading, setLoading] = useState(false)
  const [contextData, setContextData] = useState(null)
  const [processCode, setProcessCode] = useState(null)
  const [forms, setForms] = useState([])

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!instanceId) {
        setContextData(null)
        setProcessCode(null)
        setForms([])
        return
      }
      setLoading(true)
      try {
        const dashRes = await processExecApi.dashboard(instanceId)
        if (cancelled) return
        const st = dashRes.data?.status
        setContextData(st?.context_data ?? null)
        setProcessCode(st?.process_code || null)
      } catch {
        if (!cancelled) {
          setContextData(null)
          setProcessCode(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [instanceId])

  useEffect(() => {
    let cancelled = false
    async function loadForms() {
      if (!processCode) {
        setForms([])
        return
      }
      try {
        const r = await processExecApi.getProcessFormsForState(processCode, 'documents_upload')
        if (cancelled) return
        setForms(filterFormsForStudent(r.data?.forms || []))
      } catch {
        if (!cancelled) setForms([])
      }
    }
    loadForms()
    return () => {
      cancelled = true
    }
  }, [processCode])

  const galleryFields = useMemo(() => collectDocumentGalleryFields(forms), [forms])

  const hasAnyDoc = useMemo(() => {
    if (!contextData || typeof contextData !== 'object' || !galleryFields.length) return false
    return galleryFields.some((f) => {
      const v = contextData[f.name]
      if (f.type === 'sms_verification') return v != null && String(v).trim() !== ''
      const { url, isLocalPlaceholder } = parseStepFileUploadValue(v)
      return !!(url || isLocalPlaceholder)
    })
  }, [contextData, galleryFields])

  if (!instanceId) return null

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">مدارک بارگذاری‌شده در مسیر ثبت‌نام</h3>
        <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.9rem', lineHeight: 1.65, maxWidth: '48rem' }}>
          تصاویر و فایل‌هایی که در مرحلهٔ مدارک ارسال کرده‌اید اینجا برای مرور شما باقی می‌ماند؛ پس از تأیید پذیرش هم حذف نمی‌شوند.
        </p>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        {loading && <p className="muted" style={{ margin: 0 }}>در حال بارگذاری…</p>}
        {!loading && !hasAnyDoc && (
          <p className="muted" style={{ margin: 0, fontSize: '0.9rem' }}>
            هنوز مدرکی در پروندهٔ فرایند ثبت نشده یا مسیر به نمونهٔ فرایند وصل نیست.
          </p>
        )}
        {!loading && hasAnyDoc && (
          <UploadedDocumentsReadonlyGrid
            fields={galleryFields}
            contextData={contextData}
            fieldStatus={contextData?.__document_field_status}
          />
        )}
      </div>
    </div>
  )
}
