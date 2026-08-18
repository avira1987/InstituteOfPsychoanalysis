import React, { useState } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  canShowProcessRollback,
  previousStateFromHistory,
  rollbackReasonRequired,
} from '../utils/processRollbackUtils'

/**
 * بازگشت دستی به مرحلهٔ قبل — فقط مدیر سامانه / معاون آموزش (اصلاح اشتباه SOP).
 */
export default function ProcessRollbackSection({ user, instanceDetail, onRollback, busy }) {
  const [reason, setReason] = useState('')

  if (!canShowProcessRollback(instanceDetail, user)) return null

  const prev = previousStateFromHistory(instanceDetail)
  const reasonNeeded = rollbackReasonRequired(user)
  const canSubmit = !reasonNeeded || reason.trim().length >= 3

  return (
    <div
      style={{
        marginBottom: '1.25rem',
        padding: '1rem 1.25rem',
        borderRadius: '10px',
        border: '1px solid rgba(234, 179, 8, 0.45)',
        background: 'linear-gradient(135deg, rgba(254, 252, 232, 0.95) 0%, #fff 100%)',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.5rem', color: '#92400e' }}>
        بازگشت به مرحلهٔ قبل
      </h4>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', lineHeight: 1.65 }}>
        اگر آخرین اقدام یا دکمهٔ تصمیم به‌اشتباه زده شده، مدیر سامانه یا معاون آموزش می‌توانند
        فرایند را به وضعیت قبلی برگردانند. این کار خلاف دست‌به‌دست عادی SOP است و در پرونده ثبت می‌شود.
        {' '}
        <strong>مرحلهٔ هدف:</strong> {labelState(prev)}
      </p>
      <textarea
        className="form-input"
        rows={2}
        placeholder={reasonNeeded ? 'دلیل بازگشت (الزامی — در پرونده و لاگ ثبت می‌شود)' : 'دلیل بازگشت (اختیاری)'}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        style={{ width: '100%', marginBottom: '0.75rem', fontSize: '0.9rem' }}
        dir="rtl"
      />
      <button
        type="button"
        className="btn btn-outline"
        style={{ borderColor: '#d97706', color: '#b45309' }}
        disabled={busy || !canSubmit}
        onClick={() => onRollback(reason.trim() || undefined)}
      >
        {busy ? 'در حال ثبت…' : 'بازگشت به مرحلهٔ قبل'}
      </button>
    </div>
  )
}
