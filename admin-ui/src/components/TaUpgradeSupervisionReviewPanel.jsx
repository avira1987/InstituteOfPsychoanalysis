import React from 'react'
import { formatStudentCodeDisplay } from '../utils/processDisplay'

/**
 * راهنمای کمیته نظارت — فرایند ۴۷ ارتقا به کمک‌مدرس.
 */
export default function TaUpgradeSupervisionReviewPanel({ detail = null, user = null }) {
  const currentState = detail?.current_state
  const ctx = detail?.context_data || {}

  if (
    !detail
    || detail.process_code !== 'upgrade_to_ta'
    || currentState !== 'supervision_review'
  ) {
    return null
  }

  const studentLabel = detail?.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : null

  return (
    <div
      data-testid="ta-supervision-review-panel"
      style={{
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
        background: '#fffbeb',
        borderRadius: '10px',
        borderRight: '4px solid #d97706',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#92400e' }}>
        بررسی صلاحیت ارتقا به کمک‌مدرس (فرایند ۴۷)
      </h4>

      <p style={{ fontSize: '0.85rem', lineHeight: 1.7, margin: '0 0 0.75rem', color: '#334155' }}>
        پروندهٔ متقاضی را بررسی کنید. فرم تصمیم را تکمیل کنید، سپس
        {' '}
        <code style={{ fontSize: '0.8rem' }}>approved</code>
        {' '}
        یا
        {' '}
        <code style={{ fontSize: '0.8rem' }}>rejected</code>
        {' '}
        را بزنید.
      </p>

      {ctx.ta_eligibility_summary_fa && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          خلاصه احراز خودکار:
          {' '}
          <strong>{ctx.ta_eligibility_summary_fa}</strong>
        </p>
      )}

      {studentLabel && (
        <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
          پروندهٔ دانشجو:
          {' '}
          <strong>{studentLabel}</strong>
        </p>
      )}

      {user?.role && user.role !== 'supervision_committee' && user.role !== 'admin' && (
        <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
          این مرحله معمولاً بر عهدهٔ کمیته نظارت است.
        </p>
      )}
    </div>
  )
}
