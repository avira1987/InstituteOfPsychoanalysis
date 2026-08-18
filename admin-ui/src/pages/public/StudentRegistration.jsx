import React, { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { publicApi, studentApi } from '../../services/api'
import { useAuth } from '../../contexts/AuthContext'
import StudentRegistrationExtendedFields from '../../components/StudentRegistrationExtendedFields'
import InstituteActivityLicenseNotice from '../../components/InstituteActivityLicenseNotice'
import {
  REGISTRATION_FIELD_LABELS,
  buildRegistrationProfilePayload,
  emptyExtendedRegistrationFields,
  validateExtendedRegistrationClient,
} from '../../utils/studentRegistrationProfile'

/** اعتبارسنجی کد ملی ایران (۱۰ رقم + رقم کنترل) — هم‌راستا با سرور */
function validateIranNationalCode(raw) {
  const d = String(raw || '').replace(/\D/g, '')
  if (d.length !== 10) return false
  if (new Set(d).size === 1) return false
  const check = parseInt(d[9], 10)
  const csum = d.slice(0, 9).split('').reduce((acc, ch, i) => acc + parseInt(ch, 10) * (10 - i), 0) % 11
  if (csum < 2) return check === csum
  return check === 11 - csum
}

/** Map API error (string or 422 validation array) to a single Persian message. */
function getRegistrationErrorMessage(err) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const fieldNames = REGISTRATION_FIELD_LABELS
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
  if (status === 409) {
    if (typeof detail === 'string') return detail
    if (detail && typeof detail === 'object' && detail.message) return detail.message
    return 'پروفایل دانشجویی قبلاً ثبت شده است.'
  }
  if (!err.response) return 'خطا در ارتباط با سرور. اتصال اینترنت را بررسی کنید و دوباره تلاش کنید.'
  return 'خطا در ثبت‌نام. لطفاً اطلاعات را بررسی کرده و دوباره تلاش کنید.'
}

/**
 * @param {{
 *   mode?: 'public' | 'panel'
 *   embedded?: boolean
 *   onPanelSuccess?: () => void | Promise<void>
 * }} props
 * — mode=panel: پس از ورود با OTP؛ شماره از حساب کاربری است و API تکمیل ثبت‌نام فراخوانی می‌شود.
 * — embedded: بدون هدر صفحهٔ عمومی؛ برای قرارگیری داخل کارت پنل دانشجو.
 * — onPanelSuccess: پس از ثبت موفق در پنل (به‌جای navigate ساده).
 */
export default function StudentRegistration({ mode = 'public', embedded = false, onPanelSuccess }) {
  const navigate = useNavigate()
  const { user, refreshUser } = useAuth()
  const [form, setForm] = useState({
    phone: '',
    national_code: '',
    email: '',
    course_type: 'introductory',
    motivation: '',
    ...emptyExtendedRegistrationFields(),
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [duplicateNationalModal, setDuplicateNationalModal] = useState({ open: false, message: '' })

  const isPanel = mode === 'panel'

  const phoneLocked = useMemo(
    () => isPanel || (user?.role === 'student' && !!user?.phone),
    [isPanel, user?.role, user?.phone],
  )

  useEffect(() => {
    if (!user) return
    if (isPanel) {
      const full = (user.full_name_fa || '').trim()
      const space = full.indexOf(' ')
      const defaultFirst = space > 0 ? full.slice(0, space) : full
      const defaultLast = space > 0 ? full.slice(space + 1).trim() : ''
      setForm(prev => ({
        ...prev,
        phone: user.phone || prev.phone,
        first_name_fa: prev.first_name_fa || defaultFirst,
        last_name_fa: prev.last_name_fa || defaultLast,
        email: prev.email || user.email || '',
      }))
      return
    }
    if (user.role === 'student' && user.phone) {
      setForm(prev => ({ ...prev, phone: user.phone }))
    }
  }, [isPanel, user])

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    setDuplicateNationalModal({ open: false, message: '' })

    const ncDigits = String(form.national_code || '').replace(/\D/g, '')
    if (!validateIranNationalCode(ncDigits)) {
      setError('کد ملی را کامل و صحیح وارد کنید (۱۰ رقم معتبر).')
      setLoading(false)
      return
    }
    if (!(form.email || '').trim()) {
      setError('ایمیل را وارد کنید.')
      setLoading(false)
      return
    }
    const extErrors = validateExtendedRegistrationClient(form)
    if (extErrors.length) {
      setError(extErrors[0])
      setLoading(false)
      return
    }

    const profilePayload = buildRegistrationProfilePayload(form)
    const fullNameFa = `${(form.first_name_fa || '').trim()} ${(form.last_name_fa || '').trim()}`.trim()
    if (!fullNameFa) {
      setError('نام و نام خانوادگی را وارد کنید.')
      setLoading(false)
      return
    }

    try {
      if (mode === 'panel') {
        await studentApi.completeRegistration({
          full_name_fa: fullNameFa,
          national_code: ncDigits,
          email: form.email.trim(),
          education_level: profilePayload.education_level,
          field_of_study: profilePayload.field_of_study,
          course_type: form.course_type,
          motivation: form.motivation || undefined,
          ...profilePayload,
        })
        try {
          await refreshUser()
        } catch {
          /* پروفایل دانشجو از students/me لود می‌شود؛ اگر auth/me خطا داد باز هم به پنل برو */
        }
        if (onPanelSuccess) {
          await onPanelSuccess()
        } else {
          navigate('/panel/portal/student', { replace: true })
        }
        return
      }
      const res = await publicApi.register({
        full_name_fa: fullNameFa,
        national_code: ncDigits,
        phone: form.phone,
        email: form.email.trim(),
        education_level: profilePayload.education_level,
        field_of_study: profilePayload.field_of_study,
        course_type: form.course_type,
        motivation: form.motivation || undefined,
        ...profilePayload,
      })
      setResult(res.data)
    } catch (err) {
      const st = err.response?.status
      const d = err.response?.data?.detail
      if (st === 409 && d && typeof d === 'object' && d.code === 'duplicate_national_id') {
        setDuplicateNationalModal({
          open: true,
          message: d.message || getRegistrationErrorMessage(err),
        })
      } else {
        setError(getRegistrationErrorMessage(err))
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {!embedded && (
        <div className="pub-page-header">
          <h1>{isPanel ? 'تکمیل ثبت‌نام دانشجو' : 'ثبت‌نام دانشجو'}</h1>
          <p>
            {isPanel
              ? 'شماره موبایل شما از ورود با پیامک تأیید شده است. بقیهٔ اطلاعات را تکمیل کنید تا مسیر ثبت‌نام دوره در پنل شما باز شود.'
              : 'ثبت‌نام اولیه از طریق ورود با موبایل انجام می‌شود؛ پس از دریافت کد، در صورت نیاز همین فرم در پنل نمایش داده می‌شود.'}
          </p>
        </div>
      )}

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
            از این پس با همان شماره موبایل از صفحه ورود، کد پیامکی بگیرید و وارد پنل شوید.
            {result.initial_password && result.username
              ? ' در صورت نیاز می‌توانید یک‌بار با نام کاربری و رمز اولیهٔ بالا هم از مسیر «ورود پرسنل» در صفحه ورود وارد شوید.'
              : ''}
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

          <InstituteActivityLicenseNotice />

          <div className="pub-form-row">
            <div className="pub-form-group">
              <label>شماره تماس *</label>
              {phoneLocked ? (
                <input
                  data-testid="register-input-phone"
                  readOnly
                  tabIndex={-1}
                  value={user?.phone || form.phone || ''}
                  style={{ direction: 'ltr', textAlign: 'right', background: 'var(--bg-muted, #f3f4f6)' }}
                  title={isPanel ? 'شماره از ورود با پیامک' : 'شماره از حساب کاربری شما (غیرقابل ویرایش)'}
                />
              ) : (
                <input
                  data-testid="register-input-phone"
                  name="phone"
                  value={form.phone}
                  onChange={handleChange}
                  placeholder="09123456789"
                  required
                  style={{ direction: 'ltr', textAlign: 'right' }}
                />
              )}
            </div>
            <div className="pub-form-group">
              <label>کد ملی *</label>
              <input
                data-testid="register-input-national_code"
                name="national_code"
                value={form.national_code}
                onChange={handleChange}
                placeholder="۱۰ رقم بدون خط تیره"
                required
                inputMode="numeric"
                autoComplete="off"
                maxLength={14}
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
          </div>

          <StudentRegistrationExtendedFields form={form} onChange={handleChange} />

          <div className="pub-form-group pub-form-group-full">
            <label>ایمیل *</label>
            <input
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="email@example.com"
              required
              style={{ direction: 'ltr', textAlign: 'right' }}
            />
          </div>

          <div className="pub-form-row">
            <div className="pub-form-group">
              <label>نوع دوره *</label>
              <select name="course_type" value={form.course_type} onChange={handleChange} required>
                <option value="introductory">دوره آشنایی</option>
                <option value="comprehensive">دوره جامع</option>
              </select>
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
            {loading ? 'در حال ثبت...' : 'تکمیل فرم'}
          </button>
        </form>
      )}

      {duplicateNationalModal.open && (
        <div
          className="modal-overlay"
          role="presentation"
          style={{ zIndex: 10050 }}
          onClick={() => setDuplicateNationalModal({ open: false, message: '' })}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="dup-national-title"
            className="modal"
            style={{ maxWidth: '26rem', padding: '1.35rem 1.5rem', textAlign: 'right' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="dup-national-title" style={{ marginTop: 0, marginBottom: '0.75rem' }}>
              کد ملی تکراری
            </h3>
            <p style={{ lineHeight: 1.75, color: 'var(--text-secondary)', marginBottom: '1.1rem' }}>
              {duplicateNationalModal.message}
            </p>
            <p style={{ lineHeight: 1.7, fontSize: '0.92rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
              برای پیگیری اداری، از منوی «تیکت‌ها و درخواست‌ها» تیکت جدید بسازید و گزینهٔ
              {' '}
              <strong>ثبت درخواست بدون پروفایل دانشجویی</strong>
              {' '}
              را فعال کنید تا درخواست بدون خطای سیستمی ثبت شود.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.65rem', justifyContent: 'flex-end' }}>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => setDuplicateNationalModal({ open: false, message: '' })}
              >
                بستن
              </button>
              <Link
                to="/panel/tickets"
                className="btn btn-primary btn-sm"
                style={{ textDecoration: 'none', display: 'inline-block' }}
                onClick={() => setDuplicateNationalModal({ open: false, message: '' })}
              >
                رفتن به تیکت‌ها
              </Link>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
