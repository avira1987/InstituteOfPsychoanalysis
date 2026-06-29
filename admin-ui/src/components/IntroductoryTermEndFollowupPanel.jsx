import React, { useMemo } from 'react'
import { computeSlaRemaining, SlaBanner } from '../utils/earlyTerminationChainDisplay'
import { resolveTermEndContext } from '../utils/introductoryTermEndDisplay'
import { formatStudentCodeDisplay } from '../utils/processDisplay'

const FOLLOWUP_SLA_DAYS = 7

/**
 * راهنمای مسئول پذیرش برای پیگیری افت تحصیلی — فرایند ۳۲، state followup_in_progress.
 */
export default function IntroductoryTermEndFollowupPanel({
  detail = null,
  user = null,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state

  const termEnd = useMemo(() => resolveTermEndContext(ctx), [ctx])

  if (
    !detail
    || detail.process_code !== 'introductory_term_end'
    || currentState !== 'followup_in_progress'
  ) {
    return null
  }

  const slaInfo = computeSlaRemaining(
    {
      ...ctx,
      followup_in_progress_entered_at: termEnd.followupEnteredAt,
      started_at: detail.started_at,
    },
    FOLLOWUP_SLA_DAYS,
    'followup_in_progress_entered_at',
  ) || computeSlaRemaining(ctx, FOLLOWUP_SLA_DAYS, 'started_at')

  const failedList = termEnd.failedCourses
  const studentLabel = detail.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : null

  return (
    <div
      data-testid="intro-term-end-followup-panel"
      style={{
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
        background: '#fffbeb',
        borderRadius: '10px',
        borderRight: '4px solid #d97706',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#92400e' }}>
        پیگیری دانشجویان افت تحصیلی (فرایند ۳۲)
      </h4>

      <SlaBanner
        slaInfo={slaInfo}
        title="مهلت پیگیری تماس (۷ روز)"
        fallbackText="پس از ورود به این مرحله، حداکثر ۷ روز برای تماس با دانشجویان افت تحصیلی فرصت دارید."
      />

      <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
        با دانشجویانی که حداقل یک درس مردود دارند تماس بگیرید و پس از هر تماس، تیک «پیگیری انجام شد»
        را در فرم زیر بزنید. وقتی همه ردیف‌ها تیک خوردند، «ثبت پیگیری‌ها» را بزنید و سپس انتقال
        {' '}
        <code style={{ fontSize: '0.8rem' }}>all_followups_done</code>
        {' '}
        را انجام دهید.
      </p>

      {studentLabel && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          پروندهٔ دانشجو:
          {' '}
          <strong>{studentLabel}</strong>
        </p>
      )}

      {failedList.length > 0 && (
        <div
          data-testid="intro-term-end-failed-courses-summary"
          style={{
            marginBottom: '0.75rem',
            padding: '0.65rem 0.85rem',
            borderRadius: '8px',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            fontSize: '0.82rem',
            lineHeight: 1.65,
            color: '#991b1b',
          }}
        >
          <strong>دروس مردود (از context):</strong>
          <ul style={{ margin: '0.35rem 0 0', paddingRight: '1.1rem' }}>
            {failedList.map((c, i) => (
              <li key={i}>{typeof c === 'string' ? c : (c?.name || c?.course_name || JSON.stringify(c))}</li>
            ))}
          </ul>
        </div>
      )}

      {user?.role && user.role !== 'admissions_officer' && user.role !== 'admin' && (
        <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
          این مرحله معمولاً بر عهدهٔ مسئول پذیرش است.
        </p>
      )}
    </div>
  )
}
