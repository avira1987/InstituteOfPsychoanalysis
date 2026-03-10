import React, { useState, useRef, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { authApi } from '../services/api'

const LOGIN_TAB_KEY = 'login_tab'
const LOGIN_ERROR_KEY = 'login_error'
const LOGIN_ERROR_FROM_PASSWORD_KEY = 'login_error_from_password'

function getInitialTab() {
  try {
    const saved = sessionStorage.getItem(LOGIN_TAB_KEY)
    if (saved === 'otp' || saved === 'password') return saved
  } catch (_) {}
  return 'otp'
}

function getInitialError() {
  try {
    return sessionStorage.getItem(LOGIN_ERROR_KEY) || ''
  } catch (_) {}
  return ''
}

export default function LoginPage() {
  const navigate = useNavigate()
  const { user, login, loginWithToken } = useAuth()
  const [tab, setTab] = useState(getInitialTab)
  const [phone, setPhone] = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [otpCode, setOtpCode] = useState(['', '', '', '', '', ''])
  const [timer, setTimer] = useState(0)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [challengeQuestion, setChallengeQuestion] = useState('')
  const [challengeAnswer, setChallengeAnswer] = useState('')
  const [challengeId, setChallengeId] = useState('')
  const [challengeLoading, setChallengeLoading] = useState(false)
  const [error, setError] = useState(getInitialError)
  const [loading, setLoading] = useState(false)
  const [devCode, setDevCode] = useState('')
  const otpRefs = useRef([])

  useEffect(() => {
    if (timer <= 0) return
    const interval = setInterval(() => setTimer(t => t - 1), 1000)
    return () => clearInterval(interval)
  }, [timer])

  // وقتی تب ورود با رمز عبور از sessionStorage بازیابی شده، چالش را بگیر
  useEffect(() => {
    if (tab === 'password' && !challengeQuestion && !challengeLoading) {
      fetchLoginChallenge()
    }
  }, [tab])

  // اگر خطا از فرم ورود با رمز عبور بود و تب به پیامک رفته، همیشه تب را به ورود با رمز عبور برگردان
  useEffect(() => {
    try {
      if (sessionStorage.getItem(LOGIN_ERROR_FROM_PASSWORD_KEY) && tab === 'otp') {
        setTab('password')
        sessionStorage.setItem(LOGIN_TAB_KEY, 'password')
      }
    } catch (_) {}
  }, [tab, error])

  // ریدایرکت به پنل بعد از ورود؛ دانشجو مستقیم به پنل دانشجو، بقیه به داشبرد
  useEffect(() => {
    if (!user) return
    const target = user.role === 'student' ? '/panel/portal/student' : '/panel'
    navigate(target, { replace: true })
  }, [user, navigate])

  if (user) {
    return (
      <div className="login-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <div className="loading-spinner" style={{ width: 40, height: 40 }} />
        <span style={{ marginRight: '0.75rem' }}>در حال انتقال به پنل...</span>
      </div>
    )
  }

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

  const fetchLoginChallenge = async (keepExistingError = false) => {
    setChallengeLoading(true)
    try {
      const res = await authApi.getLoginChallenge()
      setChallengeQuestion(res.data?.question || '')
      setChallengeId(res.data?.challenge_id || '')
      setChallengeAnswer('')
    } catch (err) {
      setChallengeQuestion('')
      setChallengeId('')
      if (!keepExistingError) {
        setError(err.response?.data?.detail || 'خطا در دریافت کد امنیتی. لطفاً صفحه را مجدداً بارگذاری کنید.')
      }
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
        await loginWithToken(res.data.access_token)
        // ریدایرکت در useEffect بر اساس user.role انجام می‌شود (دانشجو → پنل دانشجو)
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
    // قبل از هر درخواست تب را قفل کن تا در صورت ریلود همان تب و خطا نمایش داده شود
    setTab('password')
    try { sessionStorage.setItem(LOGIN_TAB_KEY, 'password') } catch (_) {}
    setLoading(true)
    setError('')
    try {
      sessionStorage.removeItem(LOGIN_ERROR_KEY)
      await login(username, password, challengeId, challengeAnswer)
      sessionStorage.removeItem(LOGIN_TAB_KEY)
      // ریدایرکت در useEffect بر اساس user.role انجام می‌شود (دانشجو → پنل دانشجو)
    } catch (err) {
      // حتماً روی تب ورود با رمز عبور بمان؛ هرگز به تب پیامک نرو
      setTab('password')
      const detail = err.response?.data?.detail
      const status = err.response?.status
      let errMsg = 'خطا در ورود'
      if (status === 401) {
        errMsg = 'نام کاربری یا رمز عبور اشتباه است'
      } else if (!err.response) {
        errMsg = 'خطا در اتصال به سرور'
      } else if (detail) {
        errMsg = typeof detail === 'string' ? detail : (detail.msg || detail.message || JSON.stringify(detail))
      }
      setError(errMsg)
      try {
        sessionStorage.setItem(LOGIN_TAB_KEY, 'password')
        sessionStorage.setItem(LOGIN_ERROR_KEY, errMsg)
        sessionStorage.setItem(LOGIN_ERROR_FROM_PASSWORD_KEY, '1')
      } catch (_) {}
      // هربار ورود ناموفق: حتماً چالش جدید بگیر و منتظر بمان تا در تلاش بعدی کد امنیتی معتبر باشد
      await fetchLoginChallenge(true)
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
            onClick={() => {
              setTab('otp')
              setError('')
              try {
                sessionStorage.setItem(LOGIN_TAB_KEY, 'otp')
                sessionStorage.removeItem(LOGIN_ERROR_KEY)
                sessionStorage.removeItem(LOGIN_ERROR_FROM_PASSWORD_KEY)
              } catch (_) {}
            }}
          >
            ورود با پیامک
          </button>
          <button
            className={`otp-tab ${tab === 'password' ? 'active' : ''}`}
            onClick={() => {
              setTab('password')
              setError('')
              try { sessionStorage.setItem(LOGIN_TAB_KEY, 'password') } catch (_) {}
              fetchLoginChallenge()
            }}
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
