import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { panelApi } from '../services/api'
import {
  CourseEvaluationResultCard,
  fmtDeadline,
  isEvaluationResultsVisible,
} from '../utils/instructorEvaluationResultsDisplay'

const PANEL_TITLE = 'گزارش ارزیابی عملکرد مدرس (فرایند ۵۷)'

/**
 * داشبورد نتایج ارزیابی برای مدرس — فقط دروس انتساب‌یافته.
 */
export default function InstructorEvaluationResultsPanel({ showToast = null, compact = false }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedCode, setSelectedCode] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await panelApi.instructorEvaluationResults()
      setData(res.data)
    } catch (e) {
      showToast?.(e.response?.data?.detail || 'بارگذاری نتایج ممکن نشد', 'error')
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    load()
  }, [load])

  const courses = useMemo(() => (data?.courses || []).filter((c) => c && c.course_code), [data])
  const visible = isEvaluationResultsVisible(data)

  useEffect(() => {
    if (courses.length && !selectedCode) {
      setSelectedCode(courses[0].course_code)
    }
  }, [courses, selectedCode])

  const selected = courses.find((c) => c.course_code === selectedCode) || courses[0] || null
  const deadlineFa = fmtDeadline(data?.evaluation_close_at)

  return (
    <div className="card" data-testid="instructor-evaluation-results-panel" style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}>
      <div className="card-header">
        <h3 className="card-title">{PANEL_TITLE}</h3>
        {data?.aggregated_at && (
          <span className="badge badge-success" style={{ fontSize: '0.75rem' }}>نتایج آماده</span>
        )}
      </div>
      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        {loading && <p style={{ fontSize: '0.85rem', color: '#64748b' }}>در حال بارگذاری…</p>}

        {!loading && !visible && (
          <div
            role="status"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #f59e0b',
              fontSize: '0.86rem',
              lineHeight: 1.7,
            }}
          >
            مهلت ارزیابی هنوز باز است یا نتایج تجمیع نشده‌اند.
            {deadlineFa && (
              <span>
                {' '}
                پایان مهلت:
                {' '}
                <strong>{deadlineFa}</strong>
              </span>
            )}
          </div>
        )}

        {!loading && visible && courses.length === 0 && (
          <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
            نتیجه‌ای برای دروس شما در این ترم ثبت نشده است.
          </p>
        )}

        {!loading && visible && courses.length > 0 && (
          <>
            {courses.length > 1 && (
              <label style={{ display: 'block', marginBottom: '0.75rem', fontSize: '0.85rem' }}>
                <span style={{ display: 'block', marginBottom: '0.35rem', color: '#64748b' }}>انتخاب درس</span>
                <select
                  className="psf-input"
                  value={selectedCode}
                  onChange={(e) => setSelectedCode(e.target.value)}
                  data-testid="instructor-eval-course-select"
                >
                  {courses.map((c) => (
                    <option key={c.course_code} value={c.course_code}>
                      {c.course_name || c.course_code}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {selected && <CourseEvaluationResultCard course={selected} compact={compact} />}
          </>
        )}
      </div>
    </div>
  )
}
