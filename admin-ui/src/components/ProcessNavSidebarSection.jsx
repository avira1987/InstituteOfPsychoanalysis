import React, { useEffect, useMemo, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { normalizeNavPath } from '../utils/sidebarNavActive'
import {
  defaultProcessNavCategoryOpen,
  defaultProcessNavSectionOpen,
  filterAndGroupProcessNavItems,
} from '../utils/processNavCategories'

/**
 * @param {{
 *   items: Array<object>,
 *   activeNavPath: string | null,
 *   navPendingByPath: Record<string, number>,
 *   onNavigate: () => void,
 *   collapseByDefault?: boolean,
 * }} props
 */
export default function ProcessNavSidebarSection({
  items,
  activeNavPath,
  navPendingByPath,
  onNavigate,
  collapseByDefault = false,
}) {
  const [open, setOpen] = useState(() => defaultProcessNavSectionOpen(items, { collapseByDefault }))
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryOpen, setCategoryOpen] = useState({})

  const grouped = useMemo(
    () => filterAndGroupProcessNavItems(items, searchQuery),
    [items, searchQuery],
  )

  const filteredCount = useMemo(
    () => grouped.reduce((sum, g) => sum + g.items.length, 0),
    [grouped],
  )

  useEffect(() => {
    if (collapseByDefault) return
    if (items.length === 0) return
    setOpen(defaultProcessNavSectionOpen(items, { collapseByDefault }))
  }, [items, collapseByDefault])

  useEffect(() => {
    setCategoryOpen((prev) => {
      const defaults = defaultProcessNavCategoryOpen(grouped)
      const next = { ...defaults }
      for (const id of Object.keys(prev)) {
        if (id in next) next[id] = prev[id]
      }
      return next
    })
  }, [grouped])

  useEffect(() => {
    if (!activeNavPath) return
    const activeItem = items.find((it) => normalizeNavPath(it.path) === activeNavPath)
    if (!activeItem) return
    const activeGroup = grouped.find((g) =>
      g.items.some((it) => normalizeNavPath(it.path) === activeNavPath),
    )
    if (activeGroup) {
      setOpen(true)
      setCategoryOpen((prev) => ({ ...prev, [activeGroup.id]: true }))
    }
  }, [activeNavPath, items, grouped])

  if (items.length === 0) return null

  const searching = searchQuery.trim().length > 0

  return (
    <div className="sidebar-process-group">
      <button
        type="button"
        className="sidebar-process-group-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="sidebar-link-icon" aria-hidden="true">📋</span>
        <span className="sidebar-link-label">فرایندها</span>
        <span className="sidebar-process-group-count">
          {(searching ? filteredCount : items.length).toLocaleString('fa-IR')}
        </span>
        <span className="sidebar-process-group-chevron" aria-hidden="true">
          {open ? '▾' : '◂'}
        </span>
      </button>

      {open && (
        <div className="sidebar-process-panel">
          <label className="sidebar-process-search-wrap">
            <span className="visually-hidden">جستجو در فرایندها</span>
            <span className="sidebar-process-search-icon" aria-hidden="true">🔍</span>
            <input
              type="search"
              className="sidebar-process-search"
              placeholder="جستجو در فرایندها…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setSearchQuery('')
              }}
            />
            {searchQuery ? (
              <button
                type="button"
                className="sidebar-process-search-clear"
                onClick={() => setSearchQuery('')}
                aria-label="پاک کردن جستجو"
              >
                ×
              </button>
            ) : null}
          </label>

          {filteredCount === 0 ? (
            <p className="sidebar-process-empty">فرایندی با این عبارت یافت نشد.</p>
          ) : (
            grouped.map((group) => {
              const isGroupOpen = searching || categoryOpen[group.id] !== false
              return (
                <div key={group.id} className="sidebar-process-category">
                  <button
                    type="button"
                    className="sidebar-process-category-toggle"
                    onClick={() => {
                      if (searching) return
                      setCategoryOpen((prev) => ({
                        ...prev,
                        [group.id]: !isGroupOpen,
                      }))
                    }}
                    aria-expanded={isGroupOpen}
                    title={group.hint}
                  >
                    <span className="sidebar-process-category-label">{group.label}</span>
                    <span className="sidebar-process-category-count">
                      {group.items.length.toLocaleString('fa-IR')}
                    </span>
                    {!searching ? (
                      <span className="sidebar-process-category-chevron" aria-hidden="true">
                        {isGroupOpen ? '▾' : '◂'}
                      </span>
                    ) : null}
                  </button>

                  {isGroupOpen && group.items.map((item) => {
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
                  })}
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}
