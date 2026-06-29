import React, { useMemo } from 'react'
import { formatStudentCodeDisplay } from '../utils/processDisplay'
import {
  HintBlock,
  InfoTile,
  PROCESS_CODE,
  resolveTaTrackContext,
  fmtIsoDate,
  fmtTimeHm,
  MEETING_TYPE_LABELS,
} from '../utils/taTrackChangeDisplay'

/**
 * راهنمای کمیته دروس — فرایند ۵۱ (ثبت جلسه و نتیجه).
 */
export default function TaTrackChangeCommitteePanel({
  detail = null,
  user = null,
  studentExtra = null,
}) {
  const currentState = detail?.current_state
  const ctx = detail?.context_data || {}

  const isReview = detail?.process_code === PROCESS_CODE
    && currentState === 'course_committee_review'
  const isMeeting = detail?.process_code === PROCESS_CODE
    && currentState === 'meeting_scheduled'

  const trackCtx = useMemo(
    () => resolveTaTrackContext(ctx, studentExtra || {}),
    [ctx, studentExtra],
  )

  if (!detail || (!isReview && !isMeeting)) {
    return null
  }

  const studentLabel = detail?.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : trackCtx.taName || null

  return (
    <div
      className="card"
      data-testid="ta-track-change-committee-panel"
      style={{ marginBottom: '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">
          {isReview
            ? 'ثبت جلسه بررسی رسته کمک‌مدرس (فرایند ۵۱)'
            : 'نتیجه جلسه و تخصیص رسته (فرایند ۵۱)'}
        </h3>
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        {studentLabel && (
          <p style={{ fontSize: '0.85rem', margin: '0 0 0.75rem', color: '#475569' }}>
            متقاضی:
            {' '}
            <strong>{studentLabel}</strong>
            {trackCtx.taName && trackCtx.taName !== studentLabel && (
              <>
                {' '}
                —
                {' '}
                {trackCtx.taName}
              </>
            )}
          </p>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.85rem',
          }}
        >
          {trackCtx.pathLabel !== '—' && (
            <InfoTile label="نوع درخواست" value={trackCtx.pathLabel} />
          )}
          {trackCtx.currentTracks.length > 0 && (
            <InfoTile label="رسته(های) فعلی" value={trackCtx.currentTracksLabel} />
          )}
        </div>

        {isReview && (
          <HintBlock tone="info" testId="ta-track-committee-schedule-hint">
            پس از هماهنگی تلفنی/حضوری با متقاضی، تاریخ، ساعت و نحوهٔ برگزاری را در فرم «ثبت زمان
            و مشخصات جلسه» وارد کنید. پس از ثبت فرم، دکمه «ثبت جلسه» (meeting_registered) را بزنید.
            پیامک به دانشجو و مسئول علمی ارسال می‌شود.
          </HintBlock>
        )}

        {isMeeting && (
          <>
            {(trackCtx.meetingDate || trackCtx.meetingTime) && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
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
              </div>
            )}
            <HintBlock tone="warn" testId="ta-track-committee-result-hint">
              پس از برگزاری جلسه، در فرم «نتیجه جلسه» تصمیم را ثبت کنید. در صورت موافقت، رسته(های)
              جدید را انتخاب کنید (تکراری با رسته فعلی مجاز نیست). سپس «موافقت» (approved) یا
              «عدم موافقت» (rejected) را بزنید.
            </HintBlock>
          </>
        )}

        {user?.role && !['course_committee', 'admin', 'deputy_education', 'staff'].includes(user.role) && (
          <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
            این مرحله بر عهدهٔ مسئول علمی کمیته دروس است.
          </p>
        )}
      </div>
    </div>
  )
}
