/** نمایش مشترک فرایند ۵۲ — خاتمه کمک‌مدرس برای هر رسته. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'
import { resolveStateDisplayLabel } from './processDisplay'

export const TA_TRACK_COMPLETION_PROCESS = 'ta_track_completion'

export const TA_TRACK_FLOW_STEPS = [
  { key: 'check', label: 'پایش سیستمی', states: ['end_of_track_check'] },
  { key: 'done', label: 'خاتمه رسته', states: ['track_completed'] },
]

export const TA_RANK_LABELS = {
  teaching_assistant: 'کمک مدرس',
  assistant_faculty: 'دستیار هیئت علمی',
  instructor: 'مدرس',
}

export function labelTaTrackState(state) {
  if (!state) return '—'
  return resolveStateDisplayLabel(TA_TRACK_COMPLETION_PROCESS, state) || state
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function isTaTrackTerminalState(state) {
  return state === 'track_completed'
}

export function shouldShowTaPortfolio(extraData, portfolio) {
  if (portfolio?.has_ta_data) return true
  const rank = extraData?.rank
  return rank && Object.prototype.hasOwnProperty.call(TA_RANK_LABELS, rank)
}

export function HintBlock({ children, tone = 'info' }) {
  const styles = {
    info: { bg: '#eff6ff', border: '#2563eb', color: '#1e40af' },
    success: { bg: '#f0fdf4', border: '#16a34a', color: '#166534' },
    muted: { bg: '#f8fafc', border: '#94a3b8', color: '#475569' },
  }
  const s = styles[tone] || styles.info
  return (
    <div
      style={{
        padding: '0.85rem 1rem',
        marginBottom: '1rem',
        borderRadius: '8px',
        background: s.bg,
        borderRight: `4px solid ${s.border}`,
        fontSize: '0.88rem',
        lineHeight: 1.7,
        color: s.color,
      }}
    >
      {children}
    </div>
  )
}

export function TaTrackInfoTile({ label, value, accent }) {
  return (
    <div
      style={{
        padding: '0.75rem 0.9rem',
        borderRadius: '8px',
        background: accent ? '#f0fdf4' : '#f8fafc',
        border: `1px solid ${accent ? '#bbf7d0' : '#e2e8f0'}`,
      }}
    >
      <div className="muted" style={{ fontSize: '0.78rem', marginBottom: '0.25rem' }}>{label}</div>
      <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>{value || '—'}</div>
    </div>
  )
}

export function TaTrackFlowStepper({ currentState, compact = false }) {
  const idx = TA_TRACK_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return (
    <div
      style={{
        display: 'flex',
        gap: compact ? '0.35rem' : '0.5rem',
        flexWrap: 'wrap',
        marginBottom: compact ? '0.75rem' : '1rem',
      }}
    >
      {TA_TRACK_FLOW_STEPS.map((step, i) => {
        const active = i === idx
        const done = idx >= 0 && i < idx
        return (
          <span
            key={step.key}
            style={{
              padding: '0.35rem 0.65rem',
              borderRadius: '999px',
              fontSize: '0.78rem',
              fontWeight: 600,
              background: done ? '#dcfce7' : active ? '#dbeafe' : '#f1f5f9',
              color: done ? '#166534' : active ? '#1e40af' : '#64748b',
            }}
          >
            {step.label}
          </span>
        )
      })}
    </div>
  )
}
