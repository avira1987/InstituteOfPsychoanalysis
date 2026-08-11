import React, { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { educationalTherapistSlotsApi } from '../services/api'
import CreatableSearchSelect from './CreatableSearchSelect'

const DAY_OPTIONS = [
  { value: 5, label: 'شنبه' },
  { value: 6, label: 'یکشنبه' },
  { value: 0, label: 'دوشنبه' },
  { value: 1, label: 'سه‌شنبه' },
  { value: 2, label: 'چهارشنبه' },
  { value: 3, label: 'پنج‌شنبه' },
  { value: 4, label: 'جمعه' },
]

function statusBadge(status) {
  if (status === 'booked') return <span className="badge badge-warning">رزروشده</span>
  return <span className="badge badge-success">آزاد</span>
}

export default function EducationalTherapistSlotsAdmin({ showToast }) {
  const { user } = useAuth()
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  const [therapists, setTherapists] = useState([])
  const [filterTherapist, setFilterTherapist] = useState('')
  const [includeBooked, setIncludeBooked] = useState(true)
  const [saving, setSaving] = useState(false)

  const [therapistUserId, setTherapistUserId] = useState('')
  const [dayOfWeek, setDayOfWeek] = useState(5)
  const [startTime, setStartTime] = useState('10:00')
  const [endTime, setEndTime] = useState('11:00')
  const [courseType, setCourseType] = useState('')
  const [weekInterval, setWeekInterval] = useState(1)
  const [labelFa, setLabelFa] = useState('')

  const load = () => {
    setLoading(true)
    educationalTherapistSlotsApi
      .manageList(includeBooked, filterTherapist || undefined)
      .then((r) => setSlots(r.data?.slots || []))
      .catch(() => showToast?.('بارگذاری شیت ناموفق بود.', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [includeBooked, filterTherapist])

  useEffect(() => {
    educationalTherapistSlotsApi
      .manageTherapists()
      .then((r) => {
        const rows = Array.isArray(r.data?.therapists) ? r.data.therapists : []
        setTherapists(
          rows.map((t) => ({
            value: t.id,
            label_fa: t.label_fa || t.username || t.id,
          })),
        )
      })
      .catch(() => {
        setTherapists([])
        showToast?.('بارگذاری فهرست درمانگران ناموفق بود.', 'error')
      })
  }, [])

  const therapistOptions = useMemo(() => therapists, [therapists])

  const therapistNameById = useMemo(() => {
    const map = new Map()
    for (const t of therapists) {
      if (t?.value) map.set(String(t.value), t.label_fa || t.value)
    }
    return map
  }, [therapists])

  const displayTherapistName = (slot) => {
    const fromApi = (slot?.therapist_name_fa || '').trim()
    const tid = String(slot?.therapist_user_id || '')
    const looksLikeId = !fromApi || fromApi === tid || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(fromApi)
    if (!looksLikeId) return fromApi
    return therapistNameById.get(tid) || fromApi || '—'
  }

  const createSlot = async (e) => {
    e.preventDefault()
    if (!therapistUserId) {
      showToast?.('درمانگر را انتخاب کنید.', 'error')
      return
    }
    setSaving(true)
    try {
      await educationalTherapistSlotsApi.manageCreate({
        therapist_user_id: therapistUserId,
        day_of_week: Number(dayOfWeek),
        start_local_time: startTime,
        end_local_time: endTime,
        course_type: courseType || null,
        week_interval: Number(weekInterval) === 2 ? 2 : 1,
        label_fa: labelFa || null,
      })
      showToast?.('وقت آزاد ثبت شد.')
      setLabelFa('')
      load()
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'ثبت وقت ناموفق بود.', 'error')
    } finally {
      setSaving(false)
    }
  }

  const releaseSlot = async (id) => {
    try {
      await educationalTherapistSlotsApi.manageRelease(id)
      showToast?.('اسلات آزاد شد.')
      load()
    } catch {
      showToast?.('آزادسازی ناموفق بود.', 'error')
    }
  }

  const deleteSlot = async (id) => {
    if (!window.confirm('این وقت آزاد حذف شود؟')) return
    try {
      await educationalTherapistSlotsApi.manageDelete(id)
      showToast?.('حذف شد.')
      load()
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'حذف ناموفق بود.', 'error')
    }
  }

  if (!user) return null

  return (
    <div className="card" data-testid="et-slots-admin">
      <div className="card-header">
        <h3 className="card-title">شیت وقت‌های آزاد درمانگران آموزشی</h3>
      </div>
      <p className="psf-hint" style={{ padding: '0 1rem' }}>
        وقت‌های اعلام‌شده توسط درمانگران آموزشی را در این شیت ثبت کنید. دانشجو از همین شیت انتخاب می‌کند و بدون تأیید مجدد درمانگر، پس از پرداخت فعال می‌شود.
      </p>

      <form onSubmit={createSlot} style={{ padding: '0 1rem 1rem', display: 'grid', gap: '0.75rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
          <label className="psf-field">
            <span className="psf-label">درمانگر *</span>
            <CreatableSearchSelect
              options={therapistOptions}
              value={therapistUserId}
              onChange={setTherapistUserId}
              placeholder="انتخاب درمانگر"
              allowCreate={false}
            />
          </label>
          <label className="psf-field">
            <span className="psf-label">روز هفته *</span>
            <select className="psf-input" value={dayOfWeek} onChange={(e) => setDayOfWeek(e.target.value)}>
              {DAY_OPTIONS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </label>
          <label className="psf-field">
            <span className="psf-label">شروع *</span>
            <input className="psf-input" type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
          </label>
          <label className="psf-field">
            <span className="psf-label">پایان *</span>
            <input className="psf-input" type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
          </label>
          <label className="psf-field">
            <span className="psf-label">تکرار *</span>
            <select className="psf-input" value={weekInterval} onChange={(e) => setWeekInterval(Number(e.target.value))}>
              <option value={1}>هفتگی</option>
              <option value={2}>هفته‌درمیان</option>
            </select>
          </label>
          <label className="psf-field">
            <span className="psf-label">محدودیت دوره</span>
            <select className="psf-input" value={courseType} onChange={(e) => setCourseType(e.target.value)}>
              <option value="">هر دو دوره</option>
              <option value="introductory">آشنایی</option>
              <option value="comprehensive">جامع</option>
            </select>
          </label>
          <label className="psf-field">
            <span className="psf-label">برچسب (اختیاری)</span>
            <input className="psf-input" value={labelFa} onChange={(e) => setLabelFa(e.target.value)} />
          </label>
        </div>
        <div>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'در حال ثبت…' : 'افزودن وقت آزاد'}
          </button>
        </div>
      </form>

      <div style={{ padding: '0 1rem 1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <label className="psf-field" style={{ margin: 0, minWidth: 200 }}>
          <span className="psf-label">فیلتر درمانگر</span>
          <CreatableSearchSelect
            options={[{ value: '', label_fa: 'همه' }, ...therapistOptions]}
            value={filterTherapist}
            onChange={setFilterTherapist}
            placeholder="همه"
            allowCreate={false}
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <input type="checkbox" checked={includeBooked} onChange={(e) => setIncludeBooked(e.target.checked)} />
          نمایش رزروشده‌ها
        </label>
      </div>

      {loading ? (
        <p style={{ padding: '0 1rem' }}>در حال بارگذاری…</p>
      ) : (
        <div className="table-responsive" style={{ padding: '0 1rem 1rem' }}>
          <table className="table">
            <thead>
              <tr>
                <th>درمانگر</th>
                <th>روز</th>
                <th>ساعت</th>
                <th>تکرار</th>
                <th>دوره</th>
                <th>وضعیت</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {slots.length === 0 && (
                <tr><td colSpan={7}>وقتی ثبت نشده است.</td></tr>
              )}
              {slots.map((s) => (
                <tr key={s.id}>
                  <td>{displayTherapistName(s)}</td>
                  <td>{s.day_label_fa}</td>
                  <td>{s.start_local_time}–{s.end_local_time}</td>
                  <td>{s.week_interval_label_fa || (Number(s.week_interval) === 2 ? 'هفته‌درمیان' : 'هفتگی')}</td>
                  <td>{s.course_type === 'comprehensive' ? 'جامع' : s.course_type === 'introductory' ? 'آشنایی' : '—'}</td>
                  <td>{statusBadge(s.status)}</td>
                  <td style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                    {s.status === 'booked' && (
                      <button type="button" className="btn btn-sm btn-outline" onClick={() => releaseSlot(s.id)}>
                        آزادسازی
                      </button>
                    )}
                    {s.status === 'free' && (
                      <button type="button" className="btn btn-sm btn-outline btn-danger" onClick={() => deleteSlot(s.id)}>
                        حذف
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
