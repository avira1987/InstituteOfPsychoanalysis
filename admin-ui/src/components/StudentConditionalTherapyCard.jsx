import React, { useState } from 'react'
import { studentApi } from '../services/api'
import { CONDITIONAL_THERAPY_TERM2_NOTICE_FA } from '../utils/studentProcessAccess'

/**
 * کارت داشبورد برای دانشجوی پذیرش مشروط — ensure/ادامهٔ فرایند آغاز درمان آموزشی.
 */
export default function StudentConditionalTherapyCard({
  studentProfile = null,
  onOpened = null,
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const required = studentProfile?.conditional_therapy_required === true
  if (!required) return null

  const hint =
    studentProfile?.therapy_deadline_hint_fa
    || CONDITIONAL_THERAPY_TERM2_NOTICE_FA

  const hasActiveTherapyPrimary =
    studentProfile?.extra_data?.primary_instance_id
    && !studentProfile?.therapy_started

  const ctaLabel = hasActiveTherapyPrimary
    ? 'ادامه آغاز درمان آموزشی'
    : 'آغاز درمان آموزشی'

  const handleClick = async () => {
    setBusy(true)
    setError(null)
    try {
      const res = await studentApi.ensureConditionalTherapyStart()
      const data = res?.data || {}
      if (onOpened) {
        await onOpened({
          instanceId: data.instance_id,
          currentState: data.current_state,
          alreadyExisted: data.already_existed,
        })
      }
    } catch (e) {
      const msg =
        e?.response?.data?.detail
        || e?.message
        || 'شروع فرایند آغاز درمان ممکن نشد.'
      setError(typeof msg === 'string' ? msg : 'شروع فرایند آغاز درمان ممکن نشد.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="card student-portal-alert-card student-portal-alert-card--info"
      role="region"
      aria-label="پذیرش مشروط به درمان آموزشی"
      data-testid="student-conditional-therapy-card"
      style={{
        marginBottom: '1.25rem',
        border: '1px solid rgba(217, 119, 6, 0.45)',
        background: 'linear-gradient(135deg, rgba(255, 251, 235, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%)',
      }}
    >
      <strong
        className="student-portal-alert-card-title"
        style={{ color: '#92400e' }}
        data-testid="student-conditional-therapy-card-title"
      >
        پذیرش مشروط به آغاز درمان آموزشی
      </strong>
      <p className="student-portal-alert-card-p" data-testid="student-conditional-therapy-card-hint">
        {hint}
      </p>
      {error ? (
        <p
          className="student-portal-alert-card-p"
          data-testid="student-conditional-therapy-card-error"
          style={{ color: '#b91c1c', marginTop: '0.35rem' }}
        >
          {error}
        </p>
      ) : null}
      <button
        type="button"
        className="btn btn-primary"
        data-testid="student-conditional-therapy-card-cta"
        disabled={busy}
        onClick={handleClick}
        style={{ marginTop: '0.65rem' }}
      >
        {busy ? 'در حال آماده‌سازی…' : ctaLabel}
      </button>
    </div>
  )
}
