/** برچسب‌های ثابت برای کلیدهای رایج در context_data */
export const CONTEXT_KEY_LABELS = {
  notes: 'یادداشت ثبت‌شده',
  interview_result: 'نتیجهٔ مصاحبه',
  weekly_sessions: 'تعداد جلسات هفتگی',
  to_state: 'هدف انتقال',
  termination_requests: 'درخواست‌های خاتمه',
  reminder_45_48_sent_at: 'زمان ارسال یادآور (۴۵–۴۸ ساعت)',
  student_status: 'وضعیت دانشجو (در پرونده)',
  amount: 'مبلغ',
  decision: 'تصمیم',
  interview_result_submitted: 'ثبت نتیجهٔ مصاحبه',
  return_reminder_at: 'یادآور بازگشت',
  logged_at: 'زمان ثبت',
  payload: 'جزئیات',
}

const INTERVIEW_RESULT_LABELS = {
  conditional_therapy: 'درمان شرطی',
  single_course: 'تک‌درس / محدود',
  full_admission: 'پذیرش کامل',
  rejected: 'رد',
}

/**
 * @param {unknown[]} forms
 * @returns {Map<string, string>}
 */
export function buildFieldLabelMap(forms) {
  const m = new Map()
  for (const f of forms || []) {
    for (const field of f.fields || []) {
      const name = field.name
      if (name && field.label_fa) m.set(name, field.label_fa)
    }
  }
  return m
}

export function prettyKeyFallback(key) {
  if (key.startsWith('__')) return null
  if (CONTEXT_KEY_LABELS[key]) return CONTEXT_KEY_LABELS[key]
  return key.replace(/_/g, ' ')
}

/**
 * @param {string} key
 * @param {Map<string, string>|null|undefined} fieldLabelMap
 */
export function resolveContextRowLabel(key, fieldLabelMap) {
  if (CONTEXT_KEY_LABELS[key]) return CONTEXT_KEY_LABELS[key]
  if (fieldLabelMap && fieldLabelMap.has(key)) return fieldLabelMap.get(key)
  return prettyKeyFallback(key)
}

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

function looksLikeIso(s) {
  return typeof s === 'string' && (/^\d{4}-\d{2}-\d{2}/.test(s) || (s.includes('T') && s.includes(':')))
}

export function formatInterviewResultDisplay(value, labelState) {
  if (typeof value !== 'string') return null
  return INTERVIEW_RESULT_LABELS[value] || (labelState ? labelState(value) : value)
}

const MAX_DEPTH = 5

/**
 * @param {typeof import('react')} React
 * @param {Map<string, string>|null|undefined} fieldLabelMap
 * @param {(s: string) => string} labelState
 */
export function renderFriendlyContextValue(React, value, fieldLabelMap, labelState, depth = 0) {
  if (depth > MAX_DEPTH) return '…'
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'بله' : 'خیر'
  if (typeof value === 'number') return String(value)
  if (typeof value === 'string') {
    if (looksLikeIso(value)) return formatIsoMaybe(value)
    return value
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return '—'
    const allPrimitive = value.every(x => x === null || x === undefined
      || typeof x === 'string' || typeof x === 'number' || typeof x === 'boolean')
    if (allPrimitive) {
      return value.map(x => (x === null || x === undefined ? '—' : String(x))).join('، ')
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
        {value.map((item, i) => (
          <div
            key={i}
            style={{
              padding: '0.45rem 0.55rem',
              background: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              fontSize: '0.8rem',
            }}
          >
            {renderFriendlyContextValue(React, item, fieldLabelMap, labelState, depth + 1)}
          </div>
        ))}
      </div>
    )
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value)
    if (entries.length === 0) return '—'
    return (
      <div style={{ paddingRight: depth ? '0.35rem' : 0 }}>
        {entries.map(([k, v]) => {
          const subLabel = resolveContextRowLabel(k, fieldLabelMap) || k
          return (
            <div
              key={k}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(88px, 32%) 1fr',
                gap: '0.4rem',
                fontSize: depth ? '0.78rem' : '0.82rem',
                marginBottom: '0.35rem',
                alignItems: 'start',
              }}
            >
              <span style={{ color: '#6b7280', fontWeight: 600 }}>{subLabel}</span>
              <span style={{ color: '#111827', lineHeight: 1.5 }}>
                {renderFriendlyContextValue(React, v, fieldLabelMap, labelState, depth + 1)}
              </span>
            </div>
          )
        })}
      </div>
    )
  }
  return String(value)
}
