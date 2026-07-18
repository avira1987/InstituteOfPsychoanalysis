import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { getAvatarUrl, panelApi, dynamicFormsApi } from '../services/api'
import NotificationBell from './NotificationBell'
import { getSiteLogoUrl } from '../utils/siteLogo'
import { navItemsForRole, dedupSemesterPrepNavForProcessNav } from '../utils/portalRoleNav'
import { mapProcessNavItemsFromApi, PROCESS_NAV_PATH_PREFIX } from '../utils/processNavLinks'
import { PANEL_NOTIFICATIONS_CHANGED_EVENT } from '../utils/panelNotifications'
import { labelRoleFa } from '../utils/roleLabels'
import { normalizeNavPath, resolveActiveSidebarNavPath } from '../utils/sidebarNavActive'

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const sidebarNavRef = useRef(null)
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [navPendingByPath, setNavPendingByPath] = useState({})
  const [dynamicNavItems, setDynamicNavItems] = useState([])
  const [dynamicNavMergeMode, setDynamicNavMergeMode] = useState('append')
  const [processNavItems, setProcessNavItems] = useState([])
  const [processNavOpen, setProcessNavOpen] = useState(true)

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

  const loadProcessNav = useCallback(async () => {
    if (!user) {
      setProcessNavItems([])
      return
    }
    try {
      const res = await panelApi.processNavItems()
      const mapped = mapProcessNavItemsFromApi(res.data?.items || [], user.role)
      setProcessNavItems(mapped)
      const hasPending = mapped.some((it) => it.pendingCount > 0)
      setProcessNavOpen(hasPending || mapped.length <= 12)
    } catch {
      setProcessNavItems([])
    }
  }, [user])

  useEffect(() => {
    loadNavPending()
    loadDynamicNav()
    loadProcessNav()
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
  }, [loadNavPending, loadDynamicNav, loadProcessNav])

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const visibleNav = useMemo(() => {
    const processCodes = processNavItems.map((p) => p.processCode)
    const filtered = dedupSemesterPrepNavForProcessNav(
      navItemsForRole(user?.role),
      processCodes,
    )
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
  }, [user?.role, dynamicNavItems, dynamicNavMergeMode, processNavItems])

  const processNavForSidebar = useMemo(
    () => processNavItems.map((item) => ({
      path: item.path,
      label: item.label,
      icon: item.icon,
      priority: item.priority,
      isProcessNav: true,
    })),
    [processNavItems],
  )

  const allNavForActive = useMemo(
    () => [...visibleNav, ...processNavForSidebar],
    [visibleNav, processNavForSidebar],
  )

  const activeNavPath = useMemo(() => {
    const processCode = new URLSearchParams(location.search).get('process_code')
    if (processCode) {
      const processPath = normalizeNavPath(`${PROCESS_NAV_PATH_PREFIX}${processCode}`)
      if (allNavForActive.some((n) => normalizeNavPath(n.path) === processPath)) {
        return processPath
      }
    }
    return resolveActiveSidebarNavPath(allNavForActive, location.pathname)
  }, [allNavForActive, location.pathname, location.search])

  const activeNavLabel = useMemo(() => {
    if (!activeNavPath) return null
    const item = allNavForActive.find((nav) => normalizeNavPath(nav.path) === activeNavPath)
    return item?.label || null
  }, [activeNavPath, allNavForActive])

  useEffect(() => {
    const nav = sidebarNavRef.current
    if (!nav || !activeNavPath) return
    const activeEl = nav.querySelector('.sidebar-link.active')
    if (activeEl && typeof activeEl.scrollIntoView === 'function') {
      activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [activeNavPath, location.pathname])

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
        <nav className="sidebar-nav" ref={sidebarNavRef} aria-label="منوی اصلی">
          {visibleNav.map((item, idx) => {
            const raw = navPendingByPath[item.path]
            const n = typeof raw === 'number' && raw > 0 ? raw : 0
            const badge =
              n > 0 ? (n > 99 ? '۹۹+' : n.toLocaleString('fa-IR')) : null
            const itemPath = normalizeNavPath(item.path)
            const isItemActive = activeNavPath === itemPath
            return (
              <NavLink
                key={`${item.path}-${idx}`}
                to={item.path}
                end={item.path === '/panel' || item.path === '/panel/portal/student'}
                aria-current={isItemActive ? 'page' : undefined}
                className={`sidebar-link${isItemActive ? ' active' : ''}`}
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

          {processNavForSidebar.length > 0 && (
            <div className="sidebar-process-group">
              <button
                type="button"
                className="sidebar-process-group-toggle"
                onClick={() => setProcessNavOpen((v) => !v)}
                aria-expanded={processNavOpen}
              >
                <span className="sidebar-link-icon" aria-hidden="true">📋</span>
                <span className="sidebar-link-label">فرایندها</span>
                <span className="sidebar-process-group-count">
                  {processNavForSidebar.length.toLocaleString('fa-IR')}
                </span>
                <span className="sidebar-process-group-chevron" aria-hidden="true">
                  {processNavOpen ? '▾' : '◂'}
                </span>
              </button>
              {processNavOpen && processNavForSidebar.map((item) => {
                const raw = navPendingByPath[item.path]
                const n = typeof raw === 'number' && raw > 0 ? raw : 0
                const badge =
                  n > 0 ? (n > 99 ? '۹۹+' : n.toLocaleString('fa-IR')) : null
                const itemPath = normalizeNavPath(item.path)
                const isItemActive = activeNavPath === itemPath
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    aria-current={isItemActive ? 'page' : undefined}
                    className={`sidebar-link sidebar-link-nested${isItemActive ? ' active' : ''}`}
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
            </div>
          )}
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
                <div className="sidebar-user-role">{labelRoleFa(user.role)}</div>
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
          <span className="mobile-title">{activeNavLabel || 'انستیتو روانکاوری تهران'}</span>
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
