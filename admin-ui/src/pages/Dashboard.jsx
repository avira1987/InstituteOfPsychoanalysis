import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { dashboardApi, processApi, auditApi, authApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

const SECURITY_QUESTIONS = [
  'نام اولین معلم شما چه بود؟',
  'نام اولین حیوان خانگی شما چه بود؟',
  'در چه شهری به دنیا آمدید؟',
  'نام خانوادگی مادر شما چیست؟',
  'نام بهترین دوست دوران کودکی شما چه بود؟',
]

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [showSecurityForm, setShowSecurityForm] = useState(false)
  const [secQuestion, setSecQuestion] = useState('')
  const [secAnswer, setSecAnswer] = useState('')
  const [secSaving, setSecSaving] = useState(false)
  const [processes, setProcesses] = useState([])
  const [recentLogs, setRecentLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [debugCount, setDebugCount] = useState(null)
  const [syncing, setSyncing] = useState(false)

  const handleSyncMetadata = async () => {
    setSyncing(true)
    try {
      const res = await dashboardApi.syncMetadata()
      const msg = res.data?.message || `${res.data?.added ?? 0} فرایند اضافه شد`
      alert(msg)
      loadAll()
    } catch (err) {
      alert(err.response?.data?.detail || 'خطا در همگام‌سازی')
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoadError(null)
    try {
      const [statsRes, procRes, logsRes] = await Promise.all([
        dashboardApi.stats(),
        processApi.list(),
        auditApi.list({ limit: 8, offset: 0 }),
      ])
      setStats(statsRes.data)
      setProcesses(Array.isArray(procRes.data) ? procRes.data : [])
      setRecentLogs(logsRes.data?.logs || [])
    } catch (err) {
      console.error('Failed to load dashboard:', err)
      setLoadError(err.response?.status === 401 ? 'لطفاً دوباره وارد شوید' : 'خطا در بارگذاری داشبورد')
      setStats(null)
      setProcesses([])
      setRecentLogs([])
      // Fallback: endpoint دیباگ بدون auth (همان الگوی لاگین)
      try {
        const d = await dashboardApi.debugProcessCount()
        setDebugCount(d.process_count)
      } catch (_) {}
    } finally {
      setLoading(false)
    }
  }

  const actionTypeLabel = (type) => {
    switch (type) {
      case 'transition': return { label: 'انتقال', cls: 'badge-info' }
      case 'process_start': return { label: 'شروع فرایند', cls: 'badge-success' }
      case 'process_updated': return { label: 'ویرایش فرایند', cls: 'badge-warning' }
      case 'rule_change': return { label: 'تغییر قانون', cls: 'badge-warning' }
      default: return { label: type, cls: 'badge-primary' }
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">داشبورد</h1>
          <p className="page-subtitle">
            خوش آمدید، {user?.full_name_fa || user?.username} | نمای کلی سیستم اتوماسیون آموزشی
          </p>
        </div>
      </div>

      {loadError && (
        <div className="toast toast-error" style={{ marginBottom: '1rem' }}>
          {loadError}
          {debugCount != null && ` | سرور ${debugCount} فرایند دارد — رفرش یا ورود مجدد`}
        </div>
      )}

      {/* تنظیم سوال امنیتی */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header" style={{ cursor: 'pointer' }} onClick={() => setShowSecurityForm(!showSecurityForm)}>
          <h3 className="card-title">🔐 سوال امنیتی برای ورود با رمز عبور</h3>
          <span>{showSecurityForm ? '▼' : '▶'}</span>
        </div>
        {showSecurityForm && (
          <div style={{ padding: '1rem' }}>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              با تنظیم سوال امنیتی، هنگام ورود با نام کاربری و رمز عبور باید پاسخ آن را هم وارد کنید.
            </p>
            <div className="form-group">
              <label className="form-label">سوال امنیتی</label>
              <select className="form-input" value={secQuestion} onChange={(e) => setSecQuestion(e.target.value)}>
                <option value="">انتخاب کنید...</option>
                {SECURITY_QUESTIONS.map((q, i) => (
                  <option key={i} value={q}>{q}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">پاسخ</label>
              <input className="form-input" type="password" value={secAnswer} onChange={(e) => setSecAnswer(e.target.value)} placeholder="پاسخ سوال امنیتی" />
            </div>
            <button className="btn btn-primary" disabled={!secQuestion || !secAnswer || secSaving} onClick={async () => {
              setSecSaving(true)
              try {
                await authApi.setSecurityQuestion(secQuestion, secAnswer)
                alert('سوال امنیتی ذخیره شد.')
                setSecQuestion('')
                setSecAnswer('')
                setShowSecurityForm(false)
              } catch (e) {
                alert(e.response?.data?.detail || 'خطا در ذخیره')
              } finally {
                setSecSaving(false)
              }
            }}>
              {secSaving ? 'در حال ذخیره...' : 'ذخیره'}
            </button>
          </div>
        )}
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon primary">⚙️</div>
          <div>
            <div className="stat-value">{loading ? '...' : stats?.active_processes ?? 0}</div>
            <div className="stat-label">فرایندهای فعال</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon success">📋</div>
          <div>
            <div className="stat-value">{loading ? '...' : stats?.active_rules ?? 0}</div>
            <div className="stat-label">قوانین فعال</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon info">👨‍🎓</div>
          <div>
            <div className="stat-value">{loading ? '...' : stats?.total_students ?? 0}</div>
            <div className="stat-label">تعداد دانشجویان</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon warning">🔄</div>
          <div>
            <div className="stat-value">{loading ? '...' : stats?.active_instances ?? 0}</div>
            <div className="stat-label">فرایندهای در جریان</div>
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        {/* Active Processes from API */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">فرایندهای SOP تعریف‌شده</h3>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn btn-outline btn-sm" onClick={handleSyncMetadata} disabled={syncing}>
                {syncing ? '...' : 'همگام‌سازی از JSON'}
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => navigate('/panel/processes')}>
                مدیریت
              </button>
            </div>
          </div>
          <div>
            {loading ? (
              <div className="empty-state" style={{ padding: '2rem' }}>در حال بارگذاری...</div>
            ) : processes.length === 0 ? (
              <div className="empty-state" style={{ padding: '2rem' }}>فرایندی تعریف نشده</div>
            ) : (
              processes.map((p) => (
                <div key={p.id} className="dashboard-process-item" onClick={() => navigate(`/panel/processes/${p.id}`)}>
                  <div>
                    <span style={{ fontWeight: 600 }}>{p.name_fa}</span>
                    {p.name_en && <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginRight: '0.5rem' }}>({p.name_en})</span>}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="badge badge-primary">{p.code}</span>
                    <span className={`badge ${p.is_active ? 'badge-success' : 'badge-danger'}`}>
                      {p.is_active ? 'فعال' : 'غیرفعال'}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-light)' }}>v{p.version}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">فعالیت‌های اخیر</h3>
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/panel/audit')}>
              مشاهده همه
            </button>
          </div>
          <div>
            {loading ? (
              <div className="empty-state" style={{ padding: '2rem' }}>در حال بارگذاری...</div>
            ) : recentLogs.length === 0 ? (
              <div className="empty-state" style={{ padding: '2rem' }}>هنوز فعالیتی ثبت نشده</div>
            ) : (
              recentLogs.map((log) => {
                const at = actionTypeLabel(log.action_type)
                return (
                  <div key={log.id} className="activity-item">
                    <div className="activity-dot" />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                        <span className={`badge ${at.cls}`}>{at.label}</span>
                        {log.process_code && (
                          <span style={{ fontSize: '0.8rem', fontWeight: 500 }}>{log.process_code}</span>
                        )}
                      </div>
                      {log.from_state && log.to_state && (
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          {log.from_state} → {log.to_state}
                        </div>
                      )}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', whiteSpace: 'nowrap' }}>
                      {new Date(log.timestamp).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card" style={{ marginTop: '1.5rem' }}>
        <div className="card-header">
          <h3 className="card-title">دسترسی سریع</h3>
        </div>
        <div className="quick-actions-grid">
          {(user?.role === 'student' || user?.role === 'admin') && (
            <button className="quick-action-btn" onClick={() => navigate('/panel/portal/student')}>
              <span className="quick-action-icon">🎓</span>
              <span>پنل دانشجو</span>
            </button>
          )}
          {(user?.role === 'therapist' || user?.role === 'admin') && (
            <button className="quick-action-btn" onClick={() => navigate('/panel/portal/therapist')}>
              <span className="quick-action-icon">💊</span>
              <span>پنل درمانگر</span>
            </button>
          )}
          {(user?.role === 'supervisor' || user?.role === 'admin') && (
            <button className="quick-action-btn" onClick={() => navigate('/panel/portal/supervisor')}>
              <span className="quick-action-icon">👁️</span>
              <span>پنل سوپروایزر</span>
            </button>
          )}
          {(user?.role === 'staff' || user?.role === 'admin') && (
            <button className="quick-action-btn" onClick={() => navigate('/panel/portal/staff')}>
              <span className="quick-action-icon">🏢</span>
              <span>پنل کارمند</span>
            </button>
          )}
          {(user?.role === 'site_manager' || user?.role === 'admin') && (
            <button className="quick-action-btn" onClick={() => navigate('/panel/portal/site-manager')}>
              <span className="quick-action-icon">🏗️</span>
              <span>پنل مسئول سایت</span>
            </button>
          )}
          {(['progress_committee', 'education_committee', 'supervision_committee',
            'specialized_commission', 'therapy_committee_chair', 'therapy_committee_executor',
            'deputy_education', 'monitoring_committee_officer', 'admin'].includes(user?.role)) && (
            <button className="quick-action-btn" onClick={() => navigate('/panel/portal/committee')}>
              <span className="quick-action-icon">📋</span>
              <span>پنل کمیته</span>
            </button>
          )}
          <button className="quick-action-btn" onClick={() => navigate('/panel/processes')}>
            <span className="quick-action-icon">⚙️</span>
            <span>مدیریت فرایندها</span>
          </button>
          <button className="quick-action-btn" onClick={() => navigate('/panel/students')}>
            <span className="quick-action-icon">👨‍🎓</span>
            <span>ردیابی دانشجو</span>
          </button>
          {user?.role === 'admin' && (
            <button className="quick-action-btn" onClick={() => navigate('/panel/users')}>
              <span className="quick-action-icon">👥</span>
              <span>مدیریت کاربران</span>
            </button>
          )}
          <button className="quick-action-btn" onClick={() => navigate('/panel/guide')}>
            <span className="quick-action-icon">📖</span>
            <span>راهنمای جامع</span>
          </button>
        </div>
      </div>
    </div>
  )
}
