import React from 'react'
import { formatStudentCodeDisplay } from '../utils/processDisplay'
import { fmtIsoDate, fmtTimeHm, MEETING_TYPE_LABELS, TrackChips } from '../utils/upgradeToTaDisplay'

/**
 * راهنمای کمیته دروس — مصاحبه و رسته فرایند ۴۷.
 */
export default function TaUpgradeCourseCommitteePanel({ detail = null, user = null }) {
  const currentState = detail?.current_state
  const ctx = detail?.context_data || {}

  const isScheduling = detail?.process_code === 'upgrade_to_ta'
    && currentState === 'interview_scheduling'
  const isHeld = detail?.process_code === 'upgrade_to_ta'
    && currentState === 'interview_held'
  const isTrackSelection = detail?.process_code === 'upgrade_to_ta'
    && currentState === 'track_selection'

  if (!detail || (!isScheduling && !isHeld && !isTrackSelection)) {
    return null
  }

  const studentLabel = detail?.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : null

  const tracks = Array.isArray(ctx.tracks) ? ctx.tracks : []

  return (
    <div
      data-testid="ta-course-committee-panel"
      style={{
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
        background: '#eff6ff',
        borderRadius: '10px',
        borderRight: '4px solid #2563eb',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#1e40af' }}>
        {isScheduling && 'تنظیم وقت مصاحبه ارتقا به کمک‌مدرس (فرایند ۴۷)'}
        {isHeld && 'نتیجه مصاحبه ارتقا به کمک‌مدرس (فرایند ۴۷)'}
        {isTrackSelection && 'ثبت نهایی رسته‌های کمک‌مدرس (فرایند ۴۷)'}
      </h4>

      {isScheduling && (
        <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
          وقت مصاحبه را ثبت کنید، فرم زمان را تکمیل کنید و انتقال
          {' '}
          <code style={{ fontSize: '0.8rem' }}>interview_scheduled</code>
          {' '}
          را بزنید. پیامک به دانشجو و مسئولان کمیته دروس ارسال می‌شود.
        </p>
      )}

      {isHeld && (
        <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
          پس از برگزاری مصاحبه، فرم نتیجه را تکمیل کنید و
          {' '}
          <code style={{ fontSize: '0.8rem' }}>approved</code>
          {' '}
          یا
          {' '}
          <code style={{ fontSize: '0.8rem' }}>rejected</code>
          {' '}
          را ثبت کنید.
        </p>
      )}

      {isTrackSelection && (
        <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
          رسته‌های توافق‌شده را در فرم تأیید کنید و انتقال
          {' '}
          <code style={{ fontSize: '0.8rem' }}>tracks_registered</code>
          {' '}
          را بزنید تا دانشجو به مرحلهٔ امضای تعهدنامه برود.
        </p>
      )}

      {(ctx.interview_date || ctx.interview_time) && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          زمان ثبت‌شده:
          {' '}
          <strong>
            {fmtIsoDate(ctx.interview_date)}
            {' '}
            —
            {' '}
            {fmtTimeHm(ctx.interview_time)}
            {ctx.meeting_type ? ` (${MEETING_TYPE_LABELS[ctx.meeting_type] || ctx.meeting_type})` : ''}
          </strong>
        </p>
      )}

      {tracks.length > 0 && (isHeld || isTrackSelection) && (
        <div style={{ marginBottom: '0.5rem' }}>
          <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.25rem' }}>رسته‌های پیشنهادی/ثبت‌شده</div>
          <TrackChips tracks={tracks} />
        </div>
      )}

      {studentLabel && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          پروندهٔ دانشجو:
          {' '}
          <strong>{studentLabel}</strong>
        </p>
      )}

      {user?.role && !['course_committee', 'course_committee_scientific', 'course_committee_executive', 'scientific_officer_course_committee', 'admin', 'staff'].includes(user.role) && (
        <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
          این مرحله بر عهدهٔ کمیته دروس است.
        </p>
      )}
    </div>
  )
}
