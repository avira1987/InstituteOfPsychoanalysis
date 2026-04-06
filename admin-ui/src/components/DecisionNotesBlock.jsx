import React from 'react'

/**
 * فیلد استاندارد «توضیح / نظر» قبل از دکمه‌های انتقال فرایند (جایگزین textareaی JSON خام).
 */
export default function DecisionNotesBlock({
  value,
  onChange,
  title = 'توضیح یا نظر شما (اختیاری)',
  hint = 'در صورت نیاز قبل از زدن دکمه بنویسید؛ متن با همان اقدام ثبت می‌شود.',
  placeholder = 'مثال: تأیید با توجه به مدارک ارسال‌شده…',
  minHeight = '72px',
}) {
  return (
    <div style={{ marginBottom: '0.75rem' }}>
      <label style={{
        fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '0.35rem', color: '#374151',
      }}>
        {title}
      </label>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        dir="rtl"
        style={{
          width: '100%',
          minHeight,
          padding: '0.65rem 0.75rem',
          borderRadius: '8px',
          border: '1px solid #d1d5db',
          fontSize: '0.88rem',
          lineHeight: 1.6,
          resize: 'vertical',
          fontFamily: 'inherit',
          boxSizing: 'border-box',
        }}
      />
      {hint ? (
        <p style={{
          fontSize: '0.72rem', color: '#6b7280', marginTop: '0.35rem', marginBottom: 0, lineHeight: 1.5,
        }}>
          {hint}
        </p>
      ) : null}
    </div>
  )
}
