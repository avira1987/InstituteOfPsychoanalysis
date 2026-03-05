import React, { useState, useRef, useEffect } from 'react'
import { useNavigate, Navigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { authApi } from '../services/api'

export default function LoginPage() {
  const navigate = useNavigate()
  const { user, login, loginWithToken } = useAuth()
  const [tab, setTab] = useState('otp') // 'otp' | 'password'
  const [phone, setPhone] = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [otpCode, setOtpCode] = useState(['', '', '', '', '', ''])
  const [timer, setTimer] = useState(0)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [securityAnswer, setSecurityAnswer] = useState('')
  const [challengeQuestion, setChallengeQuestion] = useState('')
  const [challengeAnswer, setChallengeAnswer] = useState('')
  const [challengeId, setChallengeId] = useState('')
  const [challengeLoading, setChallengeLoading] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [devCode, setDevCode] = useState('')
  const otpRefs = useRef([])

  if (user) return <Navigate to="/panel" replace />

  useEffect(() => {
    if (timer <= 0) return
    const interval = setInterval(() => setTimer(t => t - 1), 1000)
    return () => clearInterval(interval)
  }, [timer])

  const handleRequestOTP = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setDevCode('')
    try {
      const res = await authApi.otpRequest(phone)
      setOtpSent(true)
      setTimer(120)
      if (res.data?.dev_code) {
        setDevCode(res.data.dev_code)
      }
      setTimeout(() => otpRefs.current[0]?.focus(), 100)
    } catch (err) {
      setError(err.response?.data?.detail || 'خطا در ارسال کد. لطفاً دوباره تلاش کنید.')
    } finally {
      setLoading(false)
    }
  }

  const fetchLoginChallenge = async () => {
    setChallengeLoading(true)
    try {
      const res = await authApi.getLoginChallenge()
      setChallengeQuestion(res.data?.question || '')
      setChallengeId(res.data?.challenge_id || '')
      setChallengeAnswer('')
    } catch (err) {
      setChallengeQuestion('')
      setChallengeId('')
      setError(err.response?.data?.detail || 'خطا در دریافت کد امنیتی. لطفاً صفحه را مجدداً بارگذاری کنید.')
    } finally {
      setChallengeLoading(false)
    }
  }

  const handleOtpChange = (index, value) => {
    if (value.length > 1) value = value.slice(-1)
    if (value && !/^\d$/.test(value)) return

    const newCode = [...otpCode]
    newCode[index] = value
    setOtpCode(newCode)

    if (value && index < 5) {
      otpRefs.current[index + 1]?.focus()
    }

    if (newCode.every(c => c !== '')) {
      submitOTP(newCode.join(''))
    }
  }

  const handleOtpKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !otpCode[index] && index > 0) {
      otpRefs.current[index - 1]?.focus()
    }
  }

  const handleOtpPaste = (e) => {
    const paste = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    if (paste.length === 6) {
      const newCode = paste.split('')
      setOtpCode(newCode)
      otpRefs.current[5]?.focus()
      submitOTP(paste)
      e.preventDefault()
    }
  }

  const submitOTP = async (code) => {
    setLoading(true)
    setError('')
    try {
      const res = await authApi.otpVerify(phone, code)
      if (res.data.access_token) {
        loginWithToken(res.data.access_token)
        navigate('/panel')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'کد وارد شده صحیح نیست.')
      setOtpCode(['', '', '', '', '', ''])
      otpRefs.current[0]?.focus()
    } finally {
      setLoading(false)
    }
  }

  const handlePasswordLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(username, password, securityAnswer || undefined, challengeId, challengeAnswer)
      navigate('/panel')
    } catch (err) {
      const detail = err.response?.data?.detail
      const status = err.response?.status
      if (status === 401) {
        setError('نام کاربری یا رمز عبور اشتباه است')
      } else if (!err.response) {
        setError('خطا در اتصال به سرور')
      } else {
        setError(detail || 'خطا در ورود')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleResend = () => {
    setOtpCode(['', '', '', '', '', ''])
    setOtpSent(false)
    setDevCode('')
    setError('')
  }

  return (
    <div className="login-page">
      <div className="login-card" style={{ maxWidth: '420px' }}>
        <h2 className="login-title">انیستیتو روانکاوی تهران</h2>
        <p className="login-subtitle">Tehran Institute of Psychoanalysis</p>

        {/* Tab Switch */}
        <div className="otp-tabs">
          <button
            className={`otp-tab ${tab === 'otp' ? 'active' : ''}`}
            onClick={() => { setTab('otp'); setError('') }}
          >
            ورود با پیامک
          </button>
          <button
            className={`otp-tab ${tab === 'password' ? 'active' : ''}`}
            onClick={() => { setTab('password'); setError(''); fetchLoginChallenge() }}
          >
            ورود با رمز عبور
          </button>
        </div>

        {/* OTP Tab */}
        {tab === 'otp' && (
          <>
            {!otpSent ? (
              <form onSubmit={handleRequestOTP}>
                <div className="form-group">
                  <label className="form-label">شماره موبایل</label>
                  <input
                    className="form-input"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="09123456789"
                    required
                    autoFocus
                    style={{ direction: 'ltr', textAlign: 'center', fontSize: '1.1rem', letterSpacing: '2px' }}
                  />
                </div>
                {error && <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>{error}</div>}
                <button
                  className="btn btn-primary"
                  type="submit"
                  disabled={loading}
                  style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }}
                >
                  {loading ? 'در حال ارسال...' : 'ارسال کد تأیید'}
                </button>
              </form>
            ) : (
              <div>
                <p style={{ textAlign: 'center', fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                  کد ارسال شده به <strong style={{ direction: 'ltr', display: 'inline-block' }}>{phone}</strong> را وارد کنید
                </p>
                {devCode && (
                  <div className="alert" style={{ background: 'var(--bg-card)', border: '1px dashed var(--border)', marginBottom: '1rem', padding: '0.75rem', textAlign: 'center', fontSize: '1.1rem', letterSpacing: '4px', direction: 'ltr' }}>
                    کد تست: <strong>{devCode}</strong>
                  </div>
                )}
                <div className="otp-input-group" onPaste={handleOtpPaste}>
                  {otpCode.map((digit, i) => (
                    <input
                      key={i}
                      ref={el => otpRefs.current[i] = el}
                      type="text"
                      inputMode="numeric"
                      maxLength={1}
                      value={digit}
                      onChange={(e) => handleOtpChange(i, e.target.value)}
                      onKeyDown={(e) => handleOtpKeyDown(i, e)}
                      autoFocus={i === 0}
                    />
                  ))}
                </div>

                {error && <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>{error}</div>}

                {loading && (
                  <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                    <div className="loading-spinner" style={{ margin: '0 auto', width: 28, height: 28 }} />
                  </div>
                )}

                <div className="otp-timer">
                  {timer > 0 ? (
                    <span>ارسال مجدد تا <strong>{Math.floor(timer / 60)}:{String(timer % 60).padStart(2, '0')}</strong></span>
                  ) : (
                    <button className="otp-resend" onClick={handleResend}>
                      ارسال مجدد کد
                    </button>
                  )}
                </div>

                <button
                  onClick={handleResend}
                  style={{
                    display: 'block', margin: '1rem auto 0', background: 'none', border: 'none',
                    color: 'var(--text-light)', fontSize: '0.82rem', cursor: 'pointer'
                  }}
                >
                  تغییر شماره موبایل
                </button>
              </div>
            )}
          </>
        )}

        {/* Password Tab */}
        {tab === 'password' && (
          <form onSubmit={handlePasswordLogin}>
            <div className="form-group">
              <label className="form-label">نام کاربری</label>
              <input
                className="form-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="نام کاربری خود را وارد کنید"
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label className="form-label">رمز عبور</label>
              <input
                className="form-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="رمز عبور خود را وارد کنید"
                required
              />
            </div>
            {challengeLoading && (
              <div
                style={{
                  fontSize: '0.8rem',
                  color: 'var(--text-light)',
                  marginBottom: '0.5rem',
                }}
              >
                در حال آماده‌سازی کد امنیتی...
              </div>
            )}
            {!challengeLoading && challengeQuestion && (
              <div className="form-group">
                <label className="form-label">کد امنیتی</label>
                <div
                  style={{
                    padding: '0.6rem 0.75rem',
                    borderRadius: '0.5rem',
                    background: 'var(--bg-muted)',
                    fontSize: '0.85rem',
                    marginBottom: '0.5rem',
                  }}
                >
                  {challengeQuestion}
                </div>
                <input
                  className="form-input"
                  type="text"
                  value={challengeAnswer}
                  onChange={(e) => setChallengeAnswer(e.target.value)}
                  placeholder="پاسخ کد امنیتی را وارد کنید"
                  required
                />
              </div>
            )}
            <div className="form-group">
              <label className="form-label">پاسخ سوال امنیتی</label>
              <input
                className="form-input"
                type="password"
                value={securityAnswer}
                onChange={(e) => setSecurityAnswer(e.target.value)}
                placeholder="در صورت تنظیم سوال امنیتی، پاسخ را وارد کنید"
                autoComplete="off"
              />
            </div>
            {error && <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>{error}</div>}
            <button
              className="btn btn-primary"
              type="submit"
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }}
            >
              {loading ? 'در حال ورود...' : 'ورود'}
            </button>
          </form>
        )}

        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <Link to="/register" style={{ fontSize: '0.85rem', color: 'var(--primary)', fontWeight: 500 }}>
            هنوز ثبت‌نام نکرده‌اید؟ ثبت‌نام دانشجو
          </Link>
        </div>

        <div style={{ textAlign: 'center', marginTop: '1rem' }}>
          <Link to="/" style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>
            ← بازگشت به صفحه اصلی
          </Link>
        </div>
      </div>
    </div>
  )
}
