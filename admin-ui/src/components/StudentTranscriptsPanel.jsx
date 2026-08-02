import React from 'react'
import { useStudentArtifacts } from '../hooks/useStudentArtifacts'

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
  const {
    loading,
    artifacts,
    error,
    downloadingId,
    downloadError,
    downloadPdf,
  } = useStudentArtifacts(studentId)

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
        {downloadError && (
          <p style={{ margin: '0.5rem 0 0', color: '#b91c1c', fontSize: '0.85rem' }}>{downloadError}</p>
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
                <div className="muted" style={{ fontSize: '0.78rem', marginBottom: '0.5rem' }}>
                  {a.created_at ? new Date(a.created_at).toLocaleDateString('fa-IR') : '—'}
                  {a.signed ? ' · امضاشده' : ''}
                </div>
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  disabled={downloadingId === a.id}
                  onClick={() => downloadPdf(a)}
                >
                  {downloadingId === a.id ? 'در حال دانلود…' : 'دانلود PDF'}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
