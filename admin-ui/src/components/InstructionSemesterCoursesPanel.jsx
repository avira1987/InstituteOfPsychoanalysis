import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { panelApi } from '../services/api'
import OnlineMeetingJoinCta from './OnlineMeetingJoinCta'
import { labelRoleFa } from '../utils/roleLabels'
import { useToast } from '../contexts/ToastContext'
import {
  todayIsoDate,
} from '../utils/lessonAttendanceDisplay'
import { fmtIsoDate } from '../utils/lessonStartPerTermDisplay'

/**
 * داشبورد کلاس‌های مدرس/کمک‌مدرس: برنامه، لینک ورود، لیست کلاس، ثبت حضور جلسه‌ای.
 */
export default function InstructionSemesterCoursesPanel() {
  const { showToast } = useToast()
  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedCode, setExpandedCode] = useState(null)
  const [roster, setRoster] = useState([])
  const [loadingRoster, setLoadingRoster] = useState(false)
  const [sessionDate, setSessionDate] = useState(todayIsoDate())
  const [meetingUrl, setMeetingUrl] = useState('')
  const [hostMeetingUrl, setHostMeetingUrl] = useState('')
  const [savingLink, setSavingLink] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [lastSummary, setLastSummary] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await panelApi.mySemesterCourses()
      setCourses(Array.isArray(res.data?.courses) ? res.data.courses : [])
    } catch {
      setCourses([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const expandedCourse = useMemo(
    () => courses.find((c) => (c.course_code || c.course_name) === expandedCode) || null,
    [courses, expandedCode],
  )

  const openCourse = async (course) => {
    const code = course.course_code || course.course_name
    setExpandedCode(code)
    setMeetingUrl(course.online_meeting_url || '')
    setHostMeetingUrl(course.host_meeting_url || '')
    setLastSummary(null)
    const sessions = Array.isArray(course.scheduled_sessions) ? course.scheduled_sessions : []
    const today = todayIsoDate()
    const due = sessions.find((s) => (s.session_date || '') <= today)
    const pick = due || sessions[0]
    setSessionDate(pick?.session_date || today)
    setLoadingRoster(true)
    try {
      const res = await panelApi.instructorCourseRoster(code)
      const rows = res.data?.roster || []
      setRoster(rows.map((r) => ({
        ...r,
        status: r.present_blocked ? 'absent' : (r.status || 'present'),
      })))
    } catch (e) {
      setRoster([])
      const msg = e?.response?.data?.detail || e.message || 'خطا در بارگذاری لیست کلاس'
      showToast?.(typeof msg === 'string' ? msg : 'خطا در بارگذاری لیست کلاس', 'error')
    } finally {
      setLoadingRoster(false)
    }
  }

  const setStatus = (studentId, status) => {
    setRoster((prev) => prev.map((r) => {
      if (r.student_id !== studentId) return r
      if (r.present_blocked) return { ...r, status: 'absent' }
      return { ...r, status }
    }))
  }

  const setAllStatus = (status) => {
    setRoster((prev) => prev.map((r) => {
      if (status === 'present' && r.present_blocked) return { ...r, status: 'absent' }
      return { ...r, status }
    }))
  }

  const saveMeetingLink = async () => {
    if (!expandedCode) return
    setSavingLink(true)
    try {
      await panelApi.updateCourseMeetingLink(expandedCode, {
        online_meeting_url: meetingUrl.trim() || null,
        host_meeting_url: hostMeetingUrl.trim() || null,
      })
      showToast?.('لینک کلاس ذخیره شد')
      await load()
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'ذخیره لینک ناموفق بود'
      showToast?.(typeof msg === 'string' ? msg : 'ذخیره لینک ناموفق بود', 'error')
    } finally {
      setSavingLink(false)
    }
  }

  const submitAttendance = async () => {
    if (!expandedCode) return
    if (!roster.length) {
      showToast?.('لیست کلاس خالی است.', 'error')
      return
    }
    setSubmitting(true)
    try {
      const rows = roster.map((r) => ({
        student_id: r.student_id,
        student_name: r.name_fa || r.student_code,
        person_name: r.name_fa || r.student_code,
        role: r.role || 'student',
        status: r.present_blocked ? 'absent' : (r.status || 'present'),
      }))
      const sessionNumber = (expandedCourse?.scheduled_sessions || [])
        .find((s) => s.session_date === sessionDate)?.session_number
      const res = await panelApi.recordCourseAttendance(expandedCode, {
        session_date: sessionDate,
        rows,
        session_number: sessionNumber || undefined,
      })
      setLastSummary(res.data?.summary || null)
      showToast?.('حضور و غیاب جلسه ثبت شد')
      // refresh roster absence counts
      const rosterRes = await panelApi.instructorCourseRoster(expandedCode)
      const rows2 = rosterRes.data?.roster || []
      setRoster(rows2.map((r) => ({
        ...r,
        status: r.present_blocked ? 'absent' : (r.status || 'present'),
      })))
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'خطا در ثبت حضور'
      showToast?.(typeof msg === 'string' ? msg : 'خطا در ثبت حضور', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: '1.25rem', padding: '1rem' }} data-testid="instruction-semester-courses">
        <p className="muted" style={{ margin: 0 }}>در حال بارگذاری دروس انتساب‌یافته…</p>
      </div>
    )
  }

  if (!courses.length) {
    return (
      <div
        className="card"
        style={{ marginBottom: '1.25rem', padding: '1rem 1.15rem' }}
        data-testid="instruction-semester-courses"
      >
        <h3 style={{ margin: '0 0 0.35rem', fontSize: '1rem', color: '#5b21b6' }}>
          کلاس‌های من
        </h3>
        <p style={{ margin: 0, fontSize: '0.88rem', color: '#64748b', lineHeight: 1.7 }}>
          هنوز درسی به شما انتساب داده نشده است. پس از انتساب در آماده‌سازی ترم، همین‌جا لیست کلاس‌ها
          و دکمهٔ ورود نمایش داده می‌شود — نیازی به جستجو یا انتخاب دانشجو نیست.
        </p>
      </div>
    )
  }

  return (
    <div
      className="card"
      style={{
        marginBottom: '1.25rem',
        padding: '1rem 1.15rem',
        borderRight: '4px solid #7c3aed',
        background: 'linear-gradient(180deg, #f5f3ff 0%, #fff 100%)',
      }}
      data-testid="instruction-semester-courses"
    >
      <h3 style={{ margin: '0 0 0.35rem', fontSize: '1rem', color: '#5b21b6' }}>
        کلاس‌های من
      </h3>
      <p style={{ margin: '0 0 0.75rem', fontSize: '0.82rem', color: '#64748b', lineHeight: 1.6 }}>
        کلاس‌های انتساب‌یافته به شما. برای ورود، دکمهٔ «ورود به کلاس» همان درس را بزنید.
        لینک دانشجو و لینک میزبان را از «مدیریت کلاس» ثبت کنید. حضور و غیاب جلسه‌ای هم همین‌جاست.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {courses.map((c, idx) => {
          const code = c.course_code || c.course_name
          const isOpen = expandedCode === code
          const instructorJoinUrl = String(c.host_meeting_url || c.online_meeting_url || '').trim()
          return (
            <div
              key={`${code}-${idx}`}
              style={{
                padding: '0.65rem 0.85rem',
                background: '#fff',
                borderRadius: '8px',
                border: isOpen ? '1px solid #7c3aed' : '1px solid #ddd6fe',
                fontSize: '0.88rem',
                lineHeight: 1.65,
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 700, color: '#1e293b' }}>{c.course_name || code || '—'}</div>
                  <div style={{ color: '#475569', fontSize: '0.82rem' }}>
                    {c.track_label_fa || c.track ? `رسته: ${c.track_label_fa || c.track}` : null}
                    {c.day ? ` · ${c.day}` : ''}
                    {c.time || c.time_text ? ` · ${c.time || c.time_text}` : ''}
                    {c.classroom_location ? ` · ${c.classroom_location}` : ''}
                    {c.role_kind ? ` · نقش: ${labelRoleFa(c.role_kind)}` : ''}
                    {typeof c.roster_count === 'number' ? ` · ${c.roster_count.toLocaleString('fa-IR')} دانشجو` : ''}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: c.online_meeting_url ? '#166534' : '#b45309' }}>
                    {c.online_meeting_url ? 'لینک کلاس ثبت شده' : 'لینک کلاس هنوز ثبت نشده'}
                  </div>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
                  <OnlineMeetingJoinCta
                    mode="online"
                    meetingLink={instructorJoinUrl || null}
                    meetingLinkReady={Boolean(instructorJoinUrl)}
                    meetingLinkIsVisible={Boolean(instructorJoinUrl)}
                    allowStaffCopy={Boolean(instructorJoinUrl)}
                    studentJoinOpen
                    label="ورود به کلاس"
                    compact
                    preparing={!instructorJoinUrl}
                    preparingText="لینک ورود هنوز ثبت نشده. از «مدیریت کلاس» لینک میزبان یا دانشجو را ذخیره کنید."
                  />
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    data-testid={`instructor-open-course-${code}`}
                    onClick={() => (isOpen ? setExpandedCode(null) : openCourse(c))}
                  >
                    {isOpen ? 'بستن' : 'مدیریت کلاس'}
                  </button>
                </div>
              </div>

              {isOpen ? (
                <div style={{ marginTop: '0.85rem', display: 'grid', gap: '0.85rem' }} data-testid={`instructor-course-dashboard-${code}`}>
                  <div style={{ display: 'grid', gap: '0.5rem' }}>
                    <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>
                      لینک ورود دانشجو
                      <input
                        className="form-input"
                        style={{ marginTop: '0.25rem' }}
                        value={meetingUrl}
                        onChange={(e) => setMeetingUrl(e.target.value)}
                        placeholder="https://..."
                        data-testid="instructor-meeting-url-input"
                      />
                    </label>
                    <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>
                      لینک میزبان (اختیاری)
                      <input
                        className="form-input"
                        style={{ marginTop: '0.25rem' }}
                        value={hostMeetingUrl}
                        onChange={(e) => setHostMeetingUrl(e.target.value)}
                        placeholder="https://..."
                        data-testid="instructor-host-meeting-url-input"
                      />
                    </label>
                    <div>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={saveMeetingLink}
                        disabled={savingLink}
                        data-testid="instructor-save-meeting-link"
                      >
                        {savingLink ? 'در حال ذخیره…' : 'ذخیره لینک کلاس'}
                      </button>
                      {(hostMeetingUrl || meetingUrl) ? (
                        <a
                          href={(hostMeetingUrl || meetingUrl).trim()}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-outline btn-sm"
                          style={{ marginRight: '0.5rem' }}
                          data-testid="instructor-join-class-link"
                        >
                          {hostMeetingUrl ? 'ورود میزبان' : 'ورود به کلاس'}
                        </a>
                      ) : null}
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end' }}>
                    <label style={{ fontSize: '0.85rem' }}>
                      <span style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>تاریخ جلسه</span>
                      {(c.scheduled_sessions || []).length > 0 ? (
                        <select
                          className="form-input"
                          value={sessionDate}
                          onChange={(e) => setSessionDate(e.target.value)}
                          data-testid="instructor-attendance-session-select"
                        >
                          {(c.scheduled_sessions || []).map((s) => (
                            <option key={s.session_date} value={s.session_date}>
                              جلسه {s.session_number} — {fmtIsoDate(s.session_date)}
                              {s.session_time ? ` · ${s.session_time}` : ''}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="date"
                          className="form-input"
                          value={sessionDate}
                          onChange={(e) => setSessionDate(e.target.value)}
                          data-testid="instructor-attendance-session-date"
                        />
                      )}
                    </label>
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => setAllStatus('present')} disabled={!roster.length}>
                      همه حاضر
                    </button>
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => setAllStatus('absent')} disabled={!roster.length}>
                      همه غایب
                    </button>
                  </div>

                  {loadingRoster ? (
                    <p className="muted" style={{ fontSize: '0.85rem' }}>در حال بارگذاری لیست کلاس…</p>
                  ) : roster.length === 0 ? (
                    <p className="muted" style={{ fontSize: '0.85rem' }}>هنوز دانشجویی در این درس ثبت‌نام نکرده است.</p>
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      {roster.some((r) => r.present_blocked) && (
                        <div
                          role="status"
                          style={{
                            marginBottom: '0.75rem',
                            padding: '0.65rem 0.85rem',
                            borderRadius: '8px',
                            background: '#fef2f2',
                            borderRight: '4px solid #dc2626',
                            fontSize: '0.82rem',
                            color: '#991b1b',
                          }}
                        >
                          برخی دانشجویان به‌خاطر قسط معوق، ردیف حضور و غیاب قفل است و فقط «غایب» ثبت می‌شود.
                        </div>
                      )}
                      <table className="data-table" style={{ width: '100%', fontSize: '0.84rem' }}>
                        <thead>
                          <tr>
                            <th>نام</th>
                            <th>نقش</th>
                            <th>غیبت</th>
                            <th>وضعیت</th>
                          </tr>
                        </thead>
                        <tbody>
                          {roster.map((r) => {
                            const blocked = Boolean(r.present_blocked)
                            return (
                            <tr
                              key={r.student_id}
                              data-testid={blocked ? 'attendance-row-installment-locked' : undefined}
                              style={blocked ? { background: '#f1f5f9', color: '#64748b', opacity: 0.92 } : undefined}
                            >
                              <td>
                                {r.name_fa || r.student_code}
                                {blocked ? (
                                  <span
                                    className="badge"
                                    data-testid="attendance-overdue-badge"
                                    style={{
                                      marginRight: '0.4rem',
                                      fontSize: '0.68rem',
                                      background: '#fee2e2',
                                      color: '#991b1b',
                                      border: '1px solid #fecaca',
                                    }}
                                  >
                                    قسط معوق
                                  </span>
                                ) : null}
                                {Number(r.absence_count || 0) >= 4 ? (
                                  <span style={{ marginRight: '0.35rem', color: '#b91c1c', fontSize: '0.75rem' }}>
                                    (هشدار غیبت)
                                  </span>
                                ) : null}
                              </td>
                              <td>{r.role === 'teaching_assistant' ? 'کمک‌مدرس' : 'دانشجو'}</td>
                              <td>{Number(r.absence_count || 0).toLocaleString('fa-IR')}</td>
                              <td>
                                <select
                                  className="form-input"
                                  style={{ minWidth: '7rem' }}
                                  value={blocked ? 'absent' : (r.status || 'present')}
                                  disabled={blocked}
                                  onChange={(e) => setStatus(r.student_id, e.target.value)}
                                >
                                  <option value="present">حاضر</option>
                                  <option value="absent">غایب</option>
                                </select>
                              </td>
                            </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <div>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={submitAttendance}
                      disabled={submitting || !roster.length}
                      data-testid="instructor-submit-attendance"
                    >
                      {submitting ? 'در حال ثبت…' : 'ثبت حضور و غیاب این جلسه'}
                    </button>
                  </div>

                  {lastSummary ? (
                    <div
                      style={{
                        padding: '0.75rem 0.85rem',
                        borderRadius: '8px',
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        fontSize: '0.85rem',
                      }}
                      data-testid="instructor-attendance-last-summary"
                    >
                      خلاصه ثبت:
                      {' '}
                      حاضر {Number(lastSummary.present || 0).toLocaleString('fa-IR')}
                      {' — '}
                      غایب {Number(lastSummary.absent || 0).toLocaleString('fa-IR')}
                      {' — '}
                      تاریخ {fmtIsoDate(lastSummary.session_date)}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
