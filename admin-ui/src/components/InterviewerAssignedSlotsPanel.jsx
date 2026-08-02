import React, { useEffect, useState } from 'react'
import { interviewSlotsApi } from '../services/api'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

function formatCourseTypeLabel(courseType) {
  if (courseType === 'introductory') return 'آشنایی'
  if (courseType === 'comprehensive') return 'جامع'
  return courseType || 'عمومی'
}

/**
 * وقت‌های آزاد اختصاص‌یافته به مصاحبه‌گر جاری.
 */
export default function InterviewerAssignedSlotsPanel({ showToast }) {
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  const [includePast, setIncludePast] = useState(false)

  const load = () => {
    setLoading(true)
    interviewSlotsApi
      .myAssigned(includePast)
      .then((r) => setSlots(r.data?.slots || []))
      .catch(() => showToast?.('بارگذاری وقت‌های اختصاص‌یافته ناموفق بود.', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [includePast])

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }} data-testid="interviewer-assigned-slots">
      <div className="card-header">
        <h3 className="card-title">وقت‌های اختصاص‌یافته به من</h3>
        <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.88rem', maxWidth: '48rem', lineHeight: 1.55 }}>
          بازه‌های آزاد که برای شما تعریف شده‌اند. پس از انتخاب توسط دانشجو، در بخش «رزروهای وقت مصاحبه» نمایش داده می‌شود
          و اعلان دریافت خواهید کرد.
        </p>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.88rem', marginBottom: '0.75rem' }}>
          <input type="checkbox" checked={includePast} onChange={(e) => setIncludePast(e.target.checked)} />
          نمایش گذشته
        </label>
        {loading ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : !slots.length ? (
          <p className="muted">وقت آزاد اختصاص‌یافته‌ای ثبت نشده است.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
              <thead>
                <tr>
                  <th>شروع</th>
                  <th>پایان</th>
                  <th>دوره</th>
                  <th>برگزاری</th>
                  <th>مکان</th>
                </tr>
              </thead>
              <tbody>
                {slots.map((s) => (
                  <tr key={s.id}>
                    <td>{formatShamsiTehran(s.starts_at)}</td>
                    <td>{formatShamsiTehran(s.ends_at)}</td>
                    <td>{formatCourseTypeLabel(s.course_type)}</td>
                    <td>{s.mode === 'online' ? 'آنلاین' : 'حضوری'}</td>
                    <td dir="rtl">{s.mode === 'online' ? 'آنلاین' : (s.location_fa || '—')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
