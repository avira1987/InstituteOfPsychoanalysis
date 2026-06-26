import React, { useMemo } from 'react'

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

/**
 * وضعیت دروس ثبت‌شده، قفل نمره، و شمارندهٔ غیبت کلاس.
 */
export default function StudentCourseStatusPanel({ extraData, activeProcesses = [] }) {
  const lms = extraData?.lms || {}
  const absenceCount = Number(
    extraData?.absence_counter_unexcused
    ?? extraData?.class_absence_count
    ?? lms?.absence_count
    ?? 0,
  )

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
      const key = r.code || r.course_code || r.id || courseLabel(r)
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [lms.enrolled_courses, lms.course_links])

  const incompleteProcesses = (activeProcesses || []).filter(
    (p) => p.process_code === 'class_attendance' && !p.is_completed,
  )

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
            background: absenceCount >= 5 ? '#fef2f2' : '#f0fdf4',
            borderRight: `4px solid ${absenceCount >= 5 ? '#dc2626' : '#16a34a'}`,
          }}
        >
          <div style={{ fontWeight: 700, fontSize: '0.92rem', marginBottom: '0.25rem' }}>
            غیبت‌های ثبت‌شده در کلاس‌ها
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800 }}>
            {absenceCount.toLocaleString('fa-IR')}
            <span className="muted" style={{ fontSize: '0.85rem', fontWeight: 500 }}> از ۵</span>
          </div>
          {absenceCount >= 5 && (
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.85rem', color: '#b91c1c', lineHeight: 1.6 }}>
              با ۵ غیبت، وضعیت Incomplete و قفل نمره اعمال می‌شود. با مدرس و پذیرش هماهنگ کنید.
            </p>
          )}
        </div>

        {incompleteProcesses.length > 0 && (
          <p style={{ fontSize: '0.85rem', color: '#92400e', marginBottom: '0.75rem', lineHeight: 1.6 }}>
            {incompleteProcesses.length.toLocaleString('fa-IR')} فرایند حضور کلاس فعال دارید — پیگیری از بخش فرایندها.
          </p>
        )}

        {courses.length === 0 ? (
          <p className="muted" style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.65 }}>
            هنوز درسی در LMS ثبت نشده است. پس از ثبت‌نام ترم، دروس اینجا نمایش داده می‌شوند.
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.88rem' }}>
              <thead>
                <tr>
                  <th>درس</th>
                  <th>وضعیت</th>
                  <th>نمره</th>
                </tr>
              </thead>
              <tbody>
                {courses.map((c, idx) => {
                  const locked = c.grades_locked || c.grade_locked || c.incomplete || c.status === 'I'
                  const grade = c.letter_grade || c.grade || c.numeric_grade || '—'
                  const status = c.incomplete || c.status === 'I'
                    ? 'Incomplete / قفل'
                    : (c.pass_fail || c.status_fa || (locked ? 'ثبت‌شده' : c.status) || 'در جریان')
                  return (
                    <tr key={c.code || c.course_code || idx}>
                      <td>{courseLabel(c)}</td>
                      <td>{status}</td>
                      <td>{grade}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
