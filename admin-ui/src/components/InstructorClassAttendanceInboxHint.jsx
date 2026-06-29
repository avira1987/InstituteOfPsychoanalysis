import React, { useMemo } from 'react'
import { courseCodeFromInstanceContext } from '../utils/lessonAttendanceDisplay'

/**
 * هشدار گروه‌بندی instanceهای تکراری class_attendance در صندوق مدرس.
 */
export default function InstructorClassAttendanceInboxHint({ pendingActions = [] }) {
  const groups = useMemo(() => {
    const map = {}
    ;(pendingActions || []).forEach((item) => {
      if (item.process_code !== 'class_attendance') return
      if (item.current_state !== 'attendance_list_ready') return
      const ctx = item.context_data || {}
      const course = courseCodeFromInstanceContext(ctx) || item.course_code || '—'
      const date = ctx.session_date || '—'
      const key = `${course}::${date}`
      if (!map[key]) {
        map[key] = { course, date, count: 0, instanceIds: [] }
      }
      map[key].count += 1
      const iid = item.instance_id || item.id
      if (iid) map[key].instanceIds.push(iid)
    })
    return Object.values(map).filter((g) => g.count > 1)
  }, [pendingActions])

  if (!groups.length) return null

  return (
    <div
      data-testid="instructor-class-attendance-inbox-hint"
      style={{
        marginBottom: '1rem',
        padding: '0.85rem 1rem',
        borderRadius: '8px',
        background: '#eff6ff',
        borderRight: '4px solid #2563eb',
        fontSize: '0.85rem',
        lineHeight: 1.65,
        color: '#1e3a8a',
      }}
    >
      <strong>نکتهٔ ثبت حضور کلاس:</strong>
      {' '}
      برای هر درس و تاریخ جلسه، یک بار ثبت حضور کافی است؛ همهٔ پرونده‌های زیر مربوط به همان جلسه‌اند:
      <ul style={{ margin: '0.5rem 0 0', paddingRight: '1.25rem' }}>
        {groups.map((g) => (
          <li key={`${g.course}-${g.date}`}>
            {g.course}
            {' '}
            —
            تاریخ
            {' '}
            {g.date}
            :
            {' '}
            {g.count.toLocaleString('fa-IR')}
            {' '}
            پرونده (یکی را باز کنید و لیست کامل کلاس را ثبت کنید)
          </li>
        ))}
      </ul>
    </div>
  )
}
