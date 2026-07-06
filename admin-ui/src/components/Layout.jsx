import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { getAvatarUrl, panelApi, dynamicFormsApi } from '../services/api'
import NotificationBell from './NotificationBell'
import { getSiteLogoUrl } from '../utils/siteLogo'
import { navItemsForRole } from '../utils/portalRoleNav'
import { PANEL_NOTIFICATIONS_CHANGED_EVENT } from '../utils/panelNotifications'

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
  const [dynamicNavItems, setDynamicNavItems] = useState([])
  const [dynamicNavMergeMode, setDynamicNavMergeMode] = useState('append')

  const loadNavPending = useCallback(async () => {
    if (!user) return
    try {
      const res = await panelApi.navPendingCounts()
      setNavPendingByPath(res.data?.counts || {})
    } catch {
      setNavPendingByPath({})
    }
  }, [user])

  const loadDynamicNav = useCallback(async () => {
    if (!user) {
      setDynamicNavItems([])
      return
    }
    try {
      const res = await dynamicFormsApi.getPortalNavDynamic()
      const raw = res.data?.items
      const mode = res.data?.merge_mode || 'append'
      setDynamicNavMergeMode(mode)
      if (!Array.isArray(raw)) {
        setDynamicNavItems([])
        return
      }
      const mapped = raw
        .filter((it) => it && it.path && it.label)
        .map((it) => ({
          path: String(it.path).startsWith('/') ? it.path : `/panel/${String(it.path).replace(/^\//, '')}`,
          label: it.label,
          icon: it.icon || '📎',
          priority: typeof it.priority === 'number' ? it.priority : 55,
          roles: it.roles,
          strictRoles: false,
        }))
      setDynamicNavItems(mapped)
    } catch {
      setDynamicNavItems([])
    }
  }, [user])

  useEffect(() => {
    loadNavPending()
    loadDynamicNav()
    const t = setInterval(loadNavPending, 60000)
    const onVis = () => {
      if (document.visibilityState === 'visible') loadNavPending()
    }
    const onNotifChanged = () => loadNavPending()
    document.addEventListener('visibilitychange', onVis)
    window.addEventListener(PANEL_NOTIFICATIONS_CHANGED_EVENT, onNotifChanged)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener(PANEL_NOTIFICATIONS_CHANGED_EVENT, onNotifChanged)
    }
  }, [loadNavPending, loadDynamicNav])

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const visibleNav = useMemo(() => {
    const filtered = navItemsForRole(user?.role)
    const dyn = dynamicNavItems.filter((item) => {
      if (!item.roles || !Array.isArray(item.roles) || item.roles.length === 0) return true
      return item.roles.includes(user?.role) || user?.role === 'admin'
    })
    let merged
    if (dynamicNavMergeMode === 'replace') {
      // منوی داینامیک فقط جایگزین آیتم‌های هم‌مسیر می‌شود؛ منوی اصلی (داشبورد، اتوماسیون، …) حفظ می‌ماند
      if (dyn.length > 0) {
        const dynPaths = new Set(dyn.map((d) => d.path))
        merged = [...filtered.filter((f) => !dynPaths.has(f.path)), ...dyn]
      } else {
        merged = [...filtered]
      }
    } else if (dynamicNavMergeMode === 'prepend') {
      merged = [...dyn, ...filtered]
    } else {
      merged = [...filtered, ...dyn]
    }
    return merged.sort((a, b) => {
      const pa = a.priority ?? 50
      const pb = b.priority ?? 50
      if (pa !== pb) return pa - pb
      return a.path.localeCompare(b.path)
    })
  }, [user?.role, dynamicNavItems, dynamicNavMergeMode])

  return (
    <div className="layout">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <div className="sidebar-brand-row">
            <div className="sidebar-brand-main">
              <div className="sidebar-brand-mark" aria-hidden="true">
                <img src={getSiteLogoUrl()} alt="" className="site-logo-img" width={44} height={51} />
              </div>
              <div className="sidebar-brand-text">
                <h1 className="sidebar-brand-title">انستیتو روانکاوری تهران</h1>
                <p className="sidebar-brand-sub">Tehran Institute of Psychoanalysis</p>
              </div>
            </div>
            <NotificationBell variant="sidebar" />
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="منوی اصلی">
          {visibleNav.map((item, idx) => {
            const raw = navPendingByPath[item.path]
            const n = typeof raw === 'number' && raw > 0 ? raw : 0
            const badge =
              n > 0 ? (n > 99 ? '۹۹+' : n.toLocaleString('fa-IR')) : null
            return (
              <NavLink
                key={`${item.path}-${idx}`}
                to={item.path}
                end={item.path === '/panel' || item.path === '/panel/portal/student'}
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
          <NotificationBell variant="mobile" />
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
