import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { panelApi } from '../services/api'
import {
  ANONYMITY_NOTICE_FA,
  PROCESS_TITLE_FA,
  SCORE_FIELDS,
  EvaluationFlowStepper,
  ScorePicker,
  buildCourseSubmissionPayload,
  fmtDeadline,
  labelEvaluationState,
  resolveEvaluationCourses,
  validateCourseForm,
} from '../utils/studentInstructorEvaluationDisplay'

const EMPTY_FORM = {
  overall_score: '',
  teaching_clarity: '',
  interaction_quality: '',
  comments: '',
}

function CourseEvalCard({
  course,
  disabled,
  onSubmit,
  submitting,
}) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [expanded, setExpanded] = useState(!course.submitted)

  useEffect(() => {
    if (!course.submitted) setForm(EMPTY_FORM)
  }, [course.course_code, course.submitted])

  const handleSubmit = async () => {
    const { ok, missing } = validateCourseForm(form)
    if (!ok) {
      onSubmit(null, { error: `موارد ناقص: ${missing.join('، ')}` })
      return
    }
    await onSubmit(course.course_code, { payload: buildCourseSubmissionPayload(form) })
  }

  if (course.submitted) {
    return (
      <div
        data-testid={`eval-course-card-${course.course_code}`}
        style={{
          padding: '0.85rem 1rem',
          borderRadius: '10px',
          background: '#f0fdf4',
          border: '1px solid #86efac',
          marginBottom: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
          <div>
            <strong style={{ fontSize: '0.92rem' }}>{course.course_name}</strong>
            <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.2rem' }}>
              مدرس:
              {' '}
              {course.instructor_name}
            </div>
          </div>
          <span className="badge badge-success" style={{ fontSize: '0.75rem' }}>ثبت‌شده</span>
        </div>
      </div>
    )
  }

  return (
    <div
      data-testid={`eval-course-card-${course.course_code}`}
      className="card"
      style={{ marginBottom: '0.75rem', border: '1px solid #e2e8f0' }}
    >
      <div
        className="card-header"
        style={{ cursor: 'pointer' }}
        onClick={() => setExpanded((v) => !v)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter') setExpanded((v) => !v) }}
      >
        <div>
          <h4 className="card-title" style={{ fontSize: '0.95rem', margin: 0 }}>{course.course_name}</h4>
          <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.25rem' }}>
            مدرس:
            {' '}
            {course.instructor_name}
          </div>
        </div>
        <span className="badge badge-warning" style={{ fontSize: '0.75rem' }}>در انتظار</span>
      </div>
      {expanded && (
        <div style={{ padding: '0 1rem 1rem' }}>
          {SCORE_FIELDS.map(({ name, label_fa }) => (
            <ScorePicker
              key={name}
              name={name}
              label={label_fa}
              value={form[name]}
              onChange={(v) => setForm((prev) => ({ ...prev, [name]: v }))}
              disabled={disabled || submitting}
            />
          ))}
          <label className="psf-field" style={{ display: 'block', marginBottom: '0.75rem' }}>
            <span className="psf-label">نظر یا پیشنهاد (اختیاری)</span>
            <textarea
              className="psf-input"
              rows={3}
              value={form.comments}
              onChange={(e) => setForm((prev) => ({ ...prev, comments: e.target.value }))}
              disabled={disabled || submitting}
            />
          </label>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={disabled || submitting}
            onClick={handleSubmit}
            data-testid={`eval-submit-${course.course_code}`}
          >
            {submitting ? 'در حال ثبت…' : 'ثبت ناشناس'}
          </button>
        </div>
      )}
    </div>
  )
}

/**
 * داشبورد «ارزیابی دانشجو از مدرسین» — فرایند ۵۷.
 */
export default function StudentInstructorEvaluationPanel({
  detail = null,
  instanceId = null,
  studentProfile = null,
  active = true,
  compact = false,
  showToast = null,
  onRefreshInstance = null,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const extraData = studentProfile?.extra_data || {}

  const [apiCourses, setApiCourses] = useState(null)
  const [deadline, setDeadline] = useState(null)
  const [loading, setLoading] = useState(false)
  const [submittingCode, setSubmittingCode] = useState(null)

  const localCourses = useMemo(
    () => resolveEvaluationCourses(extraData, ctx),
    [extraData, ctx],
  )

  const courses = apiCourses?.courses?.length ? apiCourses.courses : localCourses
  const submittedCount = courses.filter((c) => c.submitted).length

  const loadCourses = useCallback(async () => {
    if (!instanceId || currentState !== 'evaluation_open') return
    setLoading(true)
    try {
      const res = await panelApi.studentInstructorEvaluationCourses(instanceId)
      setApiCourses(res.data)
      if (res.data?.evaluation_close_at) setDeadline(res.data.evaluation_close_at)
    } catch {
      /* fallback to local */
    } finally {
      setLoading(false)
    }
  }, [instanceId, currentState])

  useEffect(() => {
    loadCourses()
    panelApi.activeAcademicCalendar()
      .then((res) => {
        if (res.data?.evaluation_close_at) setDeadline(res.data.evaluation_close_at)
      })
      .catch(() => {})
  }, [loadCourses])

  const handleSubmit = async (courseCode, result) => {
    if (!courseCode) {
      showToast?.(result?.error || 'خطا', 'error')
      return
    }
    if (!instanceId) {
      showToast?.('شناسه پرونده یافت نشد', 'error')
      return
    }
    setSubmittingCode(courseCode)
    try {
      await panelApi.submitStudentInstructorEvaluation(instanceId, courseCode, result.payload)
      showToast?.('ارزیابی این درس به‌صورت ناشناس ثبت شد', 'success')
      await loadCourses()
      await onRefreshInstance?.()
    } catch (e) {
      const d = e.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : (e.message || 'خطا در ثبت'), 'error')
    } finally {
      setSubmittingCode(null)
    }
  }

  if (!active || !detail || detail.process_code !== 'student_instructor_evaluation') {
    return null
  }

  const isClosed = currentState === 'evaluation_closed'
  const deadlineFa = fmtDeadline(deadline)

  return (
    <div className="card" data-testid="student-instructor-evaluation-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isClosed ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelEvaluationState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <EvaluationFlowStepper currentState={currentState} compact={compact} />

        <div
          data-testid="eval-anonymity-notice"
          style={{
            marginBottom: '0.85rem',
            padding: '0.75rem 1rem',
            borderRadius: '10px',
            background: '#f5f3ff',
            borderRight: '4px solid #7c3aed',
            fontSize: '0.86rem',
            lineHeight: 1.75,
            color: '#4c1d95',
          }}
        >
          {ANONYMITY_NOTICE_FA}
        </div>

        {deadlineFa && !isClosed && (
          <p style={{ fontSize: '0.82rem', color: '#b45309', margin: '0 0 0.75rem' }}>
            مهلت پایان ارزیابی:
            {' '}
            <strong>{deadlineFa}</strong>
          </p>
        )}

        {!isClosed && (
          <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '0 0 0.85rem' }}>
            {submittedCount.toLocaleString('fa-IR')}
            {' '}
            از
            {' '}
            {courses.length.toLocaleString('fa-IR')}
            {' '}
            درس ارزیابی شده است.
          </p>
        )}

        {isClosed ? (
          <div
            data-testid="eval-closed-summary"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
              fontSize: '0.88rem',
              lineHeight: 1.7,
            }}
          >
            مهلت ارزیابی پایان یافت. از مشارکت شما سپاسگزاریم.
            {submittedCount > 0 && (
              <span>
                {' '}
                (
                {submittedCount.toLocaleString('fa-IR')}
                {' '}
                درس ثبت شد.)
              </span>
            )}
          </div>
        ) : (
          <>
            {loading && courses.length === 0 && (
              <p style={{ fontSize: '0.85rem', color: '#64748b' }}>در حال بارگذاری دروس…</p>
            )}
            {!loading && courses.length === 0 && (
              <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
                درسی برای ارزیابی در این ترم یافت نشد. در صورت اشتباه با دفتر آموزش تماس بگیرید.
              </p>
            )}
            {courses.map((course) => (
              <CourseEvalCard
                key={course.course_code}
                course={course}
                disabled={isClosed}
                submitting={submittingCode === course.course_code}
                onSubmit={handleSubmit}
              />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
