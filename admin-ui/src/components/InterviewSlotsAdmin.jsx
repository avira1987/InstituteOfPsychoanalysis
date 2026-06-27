import React, { useState, useEffect } from 'react'
import { interviewSlotsApi } from '../services/api'
import ShamsiDateTimePicker, { addMinutesToShamsiParts } from './ShamsiDateTimePicker'
import InterviewSlotRescheduleModal from './InterviewSlotRescheduleModal'
import OnlineMeetingJoinCta from './OnlineMeetingJoinCta'
import {
  defaultShamsiTehranNow,
  formatShamsiTehran,
  isValidJalaaliDate,
  shamsiDateTimeToUtcIso,
  utcIsoToShamsiTehran,
} from '../utils/shamsiDateTime'

function formatSlotAdmin(iso) {
  return formatShamsiTehran(iso)
}

export default function InterviewSlotsAdmin({ showToast, onCapacityChanged }) {
  const [slots, setSlots] = useState([])
  const [includePast, setIncludePast] = useState(false)
  const [loading, setLoading] = useState(true)
  const [startsParts, setStartsParts] = useState(() => defaultShamsiTehranNow())
  const [endsParts, setEndsParts] = useState(() => addMinutesToShamsiParts(defaultShamsiTehranNow(), 60) || defaultShamsiTehranNow())
  const [courseType, setCourseType] = useState('')
  const [mode, setMode] = useState('online')
  const [locationFa, setLocationFa] = useState('')
  const [meetingLink, setMeetingLink] = useState('')
  const [labelFa, setLabelFa] = useState('')
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [togglingJoinId, setTogglingJoinId] = useState(null)
  const [rescheduleSlot, setRescheduleSlot] = useState(null)

  const toggleStudentJoinOpen = async (slot, nextOpen) => {
    setTogglingJoinId(slot.id)
    try {
      await interviewSlotsApi.manageUpdate(slot.id, { student_join_open: nextOpen })
      showToast?.(nextOpen ? 'ورود دانشجو به جلسه فعال شد.' : 'ورود زودهنگام دانشجو غیرفعال شد.')
      load()
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'تغییر وضعیت ورود ناموفق بود.', 'error')
    } finally {
      setTogglingJoinId(null)
    }
  }

  const load = () => {
    setLoading(true)
    interviewSlotsApi
      .manageList(includePast)
      .then((r) => setSlots(r.data?.slots || []))
      .catch(() => showToast?.('بارگذاری وقت‌ها ناموفق بود.', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [includePast])

  const resetFormToNew = () => {
    const now = defaultShamsiTehranNow()
    setStartsParts(now)
    setEndsParts(addMinutesToShamsiParts(now, 60) || now)
    setCourseType('')
    setMode('online')
    setLocationFa('')
    setMeetingLink('')
    setLabelFa('')
    setEditingId(null)
  }

  const startEdit = (s) => {
    const sp = utcIsoToShamsiTehran(s.starts_at)
    const ep = utcIsoToShamsiTehran(s.ends_at)
    if (sp) setStartsParts(sp)
    if (ep) setEndsParts(ep)
    setCourseType(s.course_type || '')
    setMode(s.mode === 'online' ? 'online' : 'in_person')
    setLocationFa(s.location_fa || '')
    setMeetingLink(s.meeting_link || '')
    setLabelFa(s.label_fa || '')
    setEditingId(s.id)
  }

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
      const bodyBase = {
        starts_at: startsIso,
        ends_at: endsIso,
        course_type: courseType || null,
        mode,
        location_fa: locationFa || null,
        meeting_link: meetingLink || null,
        label_fa: labelFa || null,
      }
      if (editingId) {
        await interviewSlotsApi.manageUpdate(editingId, bodyBase)
        showToast?.('تغییرات وقت ذخیره شد.')
      } else {
        await interviewSlotsApi.manageCreate(bodyBase)
        showToast?.('وقت ثبت شد.')
      }
      resetFormToNew()
      load()
      onCapacityChanged?.()
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'ثبت ناموفق بود.', 'error')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('حذف این وقت؟ فقط در صورت عدم رزرو امکان‌پذیر است.')) return
    try {
      await interviewSlotsApi.manageDelete(id)
      showToast?.('حذف شد.')
      if (editingId === id) resetFormToNew()
      load()
      onCapacityChanged?.()
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'حذف ناموفق بود.', 'error')
    }
  }

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }}>
      {rescheduleSlot ? (
        <InterviewSlotRescheduleModal
          slot={rescheduleSlot}
          onClose={() => setRescheduleSlot(null)}
          onSaved={load}
          showToast={showToast}
        />
      ) : null}
      <div className="card-header">
        <h3 className="card-title">تعریف وقت مصاحبه</h3>
        <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.88rem', maxWidth: '48rem', lineHeight: 1.55 }}>
          زمان‌های قابل رزرو برای دانشجو در مرحلهٔ انتخاب وقت. پس از انتخاب، تا{' '}
          <strong>۱۰ دقیقه</strong> مهلت پرداخت هزینهٔ مصاحبه وجود دارد؛ در غیر این صورت وقت آزاد و فرایند به مرحلهٔ قبل برمی‌گردد.
          پس از تأیید پرداخت، زمان تا برگزاری مصاحبه برای دیگران بسته می‌ماند. یادآوری پیامکی توسط سامانه ارسال می‌شود.
          {' '}
          <strong>مصاحبه‌گر:</strong> با هر بار ثبت وقت آزاد <em>دستی</em> جدید، فقط وقت‌های آزاد قبلیٔ <strong>همین مسیر دستی</strong> شما پاک می‌شود؛ وقت‌های ساخته‌شده از <strong>الگوی زمانی تکراری</strong> دست‌نخورده می‌مانند.
        </p>
      </div>
      <div style={{ padding: '0 1.25rem 1rem' }}>
        <form onSubmit={createSlot} className="interview-slots-admin__form">
          {editingId && (
            <p className="muted" style={{ margin: 0, fontSize: '0.86rem', padding: '0.35rem 0.5rem', background: 'var(--bg-muted)', borderRadius: '8px' }}>
              در حال ویرایش وقت انتخاب‌شده —{' '}
              <button type="button" className="btn btn-link btn-sm" style={{ padding: 0, verticalAlign: 'baseline' }} onClick={resetFormToNew}>
                انصراف
              </button>
            </p>
          )}
          <div className="interview-slots-admin__datetime-row">
            <ShamsiDateTimePicker
              compact
              label="شروع"
              idPrefix="slot-start"
              value={startsParts}
              onChange={setStartsParts}
            />
            <ShamsiDateTimePicker
              compact
              label="پایان"
              idPrefix="slot-end"
              value={endsParts}
              onChange={setEndsParts}
            />
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(11rem, 1fr))',
              gap: '0.45rem',
            }}
          >
            <label style={{ margin: 0 }}>
              <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>نوع دوره</span>
              <select className="psf-input" value={courseType} onChange={(e) => setCourseType(e.target.value)} style={{ width: '100%', minHeight: '2.35rem' }}>
                <option value="">هر دو / عمومی</option>
                <option value="introductory">آشنایی (مقدماتی)</option>
                <option value="comprehensive">جامع</option>
              </select>
            </label>
            <label style={{ margin: 0 }}>
              <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>برگزاری</span>
              <select className="psf-input" value={mode} onChange={(e) => setMode(e.target.value)} style={{ width: '100%', minHeight: '2.35rem' }}>
                <option value="online">آنلاین</option>
                <option value="in_person">حضوری</option>
              </select>
            </label>
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(14rem, 1fr))',
              gap: '0.45rem',
            }}
          >
            <label style={{ margin: 0 }}>
              <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>مکان (حضوری)</span>
              <input className="psf-input" value={locationFa} onChange={(e) => setLocationFa(e.target.value)} style={{ width: '100%', minHeight: '2.35rem' }} dir="rtl" />
            </label>
            <label style={{ margin: 0 }}>
              <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>لینک جلسه (آنلاین)</span>
              <input className="psf-input" value={meetingLink} onChange={(e) => setMeetingLink(e.target.value)} style={{ width: '100%', minHeight: '2.35rem' }} dir="ltr" />
            </label>
          </div>
          <label style={{ margin: 0, maxWidth: '28rem' }}>
            <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>برچسب کوتاه (اختیاری)</span>
            <input className="psf-input" value={labelFa} onChange={(e) => setLabelFa(e.target.value)} style={{ width: '100%', minHeight: '2.35rem' }} dir="rtl" />
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'در حال ذخیره…' : editingId ? 'ذخیرهٔ ویرایش' : 'ثبت وقت'}
            </button>
          </div>
        </form>
      </div>

      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <h4 style={{ margin: 0 }}>فهرست وقت‌ها</h4>
            <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.82rem', maxWidth: '40rem', lineHeight: 1.55 }}>
              همهٔ بازه‌های تعریف‌شده (آزاد، در انتظار پرداخت، رزروشده). برای جزئیات دانشجو و ثبت برگزاری، بخش «رزروهای وقت مصاحبه» را ببینید.
            </p>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.88rem' }}>
            <input type="checkbox" checked={includePast} onChange={(e) => setIncludePast(e.target.checked)} />
            نمایش گذشته
          </label>
        </div>
        {loading ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
              <thead>
                <tr>
                  <th>شروع</th>
                  <th>پایان</th>
                  <th>دوره</th>
                  <th>حضور</th>
                  <th>مکان / لینک</th>
                  <th>ورود دانشجو</th>
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
                    <td style={{ maxWidth: '14rem', fontSize: '0.8rem' }} dir={s.mode === 'online' ? 'ltr' : 'rtl'}>
                      {s.mode === 'online' ? (
                        <OnlineMeetingJoinCta
                          compact
                          mode="online"
                          meetingLink={s.meeting_link}
                          meetingLinkOpenAt={s.meeting_link_open_at}
                          meetingLinkIsVisible={s.meeting_link_is_visible}
                          startsAt={s.starts_at}
                          studentJoinOpen={!!s.student_join_open}
                          label="ورود به مصاحبه"
                          allowStaffCopy
                          preparing={!s.meeting_link && !!s.assigned_student_id && !s.booking_payment_deadline_at}
                          preparingText={
                            s.booking_payment_deadline_at
                              ? 'پس از پرداخت دانشجو، لینک آنلاین تولید می‌شود.'
                              : s.assigned_student_id
                                ? 'لینک آنلاین در حال آماده‌سازی است.'
                                : (s.meeting_link ? '' : 'لینک دستی ثبت نشده — پس از رزرو و پرداخت از الوکام ساخته می‌شود.')
                          }
                        />
                      ) : (
                        s.location_fa || '—'
                      )}
                    </td>
                    <td>
                      {s.mode === 'online' && s.assigned_student_id && !s.booking_payment_deadline_at ? (
                        <label
                          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.82rem', cursor: togglingJoinId === s.id ? 'wait' : 'pointer' }}
                          title="با فعال‌سازی، دانشجو می‌تواند قبل از ۳۰ دقیقه مانده به مصاحبه وارد جلسه شود."
                        >
                          <input
                            type="checkbox"
                            checked={!!s.student_join_open}
                            disabled={togglingJoinId === s.id}
                            onChange={(e) => toggleStudentJoinOpen(s, e.target.checked)}
                          />
                          {s.student_join_open ? 'فعال' : 'بسته'}
                        </label>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      {s.assigned_student_id
                        ? (s.booking_payment_deadline_at ? 'در انتظار پرداخت' : 'رزرو قطعی')
                        : 'آزاد'}
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {!s.assigned_student_id && (
                        <>
                          <button type="button" className="btn btn-outline btn-sm" onClick={() => startEdit(s)}>
                            ویرایش
                          </button>
                          {' '}
                          <button type="button" className="btn btn-outline btn-sm" onClick={() => remove(s.id)}>
                            حذف
                          </button>
                        </>
                      )}
                      {s.assigned_student_id && !s.booking_payment_deadline_at ? (
                        <button
                          type="button"
                          className="btn btn-outline btn-sm"
                          onClick={() => setRescheduleSlot(s)}
                        >
                          تغییر زمان
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!slots.length && <p className="muted" style={{ marginTop: '0.5rem' }}>وقتی ثبت نشده است.</p>}
          </div>
        )}
      </div>
    </div>
  )
}
