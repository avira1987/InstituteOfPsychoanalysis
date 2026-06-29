import React, { useMemo } from 'react'
import {
  AbsenceCounterTile,
  ClassAttendanceFlowStepper,
  ClassAttendanceHintBlock,
  PROCESS_TITLE_FA,
  STUDENT_STATE_HINTS,
  labelAttendanceStatus,
  labelClassAttendanceState,
  labelClassSessionRowStatus,
  resolveClassAttendanceContext,
} from '../utils/lessonAttendanceDisplay'
import { fmtIsoDate, labelAttendanceSessionStatus } from '../utils/lessonStartPerTermDisplay'

/**
 * داشبورد دانشجو — فرایند ۵۴ حضور و غیاب کلاس.
 */
export default function StudentClassAttendancePanel({
  detail = null,
  studentProfile = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const extraData = studentProfile?.extra_data || {}

  const lessonCtx = useMemo(
    () => resolveClassAttendanceContext(ctx, extraData),
    [ctx, extraData],
  )

  if (!active || !detail || detail.process_code !== 'class_attendance') {
    return null
  }

  const hint = STUDENT_STATE_HINTS[currentState]
    || 'پیگیری حضور و غیاب کلاس از این بخش.'
  const isWaiting = currentState === 'attendance_list_ready'
  const isIncomplete = currentState === 'incomplete_triggered'
  const isArticleViolation = currentState === 'article_violation_reported'

  return (
    <div className="card" data-testid="student-class-attendance-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${
              isIncomplete ? 'badge-danger' : isArticleViolation ? 'badge-warning' : isWaiting ? 'badge-info' : 'badge-success'
            }`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelClassAttendanceState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 1rem 1rem' : '0 1.25rem 1.25rem' }}>
        {!compact && <ClassAttendanceFlowStepper currentState={currentState} compact={compact} />}

        <ClassAttendanceHintBlock tone={isIncomplete ? 'warn' : 'info'}>
          {hint}
        </ClassAttendanceHintBlock>

        <p style={{ fontSize: '0.85rem', margin: '0 0 0.75rem', color: '#334155' }}>
          درس:
          {' '}
          <strong>{lessonCtx.lessonName}</strong>
          {lessonCtx.sessionDate && (
            <>
              {' '}
              — جلسه:
              {' '}
              {fmtIsoDate(lessonCtx.sessionDate)}
            </>
          )}
        </p>

        <AbsenceCounterTile count={lessonCtx.absenceCount} />

        {isIncomplete && (
          <div
            data-testid="student-class-attendance-incomplete"
            style={{
              padding: '0.75rem 0.85rem',
              marginBottom: '0.85rem',
              borderRadius: '8px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.85rem',
              lineHeight: 1.65,
              color: '#991b1b',
            }}
          >
            وضعیت Incomplete و قفل نمره برای این درس اعمال شده است. برای ادامهٔ آموزش باید در ترم بعد درس را مجدداً اخذ کنید.
          </div>
        )}

        {isArticleViolation && (
          <div
            data-testid="student-class-attendance-article-violation"
            style={{
              padding: '0.75rem 0.85rem',
              marginBottom: '0.85rem',
              borderRadius: '8px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.85rem',
              lineHeight: 1.65,
              color: '#92400e',
            }}
          >
            غیبت‌های شما در درس مقاله‌نویسی به کمیته نظارت گزارش شده است. وضعیت Incomplete اعمال نمی‌شود؛ پیگیری از مسیر ثبت تخلفات انجام می‌شود.
          </div>
        )}

        {lessonCtx.sessions.length > 0 && (
          <div data-testid="student-class-attendance-sessions">
            <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: '0.4rem', color: '#334155' }}>
              جلسات ثبت‌شده — {lessonCtx.lessonName}
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
                  {lessonCtx.sessions.map((session, sIdx) => {
                    const rowStatus = labelClassSessionRowStatus(session)
                    const isCancelled = rowStatus === 'کنسل'
                    const isMakeup = rowStatus === 'جبرانی'
                    return (
                    <tr key={session.session_number || session.date || sIdx}>
                      <td>
                        {session.session_number ?? sIdx + 1}
                        {isMakeup && (
                          <span className="badge badge-info" style={{ marginRight: '0.35rem', fontSize: '0.7rem' }}>
                            جبرانی
                          </span>
                        )}
                      </td>
                      <td>{session.date ? fmtIsoDate(session.date) : '—'}</td>
                      <td>
                        <span
                          style={{
                            color: isCancelled ? '#991b1b' : isMakeup ? '#0f766e' : undefined,
                            fontWeight: isCancelled || isMakeup ? 700 : undefined,
                          }}
                        >
                          {rowStatus}
                        </span>
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {currentState === 'session_recorded' && lessonCtx.studentsAttendance.length > 0 && (
          <div style={{ marginTop: '0.85rem', fontSize: '0.82rem', color: '#64748b' }}>
            وضعیت ثبت‌شده در این جلسه:
            {' '}
            {lessonCtx.studentsAttendance
              .filter((r) => String(r.student_id) === String(studentProfile?.id))
              .map((r) => labelAttendanceStatus(r.status))
              .join('')}
          </div>
        )}
      </div>
    </div>
  )
}
