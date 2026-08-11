import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { getAvatarUrl, panelApi, dynamicFormsApi } from '../services/api'
import NotificationBell from './NotificationBell'
import { getSiteLogoUrl } from '../utils/siteLogo'
import { navItemsForRoles } from '../utils/portalRoleNav'
import { mapProcessNavItemsFromApi, PROCESS_NAV_PATH_PREFIX } from '../utils/processNavLinks'
import ProcessNavSidebarSection from './ProcessNavSidebarSection'
import SidebarNavGroups, { SidebarFooterNavLinks } from './SidebarNavGroups'
import { PANEL_NOTIFICATIONS_CHANGED_EVENT } from '../utils/panelNotifications'
import { labelRoleFa } from '../utils/roleLabels'
import { normalizeNavPath, resolveActiveSidebarNavPath } from '../utils/sidebarNavActive'
import { groupSidebarNavItems, inferSidebarGroupId } from '../utils/sidebarNavGroups'
import { getUserRoles, primaryRole } from '../utils/userRoles'

const SIDEBAR_WIDTH_KEY = 'anistito.sidebarWidth'
const SIDEBAR_WIDTH_DEFAULT = 272
const SIDEBAR_WIDTH_MIN = 200
const SIDEBAR_WIDTH_MAX = 480

function readStoredSidebarWidth() {
  try {
    const raw = localStorage.getItem(SIDEBAR_WIDTH_KEY)
    const n = Number(raw)
    if (Number.isFinite(n) && n >= SIDEBAR_WIDTH_MIN && n <= SIDEBAR_WIDTH_MAX) return n
  } catch {
    /* ignore */
  }
  return SIDEBAR_WIDTH_DEFAULT
}

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const sidebarNavRef = useRef(null)
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(readStoredSidebarWidth)
  const [isResizingSidebar, setIsResizingSidebar] = useState(false)
  const [navPendingByPath, setNavPendingByPath] = useState({})
  const [dynamicNavItems, setDynamicNavItems] = useState([])
  const [dynamicNavMergeMode, setDynamicNavMergeMode] = useState('append')
  const [processNavItems, setProcessNavItems] = useState([])

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
        .map((it) => {
          const path = String(it.path).startsWith('/')
            ? it.path
            : `/panel/${String(it.path).replace(/^\//, '')}`
          return {
            path,
            label: it.label,
            icon: it.icon || '📎',
            priority: typeof it.priority === 'number' ? it.priority : 55,
            roles: it.roles,
            strictRoles: false,
            groupId: it.groupId || inferSidebarGroupId(path),
          }
        })
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
      const mapped = mapProcessNavItemsFromApi(res.data?.items || [], getUserRoles(user))
      setProcessNavItems(mapped)
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
    const userRoles = getUserRoles(user)
    const filtered = navItemsForRoles(userRoles)
    const dyn = dynamicNavItems.filter((item) => {
      if (!item.roles || !Array.isArray(item.roles) || item.roles.length === 0) return true
      return item.roles.some((r) => userRoles.includes(r)) || userRoles.includes('admin')
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
  }, [user, dynamicNavItems, dynamicNavMergeMode, processNavItems])

  const footerNavItems = useMemo(
    () => groupSidebarNavItems(visibleNav).footerItems,
    [visibleNav],
  )

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

  const closeMobile = () => setMobileOpen(false)

  const clampSidebarWidth = useCallback((w) => {
    const maxForViewport = typeof window !== 'undefined'
      ? Math.min(SIDEBAR_WIDTH_MAX, Math.floor(window.innerWidth * 0.55))
      : SIDEBAR_WIDTH_MAX
    return Math.min(maxForViewport, Math.max(SIDEBAR_WIDTH_MIN, Math.round(w)))
  }, [])

  const onSidebarResizeStart = useCallback((e) => {
    if (typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches) return
    e.preventDefault()
    setIsResizingSidebar(true)
    const startX = e.clientX
    const startWidth = sidebarWidth

    const onMove = (ev) => {
      // سایدبار در RTL سمت راست است؛ کشیدن به چپ = پهن‌تر، به راست = باریک‌تر
      const next = clampSidebarWidth(startWidth + (startX - ev.clientX))
      setSidebarWidth(next)
    }
    const onUp = () => {
      setIsResizingSidebar(false)
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [clampSidebarWidth, sidebarWidth])

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth))
    } catch {
      /* ignore */
    }
  }, [sidebarWidth])

  return (
    <div
      className={`layout${isResizingSidebar ? ' layout-sidebar-resizing' : ''}`}
      style={{ '--sidebar-width': `${sidebarWidth}px` }}
    >
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <button
          type="button"
          className="sidebar-resize-handle"
          aria-label="تغییر عرض منو"
          title="کشیدن برای تغییر عرض"
          onMouseDown={onSidebarResizeStart}
        />
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
          <SidebarNavGroups
            items={visibleNav}
            activeNavPath={activeNavPath}
            navPendingByPath={navPendingByPath}
            onNavigate={closeMobile}
          />

          {processNavItems.length > 0 && (
            <ProcessNavSidebarSection
              items={processNavItems}
              activeNavPath={activeNavPath}
              navPendingByPath={navPendingByPath}
              onNavigate={closeMobile}
            />
          )}
        </nav>

        <div className="sidebar-footer">
          <SidebarFooterNavLinks
            items={footerNavItems}
            activeNavPath={activeNavPath}
            navPendingByPath={navPendingByPath}
            onNavigate={closeMobile}
          />
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
                <div className="sidebar-user-role">
                  {getUserRoles(user).map((r) => labelRoleFa(r, { includeCode: false })).join('، ') || labelRoleFa(primaryRole(user))}
                </div>
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
