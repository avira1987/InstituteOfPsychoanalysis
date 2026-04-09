import React from 'react'

/**
 * بلوک‌های «دربارهٔ فرایند»، «خلاصهٔ مرحله»، «تکلیف شما» — variant=quest برای پس‌زمینه تیره داشبورد، light برای کارت روشن.
 */
export default function StudentProcessGuidancePanel({ guidance, variant = 'quest' }) {
  if (!guidance) return null
  const { overviewFa, shortFa, taskFa } = guidance
  if (!overviewFa && !shortFa && !taskFa) return null
  return (
    <div className={`spg spg--${variant}`}>
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
      {taskFa && (
        <div className="spg-block spg-block--task">
          <span className="spg-label">تکلیف / اقدام شما در پنل</span>
          <p className="spg-text" data-testid="guidance-task-text">{taskFa}</p>
        </div>
      )}
    </div>
  )
}
