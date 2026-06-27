import React, { useState, useRef, useEffect } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { authApi } from '../services/api'
import { getSiteLogoUrl } from '../utils/siteLogo'
import { getPortalHomeHref } from '../utils/portalRoleHome'
import { toLatinDigits } from '../utils/persianDigits'

const LOGIN_TAB_KEY = 'login_tab'
const LOGIN_ERROR_KEY = 'login_error'
const LOGIN_ERROR_FROM_PASSWORD_KEY = 'login_error_from_password'
const OTP_STUDENT_ONBOARDING_KEY = 'otp_student_onboarding'

function getInitialTab(staffMode) {
  if (staffMode) return 'password'
  /* ورود عمومی همیشه پیامک؛ session تب «رمز» برای /login بدون staff اعمال نمی‌شود */
  try {
    const saved = sessionStorage.getItem(LOGIN_TAB_KEY)
    if (saved === 'otp') return 'otp'
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
  const [searchParams] = useSearchParams()
  const staffMode = searchParams.get('staff') === '1'
  const { user, login, loginWithToken } = useAuth()
  const [tab, setTab] = useState(() => getInitialTab(staffMode))
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
  const [otpWelcomeMessage, setOtpWelcomeMessage] = useState('')
  const [pendingOtpToken, setPendingOtpToken] = useState(null)
  const [pendingOtpUser, setPendingOtpUser] = useState(null)
  const otpRefs = useRef([])
  /** جلوگیری از دو درخواست verify هم‌زمان؛ نتیجهٔ دوم اغلب «کد منقضی» است چون اولین درخواست کد را مصرف می‌کند. */
  const otpVerifyLockRef = useRef(false)
  const otpSubmitInFlightRef = useRef(false)

  useEffect(() => {
    if (timer <= 0) return
    const interval = setInterval(() => setTimer(t => t - 1), 1000)
    return () => clearInterval(interval)
  }, [timer])

  useEffect(() => {
    if (staffMode) {
      setTab('password')
      try { sessionStorage.setItem(LOGIN_TAB_KEY, 'password') } catch (_) {}
    }
  }, [staffMode])

  // وقتی تب ورود با رمز عبور از sessionStorage بازیابی شده، چالش را بگیر
  useEffect(() => {
    if (tab === 'password' && !challengeQuestion && !challengeLoading) {
      fetchLoginChallenge()
    }
  }, [tab])

  useEffect(() => {
    if (!staffMode) return
    try {
      if (sessionStorage.getItem(LOGIN_ERROR_FROM_PASSWORD_KEY) && tab === 'otp') {
        setTab('password')
        sessionStorage.setItem(LOGIN_TAB_KEY, 'password')
      }
    } catch (_) {}
  }, [tab, error, staffMode])

  // ریدایرکت به پنل بعد از ورود؛ ترجیحاً بر اساس /api/auth/home (خانه نقش)،
  // و در صورت عدم دسترسی، به‌صورت پیش‌فرض بر اساس نقش کاربر.
  useEffect(() => {
    if (!user) return

    const doRedirect = async () => {
      try {
        if (sessionStorage.getItem(OTP_STUDENT_ONBOARDING_KEY) === '1') {
          sessionStorage.removeItem(OTP_STUDENT_ONBOARDING_KEY)
          navigate('/panel/complete-registration', { replace: true })
          return
        }
      } catch (_) {}

      try {
        const res = await authApi.home()
        const target = res.data?.redirect_url
          || getPortalHomeHref(user.role)
        navigate(target, { replace: true })
      } catch {
        navigate(getPortalHomeHref(user.role), { replace: true })
      }
    }

    doRedirect()
  }, [user, navigate])

  if (user) {
    return (
      <div className="login-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <div className="loading-spinner" style={{ width: 40, height: 40 }} />
        <span style={{ marginRight: '0.75rem' }}>در حال انتقال...</span>
      </div>
    )
  }

  const handleRequestOTP = async (e) => {
    e.preventDefault()
    if (otpSent) return
    setLoading(true)
    setError('')
    try {
      const res = await authApi.otpRequest(phone)
      setOtpSent(true)
      setTimer(120)
      setOtpCode(['', '', '', '', '', ''])
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

  const completeOtpLogin = async (token, userPayload) => {
    if (userPayload?.is_new && userPayload?.role === 'student') {
      try {
        sessionStorage.setItem(OTP_STUDENT_ONBOARDING_KEY, '1')
      } catch (_) {}
    }
    setOtpWelcomeMessage('')
    setPendingOtpToken(null)
    setPendingOtpUser(null)
    await loginWithToken(token)
  }

  const submitOTP = async (code) => {
    const digits = String(code || '').replace(/\D/g, '')
    if (digits.length !== 6) return
    if (otpVerifyLockRef.current || otpSubmitInFlightRef.current) return
    otpVerifyLockRef.current = true
    otpSubmitInFlightRef.current = true
    setLoading(true)
    setError('')
    let holdVerifyLock = false
    try {
      const res = await authApi.otpVerify(phone, digits)
      if (res.data.access_token) {
        const u = res.data.user
        const welcome = (res.data.welcome_message || '').trim()
        if (welcome) {
          holdVerifyLock = true
          setPendingOtpToken(res.data.access_token)
          setPendingOtpUser(u || null)
          setOtpWelcomeMessage(welcome)
          return
        }
        await completeOtpLogin(res.data.access_token, u)
      }
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(
        typeof detail === 'string' && detail.trim()
          ? detail
          : 'کد وارد شده صحیح نیست. اگر چند پیامک دارید فقط **آخرین** کد را وارد کنید.'
      )
      setOtpCode(['', '', '', '', '', ''])
      otpRefs.current[0]?.focus()
    } finally {
      setLoading(false)
      otpSubmitInFlightRef.current = false
      if (!holdVerifyLock) {
        otpVerifyLockRef.current = false
      }
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
      await login(
        toLatinDigits(username).trim(),
        toLatinDigits(password),
        challengeId,
        toLatinDigits(challengeAnswer).trim(),
      )
      sessionStorage.removeItem(LOGIN_TAB_KEY)
      // ریدایرکت بعد از ورود در useEffect بر اساس /api/auth/home انجام می‌شود.
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
    setError('')
    setOtpWelcomeMessage('')
    setPendingOtpToken(null)
    setPendingOtpUser(null)
    otpVerifyLockRef.current = false
    otpSubmitInFlightRef.current = false
  }

  return (
    <div className="login-page">
      <div className="login-card" style={{ maxWidth: '420px' }}>
        <div className="login-brand-logo-wrap">
          <img src={getSiteLogoUrl()} alt="" className="login-brand-logo site-logo-img" width={200} height={80} />
        </div>
        <h2 className="login-title">
          {staffMode ? 'ورود پرسنل و مدیران' : 'ورود و ثبت‌نام با موبایل'}
        </h2>
        <p className="login-subtitle">
          {staffMode
            ? 'Tehran Institute of Psychoanalysis — staff sign-in'
            : 'Tehran Institute of Psychoanalysis'}
        </p>

        {!staffMode && (
          <>
            <form onSubmit={handleRequestOTP}>
              <div className="form-group">
                <label className="form-label" htmlFor="login-otp-phone">شماره موبایل</label>
                <input
                  id="login-otp-phone"
                  data-testid="login-otp-phone"
                  className="form-input"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="09123456789"
                  required={!otpSent}
                  readOnly={otpSent}
                  disabled={otpSent}
                  autoFocus={!otpSent}
                  style={{
                    direction: 'ltr',
                    textAlign: 'center',
                    fontSize: '1.1rem',
                    letterSpacing: '2px',
                    ...(otpSent ? { opacity: 0.92, cursor: 'default' } : {}),
                  }}
                />
              </div>
              {!otpSent && (
                <>
                  {error && <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>{error}</div>}
                  <button
                    className="btn btn-primary"
                    type="submit"
                    disabled={loading}
                    style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }}
                  >
                    {loading ? 'در حال ارسال...' : 'ارسال کد پیامکی'}
                  </button>
                </>
              )}
            </form>

            {otpSent && (
              <div>
                {otpWelcomeMessage && pendingOtpToken && (
                  <div
                    className="alert alert-success"
                    style={{ marginBottom: '1rem', textAlign: 'right', lineHeight: 1.7, fontSize: '0.92rem' }}
                  >
                    <div style={{ marginBottom: '0.75rem' }}>{otpWelcomeMessage}</div>
                    <button
                      type="button"
                      className="btn btn-primary"
                      style={{ width: '100%', justifyContent: 'center' }}
                      disabled={loading}
                      onClick={async () => {
                        setLoading(true)
                        try {
                          await completeOtpLogin(pendingOtpToken, pendingOtpUser)
                        } finally {
                          setLoading(false)
                        }
                      }}
                    >
                      ادامه و ورود به پنل
                    </button>
                  </div>
                )}
                {!otpWelcomeMessage && (
                  <>
                    <p style={{ textAlign: 'center', fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                      کد یکبارمصرف ارسال‌شده به <strong style={{ direction: 'ltr', display: 'inline-block' }}>{phone}</strong> را وارد کنید
                    </p>
                    <p
                      style={{
                        textAlign: 'center',
                        fontSize: '0.82rem',
                        color: 'var(--text-light)',
                        marginBottom: '0.75rem',
                        lineHeight: 1.6,
                      }}
                    >
                      اگر پیامک دیر رسید یا «ارسال مجدد» زدید، فقط کد <strong>آخرین</strong> پیامک را وارد کنید؛ کدهای قبلی دیگر معتبر نیستند.
                    </p>
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
                  </>
                )}

                {error && <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>{error}</div>}

                {loading && (
                  <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                    <div className="loading-spinner" style={{ margin: '0 auto', width: 28, height: 28 }} />
                  </div>
                )}

                {!otpWelcomeMessage && (
                  <>
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
                  </>
                )}
              </div>
            )}
          </>
        )}

        {staffMode && (
          <>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-light)', textAlign: 'center', marginBottom: '0.75rem' }}>
              <Link to="/login" style={{ color: 'var(--primary)', fontWeight: 500 }}>
                ← ورود دانشجو و ثبت‌نام با شماره موبایل
              </Link>
            </p>
            <p
              style={{
                fontSize: '0.78rem',
                color: 'var(--text-secondary)',
                textAlign: 'center',
                marginBottom: '1rem',
                lineHeight: 1.6,
              }}
            >
              حساب دمو معاون آموزش: <code style={{ direction: 'ltr' }}>deputy_education1</code> / <code style={{ direction: 'ltr' }}>demo123</code>
            </p>
          </>
        )}

        {staffMode && (
          <form onSubmit={handlePasswordLogin} data-testid="login-staff-password-form">
            <div className="form-group">
              <label className="form-label">نام کاربری</label>
              <input
                data-testid="login-username"
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
                data-testid="login-password"
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
                  data-testid="login-challenge-answer"
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
              data-testid="login-submit"
              className="btn btn-primary"
              type="submit"
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }}
            >
              {loading ? 'در حال ورود...' : 'ورود'}
            </button>
          </form>
        )}

        {!staffMode && (
          <div style={{ textAlign: 'center', marginTop: '1.25rem', fontSize: '0.82rem' }}>
            <span style={{ color: 'var(--text-light)' }}>اولین بار است؟ </span>
            <span style={{ color: 'var(--text-secondary)' }}>
              همان شماره را وارد کنید؛ پس از کد، فرم ثبت‌نام باز می‌شود.
            </span>
          </div>
        )}

        {!staffMode && (
          <div style={{ textAlign: 'center', marginTop: '0.85rem', fontSize: '0.82rem' }}>
            <Link to="/login?staff=1" style={{ color: 'var(--text-light)' }}>
              ورود پرسنل و مدیران (نام کاربری و رمز عبور)
            </Link>
          </div>
        )}

        <div style={{ textAlign: 'center', marginTop: '1rem' }}>
          <Link to="/" style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>
            ← بازگشت به صفحه اصلی
          </Link>
        </div>
      </div>
    </div>
  )
}
