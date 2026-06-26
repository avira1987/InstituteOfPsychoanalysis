import React, { useEffect, useState } from 'react'
import { processExecApi } from '../services/api'

const TYPE_LABELS = {
  term_transcript: 'کارنامه ترم',
  cumulative_transcript: 'کارنامه کل',
  certificate: 'گواهی پایان دوره',
  pdf_export: 'خروجی PDF',
  decline_list: 'فهرست انصراف',
  termination_letter: 'نامه خاتمه',
}

/**
 * کارنامه‌ها و گواهی‌های قابل دانلود در پورتال دانشجو.
 */
export default function StudentTranscriptsPanel({ studentId }) {
  const [loading, setLoading] = useState(true)
  const [artifacts, setArtifacts] = useState([])
  const [error, setError] = useState(null)
  const [openDocId, setOpenDocId] = useState(null)
  const [openDoc, setOpenDoc] = useState(null)
  const [docLoading, setDocLoading] = useState(false)

  const viewDocument = async (artifact) => {
    if (openDocId === artifact.id) {
      setOpenDocId(null)
      setOpenDoc(null)
      return
    }
    setOpenDocId(artifact.id)
    setOpenDoc(null)
    setDocLoading(true)
    try {
      const r = await processExecApi.studentDocument(studentId, artifact.id)
      setOpenDoc(r.data || null)
    } catch (_) {
      setOpenDoc({ body_fa: 'نمایش محتوای این سند ممکن نشد.' })
    } finally {
      setDocLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    if (!studentId) {
      setArtifacts([])
      setLoading(false)
      return undefined
    }
    setLoading(true)
    processExecApi
      .studentArtifacts(studentId)
      .then((r) => {
        if (cancelled) return
        setArtifacts(r.data?.artifacts || [])
        setError(null)
      })
      .catch(() => {
        if (cancelled) return
        setArtifacts([])
        setError('بارگذاری کارنامه‌ها و گواهی‌ها ممکن نشد.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [studentId])

  if (!studentId) return null

  return (
    <div className="card" data-testid="student-transcripts-panel">
      <div className="card-header">
        <h3 className="card-title">کارنامه‌ها و گواهی‌ها</h3>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        {loading && <p className="muted" style={{ margin: 0 }}>در حال بارگذاری…</p>}
        {error && (
          <p style={{ margin: 0, color: '#b91c1c', fontSize: '0.9rem' }}>{error}</p>
        )}
        {!loading && !error && artifacts.length === 0 && (
          <p className="muted" style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.65 }}>
            هنوز کارنامه یا گواهی آمادهٔ دانلود در پورتال شما ثبت نشده است. پس از پایان هر ترم یا
            خاتمه دوره آشنایی، اینجا نمایش داده می‌شود.
          </p>
        )}
        {!loading && artifacts.length > 0 && (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
            {artifacts.map((a) => (
              <li
                key={a.id || `${a.type}-${a.created_at}`}
                style={{
                  padding: '0.85rem 1rem',
                  borderRadius: '8px',
                  border: '1px solid var(--border, #e5e7eb)',
                  background: 'var(--bg, #f9fafb)',
                }}
              >
                <div style={{ fontWeight: 700, fontSize: '0.92rem', marginBottom: '0.25rem' }}>
                  {a.title_fa || TYPE_LABELS[a.type] || a.type}
                </div>
                {a.body_fa && (
                  <div className="muted" style={{ fontSize: '0.85rem', marginBottom: '0.35rem', lineHeight: 1.55 }}>
                    {a.body_fa}
                  </div>
                )}
                <div className="muted" style={{ fontSize: '0.78rem' }}>
                  {a.created_at ? new Date(a.created_at).toLocaleDateString('fa-IR') : '—'}
                  {a.signed ? ' · امضاشده' : ''}
                </div>
                <button
                  type="button"
                  className="btn btn-sm btn-outline"
                  style={{ marginTop: '0.5rem' }}
                  onClick={() => viewDocument(a)}
                >
                  {openDocId === a.id ? 'بستن' : 'مشاهده / دانلود'}
                </button>
                {openDocId === a.id && (
                  <div
                    style={{
                      marginTop: '0.65rem',
                      padding: '0.85rem 1rem',
                      borderRadius: '8px',
                      background: 'var(--bg, #fff)',
                      border: '1px dashed var(--border, #cbd5e1)',
                    }}
                  >
                    {docLoading && <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>در حال بارگذاری…</p>}
                    {!docLoading && openDoc && (
                      <>
                        <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: '0.4rem' }}>
                          {openDoc.title_fa || a.title_fa}
                        </div>
                        <div style={{ fontSize: '0.85rem', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                          {openDoc.body_fa || '—'}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
