import React, { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

const DROPDOWN_MAX_H = 220
const DROPDOWN_Z = 10050

function norm(s) {
  return String(s || '').trim().toLowerCase()
}

function optionValue(opt) {
  return typeof opt === 'object' ? opt.value : opt
}

function optionLabel(opt) {
  if (typeof opt === 'object') return opt.label_fa || opt.value || ''
  return String(opt)
}

/**
 * کشویی با جست‌وجو و امکان افزودن مقدار جدید.
 */
export default function CreatableSearchSelect({
  value,
  onChange,
  options = [],
  disabled = false,
  placeholder = 'جست‌وجو یا انتخاب…',
  needsTrack = false,
  needsCourse = false,
  trackHint = 'ابتدا رسته را انتخاب کنید',
  courseHint = 'ابتدا درس را انتخاب کنید',
  allowCreate = true,
  createLabel = (text) => `افزودن «${text}»`,
  createSectionLabel = 'افزودن مورد جدید',
  createInputPlaceholder = 'نام جدید را وارد کنید',
  onCreateNew = null,
  onCreated = null,
  onCreateError = null,
  style,
  minWidth,
  testId,
}) {
  const uid = useId()
  const wrapRef = useRef(null)
  const inputRef = useRef(null)
  const dropdownRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [openUp, setOpenUp] = useState(false)
  const [panelPos, setPanelPos] = useState(null)
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const [extraOptions, setExtraOptions] = useState([])
  const [newEntryDraft, setNewEntryDraft] = useState('')

  const allOptions = useMemo(() => {
    const seen = new Set()
    const out = []
    for (const opt of [...options, ...extraOptions]) {
      const v = String(optionValue(opt))
      if (!v || seen.has(v)) continue
      seen.add(v)
      out.push(opt)
    }
    return out
  }, [options, extraOptions])

  const selectedLabel = useMemo(() => {
    if (!value) return ''
    const hit = allOptions.find((o) => String(optionValue(o)) === String(value))
    return hit ? optionLabel(hit) : String(value)
  }, [allOptions, value])

  useEffect(() => {
    if (!open) setQuery(selectedLabel)
  }, [selectedLabel, open])

  const filtered = useMemo(() => {
    const q = norm(query)
    if (!q) return allOptions
    return allOptions.filter((opt) => norm(optionLabel(opt)).includes(q))
  }, [allOptions, query])

  const updatePanelPosition = useCallback(() => {
    if (!open || !inputRef.current) return
    const r = inputRef.current.getBoundingClientRect()
    const margin = 8
    const spaceBelow = window.innerHeight - r.bottom - margin
    const spaceAbove = r.top - margin
    const maxHeight = Math.min(DROPDOWN_MAX_H, Math.max(spaceBelow, spaceAbove, 100))
    const openUpward = spaceBelow < 140 && spaceAbove > spaceBelow
    setOpenUp(openUpward)
    const top = openUpward
      ? Math.max(margin, r.top - maxHeight - 2)
      : Math.round(r.bottom + 2)
    setPanelPos({
      top,
      left: Math.round(r.left),
      width: Math.round(r.width),
      maxHeight,
    })
  }, [open])

  useLayoutEffect(() => {
    if (!open) {
      setPanelPos(null)
      return
    }
    updatePanelPosition()
    window.addEventListener('resize', updatePanelPosition)
    window.addEventListener('scroll', updatePanelPosition, true)
    return () => {
      window.removeEventListener('resize', updatePanelPosition)
      window.removeEventListener('scroll', updatePanelPosition, true)
    }
  }, [open, updatePanelPosition, filtered.length])

  useLayoutEffect(() => {
    if (!open || !dropdownRef.current) return
    dropdownRef.current.scrollTop = 0
  }, [open, openUp, filtered.length])

  useEffect(() => {
    if (!open) return
    const onDoc = (e) => {
      const t = e.target
      const inWrap = wrapRef.current?.contains(t)
      const inDrop = dropdownRef.current?.contains(t)
      if (!inWrap && !inDrop) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const trimmedQuery = query.trim()
  const canOfferCreate =
    allowCreate &&
    trimmedQuery &&
    !allOptions.some((o) => norm(optionLabel(o)) === norm(trimmedQuery)) &&
    typeof onCreateNew === 'function'

  const pick = (v) => {
    onChange(v)
    setOpen(false)
    setNewEntryDraft('')
  }

  const canCreateName = (name) => {
    const trimmed = (name || '').trim()
    if (!trimmed || !allowCreate || typeof onCreateNew !== 'function') return false
    return !allOptions.some((o) => norm(optionLabel(o)) === norm(trimmed))
  }

  const commitCreate = async (rawName) => {
    const trimmed = (rawName || '').trim()
    if (!canCreateName(trimmed) || creating) return
    setCreating(true)
    try {
      const created = await onCreateNew(trimmed)
      if (created) {
        const opt = typeof created === 'object' ? created : { value: created, label_fa: trimmed }
        setExtraOptions((prev) => [...prev, opt])
        onCreated?.(opt)
        pick(String(optionValue(opt)))
      }
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'افزودن مورد جدید ناموفق بود'
      onCreateError?.(typeof msg === 'string' ? msg : 'افزودن مورد جدید ناموفق بود')
    } finally {
      setCreating(false)
    }
  }

  const handleCreate = () => commitCreate(trimmedQuery)

  const handleCreateFromSection = () => commitCreate(newEntryDraft)

  const showCreateSection = allowCreate && typeof onCreateNew === 'function'

  if (needsTrack || needsCourse) {
    return (
      <input
        type="text"
        className="psf-input form-input"
        disabled
        placeholder={needsCourse ? courseHint : trackHint}
        style={{ minWidth, ...style }}
        data-testid={testId}
      />
    )
  }

  const dropdownList = (
    <>
      {filtered.map((opt) => {
        const v = optionValue(opt)
        const lab = optionLabel(opt)
        const active = String(value) === String(v)
        return (
          <button
            key={String(v)}
            type="button"
            role="option"
            aria-selected={active}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => pick(String(v))}
            style={{
              display: 'block',
              width: '100%',
              textAlign: 'right',
              padding: '0.45rem 0.65rem',
              border: 'none',
              background: active ? '#eff6ff' : 'transparent',
              cursor: 'pointer',
              fontSize: '0.85rem',
              color: '#1e293b',
            }}
          >
            {lab}
          </button>
        )
      })}
      {canOfferCreate && (
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={handleCreate}
          disabled={creating}
          style={{
            display: 'block',
            width: '100%',
            textAlign: 'right',
            padding: '0.45rem 0.65rem',
            border: 'none',
            borderTop: filtered.length ? '1px solid #e5e7eb' : 'none',
            background: '#f0fdf4',
            cursor: creating ? 'wait' : 'pointer',
            fontSize: '0.85rem',
            color: '#15803d',
            fontWeight: 600,
          }}
        >
          {creating ? 'در حال افزودن…' : createLabel(trimmedQuery)}
        </button>
      )}
      {!filtered.length && !canOfferCreate && !showCreateSection && (
        <div style={{ padding: '0.5rem 0.65rem', fontSize: '0.82rem', color: '#64748b' }}>
          موردی یافت نشد
        </div>
      )}
      {showCreateSection && (
        <div
          style={{
            borderTop: '1px solid #e5e7eb',
            padding: '0.5rem 0.65rem',
            background: '#f8fafc',
          }}
          data-testid={testId ? `${testId}-create-section` : undefined}
        >
          <div style={{ fontSize: '0.78rem', color: '#475569', marginBottom: '0.35rem', fontWeight: 600 }}>
            {createSectionLabel}
          </div>
          <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
            <input
              type="text"
              className="psf-input form-input"
              value={newEntryDraft}
              disabled={creating}
              placeholder={createInputPlaceholder}
              onChange={(e) => setNewEntryDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  handleCreateFromSection()
                }
              }}
              style={{ flex: 1, minWidth: 0, fontSize: '0.85rem' }}
              data-testid={testId ? `${testId}-create-input` : undefined}
            />
            <button
              type="button"
              className="btn btn-sm btn-outline"
              disabled={creating || !canCreateName(newEntryDraft)}
              onMouseDown={(e) => e.preventDefault()}
              onClick={handleCreateFromSection}
              data-testid={testId ? `${testId}-create-btn` : undefined}
            >
              {creating ? '…' : 'افزودن'}
            </button>
          </div>
        </div>
      )}
    </>
  )

  const dropdown =
    open && !disabled && panelPos
      ? createPortal(
          <div
            ref={dropdownRef}
            role="listbox"
            style={{
              position: 'fixed',
              top: `${panelPos.top}px`,
              left: `${panelPos.left}px`,
              width: `${panelPos.width}px`,
              maxHeight: `${panelPos.maxHeight}px`,
              overflowY: 'auto',
              zIndex: DROPDOWN_Z,
              background: '#fff',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              boxShadow: '0 8px 20px rgba(15,23,42,0.12)',
              boxSizing: 'border-box',
              display: 'flex',
              flexDirection: openUp ? 'column-reverse' : 'column',
            }}
          >
            {dropdownList}
          </div>,
          document.body,
        )
      : null

  return (
    <div ref={wrapRef} style={{ position: 'relative', minWidth }} data-testid={testId}>
      <input
        ref={inputRef}
        id={uid}
        type="text"
        className="psf-input form-input"
        disabled={disabled || creating}
        placeholder={placeholder}
        value={open ? query : selectedLabel}
        onChange={(e) => {
          setQuery(e.target.value)
          if (!open) setOpen(true)
        }}
        onFocus={() => {
          setOpen(true)
          setQuery(selectedLabel)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && canOfferCreate) {
            e.preventDefault()
            handleCreate()
          }
          if (e.key === 'Escape') setOpen(false)
        }}
        style={{ width: '100%', ...style }}
        autoComplete="off"
      />
      {dropdown}
    </div>
  )
}
