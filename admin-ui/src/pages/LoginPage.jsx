import React, { useState } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
  const navigate = useNavigate()
  const { user, login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Already logged in
  if (user) return <Navigate to="/" replace />

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      await login(username, password)
      navigate('/')
    } catch (err) {
      const status = err.response?.status
      const msg = err.message || ''
      const detail = err.response?.data?.detail
      if (status === 401 || (status === 400 && msg.includes('password'))) {
        setError('نام کاربری یا رمز عبور اشتباه است')
      } else if (!err.response || (status === 500 && !detail) || msg.includes('Network') || msg.includes('ECONNREFUSED')) {
        setError('خطا در اتصال به سرور. API روی http://localhost:8000 در حال اجراست؟')
      } else {
        setError(detail || msg || 'خطا در ورود. لطفاً دوباره تلاش کنید.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h2 className="login-title">انیستیتو روانکاوری تهران</h2>
        <p className="login-subtitle">Tehran Institute of Psychoanalysis</p>
        <p className="login-subtitle" style={{ marginTop: '0.5rem', marginBottom: '1.5rem' }}>ورود به پنل مدیریت</p>

        <form onSubmit={handleSubmit}>
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
          {error && (
            <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
              {error}
            </div>
          )}
          <button
            className="btn btn-primary"
            type="submit"
            disabled={loading}
            style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }}
          >
            {loading ? 'در حال ورود...' : 'ورود'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.8rem', color: 'var(--text-light)' }}>
          v1.0 | Meta-Driven Educational Automation
        </div>
      </div>
    </div>
  )
}
