import React, { useMemo } from 'react'
import TermTranscriptGradesTable from './TermTranscriptGradesTable'
import TermEndArtifactsSection from './TermEndArtifactsSection'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import {
  ComprehensiveTermEndFlowStepper,
  labelComprehensiveTermEndState,
  resolveTermEndContext,
  hasTranscriptsReady,
  showRegistrationReminder,
  isProcessComplete,
  fmtIsoDate,
} from '../utils/comprehensiveTermEndDisplay'

const PROCESS_TITLE_FA = 'پایان ترم‌های دوره جامع (فرایند ۳۶)'
const PROC_CODE = 'comprehensive_term_end'

function resolveComprehensiveTermEndHint(state) {
  if (!state) return 'پایان ترم دوره جامع — مراحل عمدتاً خودکار است؛ این صفحه را بعداً تازه کنید.'
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  return 'پایان ترم دوره جامع — مراحل عمدتاً خودکار است؛ این صفحه را بعداً تازه کنید.'
}

const SYSTEM_STATES = new Set([
  'grades_submitted',
  'transcript_generated',
  'graduation_check',
])

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
 * داشبورد راهنمای «پایان ترم‌های دوره جامع» — فرایند ۳۶.
 */
export default function StudentComprehensiveTermEndPanel({
  detail = null,
  extraData = null,
  active = true,
  compact = false,
  studentId = null,
  activeProcesses = [],
  onGoToProfile = null,
  onGoToProcesses = null,
  onViewInstance = null,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const termEnd = useMemo(() => resolveTermEndContext(ctx, extraData || {}), [ctx, extraData])

  if (!active || !detail || detail.process_code !== 'comprehensive_term_end') {
    return null
  }

  const hint = resolveComprehensiveTermEndHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelComprehensiveTermEndState(currentState)) ?? ''
  const isComplete = isProcessComplete(currentState)
  const graduated = currentState === 'completed_all_courses' || termEnd.allCoursesPassed
  const showTranscripts = hasTranscriptsReady(currentState)
  const showRegDeadline = showRegistrationReminder(currentState) && termEnd.nextTermDeadline
  const showRemainingCourses = termEnd.remainingCourses.length > 0
    && !graduated
    && currentState !== 'grades_submitted'
  const showGradesTable = hasTranscriptsReady(currentState) || termEnd.remainingCourses.length > 0
  const nextTermStart = activeProcesses?.find(
    (p) => p.process_code === 'comprehensive_term_start' && !p.is_completed,
  )
  const showNextTermCta = currentState === 'registration_notification_sent' && !graduated

  const openNextTermRegistration = () => {
    if (typeof onViewInstance === 'function' && nextTermStart?.instance_id) {
      onViewInstance(nextTermStart.instance_id)
      return
    }
    if (typeof onGoToProcesses === 'function') onGoToProcesses()
  }

  const fmtGpa = (v) => {
    const n = Number(v)
    if (!Number.isFinite(n)) return null
    return n.toLocaleString('fa-IR', { maximumFractionDigits: 2 })
  }

  return (
    <div className="card" data-testid="student-comprehensive-term-end-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isComplete ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelComprehensiveTermEndState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ComprehensiveTermEndFlowStepper currentState={currentState} compact={compact} />

        {hint && (
          <div
            data-testid="comprehensive-term-end-state-hint"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#eff6ff',
              borderRight: '4px solid #2563eb',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#1e3a8a',
            }}
          >
            {statusShort && (
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.25rem' }}>
                وضعیت فعلی: {statusShort}
              </div>
            )}
            <div style={{ fontWeight: 600, marginBottom: '0.2rem' }}>اقدام بعدی شما</div>
            {hint}
          </div>
        )}

        {SYSTEM_STATES.has(currentState) && (
          <p
            className="muted"
            style={{ margin: '0 0 0.75rem', fontSize: '0.82rem', lineHeight: 1.65 }}
          >
            این مرحله توسط سامانه انجام می‌شود؛ در صورت تأخیر، صفحه را یک‌بار تازه کنید.
          </p>
        )}

        {(termEnd.termCode || termEnd.termGpa != null || termEnd.cumulativeGpa != null) && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: '0.65rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            {termEnd.termCode && (
              <InfoTile label="ترم" value={String(termEnd.termCode)} tone="#0d9488" bg="#f0fdfa" />
            )}
            {fmtGpa(termEnd.termGpa) && (
              <InfoTile label="معدل ترم" value={fmtGpa(termEnd.termGpa)} tone="#2563eb" bg="#eff6ff" />
            )}
            {fmtGpa(termEnd.cumulativeGpa) && (
              <InfoTile label="معدل کل" value={fmtGpa(termEnd.cumulativeGpa)} tone="#7c3aed" bg="#f5f3ff" />
            )}
          </div>
        )}

        {showGradesTable && (
          <TermTranscriptGradesTable
            detail={detail}
            extraData={extraData}
            termGpa={termEnd.termGpa}
            compact={compact}
          />
        )}

        {showTranscripts && studentId && (
          <TermEndArtifactsSection
            studentId={studentId}
            processCode="comprehensive_term_end"
            compact={compact}
          />
        )}

        {showTranscripts && (
          <div
            data-testid="comprehensive-term-end-transcripts-ready"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: '0 0 0.5rem', fontSize: '0.86rem', color: '#166534', lineHeight: 1.7 }}>
              کارنامه ترمی و کارنامه کلی (آکادمیک، بالینی و نظارتی) شما آماده است.
            </p>
            {typeof onGoToProfile === 'function' && (
              <button
                type="button"
                className="btn btn-sm btn-outline"
                data-testid="comprehensive-term-end-go-transcripts"
                onClick={onGoToProfile}
              >
                مشاهده کارنامه‌ها در پروفایل
              </button>
            )}
          </div>
        )}

        {graduated && (
          <div
            data-testid="comprehensive-term-end-graduation"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.86rem', color: '#166534', lineHeight: 1.7 }}>
              <strong>اتمام دروس دوره جامع:</strong>
              {' '}
              تمام دروس دوره جامع را با موفقیت پاس کرده‌اید.
            </p>
          </div>
        )}

        {showRemainingCourses && (
          <div
            data-testid="comprehensive-term-end-remaining-courses"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#92400e',
            }}
          >
            <strong>دروس باقی‌مانده:</strong>
            <ul style={{ margin: '0.5rem 0 0', paddingRight: '1.25rem' }}>
              {termEnd.remainingCourses.map((course, idx) => (
                <li key={idx}>{typeof course === 'string' ? course : course?.name_fa ?? course?.course_name ?? String(course)}</li>
              ))}
            </ul>
          </div>
        )}

        {showNextTermCta && (
          <div
            data-testid="comprehensive-term-end-next-term-cta"
            style={{ marginBottom: '0.85rem' }}
          >
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={openNextTermRegistration}
            >
              {nextTermStart ? 'ثبت‌نام ترم بعد' : 'رفتن به فرایند شروع ترم جامع'}
            </button>
          </div>
        )}

        {showRegDeadline && (
          <div
            data-testid="comprehensive-term-end-registration-deadline"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#92400e',
            }}
          >
            <strong>مهلت ثبت‌نام ترم بعد:</strong>
            {' '}
            {fmtIsoDate(termEnd.nextTermDeadline)}
          </div>
        )}

        {isComplete && (
          <div
            data-testid="comprehensive-term-end-complete-block"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
              فرایند پایان ترم تکمیل شد. کارنامه‌ها در تب پروفایل در دسترس است.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
