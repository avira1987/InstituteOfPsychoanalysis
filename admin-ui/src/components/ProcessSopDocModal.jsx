import React, { useEffect, useState } from 'react'
import { processApi, getApiBase } from '../services/api'
import { resolveProcessSopOrder } from '../utils/processSopOrder'

/**
 * نمایش فقط‌خواندنی متن خام SOP و تصویر فلوچارت (همان محتوای ذخیره‌شده برای کاربر/ادمین).
 */
export default function ProcessSopDocModal({ processId, onClose }) {
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [proc, setProc] = useState(null)
  const [flowchartObjectUrl, setFlowchartObjectUrl] = useState(null)

  useEffect(() => {
    if (!processId) return undefined
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setErr(null)
      setProc(null)
      try {
        const res = await processApi.get(processId)
        if (cancelled) return
        setProc(res.data)
      } catch (e) {
        if (!cancelled) {
          const d = e.response?.data?.detail
          setErr(typeof d === 'string' ? d : JSON.stringify(d || e.message || 'خطا'))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [processId])

  useEffect(() => {
    if (!processId || !proc?.has_flowchart) {
      setFlowchartObjectUrl((u) => {
        if (u) URL.revokeObjectURL(u)
        return null
      })
      return undefined
    }
    let cancelled = false
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('token') : null
    const base = getApiBase()
    fetch(`${base}admin/processes/${processId}/flowchart`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => {
        if (!r.ok) throw new Error('flowchart')
        return r.blob()
      })
      .then((blob) => {
        if (cancelled) return
        const url = URL.createObjectURL(blob)
        setFlowchartObjectUrl((old) => {
          if (old) URL.revokeObjectURL(old)
          return url
        })
      })
      .catch(() => {
        if (!cancelled) {
          setFlowchartObjectUrl((old) => {
            if (old) URL.revokeObjectURL(old)
            return null
          })
        }
      })
    return () => {
      cancelled = true
      setFlowchartObjectUrl((old) => {
        if (old) URL.revokeObjectURL(old)
        return null
      })
    }
  }, [processId, proc?.has_flowchart, proc?.version])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!processId) return null

  const sopN = proc ? resolveProcessSopOrder(proc) : null

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sop-doc-modal-title"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15, 23, 42, 0.45)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose?.()
      }}
    >
      <div
        className="card"
        style={{
          maxWidth: 'min(52rem, 100%)',
          maxHeight: '90vh',
          overflow: 'auto',
          width: '100%',
          margin: 0,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', marginBottom: '1rem' }}>
          <div>
            <h2 id="sop-doc-modal-title" className="card-title" style={{ marginBottom: '0.35rem' }}>
              متن فرایند
            </h2>
            {!loading && proc && (
              <p style={{ fontSize: '0.95rem', fontWeight: 600, margin: '0 0 0.35rem 0' }}>{proc.name_fa}</p>
            )}
            {!loading && proc && proc.description && String(proc.description).trim() && (
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', margin: '0 0 0.5rem 0', lineHeight: 1.5 }}>
                {proc.description}
              </p>
            )}
            {!loading && proc && (
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
                کد: {proc.code}
                {sopN != null ? ` | شماره SOP: ${sopN}` : ''}
                {proc.has_flowchart ? ' | تصویر: دارد' : ''}
              </p>
            )}
            {loading && (
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>در حال بارگذاری…</p>
            )}
          </div>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => onClose?.()}>
            بستن
          </button>
        </div>

        {err && !loading && (
          <p style={{ color: 'var(--danger)', padding: '1rem 0' }}>{err}</p>
        )}

        {!loading && proc && !err && (
          <>
            <h3 className="card-title" style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>متن فرایند (SOP)</h3>
            <div
              dir="rtl"
              style={{
                whiteSpace: 'pre-wrap',
                lineHeight: 1.65,
                padding: '0.75rem 1rem',
                background: 'var(--bg-secondary, #f8fafc)',
                borderRadius: 8,
                border: '1px solid var(--border)',
                minHeight: '4rem',
                fontSize: '0.92rem',
              }}
            >
              {(proc.source_text && String(proc.source_text).trim()) ? proc.source_text : 'متنی ثبت نشده است.'}
            </div>

            <h3 className="card-title" style={{ fontSize: '1rem', marginTop: '1.5rem', marginBottom: '0.5rem' }}>تصویر فرایند</h3>
            {flowchartObjectUrl ? (
              <img
                src={flowchartObjectUrl}
                alt={`فلوچارت ${proc.name_fa || proc.code || 'فرایند'}`}
                style={{ maxWidth: '100%', height: 'auto', border: '1px solid var(--border)', borderRadius: 8 }}
              />
            ) : (
              <div className="empty-state" style={{ padding: '1.25rem' }}>
                <p style={{ margin: 0 }}>تصویری ثبت نشده است.</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
