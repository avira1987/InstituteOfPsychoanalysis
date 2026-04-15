import React, { useState, useEffect, useCallback } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { getAvatarUrl, panelApi } from '../services/api'
import { getSiteLogoUrl } from '../utils/siteLogo'

/** priority: کمتر = پراستفاده‌تر (مرتب‌سازی منو)؛ پروفایل و راهنما همیشه انتهای لیست */
const navItems = [
  { path: '/panel', label: 'داشبورد', icon: '📊', priority: 10 },
  { path: '/panel/portal/student', label: 'پنل دانشجو', icon: '🎓', roles: ['student'], strictRoles: true, priority: 20 },
  { path: '/panel/portal/therapist', label: 'پنل درمانگر', icon: '💊', roles: ['therapist', 'admin'], priority: 21 },
  { path: '/panel/portal/supervisor', label: 'پنل سوپروایزر', icon: '👁️', roles: ['supervisor', 'admin'], priority: 22 },
  { path: '/panel/portal/interviewer', label: 'پنل مصاحبه‌گر', icon: '🎤', roles: ['interviewer', 'admin'], priority: 22 },
  { path: '/panel/portal/staff', label: 'پنل کارمند', icon: '🏢', roles: ['staff', 'admin'], priority: 23 },
  { path: '/panel/portal/site-manager', label: 'پنل مسئول سایت', icon: '🏗️', roles: ['site_manager', 'admin'], priority: 24 },
  { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋', roles: [
    'progress_committee', 'education_committee', 'supervision_committee',
    'specialized_commission', 'therapy_committee_chair', 'therapy_committee_executor',
    'deputy_education', 'monitoring_committee_officer', 'admin',
  ], priority: 25 },
  { path: '/panel/tickets', label: 'تیکت‌ها و درخواست‌ها', icon: '🎫', roles: [
    'student',
    'admin', 'staff', 'finance', 'therapist', 'supervisor', 'site_manager', 'interviewer',
    'progress_committee', 'education_committee', 'supervision_committee',
    'specialized_commission', 'therapy_committee_chair', 'therapy_committee_executor',
    'deputy_education', 'monitoring_committee_officer',
  ], priority: 35 },
  { path: '/panel/students', label: 'ردیابی دانشجو', icon: '👨‍🎓', roles: ['admin', 'staff', 'supervisor', 'therapist'], priority: 40 },
  {
    path: '/panel/reports',
    label: 'گزارشات',
    icon: '📈',
    roles: ['admin', 'staff', 'deputy_education', 'monitoring_committee_officer', 'finance'],
    priority: 42,
  },
  { path: '/panel/users', label: 'مدیریت کاربران', icon: '👥', roles: ['admin', 'staff'], priority: 44 },
  { path: '/panel/audit', label: 'گزارش حسابرسی', icon: '📝', roles: ['admin', 'staff'], priority: 46 },
  { path: '/panel/processes', label: 'مدیریت فرایندها', icon: '🔄', roles: ['admin', 'staff'], priority: 47 },
  { path: '/panel/rules', label: 'مدیریت قوانین', icon: '📋', roles: ['admin'], priority: 48 },
  { path: '/panel/finance', label: 'داشبورد مالی', icon: '💵', roles: ['admin', 'finance'], priority: 50 },
  { path: '/panel/profile', label: 'پروفایل من', icon: '👤', priority: 85 },
  { path: '/panel/guide', label: 'راهنمای جامع', icon: '📖', priority: 90 },
]

const roleLabels = {
  admin: 'مدیر سیستم',
  staff: 'کارمند دفتر',
  therapist: 'درمانگر',
  student: 'دانشجو',
  supervisor: 'سوپروایزر',
  site_manager: 'مسئول سایت',
  progress_committee: 'کمیته پیشرفت',
  education_committee: 'کمیته آموزش',
  supervision_committee: 'کمیته نظارت',
  specialized_commission: 'کمیسیون تخصصی',
  therapy_committee_chair: 'مسئول کمیته درمان',
  therapy_committee_executor: 'مجری کمیته درمان',
  deputy_education: 'معاون آموزش',
  monitoring_committee_officer: 'مسئول کمیته نظارت',
  finance: 'اپراتور مالی',
  interviewer: 'مصاحبه‌گر',
}

export default function Layout() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [navPendingByPath, setNavPendingByPath] = useState({})

  const loadNavPending = useCallback(async () => {
    if (!user) return
    try {
      const res = await panelApi.navPendingCounts()
      setNavPendingByPath(res.data?.counts || {})
    } catch {
      setNavPendingByPath({})
    }
  }, [user])

  useEffect(() => {
    loadNavPending()
    const t = setInterval(loadNavPending, 60000)
    const onVis = () => {
      if (document.visibilityState === 'visible') loadNavPending()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [loadNavPending])

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const visibleNav = navItems
    .filter((item) => {
      if (item.adminOnly && user?.role !== 'admin') return false
      if (item.roles) {
        const inRole = item.roles.includes(user?.role)
        if (item.strictRoles) return inRole
        if (!inRole && user?.role !== 'admin') return false
      }
      return true
    })
    .sort((a, b) => {
      const pa = a.priority ?? 50
      const pb = b.priority ?? 50
      if (pa !== pb) return pa - pb
      return a.path.localeCompare(b.path)
    })

  return (
    <div className="layout">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <div className="sidebar-brand-mark" aria-hidden="true">
            <img src={getSiteLogoUrl()} alt="" className="site-logo-img" width={44} height={51} />
          </div>
          <div className="sidebar-brand-text">
            <h1 className="sidebar-brand-title">انستیتو روانکاوری تهران</h1>
            <p className="sidebar-brand-sub">Tehran Institute of Psychoanalysis</p>
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="منوی اصلی">
          {visibleNav.map((item) => {
            const raw = navPendingByPath[item.path]
            const n = typeof raw === 'number' && raw > 0 ? raw : 0
            const badge =
              n > 0 ? (n > 99 ? '۹۹+' : n.toLocaleString('fa-IR')) : null
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/panel'}
                className={({ isActive }) =>
                  `sidebar-link ${isActive ? 'active' : ''}`
                }
                onClick={() => setMobileOpen(false)}
              >
                <span className="sidebar-link-icon" aria-hidden="true">{item.icon}</span>
                <span className="sidebar-link-text">
                  <span className="sidebar-link-label">{item.label}</span>
                  {badge != null ? (
                    <span className="sidebar-nav-badge" title="کار منتظر">
                      {badge}
                    </span>
                  ) : null}
                </span>
              </NavLink>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          {user && (
            <div className="sidebar-user-card">
              <div className="sidebar-user-avatar">
                {getAvatarUrl(user.avatar_url) ? (
                  <img src={getAvatarUrl(user.avatar_url)} alt="" />
                ) : (
                  (user.full_name_fa || user.username || '?')[0]
                )}
              </div>
              <div className="sidebar-user-info">
                <div className="sidebar-user-name">{user.full_name_fa || user.username}</div>
                <div className="sidebar-user-role">{roleLabels[user.role] || user.role}</div>
              </div>
            </div>
          )}
          <button type="button" className="sidebar-link sidebar-link-logout" onClick={handleLogout}>
            <span className="sidebar-link-icon" aria-hidden="true">🚪</span>
            <span className="sidebar-link-label">خروج از حساب</span>
          </button>
        </div>
      </aside>

      <main className="main-content">
        {/* Mobile header / top bar */}
        <div className="mobile-header">
          <button className="mobile-menu-btn" onClick={() => setMobileOpen(!mobileOpen)}>
            ☰
          </button>
          <img src={getSiteLogoUrl()} alt="" className="mobile-header-logo site-logo-img" width={32} height={37} />
          <span className="mobile-title">انستیتو روانکاوری تهران</span>
          <button
            className="header-logout-btn"
            onClick={handleLogout}
            title="خروج"
          >
            🚪 خروج
          </button>
        </div>
        <Outlet />
      </main>
    </div>
  )
}
