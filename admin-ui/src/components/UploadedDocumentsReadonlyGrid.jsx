import React, { useMemo, useState } from 'react'
import { parseStepFileUploadValue, resolveUploadPublicUrl } from '../utils/uploadPublicUrl'
import DocumentPreviewLightbox, { buildDocumentPreviewItems } from './DocumentPreviewLightbox'

/**
 * نمایش فقط‌خواندنی مدارک از روی context_data (پروفایل دانشجو / مشاهدهٔ کارمند).
 * @param {{ name: string, label_fa?: string, type?: string }[]} fields
 * @param {Record<string, unknown>} contextData
 * @param {Record<string, string>|null} [fieldStatus] — مثلاً __document_field_status از پرونده
 */
export default function UploadedDocumentsReadonlyGrid({ fields, contextData, fieldStatus }) {
  const [lightboxIndex, setLightboxIndex] = useState(null)
  const ctx = contextData && typeof contextData === 'object' ? contextData : {}

  const previewItems = useMemo(
    () => buildDocumentPreviewItems(fields, contextData, resolveUploadPublicUrl, parseStepFileUploadValue),
    [fields, contextData],
  )

  const openPreviewForField = (fieldName) => {
    const idx = previewItems.findIndex((p) => p.fieldName === fieldName || p.id === fieldName)
    if (idx >= 0) setLightboxIndex(idx)
  }

  if (!Array.isArray(fields) || fields.length === 0) return null

  return (
    <>
      <div className="doc-gallery">
        {fields.map((field) => {
          const name = field.name
          const label = field.label_fa || name
          const t = field.type || 'text'
          const raw = ctx[name]
          const st = fieldStatus && typeof fieldStatus === 'object' ? fieldStatus[name] : null

          if (t === 'checkbox' && field.show_in_document_summary) {
            const ok = !!raw
            return (
              <div key={name} className="doc-gallery__card doc-gallery__card--check">
                <div className="doc-gallery__meta">
                  <div className="doc-gallery__label">{label}</div>
                  <p className={`doc-gallery__status-text ${ok ? 'is-ok' : ''}`}>
                    {ok ? 'پذیرش قوانین ثبت شده است.' : 'هنوز تأیید نشده.'}
                  </p>
                </div>
              </div>
            )
          }

          const { url, mime, isLocalPlaceholder, fileName } = parseStepFileUploadValue(raw)
          const src = url ? resolveUploadPublicUrl(url) : ''
          const showImage = url && mime.startsWith('image/')
          const showPdf = url && mime === 'application/pdf'
          const canPreview = !!(url && (showImage || showPdf || url))

          return (
            <div
              key={name}
              className={`doc-gallery__card ${st === 'approved' ? 'is-approved' : ''} ${st === 'rejected' ? 'is-rejected' : ''}`}
            >
              <div className="doc-gallery__meta">
                <div className="doc-gallery__label">{label}</div>
                {st && (
                  <span
                    className={`badge ${st === 'rejected' ? 'badge-danger' : st === 'approved' ? 'badge-success' : 'badge-warning'}`}
                  >
                    {st === 'approved' ? 'تأیید شده' : st === 'rejected' ? 'رد شده — بارگذاری مجدد' : st}
                  </span>
                )}
              </div>

              {isLocalPlaceholder && (
                <p className="doc-gallery__hint doc-gallery__hint--warn">فقط نام فایل محلی (بدون بارگذاری روی سرور)</p>
              )}
              {!url && !isLocalPlaceholder && (
                <p className="doc-gallery__hint">ثبت نشده</p>
              )}

              {showImage && (
                <button
                  type="button"
                  className="doc-gallery__thumb"
                  onClick={() => openPreviewForField(name)}
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
                  className="doc-gallery__file-tile"
                  onClick={() => openPreviewForField(name)}
                >
                  <span className="doc-gallery__file-icon">PDF</span>
                  <span>پیش‌نمایش PDF</span>
                </button>
              )}

              {url && !showImage && !showPdf && (
                <button
                  type="button"
                  className="doc-gallery__file-tile"
                  onClick={() => openPreviewForField(name)}
                >
                  <span className="doc-gallery__file-icon">فایل</span>
                  <span>مشاهده فایل</span>
                </button>
              )}

              {(fileName || canPreview) && (
                <div className="doc-gallery__footer">
                  {fileName && <span className="doc-gallery__filename" title={fileName}>{fileName}</span>}
                  {canPreview && (
                    <button
                      type="button"
                      className="btn btn-sm btn-outline"
                      onClick={() => openPreviewForField(name)}
                    >
                      پیش‌نمایش
                    </button>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <DocumentPreviewLightbox
        open={lightboxIndex != null}
        items={previewItems}
        index={lightboxIndex ?? 0}
        onClose={() => setLightboxIndex(null)}
        onIndexChange={setLightboxIndex}
      />
    </>
  )
}

/** فیلدهای فایل و تأیید قوانین از آرایهٔ فرم‌های متادیتا */
export function collectDocumentGalleryFields(forms) {
  const out = []
  for (const f of forms || []) {
    for (const field of f.fields || []) {
      const typ = field.type || ''
      if (
        typ === 'file_upload'
        || (typ === 'checkbox' && field.show_in_document_summary)
      ) {
        if (field.name) out.push(field)
      }
    }
  }
  return out
}
