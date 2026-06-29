import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  buildAutomationReport,
  fmtIsoDate,
  HintBlock,
  InfoTile,
  labelTaToInstructorState,
  resolveTaToInstructorContext,
  TaToInstructorFlowStepper,
} from '../utils/taToInstructorAutoDisplay'

const PROCESS_TITLE_FA = 'گزارش اجرای خودکار ارتقا — فرایند ۵۰'

const AUDIENCE_INTROS = {
  committee: 'این گزارش برای اطلاع کمیته دروس است.',
  deputy: 'این گزارش برای اطلاع معاونت آموزش است.',
  staff: 'گزارش سیستمی ارتقای خودکار کمک‌مدرس به مدرس.',
}

function ReportRow({ label, value }) {
  if (!value || value === '—') return null
  return (
    <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.86rem', marginBottom: '0.35rem' }}>
      <span style={{ color: '#64748b', minWidth: '8rem' }}>{label}</span>
      <span style={{ fontWeight: 600, color: '#1e293b' }}>{value}</span>
    </div>
  )
}

/**
 * پنل فقط-خواندنی گزارش Log فرایند ۵۰ — کمیته دروس / معاونت آموزش / کارمند.
 */
export default function TaToInstructorAutoReportPanel({
  detail = null,
  extraData = null,
  active = true,
  audience = 'staff',
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const resolved = useMemo(
    () => resolveTaToInstructorContext(ctx, extraData || {}),
    [ctx, extraData],
  )
  const report = useMemo(
    () => buildAutomationReport(ctx, extraData || {}),
    [ctx, extraData],
  )

  if (!active || !detail || detail.process_code !== 'ta_to_instructor_auto') {
    return null
  }

  const showReport = currentState === 'upgrade_applied'
  const intro = AUDIENCE_INTROS[audience] || AUDIENCE_INTROS.staff

  return (
    <div
      className="card"
      data-testid="ta-to-instructor-auto-report-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${showReport ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelTaToInstructorState(currentState) || labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TaToInstructorFlowStepper currentState={currentState} compact={compact} />

        <HintBlock tone="#6366f1" bg="#eef2ff">
          {intro}
          {' '}
          این گزارش صرفاً اطلاع‌رسانی است و نیاز به تأیید دستی ندارد.
        </HintBlock>

        {!showReport && (
          <p style={{ fontSize: '0.86rem', color: '#64748b', margin: 0, lineHeight: 1.75 }}>
            {currentState === 'conditions_not_met'
              ? 'شرایط احراز نشد — گزارش ارتقا صادر نشده است.'
              : 'در انتظار تکمیل بررسی خودکار پایان ترم…'}
          </p>
        )}

        {showReport && (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: '0.65rem',
                marginBottom: '0.85rem',
              }}
            >
              <InfoTile label="تاریخ اجرا" value={fmtIsoDate(report.executedAt || detail.started_at)} />
              <InfoTile label="نام" value={report.studentName} />
              <InfoTile label="رتبه فعلی" value={report.rankLabel} tone="#7c3aed" bg="#f5f3ff" />
            </div>

            <div
              style={{
                padding: '0.85rem 1rem',
                borderRadius: '10px',
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                marginBottom: '0.75rem',
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: '0.5rem', color: '#0f172a' }}>
                ۱) تغییر نقش در درس فعلی
              </div>
              <ReportRow label="درس مبدأ" value={report.sectionRoleChange.sourceCourse} />
              <ReportRow label="حذف از" value={report.sectionRoleChange.removedFrom} />
              <ReportRow label="افزودن به" value={report.sectionRoleChange.addedTo} />
              <ReportRow label="پیامک مصوب" value={report.sectionRoleChange.smsSent ? 'ارسال شد' : '—'} />
            </div>

            <div
              style={{
                padding: '0.85rem 1rem',
                borderRadius: '10px',
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: '0.5rem', color: '#0f172a' }}>
                ۲) Sequence Unlocked
              </div>
              <ReportRow label="رسته" value={report.sectionUnlock.track} />
              <ReportRow label="درس جدید" value={report.sectionUnlock.nextCourse} />
              <ReportRow
                label="افزودن به لیست کمک‌مدرسین درس بعدی"
                value={report.sectionUnlock.addedToNextTaList ? 'بله' : 'خیر'}
              />
            </div>

            {resolved.unlockedCourses.length > 0 && (
              <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.75rem', marginBottom: 0 }}>
                دروس بازشده در LMS:
                {' '}
                {resolved.unlockedCourses.join('، ')}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
