import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  MentorDeadlineBanner,
  MentorPrivateSessionsFlowStepper,
  MentorSessionInfoTiles,
  MentorSessionsSummary,
  PROCESS_TITLE_FA,
  isMentorPrivateSessionsProcess,
  resolveMentorSessionContext,
} from '../utils/mentorPrivateSessionsDisplay'

function roleBucket(user) {
  const r = (user?.role || '').toLowerCase()
  if (r === 'instructor') return 'instructor'
  if (r === 'teaching_assistant') return 'ta'
  if (r === 'admin' || r === 'staff') return 'admin'
  return 'other'
}

const INSTRUCTOR_HINTS = {
  instructor_click: 'تاریخ و ساعت هر دو جلسهٔ تدریس خصوصی با کمک‌مدرس را در فرم زیر وارد کنید؛ پس از ذخیرهٔ فرم، دکمهٔ «ثبت جلسات» (sessions_entered) را بزنید.',
  sessions_registered: 'جلسات ثبت شد؛ سامانه به‌زودی اطلاع‌رسانی و یادآوری ۲۴ ساعته را انجام می‌دهد.',
  process_complete: 'ثبت نهایی انجام شد. پیامک برای مدرس و کمک‌مدرس ارسال شده و یادآوری ۲۴ ساعت قبل از هر جلسه برنامه‌ریزی می‌شود.',
  deadline_missed: 'مهلت ثبت تا پیش از شروع جلسهٔ دوم کلاس گذشته است. این مورد به‌عنوان تخلف ثبت شده و به کمیتهٔ نظارت ارجاع می‌شود.',
}

const TA_HINTS = {
  sessions_registered: 'مدرس تاریخ و ساعت دو جلسهٔ تدریس خصوصی را ثبت کرده است. جزئیات در باکس زیر قابل مشاهده است.',
  process_complete: 'برنامهٔ دو جلسهٔ تدریس خصوصی ثبت و نهایی شده است. یادآوری ۲۴ ساعت قبل از هر جلسه برای شما ارسال می‌شود.',
}

/**
 * راهنمای فرایند ۴۸ — ثبت تاریخ ۲ جلسه تدریس خصوصی مدرس به کمک‌مدرس.
 */
export default function MentorPrivateSessionsPanel({
  detail = null,
  user = null,
  active = true,
  compact = false,
}) {
  const processCode = detail?.process_code || null
  const currentState = detail?.current_state || null
  const ctx = detail?.context_data || {}
  const bucket = roleBucket(user)

  const mentorCtx = useMemo(() => resolveMentorSessionContext(ctx), [ctx])

  if (!active || !detail || !isMentorPrivateSessionsProcess(processCode)) {
    return null
  }

  const isViolation = currentState === 'deadline_missed'
  const isComplete = currentState === 'process_complete'
  const isRegistered = currentState === 'sessions_registered' || isComplete
  const isInstructorPhase = currentState === 'instructor_click'

  const hint = (() => {
    if (bucket === 'ta' && TA_HINTS[currentState]) return TA_HINTS[currentState]
    if (bucket === 'instructor' || bucket === 'admin') {
      return INSTRUCTOR_HINTS[currentState] || INSTRUCTOR_HINTS.instructor_click
    }
    if (isRegistered) return TA_HINTS.process_complete
    return INSTRUCTOR_HINTS.instructor_click
  })()

  const accent = isViolation ? '#dc2626' : isComplete ? '#16a34a' : '#d97706'
  const accentBg = isViolation ? '#fef2f2' : isComplete ? '#f0fdf4' : '#fffbeb'

  return (
    <div
      data-testid="mentor-private-sessions-panel"
      style={{
        padding: compact ? '0.75rem' : '1rem 1.25rem',
        marginBottom: compact ? '0.75rem' : '1.25rem',
        background: accentBg,
        borderRadius: '10px',
        borderRight: `4px solid ${accent}`,
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.35rem', color: isViolation ? '#991b1b' : isComplete ? '#166534' : '#92400e' }}>
        {PROCESS_TITLE_FA}
      </h4>
      {!compact && (
        <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '0 0 0.75rem' }}>
          وضعیت:
          {' '}
          <strong>{labelState(currentState)}</strong>
        </p>
      )}

      <MentorPrivateSessionsFlowStepper currentState={currentState} compact={compact} />

      <MentorSessionInfoTiles mentorCtx={mentorCtx} compact={compact} />

      {isInstructorPhase && bucket !== 'ta' && (
        <MentorDeadlineBanner mentorCtx={mentorCtx} currentState={currentState} />
      )}

      {isRegistered && (
        <MentorSessionsSummary mentorCtx={mentorCtx} />
      )}

      {isViolation && (
        <div
          data-testid="mentor-violation-alert"
          style={{
            padding: '0.75rem',
            marginBottom: '0.75rem',
            background: '#fef2f2',
            borderRadius: '8px',
            border: '1px solid #fecaca',
            fontSize: '0.85rem',
            lineHeight: 1.7,
            color: '#991b1b',
          }}
        >
          <strong>تخلف ثبت شد.</strong>
          {' '}
          تاریخ دو جلسهٔ تدریس خصوصی تا پیش از شروع جلسهٔ دوم کلاس ثبت نشده است.
          گزارش به کمیتهٔ نظارت و هشدار به کمیتهٔ دروس ارسال می‌شود.
        </div>
      )}

      {hint && (
        <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: 0, color: '#334155' }}>
          {hint}
        </p>
      )}
    </div>
  )
}
