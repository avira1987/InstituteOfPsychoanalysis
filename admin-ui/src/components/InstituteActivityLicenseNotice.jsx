import React, { useEffect, useState } from 'react'
import { publicApi } from '../services/api'

/**
 * متن کوتاه اطلاع‌رسانی شماره پروانه فعالیت انستیتو در فرم ثبت‌نام.
 */
export default function InstituteActivityLicenseNotice({ compact = false, testId = 'institute-activity-license-notice' }) {
  const [number, setNumber] = useState(null)

  useEffect(() => {
    let cancelled = false
    publicApi.instituteInfo()
      .then((res) => {
        if (cancelled) return
        const value = String(res.data?.activity_license_number || '').trim()
        setNumber(value || null)
      })
      .catch(() => {
        if (!cancelled) setNumber(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!number) return null

  return (
    <div
      data-testid={testId}
      role="note"
      style={{
        marginBottom: compact ? '0.65rem' : '0.9rem',
        padding: compact ? '0.65rem 0.85rem' : '0.75rem 1rem',
        borderRadius: 10,
        background: '#f8fafc',
        borderRight: '4px solid #64748b',
        fontSize: compact ? '0.8rem' : '0.86rem',
        lineHeight: 1.75,
        color: '#334155',
      }}
    >
      این مرکز دارای پروانه فعالیت است. شماره پروانه فعالیت:{' '}
      <strong style={{ direction: 'ltr', display: 'inline-block' }}>{number}</strong>
    </div>
  )
}
