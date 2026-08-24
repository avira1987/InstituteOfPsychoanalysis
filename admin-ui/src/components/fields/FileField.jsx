import React, { useState } from 'react'
import { parseStepFileUploadValue, resolveUploadPublicUrl } from '../../utils/uploadPublicUrl'
import DocumentPreviewLightbox from '../DocumentPreviewLightbox'

export default function FileField({
  field,
  value,
  onChange,
  disabled,
  onUploadFile,
  showToast,
  previewMode = 'link',
}) {
  const [lightboxOpen, setLightboxOpen] = useState(false)
  const parsed = parseStepFileUploadValue(value)
  const src = parsed.url ? resolveUploadPublicUrl(parsed.url) : ''
  const showImage = parsed.url && (parsed.mime || '').startsWith('image/')
  const showPdf = parsed.url && parsed.mime === 'application/pdf'
  const maxMb = field.validation?.max_size_mb || 8
  const useLightbox = previewMode === 'lightbox'

  const handle = async (e) => {
    const file = e.target.files?.[0]
    if (!file) { onChange(null); return }
    if (file.size > maxMb * 1024 * 1024) {
      showToast?.(`حداکثر حجم فایل ${maxMb} مگابایت است.`, 'error')
      return
    }
    if (typeof onUploadFile === 'function') {
      try {
        const result = await onUploadFile(field.name, file)
        onChange(result)
      } catch (err) {
        showToast?.(err?.message || 'خطا در آپلود فایل', 'error')
      }
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      onChange({
        file_name: file.name,
        content_base64: reader.result?.split(',')[1],
        mime_type: file.type || 'application/octet-stream',
      })
    }
    reader.readAsDataURL(file)
  }

  const preview = !src ? null : useLightbox ? (
    <button
      type="button"
      className="btn btn-sm btn-outline"
      style={{ marginTop: '0.5rem' }}
      onClick={() => setLightboxOpen(true)}
    >
      {showImage ? 'پیش‌نمایش تصویر' : showPdf ? 'پیش‌نمایش PDF' : 'مشاهده فایل'}
    </button>
  ) : (
    <>
      {showImage && (
        <div style={{ marginTop: '0.5rem' }}>
          <a href={src} target="_blank" rel="noopener noreferrer">
            <img src={src} alt="" style={{ maxWidth: '100%', maxHeight: '140px', borderRadius: '8px', border: '1px solid #e5e7eb' }} />
          </a>
        </div>
      )}
      {showPdf && (
        <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline" style={{ marginTop: '0.5rem' }}>باز کردن PDF</a>
      )}
    </>
  )

  return (
    <div>
      <input type="file" accept={field.accept || field.validation?.accept || '*/*'} disabled={disabled} onChange={handle} />
      {preview}
      {(parsed.fileName || value?.file_name) && (
        <span className="psf-file-name" style={{ display: 'block', marginTop: '0.35rem' }}>{parsed.fileName || value.file_name}</span>
      )}
      {useLightbox && (
        <DocumentPreviewLightbox
          open={lightboxOpen}
          items={src ? [{ id: field.name || 'file', label: field.label_fa || 'مدرک', src, mime: parsed.mime || '' }] : []}
          index={0}
          onClose={() => setLightboxOpen(false)}
        />
      )}
    </div>
  )
}
