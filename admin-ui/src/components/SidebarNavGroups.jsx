import React, { useEffect, useMemo, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { normalizeNavPath } from '../utils/sidebarNavActive'
import {
  defaultSidebarGroupOpen,
  groupSidebarNavItems,
} from '../utils/sidebarNavGroups'

function formatBadge(raw) {
  const n = typeof raw === 'number' && raw > 0 ? raw : 0
  if (n <= 0) return null
  return n > 99 ? '۹۹+' : n.toLocaleString('fa-IR')
}

function groupPendingTotal(items, navPendingByPath) {
  return (items || []).reduce((sum, item) => {
    const raw = navPendingByPath[item.path]
    const n = typeof raw === 'number' && raw > 0 ? raw : 0
    return sum + n
  }, 0)
}

function SidebarNavLink({ item, activeNavPath, navPendingByPath, onNavigate, nested }) {
  const badge = formatBadge(navPendingByPath[item.path])
  const itemPath = normalizeNavPath(item.path)
  const isItemActive = activeNavPath === itemPath
  return (
    <NavLink
      to={item.path}
      end={item.path === '/panel' || item.path === '/panel/portal/student'}
      aria-current={isItemActive ? 'page' : undefined}
      className={`sidebar-link${nested ? ' sidebar-link-nested' : ''}${isItemActive ? ' active' : ''}`}
      onClick={onNavigate}
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
}

/**
 * @param {{
 *   items: Array<object>,
 *   activeNavPath: string | null,
 *   navPendingByPath: Record<string, number>,
 *   onNavigate: () => void,
 * }} props
 */
export default function SidebarNavGroups({
  items,
  activeNavPath,
  navPendingByPath,
  onNavigate,
}) {
  const { mainGroups } = useMemo(() => groupSidebarNavItems(items), [items])
  const [groupOpen, setGroupOpen] = useState(() => defaultSidebarGroupOpen(mainGroups))

  useEffect(() => {
    setGroupOpen((prev) => {
      const defaults = defaultSidebarGroupOpen(mainGroups)
      const next = { ...defaults }
      for (const id of Object.keys(prev)) {
        if (id in next) next[id] = prev[id]
      }
      for (const g of mainGroups) {
        const pending = groupPendingTotal(g.items, navPendingByPath)
        if (pending > 0) next[g.id] = true
      }
      return next
    })
  }, [mainGroups, navPendingByPath])

  useEffect(() => {
    if (!activeNavPath) return
    const activeGroup = mainGroups.find((g) =>
      g.items.some((it) => normalizeNavPath(it.path) === activeNavPath),
    )
    if (activeGroup) {
      setGroupOpen((prev) => ({ ...prev, [activeGroup.id]: true }))
    }
  }, [activeNavPath, mainGroups])

  if (!mainGroups.length) return null

  return (
    <div className="sidebar-nav-groups">
      {mainGroups.map((group) => {
        const pending = groupPendingTotal(group.items, navPendingByPath)
        const pendingBadge = formatBadge(pending)
        const isSingle = group.items.length === 1

        if (isSingle) {
          return (
            <SidebarNavLink
              key={group.id}
              item={group.items[0]}
              activeNavPath={activeNavPath}
              navPendingByPath={navPendingByPath}
              onNavigate={onNavigate}
            />
          )
        }

        const isOpen = groupOpen[group.id] !== false
        return (
          <div key={group.id} className="sidebar-nav-group">
            <button
              type="button"
              className="sidebar-nav-group-toggle"
              onClick={() => setGroupOpen((prev) => ({ ...prev, [group.id]: !isOpen }))}
              aria-expanded={isOpen}
            >
              <span className="sidebar-link-icon" aria-hidden="true">{group.icon}</span>
              <span className="sidebar-link-label">{group.label}</span>
              {pendingBadge != null ? (
                <span className="sidebar-nav-badge" title="کار منتظر">
                  {pendingBadge}
                </span>
              ) : (
                <span className="sidebar-nav-group-count">
                  {group.items.length.toLocaleString('fa-IR')}
                </span>
              )}
              <span className="sidebar-nav-group-chevron" aria-hidden="true">
                {isOpen ? '▾' : '◂'}
              </span>
            </button>
            {isOpen && (
              <div className="sidebar-nav-group-panel">
                {group.items.map((item) => (
                  <SidebarNavLink
                    key={item.path}
                    item={item}
                    activeNavPath={activeNavPath}
                    navPendingByPath={navPendingByPath}
                    onNavigate={onNavigate}
                    nested
                  />
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/**
 * لینک‌های حساب کاربری برای footer سایدبار
 */
export function SidebarFooterNavLinks({
  items,
  activeNavPath,
  navPendingByPath,
  onNavigate,
}) {
  if (!items?.length) return null
  return (
    <div className="sidebar-footer-nav">
      {items.map((item) => (
        <SidebarNavLink
          key={item.path}
          item={item}
          activeNavPath={activeNavPath}
          navPendingByPath={navPendingByPath}
          onNavigate={onNavigate}
        />
      ))}
    </div>
  )
}
