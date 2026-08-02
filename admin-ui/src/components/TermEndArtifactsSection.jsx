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

const TERM_END_TYPES = new Set(['term_transcript', 'cumulative_transcript', 'pdf_export'])

/**
 * Inline transcript artifacts for term-end panels (subset of profile transcripts).
 */
export default function TermEndArtifactsSection({
  studentId,
  processCode = null,
  compact = false,
}) {
  const {
    loading,
    artifacts,
    error,
    downloadingId,
    downloadError,
    downloadPdf,
  } = useStudentArtifacts(studentId)

  const filtered = artifacts.filter((a) => {
    if (!TERM_END_TYPES.has(a.type)) return false
    if (processCode && a.process_code && a.process_code !== processCode) return false
    return true
  })

  if (!studentId) return null
  if (!loading && !error && filtered.length === 0) return null

  return (
    <div
      data-testid="term-end-artifacts-section"
      style={{
        marginBottom: compact ? '0.65rem' : '0.85rem',
        padding: compact ? '0.65rem 0.85rem' : '0.85rem 1rem',
        borderRadius: '10px',
        background: '#f8fafc',
        border: '1px solid #e2e8f0',
      }}
    >
      <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: '0.5rem', color: '#334155' }}>
        کارنامه‌ها و خروجی PDF
      </div>
      {loading && <p className="muted" style={{ margin: 0, fontSize: '0.82rem' }}>در حال بارگذاری کارنامه…</p>}
      {error && <p style={{ margin: 0, color: '#b91c1c', fontSize: '0.82rem' }}>{error}</p>}
      {downloadError && (
        <p style={{ margin: '0 0 0.5rem', color: '#b91c1c', fontSize: '0.82rem' }}>{downloadError}</p>
      )}
      {!loading && !error && (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {filtered.map((a) => (
            <li
              key={a.id || `${a.type}-${a.created_at}`}
              style={{
                padding: '0.65rem 0.75rem',
                borderRadius: '8px',
                background: '#fff',
                border: '1px solid #e2e8f0',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.4rem' }}>
                {a.title_fa || TYPE_LABELS[a.type] || a.type}
              </div>
              <button
                type="button"
                className="btn btn-sm btn-outline"
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
  )
}
