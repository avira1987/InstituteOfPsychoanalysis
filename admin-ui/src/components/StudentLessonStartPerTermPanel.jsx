import React, { useMemo } from 'react'
import {
  LessonStartFlowStepper,
  labelLessonStartState,
  resolveLessonStartContext,
  labelAttendanceSessionStatus,
  fmtIsoDate,
} from '../utils/lessonStartPerTermDisplay'

const PROCESS_TITLE_FA = 'آغاز هر درس در هر ترم (فرایند ۴۱)'

/** راهنمای هر وضعیت برای دانشجو. */
const STATE_HINTS = {
  student_enrollment: 'درس مورد نظر را از فرم زیر انتخاب و ثبت کنید. در هر جلسه می‌توانید آنلاین یا حضوری شرکت کنید؛ لینک کلاس برای همه فعال می‌شود.',
  links_created: 'سامانه در حال ایجاد و قرار دادن لینک کلاس آنلاین است. این مرحله خودکار است — چند لحظه بعد صفحه را تازه کنید.',
  attendance_list_ready: 'سامانه در حال تشکیل لیست حضور و غیاب و ثبت کمک‌مدرسین است. این مرحله خودکار است — صفحه را تازه کنید.',
  lesson_active: 'درس شما فعال است. از دکمهٔ ورود به کلاس آنلاین استفاده کنید؛ وضعیت حضور هر جلسه پس از ثبت توسط مدرس در جدول زیر به‌روز می‌شود.',
}

function InfoTile({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
  if (value == null || value === '') return null
  return (
    <div
      style={{
        padding: '0.75rem 0.85rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontSize: '1.05rem', fontWeight: 800, color: tone }}>{value}</div>
    </div>
  )
}

/**
 * داشبورد راهنمای «آغاز هر درس در هر ترم» — فرایند ۴۱.
 */
export default function StudentLessonStartPerTermPanel({
  detail = null,
  studentProfile = null,
  stepFormValues = {},
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const extraData = studentProfile?.extra_data || {}

  const lessonCtx = useMemo(
    () => resolveLessonStartContext(ctx, extraData),
    [ctx, extraData],
  )

  if (!active || !detail || detail.process_code !== 'lesson_start_per_term') {
    return null
  }

  const isComplete = currentState === 'lesson_active'
  const isSystemPending = ['links_created', 'attendance_list_ready'].includes(currentState)

  const hint = STATE_HINTS[currentState]
    ?? 'ثبت‌نام در درس — مراحل را طبق راهنمای پنل پیش ببرید.'

  const showCourseInfo = ['student_enrollment', 'lesson_active'].includes(currentState)
    && lessonCtx.courseLabel

  const showTa = currentState === 'lesson_active' && lessonCtx.teachingAssistant
  const showOnlineLink = currentState === 'lesson_active' && lessonCtx.onlineLink
  const showSessions = currentState === 'lesson_active' && lessonCtx.sessions.length > 0

  return (
    <div className="card" data-testid="student-lesson-start-per-term-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isComplete ? 'badge-success' : isSystemPending ? 'badge-info' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelLessonStartState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <LessonStartFlowStepper currentState={currentState} compact={compact} />

        {hint && (
          <div
            data-testid="lesson-start-state-hint"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: isSystemPending ? '#f0fdfa' : '#eff6ff',
              borderRight: `4px solid ${isSystemPending ? '#0d9488' : '#2563eb'}`,
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: isSystemPending ? '#134e4a' : '#1e3a8a',
            }}
          >
            {hint}
          </div>
        )}

        {(showCourseInfo || showTa) && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '0.65rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            {showCourseInfo && (
              <InfoTile label="نام درس" value={lessonCtx.courseLabel} tone="#16a34a" bg="#f0fdf4" />
            )}
            {showTa && (
              <InfoTile label="کمک‌مدرس" value={lessonCtx.teachingAssistant} tone="#7c3aed" bg="#f5f3ff" />
            )}
          </div>
        )}

        {showOnlineLink && (
          <div
            data-testid="lesson-start-online-link"
            style={{ marginBottom: compact ? '0.65rem' : '0.85rem' }}
          >
            <a
              href={lessonCtx.onlineLink}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary btn-sm"
              style={{ textDecoration: 'none' }}
            >
              ورود به کلاس آنلاین
            </a>
          </div>
        )}

        {showSessions && (
          <div
            data-testid="lesson-start-attendance-sessions"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              overflowX: 'auto',
            }}
          >
            <div style={{ fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.45rem', color: '#334155' }}>
              وضعیت حضور و غیاب شما در درس
            </div>
            <table className="table" style={{ fontSize: '0.82rem', marginBottom: 0 }}>
              <thead>
                <tr>
                  <th>جلسه</th>
                  <th>تاریخ</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {lessonCtx.sessions.map((session, idx) => (
                  <tr key={session.session_number || session.date || idx}>
                    <td>{session.session_number ?? idx + 1}</td>
                    <td>{session.date ? fmtIsoDate(session.date) : '—'}</td>
                    <td>{labelAttendanceSessionStatus(session.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {isComplete && (
          <div
            data-testid="lesson-start-complete-block"
            style={{
              marginTop: '0.5rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
              درس شما فعال شد و لینک کلاس آنلاین در دسترس است.
              {lessonCtx.lessonActiveAt ? ` — ${fmtIsoDate(lessonCtx.lessonActiveAt)}` : ''}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
