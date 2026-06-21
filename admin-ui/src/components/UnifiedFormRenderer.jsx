import React, { useMemo, useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { fieldVisible, fieldRequired } from '../utils/formConditions'
import { filterSchemaForRole } from '../utils/unifiedFormValidation'
import { resolveUploadPublicUrl, parseStepFileUploadValue } from '../utils/uploadPublicUrl'
import { studentApi } from '../services/api'
import ShamsiDatePicker from './ShamsiDatePicker'
import ShamsiDateTimePicker from './ShamsiDateTimePicker'
import {
  defaultShamsiDate,
  defaultShamsiTehranNow,
  isoDateToShamsiParts,
  shamsiDateTimeToUtcIso,
  shamsiDateToIsoDate,
  utcIsoToShamsiTehran,
} from '../utils/shamsiDateTime'

// انتخاب درمانگر — منبع پویا
function TherapistSelect({ id, field, value, onChange, disabled }) {
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let active = true
    studentApi
      .therapists()
      .then((res) => active && setOptions(Array.isArray(res.data) ? res.data : []))
      .catch(() => active && setOptions([]))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [])
  return (
    <select
      id={id}
      className="form-input psf-input"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled || loading}
    >
      <option value="">{loading ? 'در حال بارگذاری…' : '— انتخاب کنید —'}</option>
      {options.map((opt) => (
        <option key={opt.id} value={opt.id}>{opt.label_fa}</option>
      ))}
    </select>
  )
}

function FileField({ field, value, onChange, disabled, onUploadFile, showToast }) {
  const parsed = parseStepFileUploadValue(value)
  const src = parsed.url ? resolveUploadPublicUrl(parsed.url) : ''
  const showImage = parsed.url && parsed.mime.startsWith('image/')
  const showPdf = parsed.url && parsed.mime === 'application/pdf'
  const maxMb = field.validation?.max_size_mb || 8

  const handle = async (e) => {
    const file = e.target.files?.[0]
    if (!file) { onChange(null); return }
    if (file.size > maxMb * 1024 * 1024) {
      showToast?.(`حداکثر حجم فایل ${maxMb} مگابایت است.`, 'error')
      return
    }
    if (typeof onUploadFile === 'function') {
      try {
        const result = await onUploadFile(field.name, file)
        onChange(result)
      } catch (err) {
        showToast?.(err?.message || 'خطا در آپلود فایل', 'error')
      }
      return
    }
    // fallback: base64 درون answers
    const reader = new FileReader()
    reader.onload = () => {
      onChange({
        file_name: file.name,
        content_base64: reader.result?.split(',')[1],
        mime_type: file.type || 'application/octet-stream',
      })
    }
    reader.readAsDataURL(file)
  }

  return (
    <div>
      <input type="file" accept={field.accept || field.validation?.accept || '*/*'} disabled={disabled} onChange={handle} />
      {showImage && (
        <div style={{ marginTop: '0.5rem' }}>
          <a href={src} target="_blank" rel="noopener noreferrer">
            <img src={src} alt="" style={{ maxWidth: '100%', maxHeight: '140px', borderRadius: '8px', border: '1px solid #e5e7eb' }} />
          </a>
        </div>
      )}
      {showPdf && (
        <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline" style={{ marginTop: '0.5rem' }}>باز کردن PDF</a>
      )}
      {(parsed.fileName || value?.file_name) && (
        <span className="psf-file-name" style={{ display: 'block', marginTop: '0.35rem' }}>{parsed.fileName || value.file_name}</span>
      )}
    </div>
  )
}

// انتخاب چندتایی — اگر options موجود باشد چک‌باکسی؛ وگرنه ورودی برچسبی (نام‌ها).
function MultiSelectField({ field, value, onChange, disabled }) {
  const selected = Array.isArray(value) ? value : []
  const [draft, setDraft] = useState('')
  if (Array.isArray(field.options) && field.options.length) {
    const toggle = (v) => {
      const next = selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]
      onChange(next)
    }
    return (
      <div className="psf-checkbox-grid" role="group">
        {field.options.map((opt) => {
          const v = typeof opt === 'object' ? opt.value : opt
          const lab = typeof opt === 'object' ? (opt.label_fa || v) : opt
          return (
            <label key={String(v)} className="psf-check-row" style={{ display: 'flex', gap: '0.35rem' }}>
              <input type="checkbox" checked={selected.includes(v)} disabled={disabled} onChange={() => toggle(v)} />
              <span>{lab}</span>
            </label>
          )
        })}
      </div>
    )
  }
  const add = () => {
    const v = draft.trim()
    if (!v || selected.includes(v)) { setDraft(''); return }
    onChange([...selected, v])
    setDraft('')
  }
  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginBottom: '0.4rem' }}>
        {selected.map((v) => (
          <span key={v} className="badge" style={{ display: 'inline-flex', gap: '0.3rem', alignItems: 'center', padding: '0.2rem 0.5rem', borderRadius: '999px', background: '#eef2ff' }}>
            {v}
            {!disabled && (
              <button type="button" onClick={() => onChange(selected.filter((x) => x !== v))} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#6366f1' }}>×</button>
            )}
          </span>
        ))}
        {selected.length === 0 && <span className="muted">موردی افزوده نشده</span>}
      </div>
      {!disabled && (
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          <input
            type="text"
            className="psf-input form-input"
            placeholder="نام را وارد و افزودن را بزنید"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          />
          <button type="button" className="btn btn-sm btn-outline" onClick={add}>افزودن</button>
        </div>
      )}
    </div>
  )
}

// جدول قابل‌ویرایش — ستون‌ها از field.columns؛ هر ردیف یک شیء.
function EditableTableField({ field, value, onChange, disabled }) {
  const columns = Array.isArray(field.columns) ? field.columns : []
  const rows = Array.isArray(value) ? value : []
  const setCell = (rowIdx, colName, v) => {
    const next = rows.map((r, i) => (i === rowIdx ? { ...r, [colName]: v } : r))
    onChange(next)
  }
  const addRow = () => onChange([...rows, {}])
  const removeRow = (idx) => onChange(rows.filter((_, i) => i !== idx))

  const renderCell = (col, row, rowIdx) => {
    const ct = (col.type || 'text').toLowerCase()
    const v = row?.[col.name]
    if (ct === 'select' && Array.isArray(col.options)) {
      return (
        <select className="psf-input form-input" value={v ?? ''} disabled={disabled} onChange={(e) => setCell(rowIdx, col.name, e.target.value)}>
          <option value="">—</option>
          {col.options.map((opt) => {
            const ov = typeof opt === 'object' ? opt.value : opt
            const lab = typeof opt === 'object' ? (opt.label_fa || ov) : opt
            return <option key={String(ov)} value={ov}>{lab}</option>
          })}
        </select>
      )
    }
    if (ct === 'time') {
      return <input type="time" dir="ltr" className="psf-input form-input" value={v ?? ''} disabled={disabled} onChange={(e) => setCell(rowIdx, col.name, e.target.value)} />
    }
    if (ct === 'number') {
      return <input type="number" className="psf-input form-input" value={v ?? ''} disabled={disabled} onChange={(e) => setCell(rowIdx, col.name, e.target.value === '' ? '' : Number(e.target.value))} />
    }
    if (ct === 'checkbox') {
      return <input type="checkbox" checked={!!v} disabled={disabled} onChange={(e) => setCell(rowIdx, col.name, e.target.checked)} />
    }
    return <input type="text" className="psf-input form-input" value={v ?? ''} disabled={disabled} onChange={(e) => setCell(rowIdx, col.name, e.target.value)} />
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="table" style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.name} style={{ textAlign: 'right', padding: '0.3rem', borderBottom: '1px solid #e5e7eb', fontSize: '0.82rem' }}>{col.label_fa || col.name}</th>
            ))}
            {!disabled && <th style={{ width: '2.5rem' }} />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIdx) => (
            <tr key={rowIdx}>
              {columns.map((col) => (
                <td key={col.name} style={{ padding: '0.25rem', verticalAlign: 'top' }}>{renderCell(col, row, rowIdx)}</td>
              ))}
              {!disabled && (
                <td style={{ padding: '0.25rem' }}>
                  <button type="button" className="btn btn-sm btn-outline" onClick={() => removeRow(rowIdx)}>حذف</button>
                </td>
              )}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={columns.length + 1} className="muted" style={{ padding: '0.5rem' }}>ردیفی افزوده نشده</td></tr>
          )}
        </tbody>
      </table>
      {!disabled && (
        <button type="button" className="btn btn-sm btn-outline" style={{ marginTop: '0.4rem' }} onClick={addRow}>+ افزودن ردیف</button>
      )}
    </div>
  )
}

// فهرست بازه‌های تاریخ — هر مورد { start, end }.
function ShamsiDateFieldBridge({ value, onChange, disabled, idPrefix }) {
  const parts = useMemo(() => isoDateToShamsiParts(value) || defaultShamsiDate(), [value])
  const handleChange = (next) => {
    try {
      onChange(shamsiDateToIsoDate(next.jy, next.jm, next.jd))
    } catch {
      onChange('')
    }
  }
  return (
    <ShamsiDatePicker
      value={parts}
      onChange={handleChange}
      disabled={disabled}
      idPrefix={idPrefix}
      compact
    />
  )
}

function ShamsiDateTimeFieldBridge({ value, onChange, disabled, idPrefix }) {
  const parts = useMemo(() => utcIsoToShamsiTehran(value) || defaultShamsiTehranNow(), [value])
  const handleChange = (next) => {
    try {
      onChange(shamsiDateTimeToUtcIso(next.jy, next.jm, next.jd, next.hour, next.minute))
    } catch {
      onChange('')
    }
  }
  return (
    <ShamsiDateTimePicker
      value={parts}
      onChange={handleChange}
      disabled={disabled}
      idPrefix={idPrefix}
      compact
    />
  )
}

function DateRangeListField({ value, onChange, disabled }) {
  const ranges = Array.isArray(value) ? value : []
  const setPart = (idx, key, v) => onChange(ranges.map((r, i) => (i === idx ? { ...r, [key]: v } : r)))
  const addRange = () => onChange([...ranges, { start: '', end: '' }])
  const removeRange = (idx) => onChange(ranges.filter((_, i) => i !== idx))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
      {ranges.map((r, idx) => (
        <div key={idx} style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <span className="muted" style={{ fontSize: '0.8rem' }}>از</span>
          <ShamsiDateFieldBridge
            value={r?.start ?? ''}
            disabled={disabled}
            idPrefix={`range-${idx}-start`}
            onChange={(v) => setPart(idx, 'start', v)}
          />
          <span className="muted" style={{ fontSize: '0.8rem' }}>تا</span>
          <ShamsiDateFieldBridge
            value={r?.end ?? ''}
            disabled={disabled}
            idPrefix={`range-${idx}-end`}
            onChange={(v) => setPart(idx, 'end', v)}
          />
          {!disabled && <button type="button" className="btn btn-sm btn-outline" onClick={() => removeRange(idx)}>حذف</button>}
        </div>
      ))}
      {ranges.length === 0 && <span className="muted">بازه‌ای افزوده نشده</span>}
      {!disabled && <button type="button" className="btn btn-sm btn-outline" style={{ alignSelf: 'flex-start' }} onClick={addRange}>+ افزودن بازه</button>}
    </div>
  )
}

function UnifiedField({ field, values, onFieldChange, disabled, onUploadFile, showToast }) {
  const t = (field.type || 'text').toLowerCase()
  const name = field.name
  const id = `uf-${name}`
  const value = values[name]
  const onChange = (v) => onFieldChange(name, v)
  const req = fieldRequired(field, values)
  const labelText = `${field.label_fa || name}${req ? ' *' : ''}`

  const labelEl = <span className="psf-label form-label">{labelText}</span>

  if (t === 'readonly') {
    return (
      <div className="psf-field">
        {labelEl}
        <p className="muted" style={{ margin: '0.25rem 0 0' }}>{value ?? '—'}</p>
      </div>
    )
  }

  if (t === 'textarea') {
    return (
      <label className="psf-field" htmlFor={id}>
        {labelEl}
        <textarea id={id} className="psf-input form-input" rows={field.rows || 3} value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
      </label>
    )
  }

  if (t === 'therapist_select') {
    return (
      <label className="psf-field" htmlFor={id}>
        {labelEl}
        <TherapistSelect id={id} field={field} value={value} onChange={onChange} disabled={disabled} />
      </label>
    )
  }

  if ((t === 'select') && Array.isArray(field.options)) {
    return (
      <label className="psf-field" htmlFor={id}>
        {labelEl}
        <select id={id} className="psf-input form-input" value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          <option value="">— انتخاب کنید —</option>
          {field.options.map((opt) => {
            const v = typeof opt === 'object' ? opt.value : opt
            const lab = typeof opt === 'object' ? (opt.label_fa || opt.value) : opt
            return <option key={String(v)} value={v}>{lab}</option>
          })}
        </select>
      </label>
    )
  }

  if ((t === 'radio' || t === 'radio_list') && Array.isArray(field.options)) {
    return (
      <fieldset className="psf-field psf-fieldset">
        <legend className="psf-label">{labelText}</legend>
        <div className="psf-radio-group" style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          {field.options.map((opt) => {
            const v = typeof opt === 'object' ? opt.value : opt
            const lab = typeof opt === 'object' ? (opt.label_fa || String(v)) : opt
            return (
              <label key={String(v)} className="psf-radio" style={{ display: 'flex', gap: '0.35rem' }}>
                <input type="radio" name={name} checked={value === v} disabled={disabled} onChange={() => onChange(v)} />
                <span>{lab}</span>
              </label>
            )
          })}
        </div>
      </fieldset>
    )
  }

  if (t === 'checkbox_list' && Array.isArray(field.options)) {
    const selected = Array.isArray(value) ? value : []
    const maxSel = field.validation?.max_selection ?? field.max_selection
    const toggle = (v) => {
      let next = Array.isArray(value) ? [...value] : []
      if (next.includes(v)) next = next.filter((x) => x !== v)
      else if (maxSel == null || next.length < maxSel) next = [...next, v]
      onChange(next)
    }
    return (
      <div className="psf-field">
        {labelEl}
        {field.note_fa && <p className="psf-hint">{field.note_fa}</p>}
        <div className="psf-checkbox-grid" role="group">
          {field.options.map((opt) => {
            const v = typeof opt === 'object' ? opt.value : opt
            const lab = typeof opt === 'object' ? (opt.label_fa || v) : opt
            return (
              <label key={String(v)} className="psf-check-row" style={{ display: 'flex', gap: '0.35rem' }}>
                <input type="checkbox" checked={selected.includes(v)} disabled={disabled} onChange={() => toggle(v)} />
                <span>{lab}</span>
              </label>
            )
          })}
        </div>
      </div>
    )
  }

  if (t === 'number') {
    const rules = field.validation || {}
    return (
      <label className="psf-field" htmlFor={id}>
        {labelEl}
        <input id={id} type="number" className="psf-input form-input" min={rules.min ?? field.min} max={rules.max ?? field.max} value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
      </label>
    )
  }

  if (t === 'checkbox') {
    const href = field.rules_link_href
    const isExternal = typeof href === 'string' && /^https?:\/\//i.test(href)
    const linkText = field.rules_link_label_fa || 'قوانین'
    return (
      <label className="psf-field psf-check" style={{ display: 'flex', gap: '0.4rem' }}>
        <input type="checkbox" checked={!!value} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
        {href ? (
          <span>
            {isExternal
              ? <a href={href} target="_blank" rel="noopener noreferrer" className="psf-inline-link">{linkText}</a>
              : <Link to={href} className="psf-inline-link">{linkText}</Link>}
            {' '}را مطالعه کرده و می‌پذیرم.{req ? ' *' : ''}
          </span>
        ) : (
          <span>{field.label_fa || name}{req ? ' *' : ''}</span>
        )}
      </label>
    )
  }

  if (t === 'file' || t === 'file_upload') {
    return (
      <div className="psf-field">
        {labelEl}
        <FileField field={field} value={value} onChange={onChange} disabled={disabled} onUploadFile={onUploadFile} showToast={showToast} />
      </div>
    )
  }

  if (t === 'date' || t === 'date_picker') {
    return (
      <div className="psf-field">
        {labelEl}
        <ShamsiDateFieldBridge value={value ?? ''} onChange={onChange} disabled={disabled} idPrefix={id} />
      </div>
    )
  }

  if (t === 'time' || t === 'time_picker') {
    return (
      <label className="psf-field" htmlFor={id}>
        {labelEl}
        <input id={id} type="time" dir="ltr" className="psf-input form-input" value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
      </label>
    )
  }

  if (t === 'multi_select') {
    return (
      <div className="psf-field">
        {labelEl}
        {field.note_fa && <p className="psf-hint">{field.note_fa}</p>}
        <MultiSelectField field={field} value={value} onChange={onChange} disabled={disabled} />
      </div>
    )
  }

  if (t === 'table') {
    return (
      <div className="psf-field">
        {labelEl}
        {field.note_fa && <p className="psf-hint">{field.note_fa}</p>}
        <EditableTableField field={field} value={value} onChange={onChange} disabled={disabled} />
      </div>
    )
  }

  if (t === 'date_range_list') {
    return (
      <div className="psf-field">
        {labelEl}
        <DateRangeListField value={value} onChange={onChange} disabled={disabled} />
      </div>
    )
  }

  if (t === 'datetime') {
    return (
      <div className="psf-field">
        {labelEl}
        {field.description_fa && <p className="psf-hint">{field.description_fa}</p>}
        <ShamsiDateTimeFieldBridge value={value ?? ''} onChange={onChange} disabled={disabled} idPrefix={id} />
      </div>
    )
  }

  // text | email | tel fallback
  const inputType = t === 'email' ? 'email' : t === 'tel' ? 'tel' : 'text'
  const dir = field.dir === 'ltr' || inputType !== 'text' ? 'ltr' : 'rtl'
  return (
    <label className="psf-field" htmlFor={id}>
      {labelEl}
      {field.description_fa && <p className="psf-hint">{field.description_fa}</p>}
      <input id={id} type={inputType} className="psf-input form-input" dir={dir} value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
    </label>
  )
}

/**
 * رندر یکپارچهٔ فرم از schema_json { fields: [...] } — شرط‌های شیئی، فیلتر نقش،
 * آپلود multipart (در صورت ارائهٔ onUploadFile) یا base64.
 */
export default function UnifiedFormRenderer({
  schemaJson,
  values,
  onChange,
  disabled,
  role,
  onUploadFile,
  showToast,
}) {
  const filtered = useMemo(() => filterSchemaForRole(schemaJson || { fields: [] }, role), [schemaJson, role])
  const fields = filtered.fields || []

  const setVal = useCallback(
    (name, v) => onChange({ ...values, [name]: v }),
    [values, onChange],
  )

  return (
    <div className="unified-form-renderer psf-fields" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
      {fields.map((field) => {
        if (!field?.name) return null
        if (!fieldVisible(field, values)) return null
        return (
          <UnifiedField
            key={field.name}
            field={field}
            values={values}
            onFieldChange={setVal}
            disabled={disabled}
            onUploadFile={onUploadFile}
            showToast={showToast}
          />
        )
      })}
    </div>
  )
}
