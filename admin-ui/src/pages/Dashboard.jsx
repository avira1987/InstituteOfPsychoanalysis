import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { dashboardApi, processApi, auditApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [processes, setProcesses] = useState([])
  const [recentLogs, setRecentLogs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    try {
      const [statsRes, procRes, logsRes] = await Promise.all([
        dashboardApi.stats(),
        processApi.list(),
        auditApi.list({ limit: 8, offset: 0 }),
      ])
      setStats(statsRes.data)
      setProcesses(procRes.data)
      setRecentLogs(logsRes.data.logs || [])
    } catch (err) {
      console.error('Failed to load dashboard:', err)
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
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/processes')}>
              مدیریت
            </button>
          </div>
          <div>
            {loading ? (
              <div className="empty-state" style={{ padding: '2rem' }}>در حال بارگذاری...</div>
            ) : processes.length === 0 ? (
              <div className="empty-state" style={{ padding: '2rem' }}>فرایندی تعریف نشده</div>
            ) : (
              processes.map((p) => (
                <div key={p.id} className="dashboard-process-item" onClick={() => navigate(`/processes/${p.id}`)}>
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
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/audit')}>
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
          <button className="quick-action-btn" onClick={() => navigate('/processes')}>
            <span className="quick-action-icon">⚙️</span>
            <span>مدیریت فرایندها</span>
          </button>
          <button className="quick-action-btn" onClick={() => navigate('/rules')}>
            <span className="quick-action-icon">📋</span>
            <span>مدیریت قوانین</span>
          </button>
          <button className="quick-action-btn" onClick={() => navigate('/students')}>
            <span className="quick-action-icon">👨‍🎓</span>
            <span>ردیابی دانشجو</span>
          </button>
          <button className="quick-action-btn" onClick={() => navigate('/audit')}>
            <span className="quick-action-icon">📝</span>
            <span>گزارش حسابرسی</span>
          </button>
          {user?.role === 'admin' && (
            <button className="quick-action-btn" onClick={() => navigate('/users')}>
              <span className="quick-action-icon">👥</span>
              <span>مدیریت کاربران</span>
            </button>
          )}
          <button className="quick-action-btn" onClick={() => navigate('/guide')}>
            <span className="quick-action-icon">📖</span>
            <span>راهنمای جامع</span>
          </button>
        </div>
      </div>
    </div>
  )
}
