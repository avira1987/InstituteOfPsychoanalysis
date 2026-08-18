import React, { useState } from 'react'
import { labelProcess } from '../utils/processDisplay'
import {
  canShowProcessRestart,
  restartReasonRequired,
} from '../utils/processRestartUtils'

/**
 * شروع دوباره از ابتدا — مدیر/معاون (override) یا دانشجو برای پروندهٔ خود.
 */
export default function ProcessRestartSection({
  user,
  instanceDetail,
  onRestart,
  onRestartComplete,
  busy,
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [acknowledged, setAcknowledged] = useState(false)

  if (!canShowProcessRestart(instanceDetail, user)) return null

  const reasonRequired = restartReasonRequired(user)
  const processLabel = labelProcess(instanceDetail.process_code)
  const canSubmit = acknowledged && (!reasonRequired || reason.trim().length >= 3)

  const resetModal = () => {
    setOpen(false)
    setReason('')
    setAcknowledged(false)
  }

  const handleConfirm = async () => {
    if (!canSubmit || busy) return
    const ok = await onRestart(reason.trim() || undefined)
    if (ok !== false) {
      resetModal()
      onRestartComplete?.()
    }
  }

  return (
    <>
      <div
        style={{
          marginBottom: '1.25rem',
          padding: '1rem 1.25rem',
          borderRadius: '10px',
          border: '1px solid rgba(239, 68, 68, 0.35)',
          background: 'linear-gradient(135deg, rgba(254, 242, 242, 0.95) 0%, #fff 100%)',
        }}
      >
        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.5rem', color: '#b91c1c' }}>
          شروع دوباره از ابتدا
        </h4>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', lineHeight: 1.65 }}>
          اگر می‌خواهید این فرایند را از مرحلهٔ اول و با پروندهٔ تازه شروع کنید، از این گزینه استفاده کنید.
          تمام اطلاعات ثبت‌شده در پروندهٔ فعلی بایگانی می‌شود.
          برای پرسنل فقط مدیر سامانه و معاون آموزش مجازند؛ تکمیل عادی هر مرحله همچنان فقط با نقش مسئول همان مرحله است.
        </p>
        <button
          type="button"
          className="btn btn-outline"
          style={{ borderColor: '#dc2626', color: '#b91c1c' }}
          disabled={busy}
          onClick={() => setOpen(true)}
          data-testid="process-restart-open"
        >
          شروع دوباره از ابتدا
        </button>
      </div>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="process-restart-title"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1200,
            background: 'rgba(15, 23, 42, 0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !busy) resetModal()
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '28rem',
              background: '#fff',
              borderRadius: '12px',
              padding: '1.25rem 1.5rem',
              boxShadow: '0 20px 40px rgba(0,0,0,0.15)',
            }}
            dir="rtl"
          >
            <h3 id="process-restart-title" style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem' }}>
              تأیید شروع دوباره
            </h3>
            <p style={{ fontSize: '0.88rem', lineHeight: 1.7, color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
              فرایند «{processLabel}» از مرحلهٔ اول باز می‌شود. پروندهٔ فعلی بایگانی می‌شود و دیگر قابل ادامه نیست.
            </p>
            <div
              style={{
                marginBottom: '1rem',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                fontSize: '0.82rem',
                lineHeight: 1.65,
                color: '#991b1b',
              }}
            >
              پرداخت‌ها، جلسات درمان و سوابق ثبت‌شده در بخش‌های دیگر سامانه خودکار پاک نمی‌شوند.
            </div>
            <textarea
              className="form-input"
              rows={3}
              placeholder={
                reasonRequired
                  ? 'دلیل شروع دوباره (الزامی — حداقل ۳ کاراکتر)'
                  : 'دلیل شروع دوباره (اختیاری — در پرونده ثبت می‌شود)'
              }
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              style={{ width: '100%', marginBottom: '0.75rem', fontSize: '0.9rem' }}
              dir="rtl"
            />
            <label
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.5rem',
                fontSize: '0.85rem',
                lineHeight: 1.6,
                marginBottom: '1rem',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
                style={{ marginTop: '0.25rem' }}
              />
              <span>متوجه شدم که پروندهٔ فعلی بایگانی می‌شود و نمی‌توانم به همان پرونده برگردم.</span>
            </label>
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn btn-outline"
                disabled={busy}
                onClick={resetModal}
              >
                انصراف
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ background: '#dc2626', borderColor: '#dc2626' }}
                disabled={!canSubmit || busy}
                onClick={handleConfirm}
                data-testid="process-restart-confirm"
              >
                {busy ? 'در حال ثبت…' : 'بله، از اول شروع کن'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
