import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  TaTrackFlowStepper,
  HintBlock,
  InfoTile,
  STOP_MESSAGES,
  STATE_HINTS,
  PROCESS_CODE,
  PROCESS_TITLE_FA,
  resolveTaTrackContext,
  fmtIsoDate,
  fmtTimeHm,
  MEETING_TYPE_LABELS,
} from '../utils/taTrackChangeDisplay'

/**
 * داشبورد راهنمای فرایند ۵۱ — تغییر/اضافه رسته کمک‌مدرس (نمای کمک‌مدرس/دانشجو).
 */
export default function StudentTaTrackChangePanel({
  detail = null,
  studentProfile = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const extraData = studentProfile?.extra_data || {}

  const trackCtx = useMemo(
    () => resolveTaTrackContext(ctx, extraData),
    [ctx, extraData],
  )

  if (!active || !detail || detail.process_code !== PROCESS_CODE) {
    return null
  }

  const isStop = currentState === 'rejected'
  const isComplete = currentState === 'track_applied'
  const isWait = ['path_selected', 'course_committee_review', 'meeting_scheduled'].includes(currentState)

  const hint = STOP_MESSAGES[currentState]
    || STATE_HINTS[currentState]
    || 'مراحل تغییر یا اضافه کردن رسته را طبق راهنمای پنل پیش ببرید.'

  const showPath = trackCtx.path && trackCtx.path !== '—'
  const showMeeting = (trackCtx.meetingDate || trackCtx.meetingTime)
    && ['meeting_scheduled', 'track_applied'].includes(currentState)

  return (
    <div
      className="card"
      data-testid="student-ta-track-change-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${
              isStop ? 'badge-danger' : isComplete ? 'badge-success' : 'badge-warning'
            }`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TaTrackFlowStepper currentState={currentState} compact={compact} />

        {isStop && (
          <HintBlock tone="#dc2626" bg="#fef2f2">
            <strong>پایان مسیر:</strong>
            {' '}
            {hint}
          </HintBlock>
        )}

        {!isStop && !isComplete && (
          <HintBlock tone={isWait ? '#d97706' : '#2563eb'} bg={isWait ? '#fffbeb' : '#eff6ff'}>
            {hint}
          </HintBlock>
        )}

        {isComplete && (
          <HintBlock tone="#16a34a" bg="#f0fdf4">
            {hint}
            {trackCtx.appliedTracksLabel !== '—' && (
              <>
                {' '}
                رسته(های) اعمال‌شده:
                {' '}
                <strong>{trackCtx.appliedTracksLabel}</strong>
              </>
            )}
          </HintBlock>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.75rem',
          }}
        >
          {trackCtx.currentTracks.length > 0 && (
            <InfoTile
              label="رسته(های) فعلی"
              value={trackCtx.currentTracksLabel}
              tone="#6366f1"
              bg="#eef2ff"
            />
          )}
          {showPath && (
            <InfoTile
              label="نوع درخواست"
              value={trackCtx.pathLabel}
              tone="#2563eb"
              bg="#eff6ff"
            />
          )}
        </div>

        {showMeeting && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: '0.65rem',
              marginBottom: '0.75rem',
            }}
          >
            <InfoTile label="تاریخ جلسه" value={fmtIsoDate(trackCtx.meetingDate)} />
            <InfoTile label="ساعت" value={fmtTimeHm(trackCtx.meetingTime)} />
            <InfoTile
              label="نحوه برگزاری"
              value={MEETING_TYPE_LABELS[trackCtx.meetingType] || trackCtx.meetingType}
            />
            {trackCtx.meetingType === 'online' && trackCtx.meetingLink && (
              <InfoTile label="لینک جلسه" value={trackCtx.meetingLink} tone="#0d9488" bg="#f0fdfa" />
            )}
          </div>
        )}

        {currentState === 'ta_click' && (
          <HintBlock tone="#7c3aed" bg="#f5f3ff" testId="ta-track-path-hint">
            پس از هماهنگی با مدرس، در فرم پایین یکی از گزینه‌های «اضافه کردن رسته» یا «تغییر رسته» را
            انتخاب کنید، فرم را ثبت کنید و دکمه «ارسال درخواست» (path_chosen) را بزنید.
          </HintBlock>
        )}
      </div>
    </div>
  )
}
