import React, { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

/**
 * لایت‌باکس تمام‌صفحه برای پیش‌نمایش مدارک (تصویر / PDF).
 * @param {{ open: boolean, items: { id: string, label: string, src: string, mime: string }[], index: number, onClose: () => void, onIndexChange?: (i: number) => void }} props
 */
export default function DocumentPreviewLightbox({ open, items, index, onClose, onIndexChange }) {
  const list = Array.isArray(items) ? items : []
  const safeIndex = list.length ? Math.min(Math.max(0, index || 0), list.length - 1) : 0
  const current = list[safeIndex] || null
  const [zoom, setZoom] = useState(1)

  useEffect(() => {
    if (open) setZoom(1)
  }, [open, safeIndex])

  const go = useCallback(
    (delta) => {
      if (!list.length || !onIndexChange) return
      const next = (safeIndex + delta + list.length) % list.length
      onIndexChange(next)
    },
    [list.length, onIndexChange, safeIndex],
  )

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.()
      if (e.key === 'ArrowRight') go(-1)
      if (e.key === 'ArrowLeft') go(1)
      if (e.key === '+' || e.key === '=') setZoom((z) => Math.min(3, +(z + 0.25).toFixed(2)))
      if (e.key === '-') setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))
    }
    window.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [open, onClose, go])

  if (!open || !current) return null

  const isImage = (current.mime || '').startsWith('image/')
  const isPdf = current.mime === 'application/pdf'

  return createPortal(
    <div
      className="doc-lightbox"
      role="dialog"
      aria-modal="true"
      aria-label={current.label || 'پیش‌نمایش مدرک'}
      onClick={onClose}
    >
      <div className="doc-lightbox__chrome" onClick={(e) => e.stopPropagation()}>
        <div className="doc-lightbox__header">
          <div className="doc-lightbox__title-wrap">
            <h3 className="doc-lightbox__title">{current.label || 'مدرک'}</h3>
            {list.length > 1 && (
              <span className="doc-lightbox__counter">
                {safeIndex + 1} از {list.length}
              </span>
            )}
          </div>
          <div className="doc-lightbox__actions">
            {isImage && (
              <>
                <button type="button" className="doc-lightbox__btn" onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))} title="کوچک‌نمایی">
                  −
                </button>
                <span className="doc-lightbox__zoom-label">{Math.round(zoom * 100)}%</span>
                <button type="button" className="doc-lightbox__btn" onClick={() => setZoom((z) => Math.min(3, +(z + 0.25).toFixed(2)))} title="بزرگ‌نمایی">
                  +
                </button>
                <button type="button" className="doc-lightbox__btn" onClick={() => setZoom(1)} title="اندازهٔ اصلی">
                  ۱۰۰٪
                </button>
              </>
            )}
            <a
              href={current.src}
              target="_blank"
              rel="noopener noreferrer"
              className="doc-lightbox__btn doc-lightbox__btn--link"
            >
              باز کردن در تب جدید
            </a>
            <button type="button" className="doc-lightbox__btn doc-lightbox__btn--close" onClick={onClose} aria-label="بستن">
              ×
            </button>
          </div>
        </div>

        <div className="doc-lightbox__stage">
          {list.length > 1 && (
            <button
              type="button"
              className="doc-lightbox__nav doc-lightbox__nav--prev"
              onClick={() => go(-1)}
              aria-label="مدرک قبلی"
            >
              ›
            </button>
          )}

          <div className="doc-lightbox__viewport">
            {isImage && (
              <img
                src={current.src}
                alt={current.label || ''}
                className="doc-lightbox__image"
                style={{ transform: `scale(${zoom})` }}
                draggable={false}
              />
            )}
            {isPdf && (
              <iframe
                title={current.label || 'PDF'}
                src={current.src}
                className="doc-lightbox__pdf"
              />
            )}
            {!isImage && !isPdf && (
              <div className="doc-lightbox__fallback">
                <p>پیش‌نمایش برای این نوع فایل در دسترس نیست.</p>
                <a href={current.src} target="_blank" rel="noopener noreferrer" className="btn btn-primary btn-sm">
                  باز کردن فایل
                </a>
              </div>
            )}
          </div>

          {list.length > 1 && (
            <button
              type="button"
              className="doc-lightbox__nav doc-lightbox__nav--next"
              onClick={() => go(1)}
              aria-label="مدرک بعدی"
            >
              ‹
            </button>
          )}
        </div>

        {list.length > 1 && (
          <div className="doc-lightbox__thumbs" role="tablist" aria-label="مدارک">
            {list.map((item, i) => {
              const thumbImage = (item.mime || '').startsWith('image/')
              return (
                <button
                  key={item.id || i}
                  type="button"
                  role="tab"
                  aria-selected={i === safeIndex}
                  className={`doc-lightbox__thumb ${i === safeIndex ? 'is-active' : ''}`}
                  onClick={() => onIndexChange?.(i)}
                  title={item.label}
                >
                  {thumbImage ? (
                    <img src={item.src} alt="" />
                  ) : (
                    <span className="doc-lightbox__thumb-label">{(item.mime || '').includes('pdf') ? 'PDF' : 'فایل'}</span>
                  )}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}

/**
 * ساخت آیتم‌های قابل پیش‌نمایش از فیلدهای فایل + context.
 * @returns {{ id: string, label: string, src: string, mime: string, fieldName: string }[]}
 */
export function buildDocumentPreviewItems(fields, contextData, resolveUrl, parseValue) {
  const ctx = contextData && typeof contextData === 'object' ? contextData : {}
  const out = []
  for (const field of fields || []) {
    if ((field.type || '') === 'checkbox') continue
    const name = field.name
    if (!name) continue
    const { url, mime } = parseValue(ctx[name])
    if (!url) continue
    const src = resolveUrl(url)
    if (!src) continue
    out.push({
      id: name,
      fieldName: name,
      label: field.label_fa || name,
      src,
      mime: mime || '',
    })
  }
  return out
}
