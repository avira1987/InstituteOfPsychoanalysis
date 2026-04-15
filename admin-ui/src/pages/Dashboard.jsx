import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { dashboardApi } from '../services/api'
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
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [debugCount, setDebugCount] = useState(null)

  useEffect(() => {
    loadAll()
  }, [user?.role])

  const loadAll = async () => {
    setLoadError(null)
    setDebugCount(null)
    const isAdminOrStaff = user?.role === 'admin' || user?.role === 'staff'
    try {
      // فقط برای ادمین/کارمند: آمار را بگیر؛ کاربر غیرادمین این API را ندارد
      if (!isAdminOrStaff) {
        setStats(null)
        return
      }
      const settled = await Promise.allSettled([dashboardApi.stats()])
      const failedLabels = []
      if (settled[0].status === 'fulfilled') {
        setStats(settled[0].value.data)
      } else {
        setStats(null)
        failedLabels.push('آمار کلی')
        console.error('dashboard stats failed:', settled[0].reason)
      }
      if (failedLabels.length > 0) {
        const first = settled.find((s) => s.status === 'rejected')?.reason
        const status = first?.response?.status
        const detail = first?.response?.data?.detail
        const hint =
          status === 401
            ? 'لطفاً دوباره وارد شوید'
            : detail
              ? `${failedLabels.join('، ')}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`
              : `بارگذاری نشد: ${failedLabels.join('، ')}`
        setLoadError(hint)
        try {
          const d = await dashboardApi.debugProcessCount()
          setDebugCount(d.process_count)
        } catch (_) {}
      }
    } catch (err) {
      console.error('Failed to load dashboard:', err)
      setLoadError(err.response?.status === 401 ? 'لطفاً دوباره وارد شوید' : 'خطا در بارگذاری داشبورد')
      setStats(null)
      try {
        const d = await dashboardApi.debugProcessCount()
        setDebugCount(d.process_count)
      } catch (_) {}
    } finally {
      setLoading(false)
    }
  }

  const quickActions = useMemo(() => {
    const u = user?.role
    const items = []
    if (u === 'student') {
      items.push({ key: 'student', icon: '🎓', label: 'پنل دانشجو', hint: 'پرونده، فرایندها و تکالیف', onClick: () => navigate('/panel/portal/student') })
    }
    if (u === 'therapist' || u === 'admin') {
      items.push({ key: 'therapist', icon: '💊', label: 'پنل درمانگر', hint: 'جلسات و پرونده‌های درمانی', onClick: () => navigate('/panel/portal/therapist') })
    }
    if (u === 'supervisor' || u === 'admin') {
      items.push({ key: 'supervisor', icon: '👁️', label: 'پنل سوپروایزر', hint: 'سوپرویژن و بازخورد', onClick: () => navigate('/panel/portal/supervisor') })
    }
    if (u === 'staff' || u === 'admin') {
      items.push({ key: 'staff', icon: '🏢', label: 'پنل کارمند', hint: 'کارتابل و امور اداری', onClick: () => navigate('/panel/portal/staff') })
    }
    if (u === 'site_manager' || u === 'admin') {
      items.push({ key: 'site', icon: '🏗️', label: 'پنل مسئول سایت', hint: 'هماهنگی و برنامه‌ریزی', onClick: () => navigate('/panel/portal/site-manager') })
    }
    if (['progress_committee', 'education_committee', 'supervision_committee', 'specialized_commission', 'therapy_committee_chair', 'therapy_committee_executor', 'deputy_education', 'monitoring_committee_officer', 'admin'].includes(u)) {
      items.push({ key: 'committee', icon: '📋', label: 'پنل کمیته', hint: 'جلسات و تصمیمات کمیته', onClick: () => navigate('/panel/portal/committee') })
    }
    if (u === 'admin' || u === 'staff') {
      items.push({ key: 'students', icon: '👨‍🎓', label: 'ردیابی دانشجو', hint: 'جستجو و وضعیت دانشجویان', onClick: () => navigate('/panel/students') })
      items.push({
        key: 'reports-hub',
        icon: '📈',
        label: 'گزارشات',
        hint: 'چارچوب گزارش‌ها و قواعد رسمی',
        onClick: () => navigate('/panel/reports'),
      })
    }
    if (u === 'admin') {
      items.push({ key: 'users', icon: '👥', label: 'مدیریت کاربران', hint: 'نقش‌ها و دسترسی‌ها', onClick: () => navigate('/panel/users') })
    }
    items.push({ key: 'profile', icon: '👤', label: 'پروفایل من', hint: 'اطلاعات شخصی و عکس', onClick: () => navigate('/panel/profile') })
    items.push({ key: 'guide', icon: '📖', label: 'راهنمای جامع', hint: 'آموزش گام‌به‌گام سامانه', onClick: () => navigate('/panel/guide') })
    return items
  }, [user?.role, navigate])

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
        <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
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

      {user?.role !== 'admin' && (
        <div className="dashboard-grid">
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
        </div>
      )}

      {/* دسترسی سریع: برای همه نمایش داده می‌شود؛ دکمه‌ها بر اساس نقش کاربر فیلتر می‌شوند */}
      <div className="card" style={{ marginTop: '1.5rem' }}>
        <div className="card-header">
          <div>
            <h3 className="card-title">دسترسی سریع</h3>
            <p className="card-subtitle">میانبرهای پرکاربرد بر اساس نقش شما</p>
          </div>
        </div>
        <div className="quick-actions-grid">
          {quickActions.map((a) => (
            <button key={a.key} type="button" className="quick-action-btn" onClick={a.onClick}>
              <span className="quick-action-icon">{a.icon}</span>
              <span className="quick-action-label">{a.label}</span>
              <span className="quick-action-hint">{a.hint}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
