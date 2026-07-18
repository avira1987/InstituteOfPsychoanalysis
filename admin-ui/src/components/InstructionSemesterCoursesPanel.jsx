import React, { useCallback, useEffect, useState } from 'react'
import { panelApi } from '../services/api'
import { labelRoleFa } from '../utils/roleLabels'

/**
 * دروس انتساب‌یافته از آماده‌سازی ترم — نمایش در پنل مدرس/کمک‌مدرس.
 */
export default function InstructionSemesterCoursesPanel() {
  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(true)

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

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: '1.25rem', padding: '1rem' }} data-testid="instruction-semester-courses">
        <p className="muted" style={{ margin: 0 }}>در حال بارگذاری دروس انتساب‌یافته…</p>
      </div>
    )
  }

  if (!courses.length) return null

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
        دروس این ترم (انتساب از آماده‌سازی)
      </h3>
      <p style={{ margin: '0 0 0.75rem', fontSize: '0.82rem', color: '#64748b', lineHeight: 1.6 }}>
        پس از ثبت لیست دروس در کمیته، درس‌های مرتبط با شما اینجا نمایش داده می‌شوند.
        ثبت حضور و غیاب هر جلسه از تب «منتظر اقدام» و فرایند ۵۴ انجام می‌شود.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {courses.map((c, idx) => (
          <div
            key={`${c.assignment_key || c.course_name}-${idx}`}
            style={{
              padding: '0.65rem 0.85rem',
              background: '#fff',
              borderRadius: '8px',
              border: '1px solid #ddd6fe',
              fontSize: '0.88rem',
              lineHeight: 1.65,
            }}
          >
            <div style={{ fontWeight: 700, color: '#1e293b' }}>{c.course_name || '—'}</div>
            <div style={{ color: '#475569', fontSize: '0.82rem' }}>
              {c.track_label_fa || c.track ? `رسته: ${c.track_label_fa || c.track}` : null}
              {c.day ? ` · ${c.day}` : ''}
              {c.time ? ` · ${c.time}` : ''}
              {c.term_label_fa ? ` · ترم ${c.term_label_fa}` : ''}
              {c.role_kind ? ` · نقش: ${labelRoleFa(c.role_kind)}` : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
