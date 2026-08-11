import React from 'react'

/**
 * بلوک‌های «وضعیت فعلی / اقدام بعدی» و جزئیات فرایند — variant=quest برای داشبورد.
 */
export default function StudentProcessGuidancePanel({ guidance, variant = 'quest' }) {
  if (!guidance) return null
  const { overviewFa, shortFa, taskFa, whyFa, canAct, done, waitingRoleLabelFa } = guidance
  if (!overviewFa && !shortFa && !taskFa) return null

  const isWaitingForOtherRole = !done && canAct === false && !!taskFa
  const hasCollapsedBlocks = !!(overviewFa || (shortFa && !taskFa))
  const defaultOpenDetails = !taskFa && hasCollapsedBlocks
  const showNowNextStrip = !isWaitingForOtherRole && (shortFa || taskFa)

  return (
    <div className={`spg spg--${variant}`}>
      {isWaitingForOtherRole && (
        <div
          className="spg-block spg-block--waiting-role"
          data-testid="guidance-waiting-role-banner"
          role="status"
        >
          <span className="spg-label">منتظر اقدام همکار</span>
          <p className="spg-text spg-text--waiting-role" data-testid="guidance-waiting-role-text">
            {taskFa}
          </p>
          {waitingRoleLabelFa ? (
            <p className="spg-text spg-text--waiting-role-hint">
              نقش مسئول این مرحله: <strong>{waitingRoleLabelFa}</strong>
            </p>
          ) : null}
        </div>
      )}
      {showNowNextStrip && (
        <div
          className="spg-block spg-block--now-next"
          data-testid="guidance-now-next-strip"
          role="status"
        >
          {shortFa && (
            <div className="spg-now-next-row" data-testid="guidance-status-row">
              <span className="spg-label">وضعیت فعلی</span>
              <p className="spg-text spg-text--status" data-testid="guidance-status-text">{shortFa}</p>
            </div>
          )}
          {taskFa && (
            <div className="spg-now-next-row spg-now-next-row--action" data-testid="guidance-task-block">
              <span className="spg-label">اقدام بعدی شما</span>
              <p className="spg-text spg-text--task-primary" data-testid="guidance-task-text">{taskFa}</p>
            </div>
          )}
          {whyFa && (
            <p className="spg-text spg-text--why" data-testid="guidance-why-text">{whyFa}</p>
          )}
        </div>
      )}
      {hasCollapsedBlocks && (
        <details
          className="spg-details"
          defaultOpen={defaultOpenDetails}
          data-testid="guidance-more-details"
        >
          <summary className="spg-details-summary">
            توضیح بیشتر: فرایند و مرحلهٔ فعلی
          </summary>
          <div className="spg-details-inner">
            {overviewFa && (
              <div className="spg-block spg-block--overview">
                <span className="spg-label">دربارهٔ این فرایند</span>
                <p className="spg-text">{overviewFa}</p>
              </div>
            )}
            {shortFa && !taskFa && (
              <div className="spg-block spg-block--step">
                <span className="spg-label">مرحلهٔ فعلی (خلاصه)</span>
                <p className="spg-text">{shortFa}</p>
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  )
}
