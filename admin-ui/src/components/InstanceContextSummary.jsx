import React, { useMemo } from 'react'
import {
  CTX_STUDENT_FORMS_SUBMITTED,
  CTX_STUDENT_FORMS_UNLOCK,
  CTX_DOCUMENTS_RESUBMIT_FIELDS,
} from '../utils/processFormsStudent'
import { labelState, formatActorRole } from '../utils/processDisplay'
import {
  buildFieldLabelMap,
  resolveContextRowLabel,
  renderFriendlyContextValue,
  formatInterviewResultDisplay,
  formatContextStringForDisplay,
} from '../utils/contextInstanceDisplay'
import { filterContextForOperators } from '../utils/operatorContextFilter'

function formatIsoMaybe(s) {
  if (typeof s !== 'string') return s
  const t = Date.parse(s)
  if (Number.isNaN(t)) return s
  try {
    return new Date(s).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return s
  }
}

function formatScalar(value) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'بله' : 'خیر'
  if (typeof value === 'number') return String(value)
  if (typeof value === 'string') {
    const asDisplay = formatContextStringForDisplay(value)
    if (asDisplay !== null) return asDisplay
    return value
  }
  return null
}

function summarizeFormsSubmitted(obj) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return '—'
  const keys = Object.keys(obj)
  if (!keys.length) return 'هنوز ثبت نشده'
  return keys.map(k => labelState(k)).join('، ')
}

function summarizeFormsUnlock(obj) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return '—'
  const keys = Object.keys(obj).filter(k => obj[k])
  if (!keys.length) return 'هیچ مرحله‌ای باز نیست'
  return keys.map(k => labelState(k)).join('، ')
}

/**
 * سابقه انتقال + جزئیات پرونده (بدون کلیدهای فنی مثل integration_events).
 *
 * @param {boolean} [showTechnicalContext=false] — اگر true باشد همهٔ کلیدها (مثلاً برای دیباگ) نمایش داده می‌شود.
 */
export default function InstanceContextSummary({
  contextData,
  history,
  forms,
  title = 'پرونده و سابقه (قبل از تصمیم)',
  maxHeight = '240px',
  historyMaxHeight = '200px',
  showTechnicalContext = false,
}) {
  const fieldLabelMap = useMemo(() => buildFieldLabelMap(forms), [forms])

  const displayContext = useMemo(() => {
    if (showTechnicalContext && contextData && typeof contextData === 'object' && !Array.isArray(contextData)) {
      return { ...contextData }
    }
    return filterContextForOperators(contextData)
  }, [contextData, showTechnicalContext])

  const hasContext = displayContext && typeof displayContext === 'object' && Object.keys(displayContext).length > 0
  const historyList = Array.isArray(history) ? history : []
  const hasHistory = historyList.length > 0

  const rows = useMemo(() => {
    if (!hasContext) return []
    const out = []
    const keys = Object.keys(displayContext)

    const sorted = [...keys].sort((a, b) => {
      const ai = a.startsWith('__') ? 1 : 0
      const bi = b.startsWith('__') ? 1 : 0
      if (ai !== bi) return ai - bi
      return a.localeCompare(b)
    })

    for (const key of sorted) {
      const raw = displayContext[key]
      if (key === CTX_STUDENT_FORMS_SUBMITTED) {
        out.push({
          key,
          label: 'وضعیت ثبت فرم‌های مرحله',
          value: summarizeFormsSubmitted(raw),
        })
        continue
      }
      if (key === CTX_DOCUMENTS_RESUBMIT_FIELDS) {
        const parts = Array.isArray(raw) ? raw.map((k) => resolveContextRowLabel(k, fieldLabelMap) || k) : []
        out.push({
          key,
          label: 'مدارک نیازمند بارگذاری مجدد',
          value: parts.length ? parts.join('، ') : '—',
        })
        continue
      }
      if (key === '__document_field_status') {
        out.push({
          key,
          label: 'وضعیت بررسی هر مدرک',
          value: renderFriendlyContextValue(React, raw, fieldLabelMap, labelState, 0),
        })
        continue
      }
      if (key === '__document_field_rejection_notes') {
        out.push({
          key,
          label: 'توضیح نقص مدارک',
          value: renderFriendlyContextValue(React, raw, fieldLabelMap, labelState, 0),
        })
        continue
      }
      if (key === CTX_STUDENT_FORMS_UNLOCK) {
        out.push({
          key,
          label: 'مراحل با ویرایش باز برای دانشجو',
          value: summarizeFormsUnlock(raw),
        })
        continue
      }

      const label = resolveContextRowLabel(key, fieldLabelMap)
      if (!label) continue

      if (key === 'interview_result') {
        const s = formatInterviewResultDisplay(raw, labelState)
        out.push({
          key,
          label,
          value: s != null ? s : renderFriendlyContextValue(React, raw, fieldLabelMap, labelState, 0),
        })
        continue
      }

      if ((key === 'to_state' || key === 'from_state') && typeof raw === 'string') {
        out.push({ key, label, value: labelState(raw) })
        continue
      }

      const scalar = formatScalar(raw)
      if (scalar !== null) {
        out.push({ key, label, value: scalar })
        continue
      }

      out.push({
        key,
        label,
        value: renderFriendlyContextValue(React, raw, fieldLabelMap, labelState, 0),
      })
    }

    return out
  }, [displayContext, hasContext, fieldLabelMap])

  if (!hasContext && !hasHistory) {
    return null
  }

  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap',
        marginBottom: '0.65rem',
      }}>
        <label style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1f2937' }}>{title}</label>
      </div>

      {hasHistory && (
        <div style={{ marginBottom: hasContext ? '1.25rem' : 0 }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.5rem' }}>
            سابقه انتقال‌ها
          </div>
          <div style={{
            border: '1px solid #e0e7ff',
            borderRadius: '10px',
            background: 'linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%)',
            maxHeight: historyMaxHeight,
            overflowY: 'auto',
            padding: '0.5rem 0.65rem',
          }}>
            {historyList.map((h, idx) => (
              <div
                key={idx}
                style={{
                  padding: '0.55rem 0.6rem',
                  marginBottom: idx < historyList.length - 1 ? '0.45rem' : 0,
                  borderRight: '3px solid #6366f1',
                  background: '#fff',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  lineHeight: 1.55,
                }}
              >
                <div style={{ fontWeight: 600, color: '#1e293b' }}>
                  <span style={{ color: '#64748b', fontWeight: 600 }}>{idx + 1}.</span>
                  {' '}
                  {h.from_state ? labelState(h.from_state) : 'شروع'}
                  {' '}
                  <span style={{ color: '#94a3b8' }}>→</span>
                  {' '}
                  {labelState(h.to_state)}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '0.25rem' }}>
                  {h.actor_role && (
                    <span>
                      نقش:
                      {' '}
                      {formatActorRole(h.actor_role)}
                    </span>
                  )}
                  {h.entered_at && (
                    <span>
                      {h.actor_role ? ' · ' : ''}
                      {formatIsoMaybe(h.entered_at)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {hasContext && (
        <>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.5rem' }}>
            جزئیات ثبت‌شده روی پرونده
          </div>

          {rows.length === 0 ? (
            <p style={{
              fontSize: '0.82rem', color: '#6b7280', margin: 0, padding: '0.75rem 1rem',
              background: '#f9fafb', borderRadius: '8px', border: '1px dashed #d1d5db',
            }}>
              فقط اطلاعات مرتبط با پیگیری پرونده اینجا نشان داده می‌شود. اگر خالی است، سابقهٔ بالا را ببینید.
            </p>
          ) : (
            <div style={{
              border: '1px solid #e5e7eb', borderRadius: '10px', overflow: 'hidden', maxHeight, overflowY: 'auto',
              background: '#fafafa',
            }}>
              {rows.map(({ key, label, value }) => (
                <div
                  key={key}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(120px, 36%) 1fr',
                    gap: '0.65rem',
                    padding: '0.65rem 0.85rem',
                    borderBottom: '1px solid #eee',
                    fontSize: '0.82rem',
                    alignItems: 'start',
                  }}
                >
                  <div style={{ color: '#6b7280', fontWeight: 600 }}>{label}</div>
                  <div style={{ color: '#111827', lineHeight: 1.55, wordBreak: 'break-word' }}>{value}</div>
                </div>
              ))}
            </div>
          )}
          {rows.length > 0 && (
            <p style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.4rem', marginBottom: 0 }}>
              برچسب‌ها در صورت وجود، از فرم همین فرایند خوانده می‌شوند.
            </p>
          )}
        </>
      )}
    </div>
  )
}
