import React, { useMemo, useState } from 'react'
import { processExecApi } from '../services/api'
import { labelState } from '../utils/processDisplay'
import {
  computeSlaRemaining,
  RESTART_SMS_TEXT_FA,
  SlaBanner,
} from '../utils/earlyTerminationChainDisplay'

/**
 * راهنمای دانشجو در مرحله awaiting_student_restart فرایند committees_review.
 */
export default function StudentCommitteesRestartPanel({
  detail = null,
  studentId = null,
  active = true,
  showToast,
  onAfterStart,
}) {
  const [busy, setBusy] = useState(false)
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const slaInfo = useMemo(
    () => (currentState === 'awaiting_student_restart' ? computeSlaRemaining(ctx, 5) : null),
    [currentState, ctx],
  )

  if (
    !active
    || !detail
    || !['committees_review', 'specialized_commission_review'].includes(detail.process_code)
    || currentState !== 'awaiting_student_restart'
  ) {
    return null
  }

  const parentProcessCode = detail.process_code

  const startTherapyChanges = async () => {
    if (!studentId || busy) return
    setBusy(true)
    try {
      const res = await processExecApi.start({
        process_code: 'therapy_changes',
        student_id: studentId,
        initial_context: {
          parent_instance_id: detail.instance_id || detail.id,
          parent_process_code: parentProcessCode,
          trigger_reason: parentProcessCode === 'committees_review'
            ? 'committees_approved_restart'
            : 'commission_approved_restart',
        },
      })
      if (res.data?.instance_id || res.data?.id) {
        showToast?.('فرایند آغاز دوباره درمان آغاز شد')
        onAfterStart?.(res.data)
      } else {
        showToast?.('فرایند آغاز شد', 'success')
        onAfterStart?.()
      }
    } catch (e) {
      showToast?.(e.response?.data?.detail || 'خطا در آغاز فرایند', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="card"
      style={{ marginBottom: '1.25rem' }}
      data-testid="student-committees-restart-panel"
    >
      <div className="card-header">
        <h3 className="card-title">آغاز دوباره درمان آموزشی</h3>
        <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
          {labelState(currentState)}
        </span>
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        <SlaBanner
          slaInfo={slaInfo}
          title="مهلت ۵ روزه"
          fallbackText="ظرف ۵ روز باید درمانگر آموزشی جدید انتخاب کنید."
        />

        <div
          data-testid="student-committees-sms-text"
          style={{
            marginBottom: '1rem',
            padding: '0.85rem 1rem',
            borderRadius: '10px',
            background: '#eff6ff',
            borderRight: '4px solid #2563eb',
            fontSize: '0.86rem',
            lineHeight: 1.8,
          }}
        >
          {RESTART_SMS_TEXT_FA}
        </div>

        <button
          type="button"
          className="btn btn-primary"
          data-testid="student-start-therapy-changes"
          disabled={busy || slaInfo?.expired}
          onClick={startTherapyChanges}
        >
          {busy ? 'در حال آغاز…' : 'آغاز فرایند تغییر/آغاز دوباره درمان'}
        </button>

        {slaInfo?.expired && (
          <p style={{ marginTop: '0.75rem', fontSize: '0.82rem', color: '#991b1b' }}>
            مهلت به پایان رسیده است. فرایند ثبت تخلف ممکن است آغاز شود.
          </p>
        )}
      </div>
    </div>
  )
}
