import React, { useState } from 'react'
import { processExecApi } from '../services/api'

/**
 * فیلد OTP مرحلهٔ فرایند — درخواست و تأیید کد پیامکی.
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
}) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const setVerified = (v) => {
    if (typeof onVerifiedChange === 'function') onVerifiedChange(v)
  }

  const handleRequest = async () => {
    if (!instanceId) {
      setErr('شناسه پرونده یافت نشد.')
      return
    }
    setBusy(true)
    setErr('')
    setMsg('')
    try {
      const res = await processExecApi.requestStudentStepOtp(instanceId)
      if (res.data?.success === false) {
        setErr(res.data?.error || 'ارسال کد ناموفق بود.')
      } else {
        setMsg('کد پیامکی ارسال شد.')
        setVerified(false)
      }
    } catch (e) {
      setErr(e.response?.data?.detail || 'خطا در ارسال کد')
    } finally {
      setBusy(false)
    }
  }

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
    setBusy(true)
    setErr('')
    try {
      const res = await processExecApi.verifyStudentStepOtp(instanceId, { code })
      if (res.data?.success) {
        setMsg('کد تأیید شد.')
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
          className="psf-input form-input"
          dir="ltr"
          style={{ maxWidth: '140px' }}
          value={value ?? ''}
          disabled={disabled || busy}
          onChange={(e) => {
            onChange(e.target.value)
            setVerified(false)
          }}
          placeholder="کد ۶ رقمی"
        />
        <button type="button" className="btn btn-sm btn-outline" disabled={disabled || busy} onClick={handleRequest}>
          ارسال کد
        </button>
        <button type="button" className="btn btn-sm btn-primary" disabled={disabled || busy} onClick={handleVerify}>
          تأیید کد
        </button>
      </div>
      {verified && (
        <p className="psf-hint" style={{ color: '#16a34a', margin: '0.35rem 0 0' }}>کد تأیید شده است.</p>
      )}
      {msg && !err && (
        <p className="psf-hint" style={{ margin: '0.35rem 0 0' }}>{msg}</p>
      )}
      {err && (
        <p className="psf-hint psf-hint--warn" style={{ margin: '0.35rem 0 0' }}>{err}</p>
      )}
    </div>
  )
}
