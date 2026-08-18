import React from 'react'
import { formatRialAsToman, tuitionQuoteFromContext } from '../utils/introCourseCatalog'

/**
 * خلاصهٔ شهریه بر اساس واحد × هزینه هر واحد (از tuition_lines در context).
 */
export default function TuitionQuoteSummary({ contextData, compact = false, testId = 'tuition-quote-summary' }) {
  const quote = tuitionQuoteFromContext(contextData)
  if (!quote.totalRial && (!quote.lines || !quote.lines.length)) return null

  return (
    <div
      data-testid={testId}
      style={{
        marginBottom: compact ? '0.65rem' : '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: 10,
        background: '#fffbeb',
        borderRight: '4px solid #b45309',
        fontSize: '0.86rem',
        lineHeight: 1.7,
        color: '#78350f',
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: '0.35rem' }}>محاسبه شهریه بر اساس واحد</div>
      {quote.totalUnits != null ? (
        <div className="muted" style={{ fontSize: '0.8rem', marginBottom: '0.35rem', color: '#92400e' }}>
          مجموع واحد انتخاب‌شده: {Number(quote.totalUnits).toLocaleString('fa-IR')}
        </div>
      ) : null}
      {quote.lines.length > 0 ? (
        <ul style={{ margin: '0 0 0.5rem', paddingInlineStart: '1.1rem' }}>
          {quote.lines.map((line) => {
            const name = line.course_name_fa || line.course_code || 'درس'
            const units = line.units != null ? Number(line.units).toLocaleString('fa-IR') : '—'
            const amount = formatRialAsToman(line.line_amount_rial) || '—'
            return (
              <li key={String(line.course_code || name)}>
                {name} ({units} واحد) — {amount}
              </li>
            )
          })}
        </ul>
      ) : null}
      {quote.totalTomanLabel ? (
        <div style={{ fontWeight: 800, fontSize: '0.95rem' }}>
          جمع قابل پرداخت: {quote.totalTomanLabel}
        </div>
      ) : null}
    </div>
  )
}
