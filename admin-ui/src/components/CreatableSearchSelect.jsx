import React, { useEffect, useId, useMemo, useRef, useState } from 'react'

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
  trackHint = 'ابتدا رسته را انتخاب کنید',
  allowCreate = true,
  createLabel = (text) => `افزودن «${text}»`,
  onCreateNew = null,
  style,
  minWidth,
  testId,
}) {
  const uid = useId()
  const wrapRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const [extraOptions, setExtraOptions] = useState([])

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

  useEffect(() => {
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const filtered = useMemo(() => {
    const q = norm(query)
    if (!q) return allOptions
    return allOptions.filter((opt) => norm(optionLabel(opt)).includes(q))
  }, [allOptions, query])

  const trimmedQuery = query.trim()
  const canOfferCreate =
    allowCreate &&
    trimmedQuery &&
    !allOptions.some((o) => norm(optionLabel(o)) === norm(trimmedQuery)) &&
    typeof onCreateNew === 'function'

  const pick = (v) => {
    onChange(v)
    setOpen(false)
  }

  const handleCreate = async () => {
    if (!canOfferCreate || creating) return
    setCreating(true)
    try {
      const created = await onCreateNew(trimmedQuery)
      if (created) {
        const opt = typeof created === 'object' ? created : { value: created, label_fa: created }
        setExtraOptions((prev) => [...prev, opt])
        pick(String(optionValue(opt)))
      }
    } finally {
      setCreating(false)
    }
  }

  if (needsTrack) {
    return (
      <input
        type="text"
        className="psf-input form-input"
        disabled
        placeholder={trackHint}
        style={{ minWidth, ...style }}
        data-testid={testId}
      />
    )
  }

  return (
    <div ref={wrapRef} style={{ position: 'relative', minWidth }} data-testid={testId}>
      <input
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
      {open && !disabled && (
        <div
          role="listbox"
          style={{
            position: 'absolute',
            zIndex: 40,
            top: '100%',
            right: 0,
            left: 0,
            marginTop: '2px',
            maxHeight: '220px',
            overflowY: 'auto',
            background: '#fff',
            border: '1px solid #d1d5db',
            borderRadius: '8px',
            boxShadow: '0 8px 20px rgba(15,23,42,0.12)',
          }}
        >
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
          {!filtered.length && !canOfferCreate && (
            <div style={{ padding: '0.5rem 0.65rem', fontSize: '0.82rem', color: '#64748b' }}>
              موردی یافت نشد
            </div>
          )}
        </div>
      )}
    </div>
  )
}
