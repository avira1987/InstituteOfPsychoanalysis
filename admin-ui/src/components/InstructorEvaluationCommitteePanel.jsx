import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { panelApi } from '../services/api'
import {
  CourseEvaluationResultCard,
  fmtDeadline,
  formatAverageScore,
  formatParticipationRate,
  isEvaluationResultsVisible,
} from '../utils/instructorEvaluationResultsDisplay'

const PANEL_TITLE = 'گزارش ارزیابی اساتید — کمیته دروس (فرایند ۵۷)'

/**
 * داشبورد مقایسه‌ای نتایج ارزیابی برای کمیته دروس / پژوهش.
 */
export default function InstructorEvaluationCommitteePanel({ showToast = null, compact = false }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filterCourse, setFilterCourse] = useState('')
  const [filterInstructor, setFilterInstructor] = useState('')
  const [expandedCode, setExpandedCode] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await panelApi.committeeEvaluationResults()
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
  const deadlineFa = fmtDeadline(data?.evaluation_close_at)

  const filtered = useMemo(() => {
    let rows = courses
    if (filterCourse.trim()) {
      const q = filterCourse.trim().toLowerCase()
      rows = rows.filter(
        (c) => String(c.course_name || '').toLowerCase().includes(q)
          || String(c.course_code || '').toLowerCase().includes(q),
      )
    }
    if (filterInstructor.trim()) {
      const q = filterInstructor.trim().toLowerCase()
      rows = rows.filter((c) => String(c.instructor_name || '').toLowerCase().includes(q))
    }
    return rows
  }, [courses, filterCourse, filterInstructor])

  return (
    <div className="card" data-testid="committee-evaluation-results-panel" style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}>
      <div className="card-header">
        <h3 className="card-title">{PANEL_TITLE}</h3>
        {data?.term_code && (
          <span className="badge badge-info" style={{ fontSize: '0.75rem' }}>
            ترم:
            {' '}
            {data.term_code}
          </span>
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
            نتایج پس از پایان مهلت ارزیابی و تجمیع سامانه در دسترس خواهد بود.
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

        {!loading && visible && (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: '0.65rem',
                marginBottom: '0.85rem',
              }}
            >
              <label style={{ fontSize: '0.82rem' }}>
                <span style={{ display: 'block', color: '#64748b', marginBottom: '0.25rem' }}>فیلتر درس</span>
                <input
                  className="psf-input"
                  value={filterCourse}
                  onChange={(e) => setFilterCourse(e.target.value)}
                  placeholder="نام یا کد درس"
                  data-testid="committee-eval-filter-course"
                />
              </label>
              <label style={{ fontSize: '0.82rem' }}>
                <span style={{ display: 'block', color: '#64748b', marginBottom: '0.25rem' }}>فیلتر مدرس</span>
                <input
                  className="psf-input"
                  value={filterInstructor}
                  onChange={(e) => setFilterInstructor(e.target.value)}
                  placeholder="نام مدرس"
                  data-testid="committee-eval-filter-instructor"
                />
              </label>
            </div>

            {filtered.length === 0 ? (
              <p style={{ fontSize: '0.85rem', color: '#64748b' }}>موردی یافت نشد.</p>
            ) : (
              <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
                <table className="data-table" style={{ width: '100%', fontSize: '0.82rem' }}>
                  <thead>
                    <tr>
                      <th>درس</th>
                      <th>مدرس</th>
                      <th>نرخ مشارکت</th>
                      <th>میانگین</th>
                      <th>تاریخی</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((row) => (
                      <tr key={`${row.course_code}-${row.instructor_name}`}>
                        <td>{row.course_name || row.course_code}</td>
                        <td>{row.instructor_name || '—'}</td>
                        <td>{formatParticipationRate(row.participation_rate)}</td>
                        <td>{formatAverageScore(row.average_score)}</td>
                        <td>{formatAverageScore(row.historical_average)}</td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-outline btn-sm"
                            onClick={() => setExpandedCode(
                              expandedCode === row.course_code ? null : row.course_code,
                            )}
                          >
                            {expandedCode === row.course_code ? 'بستن' : 'جزئیات'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {expandedCode && filtered.filter((c) => c.course_code === expandedCode).map((course) => (
              <CourseEvaluationResultCard key={course.course_code} course={course} compact={compact} />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
