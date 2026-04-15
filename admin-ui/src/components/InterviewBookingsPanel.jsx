import React, { useState, useEffect } from 'react'
import { interviewSlotsApi } from '../services/api'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import { JALAALI_MONTHS_FA, utcIsoToShamsiTehran } from '../utils/shamsiDateTime'

function formatSlotShamsi(iso) {
  if (!iso) return '—'
  const p = utcIsoToShamsiTehran(iso)
  if (!p) {
    try {
      return new Date(iso).toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' })
    } catch {
      return iso
    }
  }
  const mon = JALAALI_MONTHS_FA[p.jm - 1] || ''
  return `${p.jy}/${String(p.jm).padStart(2, '0')}/${String(p.jd).padStart(2, '0')} ${String(p.hour).padStart(2, '0')}:${String(p.minute).padStart(2, '0')} (${mon})`
}

/**
 * فهرست اسلات‌های رزروشده با مشخصات دانشجو — برای مصاحبه‌گر و دفتر.
 */
export default function InterviewBookingsPanel({ showToast }) {
  const [bookings, setBookings] = useState([])
  const [includePast, setIncludePast] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    interviewSlotsApi
      .bookings(includePast)
      .then((r) => setBookings(r.data?.bookings || []))
      .catch(() => showToast?.('بارگذاری رزروهای مصاحبه ناموفق بود.', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [includePast])

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }}>
      <div className="card-header">
        <h3 className="card-title">رزروهای وقت مصاحبه</h3>
        <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.9rem', maxWidth: '42rem' }}>
          دانشجویانی که از اسلات‌های آزاد یک زمان را انتخاب کرده‌اند؛ زمان‌ها به‌وقت ایران و تقویم شمسی نمایش داده می‌شوند.
        </p>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.88rem' }}>
            <input type="checkbox" checked={includePast} onChange={(e) => setIncludePast(e.target.checked)} />
            نمایش گذشته
          </label>
        </div>
        {loading ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.88rem' }}>
              <thead>
                <tr>
                  <th>شروع</th>
                  <th>پایان</th>
                  <th>دانشجو</th>
                  <th>کد</th>
                  <th>تماس</th>
                  <th>دوره</th>
                  <th>حضور</th>
                  <th>مکان / لینک</th>
                  <th>فرایند</th>
                  <th>مرحله</th>
                </tr>
              </thead>
              <tbody>
                {bookings.map((row) => {
                  const s = row.slot
                  const st = row.student
                  const ins = row.instance
                  const loc = s.mode === 'online'
                    ? (s.meeting_link || '—')
                    : (s.location_fa || '—')
                  return (
                    <tr key={s.id}>
                      <td>{formatSlotShamsi(s.starts_at)}</td>
                      <td>{formatSlotShamsi(s.ends_at)}</td>
                      <td>{st.full_name_fa || '—'}</td>
                      <td>{formatStudentCodeDisplay(st.student_code)}</td>
                      <td dir="ltr" style={{ fontSize: '0.82rem' }}>{st.phone || st.email || '—'}</td>
                      <td>{st.course_type === 'comprehensive' ? 'جامع' : st.course_type === 'introductory' ? 'آشنایی' : (st.course_type || '—')}</td>
                      <td>{s.mode === 'online' ? 'آنلاین' : 'حضوری'}</td>
                      <td style={{ fontSize: '0.78rem', maxWidth: '12rem', wordBreak: 'break-word' }} dir={s.mode === 'online' ? 'ltr' : 'rtl'}>{loc}</td>
                      <td>{ins ? labelProcess(ins.process_code) : '—'}</td>
                      <td>{ins ? labelState(ins.current_state) : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {!bookings.length && (
              <p className="muted" style={{ marginTop: '0.5rem' }}>رزرو فعالی ثبت نشده است.</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
