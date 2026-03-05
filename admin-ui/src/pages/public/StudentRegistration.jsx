import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { publicApi } from '../../services/api'

export default function StudentRegistration() {
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

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const res = await publicApi.register(form)
      setResult(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'خطا در ثبت‌نام. لطفاً دوباره تلاش کنید.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="pub-page-header">
        <h1>ثبت‌نام دانشجو</h1>
        <p>فرم ثبت‌نام اولیه در دوره‌های آموزشی انیستیتو روانکاوی تهران</p>
      </div>

      {result ? (
        <div className="pub-register-form" style={{ textAlign: 'center' }}>
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
            <span style={{ fontWeight: 700, color: 'var(--primary)', fontSize: '1.2rem', direction: 'ltr', display: 'inline-block' }}>
              {result.student_code}
            </span>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
            لطفاً کد دانشجویی را یادداشت کنید. این کد برای پیگیری وضعیت ثبت‌نام استفاده خواهد شد.
          </p>
          <Link
            to="/"
            style={{
              display: 'inline-block', marginTop: '1.5rem',
              padding: '0.7rem 2rem', background: 'var(--primary)', color: '#fff',
              borderRadius: 'var(--radius-lg)', fontWeight: 600
            }}
          >
            بازگشت به صفحه اصلی
          </Link>
        </div>
      ) : (
        <form className="pub-register-form" onSubmit={handleSubmit}>
          <h2>اطلاعات ثبت‌نام</h2>

          <div className="pub-form-row">
            <div className="pub-form-group">
              <label>نام و نام خانوادگی *</label>
              <input
                name="full_name_fa"
                value={form.full_name_fa}
                onChange={handleChange}
                placeholder="نام کامل به فارسی"
                required
              />
            </div>
            <div className="pub-form-group">
              <label>شماره موبایل *</label>
              <input
                name="phone"
                value={form.phone}
                onChange={handleChange}
                placeholder="۰۹۱۲XXXXXXX"
                required
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
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

          <button type="submit" className="pub-form-submit" disabled={loading}>
            {loading ? 'در حال ثبت...' : 'ارسال فرم ثبت‌نام'}
          </button>
        </form>
      )}
    </>
  )
}
