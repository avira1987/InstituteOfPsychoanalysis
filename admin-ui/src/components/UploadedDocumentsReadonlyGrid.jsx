import React from 'react'
import { parseStepFileUploadValue, resolveUploadPublicUrl } from '../utils/uploadPublicUrl'

/**
 * نمایش فقط‌خواندنی مدارک از روی context_data (پروفایل دانشجو / مشاهدهٔ کارمند).
 * @param {{ name: string, label_fa?: string, type?: string }[]} fields
 * @param {Record<string, unknown>} contextData
 * @param {Record<string, string>|null} [fieldStatus] — مثلاً __document_field_status از پرونده
 */
export default function UploadedDocumentsReadonlyGrid({ fields, contextData, fieldStatus }) {
  if (!Array.isArray(fields) || fields.length === 0) return null
  const ctx = contextData && typeof contextData === 'object' ? contextData : {}

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
        gap: '1rem',
      }}
    >
      {fields.map((field) => {
        const name = field.name
        const label = field.label_fa || name
        const t = field.type || 'text'
        const raw = ctx[name]
        const st = fieldStatus && typeof fieldStatus === 'object' ? fieldStatus[name] : null

        if (t === 'sms_verification') {
          const ok = raw != null && String(raw).trim() !== ''
          return (
            <div
              key={name}
              style={{
                border: '1px solid #e5e7eb',
                borderRadius: '10px',
                padding: '0.75rem',
                background: '#fafafa',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.35rem' }}>{label}</div>
              {st && (
                <span className={`badge ${st === 'rejected' ? 'badge-danger' : st === 'approved' ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: '0.72rem', marginBottom: '0.35rem', display: 'inline-block' }}>
                  {st === 'approved' ? 'تأیید شده' : st === 'rejected' ? 'رد شده — نیاز به اصلاح' : st}
                </span>
              )}
              <p style={{ margin: 0, fontSize: '0.8rem', color: ok ? '#15803d' : '#64748b' }}>
                {ok ? 'تعهدنامه با کد پیامکی ثبت شده است.' : 'هنوز ثبت نشده.'}
              </p>
            </div>
          )
        }

        const { url, mime, isLocalPlaceholder } = parseStepFileUploadValue(raw)
        const src = url ? resolveUploadPublicUrl(url) : ''
        const showImage = url && mime.startsWith('image/')
        const showPdf = url && mime === 'application/pdf'

        return (
          <div
            key={name}
            style={{
              border: '1px solid #e5e7eb',
              borderRadius: '10px',
              padding: '0.75rem',
              background: '#fafafa',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.35rem' }}>{label}</div>
            {st && (
              <span
                className={`badge ${st === 'rejected' ? 'badge-danger' : st === 'approved' ? 'badge-success' : 'badge-warning'}`}
                style={{ fontSize: '0.72rem', marginBottom: '0.35rem', display: 'inline-block' }}
              >
                {st === 'approved' ? 'تأیید شده' : st === 'rejected' ? 'رد شده — بارگذاری مجدد' : st}
              </span>
            )}
            {isLocalPlaceholder && (
              <p style={{ fontSize: '0.78rem', color: '#b45309', margin: '0 0 0.35rem' }}>فقط نام فایل محلی (بدون بارگذاری روی سرور)</p>
            )}
            {!url && !isLocalPlaceholder && (
              <p style={{ fontSize: '0.78rem', color: '#64748b', margin: 0 }}>ثبت نشده</p>
            )}
            {showImage && (
              <a href={src} target="_blank" rel="noopener noreferrer">
                <img
                  src={src}
                  alt={label}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '160px',
                    borderRadius: '8px',
                    border: '1px solid #e5e7eb',
                    display: 'block',
                    marginTop: '0.35rem',
                  }}
                />
              </a>
            )}
            {showPdf && (
              <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline" style={{ marginTop: '0.35rem' }}>
                باز کردن PDF
              </a>
            )}
            {url && !showImage && !showPdf && (
              <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline" style={{ marginTop: '0.35rem' }}>
                باز کردن فایل
              </a>
            )}
          </div>
        )
      })}
    </div>
  )
}

/** فیلدهای فایل + تعهدنامه از آرایهٔ فرم‌های متادیتا */
export function collectDocumentGalleryFields(forms) {
  const out = []
  for (const f of forms || []) {
    for (const field of f.fields || []) {
      const typ = field.type || ''
      if ((typ === 'file_upload' || typ === 'sms_verification') && field.name) out.push(field)
    }
  }
  return out
}
