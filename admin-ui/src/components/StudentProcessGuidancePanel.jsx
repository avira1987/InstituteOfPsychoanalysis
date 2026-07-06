import React from 'react'

/**
 * بلوک‌های «دربارهٔ فرایند»، «خلاصهٔ مرحله»، «تکلیف شما» — variant=quest برای پس‌زمینه تیره داشبورد، light برای کارت روشن.
 * پیش‌فرض فقط «وظیفه» دیده می‌شود؛ دو بلوک دیگر زیر details.
 */
export default function StudentProcessGuidancePanel({ guidance, variant = 'quest' }) {
  if (!guidance) return null
  const { overviewFa, shortFa, taskFa, canAct, done, waitingRoleLabelFa } = guidance
  if (!overviewFa && !shortFa && !taskFa) return null

  const isWaitingForOtherRole = !done && canAct === false && !!taskFa
  const hasCollapsedBlocks = !!(overviewFa || shortFa)
  const defaultOpenDetails = !taskFa && hasCollapsedBlocks

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
      {taskFa && !isWaitingForOtherRole && (
        <div className="spg-block spg-block--task" data-testid="guidance-task-block">
          <span className="spg-label">وظیفهٔ شما در این مرحله</span>
          <p className="spg-text spg-text--task-primary" data-testid="guidance-task-text">{taskFa}</p>
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
            {shortFa && (
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
