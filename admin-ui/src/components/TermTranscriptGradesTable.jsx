import React from 'react'
import { resolveTermTranscriptRows } from '../utils/termEndTranscriptRows'

function fmtNum(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('fa-IR', { maximumFractionDigits: 2 })
}

/**
 * Read-only term grades table (SOP فرم کارنامه ترمی).
 */
export default function TermTranscriptGradesTable({
  detail = null,
  extraData = null,
  termGpa = null,
  compact = false,
}) {
  const rows = resolveTermTranscriptRows(detail?.context_data, extraData)
  if (!rows.length) return null

  const gpa = termGpa ?? detail?.context_data?.term_gpa ?? detail?.context_data?.termGPA

  return (
    <div
      data-testid="term-transcript-grades-table"
      style={{
        marginBottom: compact ? '0.65rem' : '0.85rem',
        overflowX: 'auto',
        borderRadius: '10px',
        border: '1px solid #e2e8f0',
      }}
    >
      <table className="data-table" style={{ width: '100%', fontSize: compact ? '0.8rem' : '0.85rem' }}>
        <thead>
          <tr>
            <th>نام درس</th>
            <th>واحد</th>
            <th>نمره عددی</th>
            <th>نمره حرفی</th>
            <th>وضعیت</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={row.course_code || row.course_name || idx}>
              <td>{row.course_name || '—'}</td>
              <td>{row.units ?? '—'}</td>
              <td>{row.numeric_grade != null ? fmtNum(row.numeric_grade) : '—'}</td>
              <td>{row.letter_grade || '—'}</td>
              <td>
                <span
                  className={`badge ${row.pass_fail_status === 'مردود' ? 'badge-danger' : 'badge-success'}`}
                  style={{ fontSize: '0.72rem' }}
                >
                  {row.pass_fail_status || '—'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
        {gpa != null && (
          <tfoot>
            <tr>
              <td colSpan={5} style={{ fontWeight: 700, textAlign: 'left', padding: '0.65rem 0.75rem' }}>
                معدل ترم:
                {' '}
                {fmtNum(gpa)}
              </td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
