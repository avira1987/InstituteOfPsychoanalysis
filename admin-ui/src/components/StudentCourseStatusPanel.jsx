import React, { useMemo } from 'react'
import { labelAttendanceSessionStatus, fmtIsoDate } from '../utils/lessonStartPerTermDisplay'
import { labelProcess } from '../utils/processDisplay'

const COURSE_COMPLETION_CODES = new Set([
  'theory_course_completion',
  'skills_course_completion',
  'film_observation_course_completion',
  'live_therapy_observation_course_completion',
  'live_supervision_course_completion',
  'group_supervision_course_completion',
])

function courseLabel(entry) {
  if (typeof entry === 'string') return entry
  if (!entry || typeof entry !== 'object') return '—'
  return (
    entry.course_name
    || entry.name_fa
    || entry.title_fa
    || entry.code
    || entry.course_code
    || '—'
  )
}

function courseCode(entry) {
  if (typeof entry === 'string') return entry
  return entry?.code || entry?.course_code || courseLabel(entry)
}

function perCourseAbsenceCount(code, lessonAttendance) {
  const roster = lessonAttendance[code] || lessonAttendance[String(code)] || {}
  return Number(roster.absence_count ?? 0)
}

/**
 * وضعیت دروس ثبت‌شده، قفل نمره، لینک آنلاین، جلسات حضور، و شمارندهٔ غیبت کلاس.
 */
export default function StudentCourseStatusPanel({ extraData, activeProcesses = [] }) {
  const lms = extraData?.lms || {}
  const portalLinks = lms.portal_course_links || lms.course_links || {}
  const lessonAttendance = lms.lesson_attendance || {}

  const absenceCount = Number(
    extraData?.absence_counter_unexcused
    ?? extraData?.class_absence_count
    ?? lms?.absence_count
    ?? 0,
  )

  const maxPerCourseAbsence = useMemo(() => {
    let max = 0
    Object.values(lessonAttendance).forEach((entry) => {
      if (entry && typeof entry === 'object') {
        const n = Number(entry.absence_count ?? 0)
        if (n > max) max = n
      }
    })
    return max
  }, [lessonAttendance])

  const courses = useMemo(() => {
    const enrolled = lms.enrolled_courses || []
    const links = lms.course_links || []
    const rows = []
    if (Array.isArray(enrolled)) {
      enrolled.forEach((c) => {
        rows.push(typeof c === 'object' ? c : { code: c, course_code: c })
      })
    }
    if (Array.isArray(links)) {
      links.forEach((c) => {
        if (typeof c === 'object') rows.push(c)
      })
    }
    const seen = new Set()
    return rows.filter((r) => {
      const key = courseCode(r)
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [lms.enrolled_courses, lms.course_links])

  const liveSupervision = lms.live_supervision || {}
  const liveSupervisionActive = (activeProcesses || []).filter(
    (p) => p.process_code === 'live_supervision_course_completion' && !p.is_completed,
  )

  const incompleteClassAttendance = (activeProcesses || []).filter(
    (p) => p.process_code === 'class_attendance' && !p.is_completed,
  )
  const activeLessonStart = (activeProcesses || []).filter(
    (p) => p.process_code === 'lesson_start_per_term' && !p.is_completed,
  )
  const activeCourseCompletions = (activeProcesses || []).filter(
    (p) => COURSE_COMPLETION_CODES.has(p.process_code) && !p.is_completed && !p.is_cancelled,
  )

  const completionByCourse = useMemo(() => {
    const map = {}
    const gs = lms.group_supervision || {}
    Object.entries(gs).forEach(([code, row]) => {
      if (row && typeof row === 'object') {
        map[code] = { ...map[code], ...row, source: 'group_supervision' }
      }
    })
    const fo = lms.film_observation || {}
    Object.entries(fo).forEach(([code, row]) => {
      if (row && typeof row === 'object') {
        map[code] = { ...map[code], ...row, source: 'film_observation' }
      }
    })
    const lt = lms.live_therapy_observation || {}
    Object.entries(lt).forEach(([code, row]) => {
      if (row && typeof row === 'object') {
        map[code] = { ...map[code], ...row, source: 'live_therapy_observation' }
      }
    })
    const th = lms.theory || {}
    Object.entries(th).forEach(([code, row]) => {
      if (row && typeof row === 'object') {
        map[code] = { ...map[code], ...row, source: 'theory' }
      }
    })
    const sk = lms.skills || {}
    Object.entries(sk).forEach(([code, row]) => {
      if (row && typeof row === 'object') {
        map[code] = { ...map[code], ...row, source: 'skills' }
      }
    })
    return map
  }, [lms])

  return (
    <div className="card" data-testid="student-course-status-panel">
      <div className="card-header">
        <h3 className="card-title">وضعیت دروس و حضور کلاس</h3>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <div
          style={{
            padding: '0.85rem 1rem',
            marginBottom: '1rem',
            borderRadius: '8px',
            background: maxPerCourseAbsence >= 5 ? '#fef2f2' : '#f0fdf4',
            borderRight: `4px solid ${maxPerCourseAbsence >= 5 ? '#dc2626' : '#16a34a'}`,
          }}
        >
          <div style={{ fontWeight: 700, fontSize: '0.92rem', marginBottom: '0.25rem' }}>
            غیبت‌های ثبت‌شده (مجموع همه کلاس‌ها)
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800 }}>
            {absenceCount.toLocaleString('fa-IR')}
          </div>
          {maxPerCourseAbsence > 0 && (
            <p style={{ margin: '0.35rem 0 0', fontSize: '0.82rem', color: '#64748b' }}>
              بیشترین غیبت در یک درس:
              {' '}
              {maxPerCourseAbsence.toLocaleString('fa-IR')}
              {' '}
              از ۵
            </p>
          )}
          {maxPerCourseAbsence >= 5 && (
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.85rem', color: '#b91c1c', lineHeight: 1.6 }}>
              با ۵ غیبت، وضعیت Incomplete و قفل نمره اعمال می‌شود. با مدرس و پذیرش هماهنگ کنید.
            </p>
          )}
        </div>

        {activeLessonStart.length > 0 && (
          <p
            data-testid="student-lesson-start-active-hint"
            style={{ fontSize: '0.85rem', color: '#1e40af', marginBottom: '0.75rem', lineHeight: 1.6 }}
          >
            {activeLessonStart.length.toLocaleString('fa-IR')} فرایند ثبت‌نام درس فعال دارید — از بخش فرایندها ادامه دهید.
          </p>
        )}

        {activeCourseCompletions.length > 0 && (
          <div
            data-testid="student-course-completion-active-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '8px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.84rem',
              lineHeight: 1.65,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#92400e' }}>
              خاتمه درس — اقدام یا پیگیری لازم
            </div>
            {activeCourseCompletions.map((p) => (
              <div key={p.instance_id || p.process_code} style={{ marginBottom: '0.25rem' }}>
                {labelProcess(p.process_code)}
                {p.current_state ? ` — ${p.current_state}` : ''}
                {' '}
                <span className="muted">(تب فرایندها)</span>
              </div>
            ))}
          </div>
        )}

        {incompleteClassAttendance.length > 0 && (
          <p style={{ fontSize: '0.85rem', color: '#92400e', marginBottom: '0.75rem', lineHeight: 1.6 }}>
            {incompleteClassAttendance.length.toLocaleString('fa-IR')} فرایند حضور کلاس فعال دارید — پیگیری از بخش فرایندها.
          </p>
        )}

        {(liveSupervisionActive.length > 0 || Object.keys(liveSupervision).length > 0) && (
          <div
            data-testid="student-live-supervision-progress"
            style={{
              marginBottom: '1rem',
              padding: '0.85rem 1rem',
              borderRadius: '8px',
              background: '#f0fdfa',
              borderRight: '4px solid #0d9488',
            }}
          >
            <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: '0.5rem', color: '#0f766e' }}>
              سوپرویژن زنده — پیشرفت ۱۵ عادی + ۳ پشت‌آینه
            </div>
            {Object.entries(liveSupervision).map(([code, prog]) => {
              if (!prog || typeof prog !== 'object') return null
              const normal = Number(prog.normal_count || 0)
              const mirror = Number(prog.mirror_count || 0)
              return (
                <div key={code} style={{ fontSize: '0.84rem', lineHeight: 1.65, marginBottom: '0.35rem' }}>
                  <strong>{code}</strong>
                  {' — '}
                  {normal.toLocaleString('fa-IR')}
                  {' عادی + '}
                  {mirror.toLocaleString('fa-IR')}
                  {' پشت‌آینه'}
                  {Number(prog.compensation_pending || 0) > 0 && (
                    <span style={{ color: '#dc2626' }}>
                      {' — پرداخت جبرانی: '}
                      {prog.compensation_pending}
                      {' جلسه'}
                    </span>
                  )}
                </div>
              )
            })}
            {liveSupervisionActive.length > 0 && (
              <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem', color: '#334155' }}>
                پرونده فعال فرایند ۶۷ — جزئیات در تب فرایندها.
              </p>
            )}
          </div>
        )}

        {courses.length === 0 ? (
          <p className="muted" style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.65 }}>
            هنوز درسی در LMS ثبت نشده است. پس از ثبت‌نام ترم، دروس اینجا نمایش داده می‌شوند.
          </p>
        ) : (
          <>
            <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
              <table className="data-table" style={{ width: '100%', fontSize: '0.88rem' }} data-testid="student-courses-table">
                <thead>
                  <tr>
                    <th>درس</th>
                    <th>وضعیت</th>
                    <th>غیبت کلاس</th>
                    <th>نمره</th>
                    <th>لینک آنلاین</th>
                  </tr>
                </thead>
                <tbody>
                  {courses.map((c, idx) => {
                    const code = courseCode(c)
                    const courseAbs = perCourseAbsenceCount(code, lessonAttendance)
                    const completionRow = completionByCourse[code] || completionByCourse[String(code)] || {}
                    const locked = c.grades_locked || c.grade_locked || c.incomplete || c.status === 'I'
                      || completionRow.grades_locked
                    const grade = c.letter_grade || c.grade || c.numeric_grade
                      || completionRow.total_score
                      || completionRow.grade
                      || completionRow.pass_fail
                      || '—'
                    const status = c.incomplete || c.status === 'I' || completionRow.incomplete
                      ? 'Incomplete / قفل'
                      : (completionRow.pass_fail || c.pass_fail || c.status_fa || (locked ? 'ثبت‌شده' : c.status) || 'در جریان')
                    const link = portalLinks[code] || portalLinks[String(code)] || ''
                    return (
                      <tr key={code || idx}>
                        <td>{courseLabel(c)}</td>
                        <td>{status}</td>
                        <td style={{ color: courseAbs >= 5 ? '#b91c1c' : courseAbs >= 4 ? '#d97706' : '#334155', fontWeight: courseAbs >= 4 ? 700 : 400 }}>
                          {courseAbs.toLocaleString('fa-IR')}
                          <span className="muted" style={{ fontSize: '0.78rem' }}> / ۵</span>
                        </td>
                        <td>{grade}</td>
                        <td>
                          {link ? (
                            <a href={link} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.82rem' }}>
                              ورود
                            </a>
                          ) : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {courses.some((c) => {
              const code = courseCode(c)
              const roster = lessonAttendance[code] || lessonAttendance[String(code)]
              return Array.isArray(roster?.sessions) && roster.sessions.length > 0
            }) && (
              <div data-testid="student-course-attendance-sessions">
                {courses.map((c, idx) => {
                  const code = courseCode(c)
                  const roster = lessonAttendance[code] || lessonAttendance[String(code)] || {}
                  const sessions = Array.isArray(roster.sessions) ? roster.sessions : []
                  if (!sessions.length) return null
                  return (
                    <div key={code || idx} style={{ marginBottom: '1rem' }}>
                      <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: '0.4rem', color: '#334155' }}>
                        جلسات حضور — {courseLabel(c)}
                      </div>
                      <div style={{ overflowX: 'auto' }}>
                        <table className="data-table" style={{ width: '100%', fontSize: '0.84rem' }}>
                          <thead>
                            <tr>
                              <th>جلسه</th>
                              <th>تاریخ</th>
                              <th>وضعیت</th>
                            </tr>
                          </thead>
                          <tbody>
                            {sessions.map((session, sIdx) => (
                              <tr key={session.session_number || session.date || sIdx}>
                                <td>{session.session_number ?? sIdx + 1}</td>
                                <td>{session.date ? fmtIsoDate(session.date) : '—'}</td>
                                <td>{labelAttendanceSessionStatus(session.status)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
