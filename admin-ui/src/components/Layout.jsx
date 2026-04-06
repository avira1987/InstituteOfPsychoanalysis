import React, { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { getAvatarUrl } from '../services/api'

const navItems = [
  { path: '/panel', label: 'داشبورد', icon: '📊' },
  { path: '/panel/profile', label: 'پروفایل من', icon: '👤' },
  { path: '/panel/portal/student', label: 'پنل دانشجو', icon: '🎓', roles: ['student'], strictRoles: true },
  { path: '/panel/portal/therapist', label: 'پنل درمانگر', icon: '💊', roles: ['therapist', 'admin'] },
  { path: '/panel/portal/supervisor', label: 'پنل سوپروایزر', icon: '👁️', roles: ['supervisor', 'admin'] },
  { path: '/panel/portal/staff', label: 'پنل کارمند', icon: '🏢', roles: ['staff', 'admin'] },
  { path: '/panel/portal/site-manager', label: 'پنل مسئول سایت', icon: '🏗️', roles: ['site_manager', 'admin'] },
  { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋', roles: [
    'progress_committee', 'education_committee', 'supervision_committee',
    'specialized_commission', 'therapy_committee_chair', 'therapy_committee_executor',
    'deputy_education', 'monitoring_committee_officer', 'admin',
  ]},
  { path: '/panel/processes', label: 'مدیریت فرایندها', icon: '⚙️', roles: ['admin', 'staff'] },
  { path: '/panel/rules', label: 'مدیریت قوانین', icon: '📋', roles: ['admin'] },
  { path: '/panel/students', label: 'ردیابی دانشجو', icon: '👨‍🎓', roles: ['admin', 'staff', 'supervisor', 'therapist'] },
  { path: '/panel/users', label: 'مدیریت کاربران', icon: '👥', roles: ['admin', 'staff'] },
  { path: '/panel/audit', label: 'گزارش حسابرسی', icon: '📝', roles: ['admin', 'staff'] },
  { path: '/panel/finance', label: 'داشبورد مالی', icon: '💵', roles: ['admin', 'finance'] },
  { path: '/panel/guide', label: 'راهنمای جامع', icon: '📖' },
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
}

export default function Layout() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const visibleNav = navItems.filter((item) => {
    if (item.adminOnly && user?.role !== 'admin') return false
    if (item.roles) {
      const inRole = item.roles.includes(user?.role)
      if (item.strictRoles) return inRole
      if (!inRole && user?.role !== 'admin') return false
    }
    return true
  })

  return (
    <div className="layout">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <div className="sidebar-brand-mark" aria-hidden="true">ا</div>
          <div className="sidebar-brand-text">
            <h1 className="sidebar-brand-title">انیستیتو روانکاوری تهران</h1>
            <p className="sidebar-brand-sub">Tehran Institute of Psychoanalysis</p>
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="منوی اصلی">
          {visibleNav.map((item) => (
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
              <span className="sidebar-link-label">{item.label}</span>
            </NavLink>
          ))}
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
          <span className="mobile-title">انیستیتو روانکاوری تهران</span>
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
