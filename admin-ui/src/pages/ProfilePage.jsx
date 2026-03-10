import React, { useState, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { authApi, getAvatarUrl } from '../services/api'

export default function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const [fullNameFa, setFullNameFa] = useState(user?.full_name_fa ?? '')
  const [fullNameEn, setFullNameEn] = useState(user?.full_name_en ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('')
  const [message, setMessage] = useState({ type: '', text: '' })
  const [loading, setLoading] = useState(false)
  const [avatarLoading, setAvatarLoading] = useState(false)
  const fileInputRef = useRef(null)

  React.useEffect(() => {
    if (user) {
      setFullNameFa(user.full_name_fa ?? '')
      setFullNameEn(user.full_name_en ?? '')
      setEmail(user.email ?? '')
      setPhone(user.phone ?? '')
    }
  }, [user])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setMessage({ type: '', text: '' })
    if (newPassword && newPassword !== newPasswordConfirm) {
      setMessage({ type: 'error', text: 'تکرار رمز عبور جدید با رمز جدید مطابقت ندارد.' })
      return
    }
    if (newPassword && newPassword.length < 6) {
      setMessage({ type: 'error', text: 'رمز عبور جدید باید حداقل ۶ کاراکتر باشد.' })
      return
    }
    setLoading(true)
    try {
      const data = {
        full_name_fa: fullNameFa || null,
        full_name_en: fullNameEn || null,
        email: email || null,
        phone: phone || null,
      }
      if (newPassword) {
        data.password = newPassword
        data.current_password = currentPassword
      }
      await authApi.updateMe(data)
      await refreshUser()
      setCurrentPassword('')
      setNewPassword('')
      setNewPasswordConfirm('')
      setMessage({ type: 'success', text: 'اطلاعات با موفقیت ذخیره شد.' })
    } catch (err) {
      const detail = err.response?.data?.detail
      setMessage({
        type: 'error',
        text: typeof detail === 'string' ? detail : 'خطا در ذخیره اطلاعات.',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleAvatarChange = async (e) => {
    const file = e.target?.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setMessage({ type: 'error', text: 'لطفاً یک فایل تصویری (JPG، PNG، WebP یا GIF) انتخاب کنید.' })
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setMessage({ type: 'error', text: 'حداکثر حجم فایل ۵ مگابایت است.' })
      return
    }
    setAvatarLoading(true)
    setMessage({ type: '', text: '' })
    try {
      await authApi.uploadAvatar(file)
      await refreshUser()
      setMessage({ type: 'success', text: 'عکس پروفایل با موفقیت به‌روز شد.' })
    } catch (err) {
      const detail = err.response?.data?.detail
      setMessage({
        type: 'error',
        text: typeof detail === 'string' ? detail : 'خطا در آپلود عکس.',
      })
    } finally {
      setAvatarLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const avatarUrl = getAvatarUrl(user?.avatar_url)
  const initial = (user?.full_name_fa || user?.username || '?')[0]

  return (
    <div className="profile-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">پروفایل من</h1>
          <p className="page-subtitle">اطلاعات شخصی و عکس پروفایل خود را مدیریت کنید.</p>
        </div>
      </div>

      <div className="profile-grid">
        {/* کارت عکس پروفایل */}
        <div className="card profile-card-avatar">
          <div className="card-header">
            <h3 className="card-title">عکس پروفایل</h3>
          </div>
          <div className="profile-avatar-block">
            <div
              className="sidebar-user-avatar"
              style={{
                width: 120,
                height: 120,
                fontSize: '3rem',
                borderRadius: '50%',
                overflow: 'hidden',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'var(--primary-light)',
                color: 'var(--primary)',
              }}
            >
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt="پروفایل"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <span>{initial}</span>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              onChange={handleAvatarChange}
              style={{ display: 'none' }}
            />
            <button
              type="button"
              className="btn btn-outline"
              disabled={avatarLoading}
              onClick={() => fileInputRef.current?.click()}
            >
              {avatarLoading ? 'در حال آپلود…' : 'انتخاب یا تغییر عکس'}
            </button>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              JPG، PNG، WebP یا GIF — حداکثر ۵ مگابایت
            </p>
          </div>
        </div>

        {/* فرم اطلاعات شخصی */}
        <div className="card profile-card-form">
          <div className="card-header">
            <h3 className="card-title">اطلاعات شخصی</h3>
          </div>
          <form onSubmit={handleSubmit}>
            {message.text && (
              <div
                className={message.type === 'success' ? 'alert alert-success' : 'alert alert-danger'}
                style={{ marginBottom: 0 }}
              >
                {message.text}
              </div>
            )}
            <div>
              <label className="form-label">نام و نام خانوادگی (فارسی)</label>
              <input
                type="text"
                className="form-input"
                value={fullNameFa}
                onChange={(e) => setFullNameFa(e.target.value)}
                placeholder="نام و نام خانوادگی"
                dir="rtl"
              />
            </div>
            <div>
              <label className="form-label">نام (انگلیسی)</label>
              <input
                type="text"
                className="form-input"
                value={fullNameEn}
                onChange={(e) => setFullNameEn(e.target.value)}
                placeholder="Full name"
                dir="ltr"
              />
            </div>
            <div>
              <label className="form-label">ایمیل</label>
              <input
                type="email"
                className="form-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@example.com"
                dir="ltr"
              />
            </div>
            <div>
              <label className="form-label">شماره تماس</label>
              <input
                type="tel"
                className="form-input"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                dir="ltr"
              />
            </div>
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem', marginTop: '0.5rem' }}>
              <h4 style={{ fontSize: '0.95rem', marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
                تغییر رمز عبور (اختیاری)
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div>
                  <label className="form-label">رمز عبور فعلی</label>
                  <input
                    type="password"
                    className="form-input"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="برای تغییر رمز وارد کنید"
                    autoComplete="current-password"
                  />
                </div>
                <div>
                  <label className="form-label">رمز عبور جدید</label>
                  <input
                    type="password"
                    className="form-input"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="حداقل ۶ کاراکتر"
                    autoComplete="new-password"
                  />
                </div>
                <div>
                  <label className="form-label">تکرار رمز عبور جدید</label>
                  <input
                    type="password"
                    className="form-input"
                    value={newPasswordConfirm}
                    onChange={(e) => setNewPasswordConfirm(e.target.value)}
                    placeholder="همان رمز را دوباره وارد کنید"
                    autoComplete="new-password"
                  />
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {loading ? 'در حال ذخیره…' : 'ذخیره تغییرات'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
