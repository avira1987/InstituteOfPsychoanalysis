import React, { useEffect, useState } from 'react'
import { processExecApi } from '../services/api'

/** هم‌خوان با STEP_OTP_EXPIRY_SECONDS در بک‌اند؛ منبع اصلی `expires_in` پاسخ API است. */
export const STEP_OTP_TTL_SECONDS = 180

const inflightRequests = new Map()
const autoSentInstanceIds = new Set()

function deadlineStorageKey(instanceId) {
  return `anistito:step-otp-deadline:${instanceId}`
}

function readDeadlineMs(instanceId) {
  if (!instanceId) return 0
  try {
    const n = Number(sessionStorage.getItem(deadlineStorageKey(instanceId)))
    return Number.isFinite(n) ? n : 0
  } catch {
    return 0
  }
}

function writeDeadlineMs(instanceId, ms) {
  if (!instanceId) return
  try {
    sessionStorage.setItem(deadlineStorageKey(instanceId), String(ms))
  } catch {
    /* ignore quota / private mode */
  }
}

function clearDeadline(instanceId) {
  if (!instanceId) return
  try {
    sessionStorage.removeItem(deadlineStorageKey(instanceId))
  } catch {
    /* ignore */
  }
}

function remainingFromDeadline(deadlineMs) {
  if (!deadlineMs) return 0
  return Math.max(0, Math.ceil((deadlineMs - Date.now()) / 1000))
}

function formatMmSs(total) {
  const safe = Math.max(0, Number(total) || 0)
  const m = Math.floor(safe / 60)
  const s = safe % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function requestStepOtpOnce(instanceId) {
  if (!instanceId) return Promise.reject(new Error('missing instance'))
  if (inflightRequests.has(instanceId)) return inflightRequests.get(instanceId)
  const pending = processExecApi
    .requestStudentStepOtp(instanceId)
    .finally(() => inflightRequests.delete(instanceId))
  inflightRequests.set(instanceId, pending)
  return pending
}

/**
 * فیلد OTP مرحلهٔ فرایند — درخواست و تأیید کد پیامکی.
 * پس از ارسال، تا ۳ دقیقه برای وارد کردن کد منتظر می‌ماند (اعتبار کد همان ۳ دقیقه است).
 */
export default function StepOtpField({
  instanceId,
  value,
  onChange,
  disabled,
  labelFa = 'کد تأیید پیامکی',
  required = false,
  onVerifiedChange = null,
  verified = false,
  autoRequest = false,
}) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [secondsLeft, setSecondsLeft] = useState(() => remainingFromDeadline(readDeadlineMs(instanceId)))
  const [sentOnce, setSentOnce] = useState(() => remainingFromDeadline(readDeadlineMs(instanceId)) > 0)

  const setVerified = (v) => {
    if (typeof onVerifiedChange === 'function') onVerifiedChange(v)
  }

  const applySuccessfulSend = (expiresIn) => {
    const ttl = Number(expiresIn) > 0 ? Math.round(Number(expiresIn)) : STEP_OTP_TTL_SECONDS
    writeDeadlineMs(instanceId, Date.now() + ttl * 1000)
    setSecondsLeft(ttl)
    setSentOnce(true)
    setMsg('کد پیامکی ارسال شد. تا ۳ دقیقه فرصت دارید آن را وارد کنید.')
    setVerified(false)
    if (instanceId) autoSentInstanceIds.add(instanceId)
  }

  useEffect(() => {
    const left = remainingFromDeadline(readDeadlineMs(instanceId))
    setSecondsLeft(left)
    if (left > 0) setSentOnce(true)
  }, [instanceId])

  useEffect(() => {
    if (secondsLeft <= 0) return undefined
    const interval = setInterval(() => {
      const left = remainingFromDeadline(readDeadlineMs(instanceId))
      setSecondsLeft(left)
      if (left <= 0) clearDeadline(instanceId)
    }, 1000)
    return () => clearInterval(interval)
  }, [secondsLeft > 0, instanceId])

  const handleRequest = async () => {
    if (!instanceId) {
      setErr('شناسه پرونده یافت نشد.')
      return
    }
    if (secondsLeft > 0) return
    setBusy(true)
    setErr('')
    setMsg('')
    try {
      const res = await requestStepOtpOnce(instanceId)
      if (res.data?.already_verified) {
        setVerified(true)
        setMsg('تأیید پیامکی قبلاً انجام شده است.')
        return
      }
      if (res.data?.success === false) {
        setErr(res.data?.error || 'ارسال کد ناموفق بود.')
      } else {
        applySuccessfulSend(res.data?.expires_in)
      }
    } catch (e) {
      setErr(e.response?.data?.detail || 'خطا در ارسال کد')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!autoRequest) {
      if (instanceId) autoSentInstanceIds.delete(instanceId)
      return undefined
    }
    if (!instanceId || verified || disabled) return undefined
    const left = remainingFromDeadline(readDeadlineMs(instanceId))
    if (left > 0) {
      setSecondsLeft(left)
      setSentOnce(true)
      autoSentInstanceIds.add(instanceId)
      return undefined
    }
    if (autoSentInstanceIds.has(instanceId) && !inflightRequests.has(instanceId)) return undefined
    let cancelled = false
    ;(async () => {
      setBusy(true)
      setErr('')
      try {
        const res = await requestStepOtpOnce(instanceId)
        if (cancelled) return
        if (res.data?.already_verified) {
          setVerified(true)
          setMsg('تأیید پیامکی قبلاً انجام شده است.')
          return
        }
        if (res.data?.success === false) {
          setErr(res.data?.error || 'ارسال کد ناموفق بود.')
          return
        }
        applySuccessfulSend(res.data?.expires_in)
      } catch (e) {
        if (cancelled) return
        setErr(e.response?.data?.detail || 'خطا در ارسال کد')
      } finally {
        if (!cancelled) setBusy(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [autoRequest, instanceId, verified, disabled])

  const handleVerify = async () => {
    const code = String(value || '').trim()
    if (!code) {
      setErr('کد را وارد کنید.')
      return
    }
    if (!instanceId) {
      setErr('شناسه پرونده یافت نشد.')
      return
    }
    if (secondsLeft <= 0) {
      setErr('اعتبار کد به پایان رسید. لطفاً دوباره ارسال کنید.')
      return
    }
    setBusy(true)
    setErr('')
    try {
      const res = await processExecApi.verifyStudentStepOtp(instanceId, { code })
      if (res.data?.success) {
        setMsg('کد تأیید شد.')
        clearDeadline(instanceId)
        setSecondsLeft(0)
        setVerified(true)
      } else {
        setErr('کد نامعتبر است.')
        setVerified(false)
      }
    } catch (e) {
      setErr(e.response?.data?.detail || 'کد نامعتبر است')
      setVerified(false)
    } finally {
      setBusy(false)
    }
  }

  const waiting = secondsLeft > 0 && !verified
  const timedOut = sentOnce && !verified && secondsLeft <= 0
  const sendLabel = waiting ? 'ارسال شده' : (sentOnce ? 'ارسال مجدد' : 'ارسال کد')

  return (
    <div className="psf-field" data-testid="step-otp-field">
      <span className="psf-label">
        {labelFa}
        {required ? ' *' : ''}
      </span>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', marginTop: '0.35rem' }}>
        <input
          type="text"
          inputMode="numeric"
          data-testid="step-otp-input"
          className="psf-input form-input"
          dir="ltr"
          style={{ maxWidth: '140px' }}
          value={value ?? ''}
          disabled={disabled || busy || verified}
          onChange={(e) => {
            onChange(e.target.value)
            setVerified(false)
          }}
          placeholder="کد ۶ رقمی"
        />
        <button
          type="button"
          className="btn btn-sm btn-outline"
          data-testid="step-otp-send"
          disabled={disabled || busy || verified || waiting}
          onClick={handleRequest}
        >
          {sendLabel}
        </button>
        <button
          type="button"
          className="btn btn-sm btn-primary"
          data-testid="step-otp-verify"
          disabled={disabled || busy || verified || !waiting}
          onClick={handleVerify}
        >
          تأیید کد
        </button>
      </div>
      {waiting && (
        <p className="psf-hint" data-testid="step-otp-timer" style={{ margin: '0.35rem 0 0' }}>
          تا <strong>{formatMmSs(secondsLeft)}</strong> برای وارد کردن کد فرصت دارید (اعتبار ۳ دقیقه).
        </p>
      )}
      {verified && (
        <p className="psf-hint" style={{ color: '#16a34a', margin: '0.35rem 0 0' }}>کد تأیید شده است.</p>
      )}
      {timedOut && (
        <p className="psf-hint psf-hint--warn" data-testid="step-otp-expired" style={{ margin: '0.35rem 0 0' }}>
          اعتبار کد به پایان رسید. برای دریافت کد جدید، «ارسال مجدد» را بزنید.
        </p>
      )}
      {msg && !err && !waiting && !timedOut && (
        <p className="psf-hint" style={{ margin: '0.35rem 0 0' }}>{msg}</p>
      )}
      {err && (
        <p className="psf-hint psf-hint--warn" style={{ margin: '0.35rem 0 0' }}>{err}</p>
      )}
    </div>
  )
}
