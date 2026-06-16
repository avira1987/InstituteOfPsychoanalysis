import React from 'react'
import {
  REGISTRATION_FIELD_LABELS,
  REGISTRATION_PROFILE_DISPLAY_ORDER,
  formatRegistrationProfileValue,
} from '../utils/studentRegistrationProfile'

/**
 * نمایش فقط‌خواندنی اطلاعات تکمیلی ثبت‌نام در پروفایل دانشجو.
 * @param {{ extraData?: Record<string, unknown>, email?: string }} props
 */
export default function StudentRegistrationProfileView({ extraData, email }) {
  const extra = extraData && typeof extraData === 'object' ? extraData : {}

  const items = []
  if (email) {
    items.push({ key: 'email', label: REGISTRATION_FIELD_LABELS.email, value: email })
  }
  for (const key of REGISTRATION_PROFILE_DISPLAY_ORDER) {
    const raw = extra[key]
    if (raw == null || raw === '') continue
    items.push({
      key,
      label: REGISTRATION_FIELD_LABELS[key] || key,
      value: formatRegistrationProfileValue(key, raw),
    })
  }

  if (!items.length) {
    return (
      <p className="muted" style={{ fontSize: '0.9rem', margin: 0 }}>
        اطلاعات تکمیلی ثبت‌نام هنوز ثبت نشده است.
      </p>
    )
  }

  return (
    <div className="student-registration-profile-grid">
      {items.map(({ key, label, value }) => (
        <div key={key} className="student-registration-profile-item">
          <span className="student-registration-profile-label">{label}</span>
          <span
            className="student-registration-profile-value"
            dir={key.includes('phone') || key === 'birth_date' ? 'ltr' : undefined}
            style={key.includes('phone') || key === 'birth_date' ? { textAlign: 'right' } : undefined}
          >
            {value}
          </span>
        </div>
      ))}
    </div>
  )
}
