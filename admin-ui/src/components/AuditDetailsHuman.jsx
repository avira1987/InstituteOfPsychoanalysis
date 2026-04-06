import React from 'react'
import {
  formatDetailKey,
  formatDetailScalar,
} from '../utils/auditDisplay'

function ValueBlock({ children, depth }) {
  return (
    <div
      style={{
        fontSize: '0.92rem',
        lineHeight: 1.65,
        color: 'var(--text)',
        paddingRight: depth > 0 ? `${Math.min(depth, 4) * 10}px` : 0,
        borderRight: depth > 0 ? '2px solid var(--border)' : undefined,
        marginRight: depth > 0 ? '4px' : 0,
      }}
    >
      {children}
    </div>
  )
}

function renderValue(key, value, depth) {
  const scalar = formatDetailScalar(key, value)
  if (scalar !== null) {
    return <span dir="auto">{scalar}</span>
  }
  if (value !== null && value !== undefined && typeof value !== 'object') {
    return <span dir="auto">{String(value)}</span>
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span style={{ color: 'var(--text-light)' }}>خالی</span>
    return (
      <ul style={{ margin: '0.35rem 0 0', paddingRight: '1.25rem', listStyle: 'disc' }}>
        {value.map((item, i) => (
          <li key={i} style={{ marginBottom: '0.35rem' }}>
            {typeof item === 'object' && item !== null
              ? renderNestedObject(item, depth + 1)
              : <span dir="auto">{formatDetailScalar('', item) ?? String(item)}</span>}
          </li>
        ))}
      </ul>
    )
  }
  if (value && typeof value === 'object') {
    return renderNestedObject(value, depth + 1)
  }
  return <span>—</span>
}

function renderNestedObject(obj, depth) {
  const keys = Object.keys(obj)
  if (keys.length === 0) return <span style={{ color: 'var(--text-light)' }}>بدون مقدار</span>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', marginTop: depth > 0 ? '0.35rem' : 0 }}>
      {keys.map((k) => (
        <div key={k}>
          <div className="detail-label" style={{ marginBottom: '0.2rem', fontSize: '0.82rem' }}>
            {formatDetailKey(k)}
          </div>
          <ValueBlock depth={depth}>{renderValue(k, obj[k], depth)}</ValueBlock>
        </div>
      ))}
    </div>
  )
}

/**
 * نمایش آبجکت details به‌صورت فهرست برچسب‌دار به‌جای JSON خام.
 */
export default function AuditDetailsHuman({ details }) {
  if (details == null || typeof details !== 'object' || Array.isArray(details)) {
    return null
  }
  const keys = Object.keys(details)
  if (keys.length === 0) return null

  return (
    <div
      className="audit-details-human"
      style={{
        marginTop: '1rem',
        padding: '1rem 1.1rem',
        background: 'var(--bg)',
        borderRadius: 'var(--radius)',
        border: '1px solid var(--border)',
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
        توضیحات تکمیلی
      </div>
      {renderNestedObject(details, 0)}
    </div>
  )
}
