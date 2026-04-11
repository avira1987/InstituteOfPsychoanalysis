import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { publicApi, studentApi } from '../../services/api'
import { useAuth } from '../../contexts/AuthContext'

/** Map API error (string or 422 validation array) to a single Persian message. */
function getRegistrationErrorMessage(err) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const fieldNames = {
      full_name_fa: 'نام و نام خانوادگی',
      phone: 'شماره موبایل',
      email: 'ایمیل',
      course_type: 'نوع دوره',
      education_level: 'مقطع تحصیلی',
      field_of_study: 'رشته تحصیلی',
      motivation: 'انگیزه شرکت در دوره',
    }
    const first = detail[0]
    const field = first.loc?.[first.loc.length - 1]
    const label = fieldNames[field] || field || 'فیلد'
    const msg = first.msg
    if (msg && (msg.includes('required') || msg.includes('missing'))) return `${label} را وارد کنید.`
    if (msg && msg.includes('type')) return `مقدار ${label} نامعتبر است.`
    if (first.msg) return `${label}: ${first.msg}`
    return `${label} نامعتبر است.`
  }
  const status = err.response?.status
  if (status === 500) return 'خطایی در سرور رخ داد. لطفاً چند دقیقه دیگر تلاش کنید.'
  if (status === 404) return 'سرویس ثبت‌نام در دسترس نیست. لطفاً بعداً تلاش کنید.'
  if (status === 409) return typeof detail === 'string' ? detail : 'پروفایل دانشجویی قبلاً ثبت شده است.'
  if (!err.response) return 'خطا در ارتباط با سرور. اتصال اینترنت را بررسی کنید و دوباره تلاش کنید.'
  return 'خطا در ثبت‌نام. لطفاً اطلاعات را بررسی کرده و دوباره تلاش کنید.'
}

/**
 * @param {{ mode?: 'public' | 'panel' }} props
 * — mode=panel: پس از ورود با OTP؛ شماره از حساب کاربری است و API تکمیل ثبت‌نام فراخوانی می‌شود.
 */
export default function StudentRegistration({ mode = 'public' }) {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [form, setForm] = useState({
    full_name_fa: '',
    phone: '',
    email: '',
    education_level: '',
    field_of_study: '',
    course_type: 'introductory',
    motivation: '',
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (mode === 'panel' && user?.phone) {
      setForm(prev => ({ ...prev, phone: user.phone }))
    }
  }, [mode, user?.phone])

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)

    try {
      if (mode === 'panel') {
        await studentApi.completeRegistration({
          full_name_fa: form.full_name_fa,
          email: form.email || undefined,
          education_level: form.education_level || undefined,
          field_of_study: form.field_of_study || undefined,
          course_type: form.course_type,
          motivation: form.motivation || undefined,
        })
        navigate('/panel/portal/student', { replace: true })
        return
      }
      const res = await publicApi.register(form)
      setResult(res.data)
    } catch (err) {
      setError(getRegistrationErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const isPanel = mode === 'panel'

  return (
    <>
      <div className="pub-page-header">
        <h1>{isPanel ? 'تکمیل ثبت‌نام دانشجو' : 'ثبت‌نام دانشجو'}</h1>
        <p>
          {isPanel
            ? 'شماره موبایل شما از ورود با پیامک تأیید شده است. بقیهٔ اطلاعات را تکمیل کنید تا مسیر ثبت‌نام دوره در پنل شما باز شود.'
            : 'فرم ثبت‌نام اولیه در دوره‌های آموزشی انستیتو روانکاوی تهران'}
        </p>
      </div>

      {result ? (
        <div className="pub-register-form" style={{ textAlign: 'center' }} data-testid="register-success">
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✅</div>
          <h2 style={{ color: 'var(--success)', marginBottom: '1rem' }}>ثبت‌نام موفق</h2>
          <p style={{ color: 'var(--text-secondary)', lineHeight: '2', marginBottom: '1.5rem' }}>
            {result.message}
          </p>
          <div style={{
            background: 'var(--primary-light)',
            padding: '1rem',
            borderRadius: 'var(--radius-lg)',
            marginBottom: '1.5rem'
          }}>
            <strong>کد دانشجویی شما: </strong>
            <span
              data-testid="register-student-code"
              style={{ fontWeight: 700, color: 'var(--primary)', fontSize: '1.2rem', direction: 'ltr', display: 'inline-block' }}
            >
              {result.student_code}
            </span>
          </div>
          {result.initial_password && result.username && (
            <div
              className="alert"
              style={{
                background: 'var(--bg-card)',
                border: '1px dashed var(--border)',
                marginBottom: '1.25rem',
                padding: '0.85rem 1rem',
                textAlign: 'right',
                lineHeight: 1.8,
              }}
            >
              <div style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                اطلاعات ورود (فعلاً به‌جای پیامک؛ حتماً یادداشت کنید)
              </div>
              <div style={{ direction: 'ltr', textAlign: 'center', fontSize: '1.05rem' }}>
                نام کاربری: <strong data-testid="register-username">{result.username}</strong>
              </div>
              <div style={{ direction: 'ltr', textAlign: 'center', fontSize: '1.1rem', letterSpacing: '1px', marginTop: '0.35rem' }}>
                رمز عبور اولیه: <strong data-testid="register-initial-password">{result.initial_password}</strong>
              </div>
              {result.login_hint_fa && (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-light)', marginTop: '0.65rem', textAlign: 'center' }}>
                  {result.login_hint_fa}
                </div>
              )}
            </div>
          )}
          <p style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
            می‌توانید با همان شماره موبایل از بخش «ورود با پیامک» وارد شوید، یا با نام کاربری و رمز عبور بالا از «ورود با رمز عبور» استفاده کنید.
          </p>
          <Link
            to="/login"
            style={{
              display: 'inline-block', marginTop: '1rem',
              padding: '0.7rem 2rem', background: 'var(--primary)', color: '#fff',
              borderRadius: 'var(--radius-lg)', fontWeight: 600
            }}
          >
            ورود به پنل کاربری
          </Link>
          <div style={{ marginTop: '0.75rem' }}>
            <Link
              to="/"
              style={{ fontSize: '0.9rem', color: 'var(--text-light)' }}
            >
              بازگشت به صفحه اصلی
            </Link>
          </div>
        </div>
      ) : (
        <form className="pub-register-form" onSubmit={handleSubmit} data-testid="register-form">
          <h2>اطلاعات ثبت‌نام</h2>

          <div className="pub-form-row">
            <div className="pub-form-group">
              <label>نام و نام خانوادگی *</label>
              <input
                data-testid="register-input-full_name_fa"
                name="full_name_fa"
                value={form.full_name_fa}
                onChange={handleChange}
                placeholder="نام کامل به فارسی"
                required
              />
            </div>
            <div className="pub-form-group">
              <label>شماره موبایل *</label>
              {isPanel ? (
                <input
                  data-testid="register-input-phone"
                  readOnly
                  value={user?.phone || form.phone || ''}
                  style={{ direction: 'ltr', textAlign: 'right', background: 'var(--bg-muted, #f3f4f6)' }}
                  title="شماره از ورود با پیامک"
                />
              ) : (
                <input
                  data-testid="register-input-phone"
                  name="phone"
                  value={form.phone}
                  onChange={handleChange}
                  placeholder="۰۹۱۲XXXXXXX"
                  required
                  style={{ direction: 'ltr', textAlign: 'right' }}
                />
              )}
            </div>
          </div>

          <div className="pub-form-row">
            <div className="pub-form-group">
              <label>ایمیل</label>
              <input
                name="email"
                type="email"
                value={form.email}
                onChange={handleChange}
                placeholder="email@example.com"
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
            <div className="pub-form-group">
              <label>نوع دوره *</label>
              <select name="course_type" value={form.course_type} onChange={handleChange} required>
                <option value="introductory">دوره مقدماتی</option>
                <option value="comprehensive">دوره جامع</option>
              </select>
            </div>
          </div>

          <div className="pub-form-row">
            <div className="pub-form-group">
              <label>مقطع تحصیلی</label>
              <select name="education_level" value={form.education_level} onChange={handleChange}>
                <option value="">انتخاب کنید</option>
                <option value="bachelor">کارشناسی</option>
                <option value="master">کارشناسی ارشد</option>
                <option value="phd">دکتری</option>
                <option value="specialist">تخصصی</option>
              </select>
            </div>
            <div className="pub-form-group">
              <label>رشته تحصیلی</label>
              <input
                name="field_of_study"
                value={form.field_of_study}
                onChange={handleChange}
                placeholder="مثلاً: روان‌شناسی بالینی"
              />
            </div>
          </div>

          <div className="pub-form-group">
            <label>انگیزه شرکت در دوره</label>
            <textarea
              name="motivation"
              value={form.motivation}
              onChange={handleChange}
              rows={4}
              placeholder="لطفاً به اختصار توضیح دهید چرا مایل به شرکت در این دوره هستید..."
            />
          </div>

          {error && (
            <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
              {error}
            </div>
          )}

          <button type="submit" className="pub-form-submit" disabled={loading} data-testid="register-submit">
            {loading ? 'در حال ثبت...' : 'ارسال فرم ثبت‌نام'}
          </button>
        </form>
      )}
    </>
  )
}
