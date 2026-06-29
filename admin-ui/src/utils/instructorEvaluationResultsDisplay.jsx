/** نمایش نتایج تجمیع‌شده ارزیابی مدرسین — فرایند ۵۷ */

import React, { useMemo } from 'react'

const PIE_COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#2563eb']

export const CHART_QUESTION_LABELS = {
  overall_score: 'نمره کلی کیفیت تدریس',
  teaching_clarity: 'شفافیت و انتقال مطلب',
  interaction_quality: 'کیفیت تعامل با دانشجویان',
}

export function formatParticipationRate(rate) {
  if (rate == null || Number.isNaN(Number(rate))) return '—'
  return `${(Number(rate) * 100).toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪`
}

export function formatAverageScore(score) {
  if (score == null || Number.isNaN(Number(score))) return '—'
  return Number(score).toLocaleString('fa-IR', { minimumFractionDigits: 1, maximumFractionDigits: 2 })
}

export function fmtDeadline(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleString('fa-IR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export function isEvaluationResultsVisible(data, now = Date.now()) {
  if (!data) return false
  if (data.aggregated_at) return true
  const close = data.evaluation_close_at
  if (!close) return false
  const t = Date.parse(close)
  return Number.isFinite(t) && now >= t
}

function distributionSlices(distribution) {
  const dist = distribution && typeof distribution === 'object' ? distribution : {}
  const entries = ['1', '2', '3', '4', '5'].map((k) => ({
    key: k,
    count: Number(dist[k]) || 0,
  }))
  const total = entries.reduce((s, e) => s + e.count, 0)
  if (total <= 0) return []
  let acc = 0
  return entries.map((e, i) => {
    const pct = e.count / total
    const slice = { ...e, pct, color: PIE_COLORS[i], start: acc, end: acc + pct }
    acc += pct
    return slice
  })
}

/** نمودار دایره‌ای SVG ساده از توزیع ۱–۵ */
export function PieDistributionChart({ distribution, title, size = 120 }) {
  const slices = useMemo(() => distributionSlices(distribution), [distribution])
  const total = slices.reduce((s, x) => s + x.count, 0)
  const r = size / 2 - 4
  const cx = size / 2
  const cy = size / 2

  if (total <= 0) {
    return (
      <div style={{ textAlign: 'center', fontSize: '0.78rem', color: '#94a3b8' }}>
        {title && <div style={{ marginBottom: '0.35rem', fontWeight: 600 }}>{title}</div>}
        بدون داده
      </div>
    )
  }

  const paths = slices.filter((s) => s.count > 0).map((s) => {
    const startAngle = s.start * 2 * Math.PI - Math.PI / 2
    const endAngle = s.end * 2 * Math.PI - Math.PI / 2
    const x1 = cx + r * Math.cos(startAngle)
    const y1 = cy + r * Math.sin(startAngle)
    const x2 = cx + r * Math.cos(endAngle)
    const y2 = cy + r * Math.sin(endAngle)
    const large = s.pct > 0.5 ? 1 : 0
    const d = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`
    return <path key={s.key} d={d} fill={s.color} stroke="#fff" strokeWidth="1" />
  })

  return (
    <div data-testid="pie-distribution-chart" style={{ textAlign: 'center' }}>
      {title && (
        <div style={{ fontSize: '0.78rem', fontWeight: 600, marginBottom: '0.35rem', color: '#334155' }}>
          {title}
        </div>
      )}
      <svg width={size} height={size} role="img" aria-label={title || 'نمودار توزیع'}>
        {paths}
      </svg>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', justifyContent: 'center', marginTop: '0.35rem' }}>
        {slices.map((s) => (
          <span key={s.key} style={{ fontSize: '0.72rem', color: '#64748b' }}>
            <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: s.color, marginLeft: 4 }} />
            {s.key}
            :
            {s.count.toLocaleString('fa-IR')}
          </span>
        ))}
      </div>
    </div>
  )
}

export function InfoTile({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
  if (value == null || value === '') return null
  return (
    <div
      style={{
        padding: '0.75rem 0.85rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontSize: '1.05rem', fontWeight: 800, color: tone }}>{value}</div>
    </div>
  )
}

export function CourseEvaluationResultCard({ course, compact = false }) {
  const chartData = course.chart_data || {}
  return (
    <div
      className="card"
      data-testid={`eval-result-${course.course_code}`}
      style={{ marginBottom: compact ? '0.65rem' : '1rem' }}
    >
      <div className="card-header">
        <div>
          <h4 className="card-title" style={{ fontSize: '0.95rem', margin: 0 }}>
            {course.course_name || course.course_code}
          </h4>
          <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.2rem' }}>
            مدرس:
            {' '}
            {course.instructor_name || '—'}
          </div>
        </div>
      </div>
      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.85rem',
          }}
        >
          <InfoTile
            label="نرخ مشارکت"
            value={formatParticipationRate(course.participation_rate)}
            tone="#0d9488"
            bg="#f0fdfa"
          />
          <InfoTile
            label="میانگین ترم"
            value={formatAverageScore(course.average_score)}
            tone="#2563eb"
            bg="#eff6ff"
          />
          <InfoTile
            label="میانگین تاریخی"
            value={formatAverageScore(course.historical_average)}
            tone="#7c3aed"
            bg="#f5f3ff"
          />
          <InfoTile
            label="پاسخ / ثبت‌نام"
            value={`${(course.participation_count ?? 0).toLocaleString('fa-IR')} / ${(course.enrolled_count ?? 0).toLocaleString('fa-IR')}`}
            tone="#64748b"
            bg="#f8fafc"
          />
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.75rem',
          }}
        >
          {Object.entries(CHART_QUESTION_LABELS).map(([key, label]) => (
            <PieDistributionChart
              key={key}
              title={label}
              distribution={chartData[key]?.distribution}
              size={compact ? 100 : 120}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
