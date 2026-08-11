import React, { useState, useEffect } from 'react'
import { interviewSlotsApi, processExecApi } from '../services/api'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import OnlineMeetingJoinCta from './OnlineMeetingJoinCta'
import { interviewMeetingLinkPreparingState } from '../utils/interviewMeetingLinkStatus'
import InterviewSlotRescheduleModal from './InterviewSlotRescheduleModal'

function formatSlotShamsi(iso) {
  return formatShamsiTehran(iso)
}

/**
 * فهرست وقت‌های رزروشده با مشخصات دانشجو — برای مصاحبه‌گر و دفتر.
 */
export default function InterviewBookingsPanel({ showToast, onOpenResult }) {
  const [bookings, setBookings] = useState([])
  const [includePast, setIncludePast] = useState(false)
  const [loading, setLoading] = useState(true)
  const [advancingId, setAdvancingId] = useState(null)
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
      .bookings(includePast)
      .then((r) => setBookings(r.data?.bookings || []))
      .catch(() => showToast?.('بارگذاری رزروهای مصاحبه ناموفق بود.', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [includePast])

  const advanceInterviewCompleted = async (instanceId) => {
    if (!instanceId) return
    setAdvancingId(instanceId)
    try {
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: 'interview_time_reached',
        payload: {},
      })
      if (res.data?.success) {
        showToast?.(`مرحله به «${labelState(res.data.to_state)}» رفت`)
        load()
      } else {
        showToast?.(res.data?.error || 'انتقال انجام نشد', 'error')
      }
    } catch (e) {
      const d = e.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در ثبت برگزاری مصاحبه', 'error')
    } finally {
      setAdvancingId(null)
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
        <h3 className="card-title">رزروهای وقت مصاحبه</h3>
        <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.9rem', maxWidth: '42rem' }}>
          دانشجویانی که وقت را انتخاب کرده‌اند؛ شامل نام دانشجو، مصاحبه‌گر، تماس، وضعیت فرایند و اقدام «ثبت برگزاری». برای تعریف/حذف بازهٔ آزاد به «فهرست وقت‌ها» بروید.
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
                  <th>مصاحبه‌گر</th>
                  <th>دوره</th>
                  <th>حضور</th>
                  <th>مکان / لینک</th>
                  <th>ورود دانشجو</th>
                  <th>فرایند</th>
                  <th>مرحله</th>
                  <th>اقدام</th>
                </tr>
              </thead>
              <tbody>
                {bookings.map((row) => {
                  const s = row.slot
                  const st = row.student
                  const ins = row.instance
                  const canAdvanceInterview =
                    ins?.process_code === 'introductory_course_registration'
                    && ins?.current_state === 'interview_payment_confirmed'
                  const canOpenResult =
                    !!onOpenResult
                    && ins?.id
                    && ins?.current_state === 'interview_completed'
                  const canReschedule = !s.booking_payment_deadline_at
                  const loc = s.mode === 'online'
                    ? (() => {
                      const linkState = interviewMeetingLinkPreparingState(s)
                      return (
                      <OnlineMeetingJoinCta
                        compact
                        mode="online"
                        meetingLink={s.meeting_link}
                        meetingLinkReady={s.meeting_link_ready}
                        meetingLinkOpenAt={s.meeting_link_open_at}
                        meetingLinkIsVisible={s.meeting_link_is_visible}
                        startsAt={s.starts_at}
                        studentJoinOpen={!!s.student_join_open}
                        label="ورود به مصاحبه"
                        allowStaffCopy
                        onToggleStudentJoinOpen={
                          s.mode === 'online' && !s.booking_payment_deadline_at
                            ? (nextOpen) => toggleStudentJoinOpen(s, nextOpen)
                            : null
                        }
                        togglingStudentJoin={togglingJoinId === s.id}
                        preparing={linkState.preparing}
                        preparingFailed={linkState.preparingFailed}
                        preparingText={linkState.preparingText}
                        resultRecorded={!!linkState.resultRecorded}
                      />
                      )
                    })()
                    : (s.location_fa || '—')
                  return (
                    <tr key={s.id}>
                      <td>{formatSlotShamsi(s.starts_at)}</td>
                      <td>{formatSlotShamsi(s.ends_at)}</td>
                      <td>{st.full_name_fa || '—'}</td>
                      <td>{formatStudentCodeDisplay(st.student_code)}</td>
                      <td dir="ltr" style={{ fontSize: '0.82rem' }}>{st.phone || st.email || '—'}</td>
                      <td>{s.interviewer_name_fa || '—'}</td>
                      <td>{st.course_type === 'comprehensive' ? 'جامع' : st.course_type === 'introductory' ? 'آشنایی' : (st.course_type || '—')}</td>
                      <td>{s.mode === 'online' ? 'آنلاین' : 'حضوری'}</td>
                      <td style={{ fontSize: '0.78rem', maxWidth: '12rem', wordBreak: 'break-word' }} dir={s.mode === 'online' ? 'ltr' : 'rtl'}>{loc}</td>
                      <td>
                        {s.mode === 'online' && !s.booking_payment_deadline_at ? (
                          <label
                            style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', cursor: togglingJoinId === s.id ? 'wait' : 'pointer' }}
                            title="با فعال‌سازی، دانشجو می‌تواند قبل از ۳۰ دقیقه مانده به مصاحبه وارد جلسه شود."
                          >
                            <input
                              type="checkbox"
                              checked={!!s.student_join_open}
                              disabled={togglingJoinId === s.id}
                              onChange={(e) => toggleStudentJoinOpen(s, e.target.checked)}
                            />
                            {s.student_join_open ? 'باز' : 'بسته'}
                          </label>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>{ins ? labelProcess(ins.process_code) : '—'}</td>
                      <td>{ins ? labelState(ins.current_state) : '—'}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {canReschedule ? (
                          <button
                            type="button"
                            className="btn btn-outline btn-sm"
                            onClick={() => setRescheduleSlot(s)}
                          >
                            تغییر زمان
                          </button>
                        ) : null}
                        {canAdvanceInterview && ins?.id ? (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            data-testid={`booking-advance-interview-${ins.id}`}
                            disabled={advancingId === ins.id}
                            onClick={() => advanceInterviewCompleted(ins.id)}
                            style={canReschedule ? { marginTop: '0.35rem' } : undefined}
                          >
                            {advancingId === ins.id
                              ? 'در حال ثبت…'
                              : 'ثبت برگزاری مصاحبه'}
                          </button>
                        ) : null}
                        {canOpenResult ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            data-testid={`booking-open-result-${ins.id}`}
                            onClick={() => onOpenResult(ins.id)}
                            style={(canReschedule || canAdvanceInterview) ? { marginTop: '0.35rem' } : undefined}
                          >
                            ثبت نتیجه
                          </button>
                        ) : null}
                        {!canReschedule && !canAdvanceInterview && !canOpenResult ? '—' : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {!bookings.length && (
              <p className="muted" style={{ marginTop: '0.5rem', fontSize: '0.88rem', lineHeight: 1.65 }}>
                رزرو فعالی ثبت نشده است.
                {!includePast && (
                  <> برای زمان‌هایی که بازهٔ مصاحبه‌شان گذشته، گزینهٔ «نمایش گذشته» را فعال کنید.</>
                )}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
