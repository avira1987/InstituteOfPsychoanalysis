import React, { useMemo } from 'react'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import {
  IntroCompletionFlowStepper,
  labelIntroCompletionState,
  resolveCompletionContext,
  hasCertificateReady,
  showComprehensiveInvitationReminder,
  isSystemWaitState,
  fmtIsoDate,
} from '../utils/introductoryCourseCompletionDisplay'

const PROCESS_TITLE_FA = 'خاتمه دوره آشنایی (فرایند ۳۴)'
const PROC_CODE = 'introductory_course_completion'

function resolveIntroCompletionHint(state) {
  if (!state) return 'خاتمه دوره آشنایی — مراحل عمدتاً خودکار است؛ این صفحه را بعداً تازه کنید.'
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  return 'خاتمه دوره آشنایی — مراحل عمدتاً خودکار است؛ این صفحه را بعداً تازه کنید.'
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
 * داشبورد راهنمای «خاتمه دوره آشنایی» — فرایند ۳۴.
 */
export default function StudentIntroductoryCourseCompletionPanel({
  detail = null,
  extraData = null,
  active = true,
  compact = false,
  onGoToProfile = null,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const completion = useMemo(
    () => resolveCompletionContext(ctx, extraData || {}),
    [ctx, extraData],
  )

  if (!active || !detail || detail.process_code !== 'introductory_course_completion') {
    return null
  }

  const hint = resolveIntroCompletionHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelIntroCompletionState(currentState)) ?? ''
  const isComplete = currentState === 'process_complete'
  const showCertificate = hasCertificateReady(currentState, extraData || {})
  const showDeadline = showComprehensiveInvitationReminder(currentState) && completion.comprehensiveDeadline

  const fmtUnits = (v) => {
    if (!Number.isFinite(v)) return null
    return v.toLocaleString('fa-IR', { maximumFractionDigits: 1 })
  }

  return (
    <div className="card" data-testid="student-introductory-course-completion-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isComplete ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelIntroCompletionState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <IntroCompletionFlowStepper currentState={currentState} compact={compact} />

        {hint && (
          <div
            data-testid="intro-completion-state-hint"
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

        {isSystemWaitState(currentState) && currentState !== 'certificate_review' && (
          <p
            className="muted"
            style={{ margin: '0 0 0.75rem', fontSize: '0.82rem', lineHeight: 1.65 }}
          >
            این مرحله توسط سامانه انجام می‌شود؛ در صورت تأخیر، صفحه را یک‌بار تازه کنید.
          </p>
        )}

        {(completion.totalUnits != null || completion.totalHours != null) && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: '0.65rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            {fmtUnits(completion.totalUnits) && (
              <InfoTile label="تعداد واحد" value={fmtUnits(completion.totalUnits)} tone="#0d9488" bg="#f0fdfa" />
            )}
            {fmtUnits(completion.totalHours) && (
              <InfoTile label="ساعات آموزشی" value={fmtUnits(completion.totalHours)} tone="#2563eb" bg="#eff6ff" />
            )}
          </div>
        )}

        {showDeadline && (
          <div
            data-testid="intro-completion-comprehensive-deadline"
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
            <strong>مهلت درخواست ورود به دوره جامع:</strong>
            {' '}
            {fmtIsoDate(completion.comprehensiveDeadline)}
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem' }}>
              برای ثبت درخواست پذیرش دوره جامع، در مهلت اعلام‌شده با بخش پذیرش تماس بگیرید.
            </p>
          </div>
        )}

        {showCertificate && (
          <div
            data-testid="intro-completion-certificate-ready"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: '0 0 0.5rem', fontSize: '0.86rem', color: '#166534', lineHeight: 1.7 }}>
              گواهی پایان دوره آشنایی شما آماده است.
            </p>
            {typeof onGoToProfile === 'function' && (
              <button
                type="button"
                className="btn btn-sm btn-outline"
                data-testid="intro-completion-go-certificate"
                onClick={onGoToProfile}
              >
                مشاهده گواهی در پروفایل
              </button>
            )}
          </div>
        )}

        {isComplete && (
          <div
            data-testid="intro-completion-complete-block"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
              تبریک! دوره آشنایی را با موفقیت به پایان رساندید. گواهی در تب پروفایل در دسترس است.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
