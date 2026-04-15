import React, { useState, useEffect } from 'react'
import { interviewSlotsApi } from '../services/api'
import ShamsiDateTimePicker, { addMinutesToShamsiParts } from './ShamsiDateTimePicker'
import {
  defaultShamsiTehranNow,
  isValidJalaaliDate,
  JALAALI_MONTHS_FA,
  shamsiDateTimeToUtcIso,
  utcIsoToShamsiTehran,
} from '../utils/shamsiDateTime'

function formatSlotAdmin(iso) {
  if (!iso) return '—'
  const p = utcIsoToShamsiTehran(iso)
  if (!p) return iso
  const mon = JALAALI_MONTHS_FA[p.jm - 1] || ''
  return `${p.jy}/${String(p.jm).padStart(2, '0')}/${String(p.jd).padStart(2, '0')} ${String(p.hour).padStart(2, '0')}:${String(p.minute).padStart(2, '0')} (${mon})`
}

export default function InterviewSlotsAdmin({ showToast }) {
  const [slots, setSlots] = useState([])
  const [includePast, setIncludePast] = useState(false)
  const [loading, setLoading] = useState(true)
  const [startsParts, setStartsParts] = useState(() => defaultShamsiTehranNow())
  const [endsParts, setEndsParts] = useState(() => addMinutesToShamsiParts(defaultShamsiTehranNow(), 60) || defaultShamsiTehranNow())
  const [courseType, setCourseType] = useState('')
  const [mode, setMode] = useState('in_person')
  const [locationFa, setLocationFa] = useState('')
  const [meetingLink, setMeetingLink] = useState('')
  const [labelFa, setLabelFa] = useState('')
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    interviewSlotsApi
      .manageList(includePast)
      .then((r) => setSlots(r.data?.slots || []))
      .catch(() => showToast?.('بارگذاری اسلات‌ها ناموفق بود.', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [includePast])

  const createSlot = async (e) => {
    e.preventDefault()
    const { jy: sy, jm: sm, jd: sd, hour: sh, minute: smin } = startsParts
    const { jy: ey, jm: em, jd: ed, hour: eh, minute: emin } = endsParts
    if (!isValidJalaaliDate(sy, sm, sd) || !isValidJalaaliDate(ey, em, ed)) {
      showToast?.('تاریخ شمسی نامعتبر است.', 'error')
      return
    }
    let startsIso
    let endsIso
    try {
      startsIso = shamsiDateTimeToUtcIso(sy, sm, sd, sh, smin)
      endsIso = shamsiDateTimeToUtcIso(ey, em, ed, eh, emin)
    } catch {
      showToast?.('تاریخ یا زمان نامعتبر است.', 'error')
      return
    }
    if (new Date(endsIso) <= new Date(startsIso)) {
      showToast?.('پایان باید بعد از شروع باشد.', 'error')
      return
    }
    setSaving(true)
    try {
      await interviewSlotsApi.manageCreate({
        starts_at: startsIso,
        ends_at: endsIso,
        course_type: courseType || null,
        mode,
        location_fa: locationFa || null,
        meeting_link: meetingLink || null,
        label_fa: labelFa || null,
      })
      showToast?.('اسلات ثبت شد.')
      const now = defaultShamsiTehranNow()
      setStartsParts(now)
      setEndsParts(addMinutesToShamsiParts(now, 60) || now)
      setLabelFa('')
      load()
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'ثبت ناموفق بود.', 'error')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('حذف این اسلات؟ فقط در صورت عدم رزرو امکان‌پذیر است.')) return
    try {
      await interviewSlotsApi.manageDelete(id)
      showToast?.('حذف شد.')
      load()
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'حذف ناموفق بود.', 'error')
    }
  }

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }}>
      <div className="card-header">
        <h3 className="card-title">تعریف اسلات مصاحبه</h3>
        <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.9rem', maxWidth: '42rem' }}>
          زمان‌های قابل رزرو برای دانشجویان در مرحلهٔ انتخاب وقت مصاحبه. پس از رزرو، تا پایان بازه برای دیگران بسته می‌ماند. یادآوری پیامکی قبل از مصاحبه توسط سامانه ارسال می‌شود.
        </p>
      </div>
      <div style={{ padding: '0 1.25rem 1rem' }}>
        <form onSubmit={createSlot} style={{ display: 'grid', gap: '0.9rem', maxWidth: '36rem' }}>
          <ShamsiDateTimePicker
            label="شروع (تقویم شمسی)"
            idPrefix="slot-start"
            value={startsParts}
            onChange={setStartsParts}
          />
          <ShamsiDateTimePicker
            label="پایان (تقویم شمسی)"
            idPrefix="slot-end"
            value={endsParts}
            onChange={setEndsParts}
          />
          <label>
            <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.88rem' }}>نوع دوره (اختیاری)</span>
            <select className="psf-input" value={courseType} onChange={(e) => setCourseType(e.target.value)} style={{ width: '100%' }}>
              <option value="">هر دو / عمومی</option>
              <option value="introductory">آشنایی (مقدماتی)</option>
              <option value="comprehensive">جامع</option>
            </select>
          </label>
          <label>
            <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.88rem' }}>نوع برگزاری</span>
            <select className="psf-input" value={mode} onChange={(e) => setMode(e.target.value)} style={{ width: '100%' }}>
              <option value="in_person">حضوری</option>
              <option value="online">آنلاین</option>
            </select>
          </label>
          <label>
            <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.88rem' }}>مکان (حضوری)</span>
            <input className="psf-input" value={locationFa} onChange={(e) => setLocationFa(e.target.value)} style={{ width: '100%' }} dir="rtl" />
          </label>
          <label>
            <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.88rem' }}>لینک جلسه (آنلاین)</span>
            <input className="psf-input" value={meetingLink} onChange={(e) => setMeetingLink(e.target.value)} style={{ width: '100%' }} dir="ltr" />
          </label>
          <label>
            <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.88rem' }}>برچسب کوتاه (اختیاری)</span>
            <input className="psf-input" value={labelFa} onChange={(e) => setLabelFa(e.target.value)} style={{ width: '100%' }} dir="rtl" />
          </label>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'در حال ثبت…' : 'ثبت اسلات'}
          </button>
        </form>
      </div>

      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <h4 style={{ margin: 0 }}>فهرست اسلات‌ها</h4>
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
                  <th>دوره</th>
                  <th>حضور</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {slots.map((s) => (
                  <tr key={s.id}>
                    <td>{formatSlotAdmin(s.starts_at)}</td>
                    <td>{formatSlotAdmin(s.ends_at)}</td>
                    <td>{s.course_type || '—'}</td>
                    <td>{s.mode === 'online' ? 'آنلاین' : 'حضوری'}</td>
                    <td>{s.assigned_student_id ? 'رزرو شده' : 'آزاد'}</td>
                    <td>
                      {!s.assigned_student_id && (
                        <button type="button" className="btn btn-outline btn-sm" onClick={() => remove(s.id)}>
                          حذف
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!slots.length && <p className="muted" style={{ marginTop: '0.5rem' }}>اسلاتی ثبت نشده است.</p>}
          </div>
        )}
      </div>
    </div>
  )
}
