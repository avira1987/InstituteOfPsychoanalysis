import React from 'react'
import {
  HintBlock,
  TaTrackFlowStepper,
  TaTrackInfoTile,
  fmtIsoDate,
  isTaTrackTerminalState,
  labelTaTrackState,
} from '../utils/taTrackCompletionDisplay'

/**
 * داشبورد پرونده و سوابق کمک‌مدرسی — فرایند ۵۲.
 */
export default function TaTrackPortfolioPanel({
  portfolio = null,
  studentName = '',
  portalRole = 'student',
  instanceDetail = null,
  compact = false,
  loading = false,
  readOnlyNote = null,
}) {
  if (loading) {
    return (
      <div className="card" data-testid="ta-track-portfolio-panel">
        <div className="card-header">
          <h3 className="card-title">پرونده و سوابق آموزشی کمک‌مدرس</h3>
        </div>
        <div style={{ padding: '1rem' }} className="muted">در حال بارگذاری…</div>
      </div>
    )
  }

  if (!portfolio) return null

  const currentState = instanceDetail?.current_state || null
  const isTerminal = isTaTrackTerminalState(currentState)
  const displayName = portfolio.student_name_fa || studentName || '—'
  const activeTracks = portfolio.active_tracks || []
  const completedTracks = portfolio.completed_tracks || []
  const courses = portfolio.courses || []
  const isOperator = portalRole && portalRole !== 'student'

  return (
    <div
      className="card"
      data-testid="ta-track-portfolio-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">پرونده و سوابق آموزشی کمک‌مدرس</h3>
        {currentState && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelTaTrackState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        {instanceDetail?.process_code === 'ta_track_completion' && (
          <TaTrackFlowStepper currentState={currentState} compact={compact} />
        )}

        {isTerminal && (
          <HintBlock tone="success">
            تبریک! رسته کمک‌مدرسی شما با موفقیت خاتمه یافت.
            {instanceDetail?.context_data?.track_name_fa && (
              <span> ({instanceDetail.context_data.track_name_fa})</span>
            )}
          </HintBlock>
        )}

        {isOperator && readOnlyNote && (
          <HintBlock tone="muted">{readOnlyNote}</HintBlock>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '0.75rem',
            marginBottom: '1rem',
          }}
        >
          <TaTrackInfoTile label="نام و نام خانوادگی" value={displayName} />
          <TaTrackInfoTile
            label="رتبه تحلیلی فعلی"
            value={portfolio.rank_fa || '—'}
            accent={portfolio.rank === 'assistant_faculty' || portfolio.rank === 'instructor'}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <h4 style={{ fontSize: '0.92rem', margin: '0 0 0.5rem' }}>رسته‌های فعال (در حال گذراندن)</h4>
          {activeTracks.length === 0 ? (
            <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>رسته فعالی ثبت نشده است.</p>
          ) : (
            <ul style={{ margin: 0, paddingRight: '1.25rem', lineHeight: 1.8 }}>
              {activeTracks.map((t) => (
                <li key={t.code}>
                  {t.name_fa}
                  {t.courses_total != null && (
                    <span className="muted" style={{ fontSize: '0.82rem' }}>
                      {' '}
                      — {Number(t.courses_done || 0).toLocaleString('fa-IR')} از{' '}
                      {Number(t.courses_total).toLocaleString('fa-IR')} درس تکمیل‌شده
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <h4 style={{ fontSize: '0.92rem', margin: '0 0 0.5rem' }}>رسته‌های خاتمه‌یافته</h4>
          {completedTracks.length === 0 ? (
            <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>هنوز رسته‌ای خاتمه نیافته است.</p>
          ) : (
            <ul style={{ margin: 0, paddingRight: '1.25rem', lineHeight: 1.8 }}>
              {completedTracks.map((t) => (
                <li key={t.code || t.name_fa}>
                  {t.name_fa}
                  {t.completed_at && (
                    <span className="muted" style={{ fontSize: '0.82rem' }}>
                      {' '}
                      — تاریخ اتمام: {fmtIsoDate(t.completed_at)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <h4 style={{ fontSize: '0.92rem', margin: '0 0 0.5rem' }}>جزئیات وضعیت دروس</h4>
          {courses.length === 0 ? (
            <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
              هنوز درسی در پرونده کمک‌مدرسی ثبت نشده است.
            </p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="table" style={{ fontSize: '0.85rem', minWidth: '520px' }}>
                <thead>
                  <tr>
                    <th>نام درس</th>
                    <th>رسته</th>
                    <th>پیشرفت</th>
                    <th>نقش فعلی</th>
                  </tr>
                </thead>
                <tbody>
                  {courses.map((row) => (
                    <tr key={row.course_code || row.course_name_fa}>
                      <td>{row.course_name_fa}</td>
                      <td>{row.track_name_fa || '—'}</td>
                      <td>{row.progress_fa || '—'}</td>
                      <td>{row.current_role_fa || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {portfolio.guide_fa && !compact && (
          <HintBlock tone="info">{portfolio.guide_fa}</HintBlock>
        )}
      </div>
    </div>
  )
}
