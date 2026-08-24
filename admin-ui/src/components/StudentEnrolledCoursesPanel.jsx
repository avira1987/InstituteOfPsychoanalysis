import React, { useCallback, useEffect, useState } from 'react'
import { panelApi } from '../services/api'
import OnlineMeetingJoinCta from './OnlineMeetingJoinCta'
import { fmtIsoDate, labelAttendanceSessionStatus } from '../utils/lessonStartPerTermDisplay'

/**
 * دروس ثبت‌نام‌شده دانشجو — زمان، لینک ورود، خلاصه حضور در تب کلاس و یادگیری.
 */
export default function StudentEnrolledCoursesPanel({
  studentProfile,
  active = true,
}) {
  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!studentProfile) {
      setCourses([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await panelApi.myEnrolledCourses()
      setCourses(Array.isArray(res.data?.courses) ? res.data.courses : [])
    } catch (e) {
      setCourses([])
      setError(e.response?.data?.detail || 'بارگذاری دروس ثبت‌نام‌شده ممکن نشد.')
    } finally {
      setLoading(false)
    }
  }, [studentProfile])

  useEffect(() => {
    if (active && studentProfile) load()
  }, [active, studentProfile, load])

  if (!studentProfile) {
    return (
      <div className="card" data-testid="student-enrolled-courses-panel">
        <div className="card-header">
          <h3 className="card-title">دروس من</h3>
        </div>
        <div className="empty-state" style={{ padding: '2rem' }}>پروفایل دانشجو یافت نشد.</div>
      </div>
    )
  }

  return (
    <div className="card" data-testid="student-enrolled-courses-panel" style={{ marginBottom: '1.25rem' }}>
      <div
        className="card-header"
        style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', justifyContent: 'space-between' }}
      >
        <h3 className="card-title" style={{ margin: 0 }}>دروس من</h3>
        <button type="button" className="btn btn-outline btn-sm" onClick={load} disabled={loading}>
          {loading ? 'در حال بارگذاری…' : 'تازه‌سازی'}
        </button>
      </div>

      {loading && courses.length === 0 ? (
        <p style={{ padding: '1rem', color: 'var(--text-secondary)' }}>در حال بارگذاری دروس…</p>
      ) : error ? (
        <p style={{ padding: '1rem', color: 'var(--danger, #b91c1c)' }}>{error}</p>
      ) : courses.length === 0 ? (
        <p style={{ padding: '1rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          هنوز درسی ثبت‌نام نکرده‌اید. پس از انتخاب درس و پرداخت شهریه، برنامهٔ کلاس و لینک ورود اینجا نمایش داده می‌شود.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', padding: '0 1rem 1rem' }}>
          {courses.map((course) => {
            const att = course.attendance || {}
            const sessions = Array.isArray(att.sessions) ? att.sessions : []
            const absenceCount = Number(att.absence_count ?? 0)
            const presentCount = Number(att.present_count ?? 0)
            const recorded = Number(att.sessions_recorded ?? sessions.length)
            const scheduleParts = [
              course.day,
              course.time_text,
              course.classroom_location,
            ].filter(Boolean)

            return (
              <div
                key={course.course_code}
                data-testid={`student-enrolled-course-${course.course_code}`}
                style={{
                  padding: '1rem',
                  borderRadius: '8px',
                  border: '1px solid var(--border)',
                  display: 'grid',
                  gap: '0.65rem',
                }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '1rem' }}>
                      {course.course_name_fa || course.course_code}
                    </div>
                    {course.instructor_name ? (
                      <div style={{ fontSize: '0.85rem', color: '#475569', marginTop: '0.2rem' }}>
                        مدرس: {course.instructor_name}
                      </div>
                    ) : null}
                  </div>
                  <span
                    className="badge"
                    style={{
                      fontSize: '0.72rem',
                      background: absenceCount >= 5 ? '#fef2f2' : '#f0fdf4',
                      color: absenceCount >= 5 ? '#b91c1c' : '#166534',
                      border: `1px solid ${absenceCount >= 5 ? '#fecaca' : '#bbf7d0'}`,
                    }}
                  >
                    غیبت {absenceCount.toLocaleString('fa-IR')} از ۵
                  </span>
                </div>

                {scheduleParts.length ? (
                  <div style={{ fontSize: '0.88rem', color: '#334155' }}>
                    برنامه: {scheduleParts.join(' · ')}
                  </div>
                ) : course.schedule_missing ? (
                  <div style={{ fontSize: '0.85rem', color: '#b45309' }}>
                    برنامهٔ کلاسی این درس هنوز منتشر نشده است.
                  </div>
                ) : null}

                {course.next_session_date ? (
                  <div style={{ fontSize: '0.82rem', color: '#64748b' }}>
                    نزدیک‌ترین جلسهٔ تقویم: {fmtIsoDate(course.next_session_date)}
                  </div>
                ) : null}

                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '0.75rem',
                    fontSize: '0.85rem',
                    color: '#334155',
                  }}
                >
                  <span>
                    حاضر در {presentCount.toLocaleString('fa-IR')}
                    {' '}
                    از {recorded.toLocaleString('fa-IR')} جلسه ثبت‌شده
                  </span>
                  {course.scheduled_sessions_count ? (
                    <span className="muted">
                      · {Number(course.scheduled_sessions_count).toLocaleString('fa-IR')} جلسه در تقویم ترم
                    </span>
                  ) : null}
                </div>

                {course.classroom_location && !(course.meeting_link_ready || course.join_path) ? (
                  <div style={{ fontSize: '0.85rem', color: '#475569' }}>
                    کلاس حضوری — محل: {course.classroom_location}
                  </div>
                ) : null}

                <OnlineMeetingJoinCta
                  mode="online"
                  meetingLink={null}
                  meetingLinkReady={Boolean(course.meeting_link_ready || course.join_path)}
                  meetingLinkIsVisible={Boolean(course.meeting_link_is_visible || course.join_path)}
                  authenticatedJoinReady={Boolean(course.meeting_link_ready || course.join_path)}
                  onAuthenticatedJoin={
                    (course.meeting_link_ready || course.join_path)
                      ? async () => {
                          const res = await panelApi.courseJoin(course.course_code)
                          return res.data?.join_url
                        }
                      : null
                  }
                  studentJoinOpen
                  label="ورود به کلاس"
                  compact
                  preparing={!(course.meeting_link_ready || course.join_path)}
                  preparingText="لینک ورود به کلاس هنوز توسط مدرس ثبت نشده است. زمان و محل کلاس را از برنامهٔ بالا ببینید."
                />

                {sessions.length > 0 ? (
                  <div style={{ overflowX: 'auto' }}>
                    <table className="data-table" style={{ width: '100%', fontSize: '0.82rem' }}>
                      <thead>
                        <tr>
                          <th>جلسه</th>
                          <th>تاریخ</th>
                          <th>وضعیت</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sessions.map((s, idx) => (
                          <tr key={`${s.date}-${idx}`}>
                            <td>{s.session_number != null ? Number(s.session_number).toLocaleString('fa-IR') : '—'}</td>
                            <td>{fmtIsoDate(s.date)}</td>
                            <td>{labelAttendanceSessionStatus(s.status)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted" style={{ margin: 0, fontSize: '0.82rem' }}>
                    هنوز جلسه‌ای برای این درس ثبت حضور نشده است.
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
