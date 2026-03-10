import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { dashboardApi, processApi, auditApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

const portalByRole = {
  student: { path: '/panel/portal/student', label: 'پنل دانشجو', icon: '🎓' },
  therapist: { path: '/panel/portal/therapist', label: 'پنل درمانگر', icon: '💊' },
  supervisor: { path: '/panel/portal/supervisor', label: 'پنل سوپروایزر', icon: '👁️' },
  staff: { path: '/panel/portal/staff', label: 'پنل کارمند', icon: '🏢' },
  site_manager: { path: '/panel/portal/site-manager', label: 'پنل مسئول سایت', icon: '🏗️' },
  progress_committee: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  education_committee: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  supervision_committee: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  specialized_commission: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  therapy_committee_chair: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  therapy_committee_executor: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  deputy_education: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  monitoring_committee_officer: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
}

function PortalQuickLink({ role, navigate }) {
  const portal = role ? portalByRole[role] : null
  if (!portal) return null
  return (
    <button type="button" className="btn btn-primary" onClick={() => navigate(portal.path)}>
      <span style={{ marginLeft: '0.5rem' }}>{portal.icon}</span>
      {portal.label}
    </button>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
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
  }, [user?.role])

  const loadAll = async () => {
    setLoadError(null)
    setDebugCount(null)
    const isAdmin = user?.role === 'admin'
    const isAdminOrStaff = isAdmin || user?.role === 'staff'
    try {
      // فقط برای ادمین/کارمند: آمار و لاگ و فرایندها را بگیر؛ کاربر غیرادمین این APIها را ندارد
      if (isAdminOrStaff) {
        const [statsRes, auditRes, processRes] = await Promise.all([
          dashboardApi.stats(),
          isAdmin ? auditApi.list({ limit: 8, offset: 0 }) : Promise.resolve({ data: { logs: [] } }),
          isAdmin ? processApi.list() : Promise.resolve({ data: [] }),
        ])
        setStats(statsRes.data)
        setRecentLogs(auditRes.data?.logs || [])
        setProcesses(Array.isArray(processRes?.data) ? processRes.data : [])
      } else {
        setStats(null)
        setRecentLogs([])
        setProcesses([])
      }
    } catch (err) {
      console.error('Failed to load dashboard:', err)
      setLoadError(err.response?.status === 401 ? 'لطفاً دوباره وارد شوید' : 'خطا در بارگذاری داشبورد')
      setStats(null)
      setProcesses([])
      setRecentLogs([])
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

      {/* کارت‌های آمار فقط برای ادمین و کارمند نمایش داده می‌شود */}
      {(user?.role === 'admin' || user?.role === 'staff') && (
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
      )}

      <div className="dashboard-grid">
        {/* برای ادمین: فرایندهای SOP | برای بقیه: کارت مرتبط با نقش کاربر */}
        {user?.role === 'admin' ? (
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
        ) : (
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">مربوط به شما</h3>
            </div>
            <div style={{ padding: '1.25rem' }}>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.95rem' }}>
                برای مشاهده فرایندها، کارتابل و کارهای مرتبط با نقش خود به پنل اختصاصی‌تان بروید.
              </p>
              <PortalQuickLink role={user?.role} navigate={navigate} />
            </div>
          </div>
        )}

        {/* فعالیت‌های اخیر فقط برای ادمین (دسترسی به audit) */}
        {user?.role === 'admin' && (
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
        )}
      </div>

      {/* دسترسی سریع: برای همه نمایش داده می‌شود؛ دکمه‌ها بر اساس نقش کاربر فیلتر می‌شوند */}
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
          {user?.role === 'admin' && (
            <button className="quick-action-btn" onClick={() => navigate('/panel/processes')}>
              <span className="quick-action-icon">⚙️</span>
              <span>مدیریت فرایندها</span>
            </button>
          )}
          {(user?.role === 'admin' || user?.role === 'staff') && (
            <button className="quick-action-btn" onClick={() => navigate('/panel/students')}>
              <span className="quick-action-icon">👨‍🎓</span>
              <span>ردیابی دانشجو</span>
            </button>
          )}
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
