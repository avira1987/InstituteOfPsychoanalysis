import React, { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const navItems = [
  { path: '/', label: 'داشبورد', icon: '📊' },
  { path: '/processes', label: 'مدیریت فرایندها', icon: '⚙️' },
  { path: '/rules', label: 'مدیریت قوانین', icon: '📋' },
  { path: '/students', label: 'ردیابی دانشجو', icon: '👨‍🎓' },
  { path: '/users', label: 'مدیریت کاربران', icon: '👥', adminOnly: true },
  { path: '/audit', label: 'گزارش حسابرسی', icon: '📝' },
  { path: '/guide', label: 'راهنمای جامع', icon: '📖' },
]

const roleLabels = {
  admin: 'مدیر سیستم',
  staff: 'کارمند دفتر',
  therapist: 'درمانگر',
  student: 'دانشجو',
  supervisor: 'سوپروایزر',
  progress_committee: 'کمیته پیشرفت',
}

export default function Layout() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const visibleNav = navItems.filter(
    (item) => !item.adminOnly || user?.role === 'admin'
  )

  return (
    <div className="layout">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-header">
          <h1>انیستیتو روانکاوری تهران</h1>
          <p>Tehran Institute of Psychoanalysis</p>
        </div>
        <nav className="sidebar-nav">
          {visibleNav.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? 'active' : ''}`
              }
              onClick={() => setMobileOpen(false)}
            >
              <span style={{ fontSize: '1.2rem' }}>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* User info */}
        <div className="sidebar-footer">
          {user && (
            <div className="sidebar-user">
              <div className="sidebar-user-avatar">
                {(user.full_name_fa || user.username || '?')[0]}
              </div>
              <div className="sidebar-user-info">
                <div className="sidebar-user-name">{user.full_name_fa || user.username}</div>
                <div className="sidebar-user-role">{roleLabels[user.role] || user.role}</div>
              </div>
            </div>
          )}
          <button className="sidebar-link" onClick={handleLogout} style={{ width: '100%' }}>
            <span style={{ fontSize: '1.2rem' }}>🚪</span>
            <span>خروج</span>
          </button>
        </div>
      </aside>

      <main className="main-content">
        {/* Mobile header */}
        <div className="mobile-header">
          <button className="mobile-menu-btn" onClick={() => setMobileOpen(!mobileOpen)}>
            ☰
          </button>
          <span className="mobile-title">انیستیتو روانکاوری تهران</span>
        </div>
        <Outlet />
      </main>
    </div>
  )
}
