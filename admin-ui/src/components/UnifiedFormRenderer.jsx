import React, { useMemo, useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { fieldVisible, fieldRequired } from '../utils/formConditions'
import { filterSchemaForRole } from '../utils/unifiedFormValidation'
import { resolveUploadPublicUrl, parseStepFileUploadValue } from '../utils/uploadPublicUrl'
import { studentApi } from '../services/api'
import EducationalTherapistSlotPicker from './EducationalTherapistSlotPicker'
import ShamsiDatePicker from './ShamsiDatePicker'
import ShamsiDateTimePicker from './ShamsiDateTimePicker'
import StepOtpField from './StepOtpField'
import CreatableSearchSelect from './CreatableSearchSelect'
import {
  createCourseCatalogEntry,
  createCourseCommitteeMember,
  createCourseCommitteeTrack,
  lookupRosterOptionsForRow,
  markRosterOptionsForCourse,
  resolveRosterTrackForRow,
  resolveTrackForCourse,
  resolveUnitsForCourse,
  rosterValueIsAuthorizedForRow,
  rowMeetsRosterPrerequisite,
} from '../utils/resolveFormOptionsSource'
import { shouldReplaceRowTrackFromCatalog } from '../utils/courseTableRowNormalize'
import {
  defaultShamsiDate,
  defaultShamsiTehranNow,
  isoDateToShamsiParts,
  shamsiDateTimeToUtcIso,
  shamsiDateToIsoDate,
  utcIsoToShamsiTehran,
} from '../utils/shamsiDateTime'
import {
  isSemesterPrepCalendarDateField,
  semesterPrepCalendarShamsiYearBounds,
} from '../utils/semesterPrepCalendarValidation'

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

function formatRialDisplay(num) {
  if (num === '' || num === undefined || num === null) return ''
  const n = Number(num)
  if (Number.isNaN(n)) return ''
  return n.toLocaleString('fa-IR')
}

function RialNumberField({ id, labelEl, field, value, onChange, disabled, rules, fieldError = null }) {
  const [display, setDisplay] = useState(() => formatRialDisplay(value))
  useEffect(() => {
    setDisplay(formatRialDisplay(value))
  }, [value])
  const handleBlur = () => {
    const raw = String(display).replace(/[^\d]/g, '')
    if (!raw) {
      onChange('')
      setDisplay('')
      return
    }
    const n = Number(raw)
    onChange(n)
    setDisplay(formatRialDisplay(n))
  }
  return (
    <label className={fieldShellClass(fieldError)} htmlFor={id}>
      {labelEl}
      {field.note_fa && <p className="psf-hint">{field.note_fa}</p>}
      <input
        id={id}
        type="text"
        inputMode="numeric"
        dir="ltr"
        className="psf-input form-input"
        value={display}
        disabled={disabled}
        placeholder="مثلاً ۱٬۵۰۰٬۰۰۰"
        onChange={(e) => setDisplay(e.target.value)}
        onBlur={handleBlur}
      />
      <FieldErrorMsg message={fieldError} />
    </label>
  )
}

function multiSelectOptionValue(opt) {
  return typeof opt === 'object' ? opt.value : opt
}

function multiSelectOptionLabel(opt) {
  if (typeof opt === 'object') return opt.label_fa || opt.value || ''
  return String(opt)
}

function multiSelectCreatableProps(field, { showToast }) {
  const src = field.options_source || {}
  const base = {
    allowCreate: field.creatable === true,
    onCreateError: showToast ? (msg) => showToast(msg, 'error') : null,
  }
  if (src.type === 'users') {
    return {
      ...base,
      placeholder: 'جست‌وجو یا انتخاب مصاحبه‌گر…',
      createSectionLabel: 'افزودن مصاحبه‌گر جدید',
      createInputPlaceholder: 'نام مصاحبه‌گر',
      createLabel: (text) => `افزودن «${text}»`,
    }
  }
  return {
    ...base,
    placeholder: 'جست‌وجو یا افزودن…',
    createSectionLabel: 'افزودن مورد جدید',
    createInputPlaceholder: 'نام جدید',
    createLabel: (text) => `افزودن «${text}»`,
  }
}

// انتخاب چندتایی — برچسب‌های قابل حذف + افزودن از فهرست یا نام جدید.
function MultiSelectField({ field, value, onChange, disabled, showToast }) {
  const selected = Array.isArray(value) ? value.map(String) : []
  const [draft, setDraft] = useState('')
  const [pickerKey, setPickerKey] = useState(0)
  const [extraOptions, setExtraOptions] = useState([])
  const hasDynamicOptions = Boolean(field.options_source) || (Array.isArray(field.options) && field.options.length > 0)

  const labelMap = useMemo(() => {
    const m = new Map()
    const add = (opt) => {
      const v = multiSelectOptionValue(opt)
      if (v == null || v === '') return
      m.set(String(v), multiSelectOptionLabel(opt))
    }
    ;(field.options || []).forEach(add)
    extraOptions.forEach(add)
    selected.forEach((v) => {
      if (!m.has(v)) m.set(v, v)
    })
    return m
  }, [field.options, extraOptions, selected])

  const baseOptions = useMemo(() => {
    const seen = new Set()
    const out = []
    const push = (opt) => {
      const v = String(multiSelectOptionValue(opt) ?? '')
      if (!v || seen.has(v)) return
      seen.add(v)
      out.push(typeof opt === 'object' ? opt : { value: opt, label_fa: opt })
    }
    ;(field.options || []).forEach(push)
    extraOptions.forEach(push)
    return out
  }, [field.options, extraOptions])

  const availableOptions = useMemo(
    () => baseOptions.filter((opt) => !selected.includes(String(multiSelectOptionValue(opt)))),
    [baseOptions, selected],
  )

  const addValue = useCallback((raw) => {
    const v = String(raw || '').trim()
    if (!v || selected.includes(v)) return
    onChange([...selected, v])
    setPickerKey((k) => k + 1)
  }, [onChange, selected])

  const removeValue = useCallback((raw) => {
    const v = String(raw)
    onChange(selected.filter((x) => x !== v))
  }, [onChange, selected])

  const chips = (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginBottom: hasDynamicOptions ? '0.5rem' : '0.4rem' }}>
      {selected.map((v) => (
        <span
          key={v}
          className="badge"
          style={{
            display: 'inline-flex',
            gap: '0.3rem',
            alignItems: 'center',
            padding: '0.2rem 0.5rem',
            borderRadius: '999px',
            background: '#eef2ff',
          }}
        >
          {labelMap.get(v) || v}
          {!disabled && (
            <button
              type="button"
              aria-label={`حذف ${labelMap.get(v) || v}`}
              onClick={() => removeValue(v)}
              style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#6366f1' }}
            >
              ×
            </button>
          )}
        </span>
      ))}
      {selected.length === 0 && <span className="muted">{hasDynamicOptions ? 'موردی انتخاب نشده' : 'موردی افزوده نشده'}</span>}
    </div>
  )

  if (hasDynamicOptions) {
    const creatableProps = multiSelectCreatableProps(field, { showToast })
    const allowCreate = field.creatable === true
    const onCreateNew = allowCreate
      ? async (nameFa) => {
          const trimmed = (nameFa || '').trim()
          if (!trimmed) return null
          const norm = (s) => String(s || '').trim().toLowerCase()
          const hit = baseOptions.find((o) => norm(multiSelectOptionLabel(o)) === norm(trimmed))
          if (hit) return hit
          return { value: trimmed, label_fa: trimmed }
        }
      : null

    return (
      <div>
        {chips}
        {!disabled && (
          <CreatableSearchSelect
            key={pickerKey}
            value=""
            onChange={addValue}
            options={availableOptions}
            disabled={disabled}
            onCreateNew={onCreateNew}
            onCreated={(opt) => {
              const v = String(multiSelectOptionValue(opt))
              setExtraOptions((prev) => {
                if (prev.some((o) => String(multiSelectOptionValue(o)) === v)) return prev
                return [...prev, opt]
              })
            }}
            {...creatableProps}
          />
        )}
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
      {chips}
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

// dynamic_list — ستون‌ها از field.fields (رشته یا شیء)
function DynamicListField({ field, value, onChange, disabled }) {
  const colSpecs = Array.isArray(field.fields) ? field.fields : []
  const columns = colSpecs.map((c) => {
    if (typeof c === 'string') return { name: c, label_fa: c, type: 'text' }
    return {
      name: c.name || c.code,
      label_fa: c.label_fa || c.name,
      type: c.type || 'text',
      options: c.options,
    }
  })
  const rows = Array.isArray(value) ? value : []
  const setCell = (rowIdx, colName, v) => {
    const next = rows.map((r, i) => (i === rowIdx ? { ...r, [colName]: v } : r))
    onChange(next)
  }
  const addRow = () => {
    const blank = {}
    columns.forEach((c) => { blank[c.name] = '' })
    onChange([...rows, blank])
  }
  const removeRow = (idx) => onChange(rows.filter((_, i) => i !== idx))

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
                <td key={col.name} style={{ padding: '0.25rem', verticalAlign: 'top' }}>
                  {col.type === 'select' && Array.isArray(col.options) && col.options.length > 0 ? (
                    <select
                      className="psf-input form-input"
                      value={row?.[col.name] ?? ''}
                      disabled={disabled}
                      onChange={(e) => setCell(rowIdx, col.name, e.target.value)}
                    >
                      <option value="">انتخاب کنید…</option>
                      {col.options.map((opt) => {
                        const val = typeof opt === 'object' ? opt.value : opt
                        const lab = typeof opt === 'object' ? (opt.label_fa || opt.value) : opt
                        return (
                          <option key={String(val)} value={String(val)}>{lab}</option>
                        )
                      })}
                    </select>
                  ) : col.type === 'textarea' ? (
                    <textarea
                      className="psf-input form-input"
                      rows={2}
                      value={row?.[col.name] ?? ''}
                      disabled={disabled}
                      onChange={(e) => setCell(rowIdx, col.name, e.target.value)}
                    />
                  ) : col.type === 'number' ? (
                    <input type="number" className="psf-input form-input" value={row?.[col.name] ?? ''} disabled={disabled} onChange={(e) => setCell(rowIdx, col.name, e.target.value === '' ? '' : Number(e.target.value))} />
                  ) : col.type === 'checkbox' ? (
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', justifyContent: 'center' }}>
                      <input
                        type="checkbox"
                        checked={!!row?.[col.name]}
                        disabled={disabled}
                        onChange={(e) => setCell(rowIdx, col.name, e.target.checked)}
                      />
                    </label>
                  ) : col.type === 'readonly' ? (
                    <span style={{ fontSize: '0.85rem' }}>{row?.[col.name] ?? '—'}</span>
                  ) : (
                    <input type="text" className="psf-input form-input" value={row?.[col.name] ?? ''} disabled={disabled} onChange={(e) => setCell(rowIdx, col.name, e.target.value)} />
                  )}
                </td>
              ))}
              {!disabled && (
                <td style={{ padding: '0.25rem' }}>
                  <button type="button" className="btn btn-sm btn-outline" onClick={() => removeRow(rowIdx)}>حذف</button>
                </td>
              )}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={columns.length + 1} className="muted" style={{ padding: '0.5rem' }}>ردیفی ثبت نشده</td></tr>
          )}
        </tbody>
      </table>
      {!disabled && (
        <button type="button" className="btn btn-sm btn-outline" style={{ marginTop: '0.4rem' }} onClick={addRow}>+ افزودن ردیف</button>
      )}
    </div>
  )
}

function tableBlankRow(columns) {
  const blank = {}
  columns.forEach((col) => {
    const ct = (col.type || 'text').toLowerCase()
    blank[col.name] = ct === 'checkbox' ? false : ''
  })
  return blank
}

function columnOptionsForRow(col, row, columns = []) {
  if (col._optionsByCourse || col._optionsByTrack) {
    return lookupRosterOptionsForRow(col, row, columns)
  }
  const filterCol = col.filter_by_column || col.options_source?.filter_by_column
  if (filterCol === 'course_name' && col._optionsByCourse && typeof col._optionsByCourse === 'object') {
    const courseVal = row?.course_name
    if (!courseVal) return []
    return col._optionsByCourse[courseVal] || []
  }
  if (filterCol && col._optionsByTrack && typeof col._optionsByTrack === 'object') {
    const trackVal = row?.[filterCol]
    if (!trackVal) return []
    return col._optionsByTrack[trackVal] || []
  }
  return Array.isArray(col.options) ? col.options : []
}

function rosterDependentColumns(columns) {
  const byFilter = {}
  for (const col of columns) {
    const filterCol = col.filter_by_column || col.options_source?.filter_by_column
    if (filterCol) {
      if (!byFilter[filterCol]) byFilter[filterCol] = []
      byFilter[filterCol].push(col.name)
    }
  }
  return byFilter
}

function clearTrackDependents(updated, dependentsByTrack) {
  const trackDeps = dependentsByTrack.track
  if (!trackDeps?.length) return updated
  const next = { ...updated }
  for (const dep of trackDeps) {
    next[dep] = ''
    if (dep === 'instructor') next.instructor_id = ''
    if (dep === 'teaching_assistant') next.teaching_assistant_id = ''
  }
  return next
}

function clearUnauthorizedRosterSelections(row, columns) {
  const next = { ...row }
  for (const col of columns || []) {
    const src = col.options_source || {}
    if (src.type !== 'course_committee_roster') continue
    const raw = next[col.name]
    if (raw == null || String(raw).trim() === '') continue
    if (rosterValueIsAuthorizedForRow(col, next, columns)) continue
    next[col.name] = ''
    if (col.name === 'instructor') next.instructor_id = ''
    if (col.name === 'teaching_assistant') next.teaching_assistant_id = ''
  }
  return next
}

function applyCourseTrackAutoFill(updated, columns, courseValue, dependentsByTrack, extraCatalog = []) {
  const courseCol = columns.find((c) => c.name === 'course_name')
  const trackCol = columns.find((c) => c.name === 'track')
  let next = { ...updated }
  const catalog = [...(courseCol?.options || []), ...(extraCatalog || [])]
  if (courseCol && trackCol) {
    const trackCode = resolveTrackForCourse(courseValue, catalog)
    if (trackCode) {
      if (!next.track_code) next = { ...next, track_code: trackCode }
      if (!String(next.track || '').trim()) {
        next = { ...next, track: trackCode, track_code: trackCode }
      } else if (shouldReplaceRowTrackFromCatalog(next, trackCode, trackCol)) {
        next = { ...next, track: trackCode, track_code: trackCode }
        next = clearTrackDependents(next, dependentsByTrack)
      }
    }
  }
  const unitsCol = columns.find((c) => c.name === 'units' && c.auto_fill_from === 'course_name')
  if (unitsCol && courseCol) {
    const units = resolveUnitsForCourse(courseValue, catalog)
    if (units !== '') next = { ...next, units }
  }
  return next
}

const TABLE_COLUMN_MIN_WIDTH = {
  course_name: '12.5rem',
  track: '9.5rem',
  units: '5rem',
  day: '7.5rem',
  time: '7.5rem',
  instructor: '10.5rem',
  teaching_assistant: '10.5rem',
  proposed_day: '7.5rem',
  proposed_time: '7.5rem',
  classroom_location: '14rem',
  instructor_coordinated: '6.5rem',
}

function columnMinWidth(col) {
  return TABLE_COLUMN_MIN_WIDTH[col?.name] || undefined
}

function tableCellInputStyle(col, readOnlyStyle) {
  const minW = columnMinWidth(col) || '6.5rem'
  return {
    ...readOnlyStyle,
    width: '100%',
    minWidth: minW,
    maxWidth: '100%',
    boxSizing: 'border-box',
  }
}

function isCreatableSelectColumn(col) {
  const t = (col?.type || '').toLowerCase()
  return t === 'creatable_select' || (t === 'select' && (col.creatable || col.searchable))
}

function buildCreateHandler(col, row, columns = []) {
  const src = col.options_source || {}
  if (src.type === 'course_catalog') {
    return async (nameFa) => {
      const track = resolveRosterTrackForRow(col, row, columns) || String(row?.track || '').trim()
      if (!track) throw new Error('ابتدا رسته را انتخاب کنید')
      return createCourseCatalogEntry(nameFa, track)
    }
  }
  if (src.type === 'course_committee_tracks') {
    return async (nameFa) => createCourseCommitteeTrack(nameFa)
  }
  if (src.type === 'course_committee_roster') {
    const kind = src.kind || 'instructor'
    return async (nameFa) => {
      const track = resolveRosterTrackForRow(col, row, columns)
      if (!track) throw new Error('ابتدا رسته را انتخاب کنید')
      const course = String(row?.course_name || '').trim()
      return createCourseCommitteeMember({
        track,
        kind,
        nameFa,
        authorizedCourses: course ? [course] : undefined,
      })
    }
  }
  return null
}

function optionValueForMerge(opt) {
  return typeof opt === 'object' ? opt.value : opt
}

function creatableSelectProps(col, row, { showToast, onOptionCreated }) {
  const src = col.options_source || {}
  const base = {
    allowCreate: col.creatable === true,
    onCreateError: showToast ? (msg) => showToast(msg, 'error') : null,
    onCreated: onOptionCreated ? (opt) => onOptionCreated(col.name, opt) : null,
  }
  if (src.type === 'course_catalog') {
    return {
      ...base,
      placeholder: 'جست‌وجو یا انتخاب درس…',
      createSectionLabel: 'افزودن درس جدید به فهرست',
      createInputPlaceholder: 'نام درس جدید',
      createLabel: (text) => `افزودن درس «${text}»`,
    }
  }
  if (src.type === 'course_committee_tracks') {
    return {
      ...base,
      createSectionLabel: 'افزودن رسته جدید',
      createInputPlaceholder: 'نام رسته جدید',
      createLabel: (text) => `افزودن رسته «${text}»`,
    }
  }
  if (src.type === 'course_committee_roster') {
    const kind = src.kind === 'teaching_assistant' ? 'کمک‌مدرس' : 'مدرس'
    return {
      ...base,
      createSectionLabel: `افزودن ${kind} جدید`,
      createInputPlaceholder: `نام ${kind} جدید`,
      createLabel: (text) => `افزودن ${kind} «${text}»`,
    }
  }
  return base
}

// جدول قابل‌ویرایش — ستون‌ها از field.columns؛ هر ردیف یک شیء.
function EditableTableField({ field, value, onChange, disabled, showToast, onRosterMemberCreated }) {
  const columns = Array.isArray(field.columns) ? field.columns : []
  const rows = Array.isArray(value) ? value : []
  const allowAddRows = field.allow_add_rows !== false
  const allowRemoveRows = field.allow_remove_rows !== false
  const dependentsByTrack = useMemo(() => rosterDependentColumns(columns), [columns])
  const [createdOptionsByCol, setCreatedOptionsByCol] = useState({})

  const rememberCreatedOption = useCallback((colName, opt, col, row) => {
    if (!colName || !opt) return
    setCreatedOptionsByCol((prev) => {
      const existing = prev[colName] || []
      const v = String(typeof opt === 'object' ? opt.value : opt)
      if (!v || existing.some((o) => String(typeof o === 'object' ? o.value : o) === v)) {
        return prev
      }
      return { ...prev, [colName]: [...existing, opt] }
    })
    if (onRosterMemberCreated && col?.options_source?.type === 'course_committee_roster') {
      const track = resolveRosterTrackForRow(col, row, columns)
      const kind = col.options_source.kind || 'instructor'
      if (track) {
        onRosterMemberCreated(opt, { kind, track, colName })
      }
    }
  }, [columns, onRosterMemberCreated])

  const courseCatalogOptions = useMemo(() => {
    const courseCol = columns.find((c) => c.name === 'course_name')
    const base = courseCol?.options || []
    const extra = createdOptionsByCol.course_name || []
    if (!extra.length) return base
    const seen = new Set(base.map((o) => String(typeof o === 'object' ? o.value : o)))
    const merged = [...base]
    for (const opt of extra) {
      const v = String(typeof opt === 'object' ? opt.value : opt)
      if (!v || seen.has(v)) continue
      seen.add(v)
      merged.push(opt)
    }
    return merged
  }, [columns, createdOptionsByCol])

  const mergeCreatedOptions = useCallback(
    (col, rowOptions, row) => {
      const extras = createdOptionsByCol[col.name] || []
      if (!extras.length) return rowOptions
      const src = col.options_source || {}
      const markedExtras = src.type === 'course_committee_roster'
        ? markRosterOptionsForCourse(extras, row?.course_name, {
            kind: src.kind || 'instructor',
            catalogOptions: courseCatalogOptions,
            hideUnauthorized: true,
          })
        : extras
      const seen = new Set(rowOptions.map((o) => String(optionValueForMerge(o))))
      const merged = [...rowOptions]
      for (const opt of markedExtras) {
        const v = String(optionValueForMerge(opt))
        if (!v || seen.has(v)) continue
        seen.add(v)
        merged.push(opt)
      }
      return merged
    },
    [createdOptionsByCol, courseCatalogOptions],
  )

  useEffect(() => {
    // فقط وقتی افزودن ردیف مجاز است ردیف خالی اولیه بساز
    if (disabled || !field.required || !allowAddRows) return
    if (Array.isArray(value) && value.length > 0) return
    onChange([tableBlankRow(columns)])
    // فقط هنگام خالی بودن مقدار — وابستگی به columns/onChange عمداً محدود است
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled, field.required, allowAddRows, Array.isArray(value) ? value.length : 0])

  const setCell = (rowIdx, colName, v) => {
    const next = rows.map((r, i) => {
      if (i !== rowIdx) return r
      let updated = { ...r, [colName]: v }
      if (colName === 'course_name') {
        const extra = createdOptionsByCol.course_name || []
        updated = applyCourseTrackAutoFill(updated, columns, v, dependentsByTrack, extra)
        updated = clearUnauthorizedRosterSelections(updated, columns)
      }
      const deps = dependentsByTrack[colName]
      if (deps?.length) {
        for (const dep of deps) {
          updated[dep] = ''
          if (dep === 'instructor') {
            updated.instructor_id = ''
          }
          if (dep === 'teaching_assistant') {
            updated.teaching_assistant_id = ''
          }
        }
      }
      return updated
    })
    onChange(next)
  }
  const addRow = () => {
    if (!allowAddRows) return
    onChange([...rows, tableBlankRow(columns)])
  }
  const removeRow = (idx) => {
    if (!allowRemoveRows) return
    const next = rows.filter((_, i) => i !== idx)
    if (field.required && allowAddRows && next.length === 0) {
      onChange([tableBlankRow(columns)])
      return
    }
    onChange(next)
  }

  const trackAutoFillFromCourse = Boolean(
    columns.find((c) => c.name === 'track' && c.auto_fill_from === 'course_name'),
  )

  useEffect(() => {
    if (disabled || !trackAutoFillFromCourse || !courseCatalogOptions.length) return
    const trackCol = columns.find((c) => c.name === 'track')
    const extra = createdOptionsByCol.course_name || []
    let changed = false
    const next = rows.map((row) => {
      const courseVal = row?.course_name
      if (!courseVal) return row
      const expected = resolveTrackForCourse(courseVal, courseCatalogOptions)
      if (!expected) return row
      if (!shouldReplaceRowTrackFromCatalog(row, expected, trackCol)) {
        if (!row.track_code) {
          changed = true
          return { ...row, track_code: expected }
        }
        return row
      }
      changed = true
      return applyCourseTrackAutoFill({ ...row }, columns, courseVal, dependentsByTrack, extra)
    })
    if (changed) onChange(next)
    // همگام‌سازی اولیه پس از بارگذاری کاتالوگ — مدرس را به‌خاطر برچسب فارسی رسته پاک نکن
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled, trackAutoFillFromCourse, courseCatalogOptions.length, columns, dependentsByTrack])

  const renderCell = (col, row, rowIdx) => {
    const ct = (col.type || 'text').toLowerCase()
    const v = row?.[col.name]
    const trackLocked =
      col.name === 'track'
      && col.auto_fill_from === 'course_name'
      && Boolean(resolveTrackForCourse(row?.course_name, courseCatalogOptions))
    const cellDisabled = disabled || Boolean(col.auto_fill) || trackLocked
    const readOnlyStyle = col.auto_fill || trackLocked ? { background: '#f1f5f9' } : undefined
    const minW = columnMinWidth(col)

    if (isCreatableSelectColumn(col)) {
      const rowOptions = mergeCreatedOptions(col, columnOptionsForRow(col, row, columns), row)
      const src = col.options_source || {}
      const filterCol = col.filter_by_column || src.filter_by_column
      const isRoster = src.type === 'course_committee_roster'
      const missingCourse = isRoster
        && columns.some((c) => c.name === 'course_name')
        && !String(row?.course_name || '').trim()
      const needsPrerequisite = (filterCol || isRoster) && !rowMeetsRosterPrerequisite(col, row, columns)
      const needsCourse = missingCourse || (filterCol === 'course_name' && needsPrerequisite)
      const needsTrack = !needsCourse && filterCol === 'track' && needsPrerequisite
      const creatableProps = creatableSelectProps(col, row, {
        showToast,
        onOptionCreated: (colName, opt) => rememberCreatedOption(colName, opt, col, row),
      })
      return (
        <CreatableSearchSelect
          value={v ?? ''}
          onChange={(next) => setCell(rowIdx, col.name, next)}
          options={rowOptions}
          disabled={cellDisabled}
          needsTrack={needsTrack}
          needsCourse={needsCourse}
          onCreateNew={cellDisabled || col.creatable !== true ? null : buildCreateHandler(col, row, columns)}
          style={readOnlyStyle}
          minWidth={minW}
          testId={`table-cell-${col.name}-${rowIdx}`}
          {...creatableProps}
        />
      )
    }

    if (ct === 'select' && (Array.isArray(col.options) || col._optionsByTrack || col._optionsByCourse)) {
      const rowOptions = columnOptionsForRow(col, row, columns)
      const src = col.options_source || {}
      const filterCol = col.filter_by_column || src.filter_by_column
      const isRoster = src.type === 'course_committee_roster'
      const missingCourse = isRoster
        && columns.some((c) => c.name === 'course_name')
        && !String(row?.course_name || '').trim()
      const needsPrerequisite = (filterCol || isRoster) && !rowMeetsRosterPrerequisite(col, row, columns)
      const placeholder = missingCourse || (filterCol === 'course_name' && needsPrerequisite)
        ? 'ابتدا درس را انتخاب کنید'
        : (needsPrerequisite ? 'ابتدا رسته را انتخاب کنید' : '—')
      return (
        <select
          className="psf-input form-input"
          style={readOnlyStyle}
          value={v ?? ''}
          disabled={cellDisabled || needsPrerequisite}
          onChange={(e) => setCell(rowIdx, col.name, e.target.value)}
        >
          <option value="">{placeholder}</option>
          {rowOptions.map((opt) => {
            const ov = typeof opt === 'object' ? opt.value : opt
            const blocked = typeof opt === 'object' && opt.disabled
            const lab = typeof opt === 'object'
              ? (blocked
                ? `${opt.label_fa || ov} — ${opt.disabled_reason_fa || 'مجاز برای این درس نیست'}`
                : (opt.label_fa || ov))
              : opt
            return (
              <option key={String(ov)} value={ov} disabled={blocked}>
                {lab}
              </option>
            )
          })}
          {v && !rowOptions.some((opt) => String(typeof opt === 'object' ? opt.value : opt) === String(v)) ? (
            <option value={v}>{typeof v === 'string' && v.length > 20 ? v : v}</option>
          ) : null}
        </select>
      )
    }
    if (ct === 'time') {
      return <input type="time" dir="ltr" className="psf-input form-input" style={tableCellInputStyle(col, readOnlyStyle)} value={v ?? ''} disabled={cellDisabled} onChange={(e) => setCell(rowIdx, col.name, e.target.value)} />
    }
    if (ct === 'number') {
      return <input type="number" className="psf-input form-input" style={tableCellInputStyle(col, readOnlyStyle)} value={v ?? ''} disabled={cellDisabled} onChange={(e) => setCell(rowIdx, col.name, e.target.value === '' ? '' : Number(e.target.value))} />
    }
    if (ct === 'checkbox') {
      return (
        <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '2.25rem' }}>
          <input type="checkbox" checked={!!v} disabled={cellDisabled} onChange={(e) => setCell(rowIdx, col.name, e.target.checked)} />
        </label>
      )
    }
    return <input type="text" className="psf-input form-input" style={tableCellInputStyle(col, readOnlyStyle)} value={v ?? ''} disabled={cellDisabled} onChange={(e) => setCell(rowIdx, col.name, e.target.value)} />
  }

  return (
    <div className="unified-form-table-scroll" style={{ overflowX: 'auto', width: '100%', maxWidth: '100%', minWidth: 0 }}>
      <table className="table" style={{ width: '100%', minWidth: '64rem', borderCollapse: 'collapse', tableLayout: 'auto' }}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.name} style={{ textAlign: 'right', padding: '0.3rem', borderBottom: '1px solid #e5e7eb', fontSize: '0.82rem', minWidth: columnMinWidth(col) }}>{col.label_fa || col.name}</th>
            ))}
            {!disabled && allowRemoveRows && <th style={{ width: '2.5rem' }} />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIdx) => (
            <tr key={rowIdx}>
              {columns.map((col) => (
                <td key={col.name} style={{ padding: '0.25rem', verticalAlign: 'top', minWidth: columnMinWidth(col) }}>{renderCell(col, row, rowIdx)}</td>
              ))}
              {!disabled && allowRemoveRows && (
                <td style={{ padding: '0.25rem' }}>
                  <button type="button" className="btn btn-sm btn-outline" onClick={() => removeRow(rowIdx)}>حذف</button>
                </td>
              )}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length + (allowRemoveRows ? 1 : 0)} className="muted" style={{ padding: '0.5rem' }}>
                {allowAddRows ? 'ردیفی ثبت نشده — با «افزودن ردیف» شروع کنید' : 'ردیفی از پیش‌آماده‌سازی ثبت نشده'}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {!disabled && allowAddRows && (
        <button type="button" className="btn btn-sm btn-outline" style={{ marginTop: '0.4rem' }} onClick={addRow}>+ افزودن ردیف</button>
      )}
    </div>
  )
}

// فهرست بازه‌های تاریخ — هر مورد { start, end }.
function ShamsiDateFieldBridge({ value, onChange, disabled, idPrefix, fieldName = null }) {
  const parts = useMemo(() => isoDateToShamsiParts(value) || defaultShamsiDate(), [value])
  const yearBounds = useMemo(() => {
    if (!fieldName || !isSemesterPrepCalendarDateField(fieldName)) return {}
    const { minJy, maxJy } = semesterPrepCalendarShamsiYearBounds()
    return { minJy, maxJy }
  }, [fieldName])
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
      {...yearBounds}
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

function DateRangeListField({ value, onChange, disabled, listFieldName = null }) {
  const ranges = Array.isArray(value) ? value : []
  const setPart = (idx, key, v) => onChange(ranges.map((r, i) => (i === idx ? { ...r, [key]: v } : r)))
  const addRange = () => onChange([...ranges, { start: '', end: '' }])
  const removeRange = (idx) => onChange(ranges.filter((_, i) => i !== idx))
  return (
    <div className="date-range-list-field">
      {ranges.map((r, idx) => {
        const rangeInvalid = r?.start && r?.end && String(r.end) <= String(r.start)
        return (
          <div key={idx} className="date-range-list-field__item">
            <div className="date-range-list-field__dates">
              <div className="date-range-list-field__part">
                <span className="date-range-list-field__label muted">از</span>
                <ShamsiDateFieldBridge
                  value={r?.start ?? ''}
                  disabled={disabled}
                  idPrefix={`range-${idx}-start`}
                  fieldName={listFieldName}
                  onChange={(v) => setPart(idx, 'start', v)}
                />
              </div>
              <div className="date-range-list-field__part">
                <span className="date-range-list-field__label muted">تا</span>
                <ShamsiDateFieldBridge
                  value={r?.end ?? ''}
                  disabled={disabled}
                  idPrefix={`range-${idx}-end`}
                  fieldName={listFieldName}
                  onChange={(v) => setPart(idx, 'end', v)}
                />
              </div>
            </div>
            {!disabled && (
              <button type="button" className="btn btn-sm btn-outline date-range-list-field__remove" onClick={() => removeRange(idx)}>
                حذف
              </button>
            )}
            {rangeInvalid && (
              <p className="date-range-list-field__error">
                تاریخ پایان باید بعد از شروع باشد
              </p>
            )}
          </div>
        )
      })}
      {ranges.length === 0 && <span className="muted">بازه‌ای افزوده نشده</span>}
      {!disabled && (
        <button type="button" className="btn btn-sm btn-outline date-range-list-field__add" onClick={addRange}>
          + افزودن بازه
        </button>
      )}
    </div>
  )
}

function RequiredMark() {
  return <span className="psf-required-mark" aria-hidden="true"> *</span>
}

function FieldErrorMsg({ message }) {
  if (!message) return null
  return <p className="psf-field-error-msg" role="alert">{message}</p>
}

function fieldShellClass(error, base = 'psf-field') {
  return error ? `${base} psf-field--error` : base
}

function UnifiedField({ field, values, onFieldChange, disabled, onUploadFile, showToast, instanceId = null, fieldError = null, onRosterMemberCreated = null }) {
  const t = (field.type || 'text').toLowerCase()
  const name = field.name
  const id = `uf-${name}`
  const value = values[name]
  const onChange = (v) => onFieldChange(name, v)
  const req = fieldRequired(field, values)
  const fieldTestId = `uf-field-${name}`
  const inputTestId = `uf-input-${name}`
  const shellCls = fieldShellClass(fieldError)
  const labelEl = (
    <span className="psf-label form-label">
      {field.label_fa || name}
      {req ? <RequiredMark /> : null}
    </span>
  )
  const legendLabel = (
    <legend className="psf-label">
      {field.label_fa || name}
      {req ? <RequiredMark /> : null}
    </legend>
  )

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
      <label className={shellCls} htmlFor={id} data-testid={fieldTestId}>
        {labelEl}
        <textarea id={id} className="psf-input form-input" data-testid={inputTestId} rows={field.rows || 3} value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
        <FieldErrorMsg message={fieldError} />
      </label>
    )
  }

  if (t === 'hidden') {
    return null
  }

  if (t === 'therapist_slot_picker') {
    const courseType = values.course_type || null
    const isSupervisorPick = name === 'new_supervisor_id'
    return (
      <div className={shellCls} data-testid={fieldTestId}>
        {labelEl}
        <EducationalTherapistSlotPicker
          therapistId={value ?? ''}
          slotIds={values.slot_ids || []}
          weeklySessions={values.weekly_sessions || values.selected_supervision_weekly_count || (isSupervisorPick ? 1 : '')}
          courseType={courseType}
          therapistFieldName={name}
          slotRole={isSupervisorPick ? 'supervisor' : 'therapist'}
          onTherapistChange={(v) => onFieldChange(name, v)}
          onSlotsChange={(ids) => {
            onFieldChange('slot_ids', ids)
            if (isSupervisorPick) {
              onFieldChange('weekly_sessions', 1)
              onFieldChange('selected_supervision_weekly_count', 1)
            }
          }}
          disabled={disabled}
        />
        <FieldErrorMsg message={fieldError} />
      </div>
    )
  }

  if (t === 'therapist_select') {
    return (
      <label className={shellCls} htmlFor={id}>
        {labelEl}
        <TherapistSelect id={id} field={field} value={value} onChange={onChange} disabled={disabled} />
        <FieldErrorMsg message={fieldError} />
      </label>
    )
  }

  if (t === 'user_select') {
    const userField = {
      ...field,
      type: 'select',
      options_source: field.options_source || { type: 'users' },
    }
    if (Array.isArray(userField.options) && userField.options.length) {
      return (
        <label className={shellCls} htmlFor={id}>
          {labelEl}
          <select id={id} className="psf-input form-input" value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
            {userField.options.map((opt) => {
              const v = typeof opt === 'object' ? opt.value : opt
              const lab = typeof opt === 'object' ? (opt.label_fa || opt.value) : opt
              return <option key={String(v)} value={v}>{lab}</option>
            })}
          </select>
          <FieldErrorMsg message={fieldError} />
        </label>
      )
    }
    return (
      <label className={shellCls} htmlFor={id} data-testid={fieldTestId}>
        {labelEl}
        <select id={id} className="psf-input form-input" data-testid={inputTestId} value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          <option value="">— بارگذاری گزینه‌ها —</option>
        </select>
        <FieldErrorMsg message={fieldError} />
      </label>
    )
  }

  if ((t === 'select') && Array.isArray(field.options)) {
    return (
      <label className={shellCls} htmlFor={id} data-testid={fieldTestId}>
        {labelEl}
        <select id={id} className="psf-input form-input" data-testid={inputTestId} value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          <option value="">— انتخاب کنید —</option>
          {field.options.map((opt) => {
            const v = typeof opt === 'object' ? opt.value : opt
            const lab = typeof opt === 'object' ? (opt.label_fa || opt.value) : opt
            return <option key={String(v)} value={v}>{lab}</option>
          })}
        </select>
        <FieldErrorMsg message={fieldError} />
      </label>
    )
  }

  if ((t === 'radio' || t === 'radio_list') && Array.isArray(field.options)) {
    return (
      <fieldset className={fieldShellClass(fieldError, 'psf-field psf-fieldset')}>
        {legendLabel}
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
        <FieldErrorMsg message={fieldError} />
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
      <div className={shellCls}>
        {labelEl}
        {field.note_fa && <p className="psf-hint">{field.note_fa}</p>}
        <div className="psf-checkbox-grid" role="group">
          {field.options.map((opt) => {
            const v = typeof opt === 'object' ? opt.value : opt
            let lab = typeof opt === 'object' ? (opt.display_label_fa || opt.label_fa || v) : opt
            if (typeof opt === 'object' && opt.units != null && !String(lab).includes('واحد')) {
              const units = Number(opt.units)
              if (Number.isFinite(units) && units > 0) {
                lab = `${opt.label_fa || v} — ${units.toLocaleString('fa-IR')} واحد`
              }
            }
            let amountHint = ''
            if (typeof opt === 'object' && opt.line_amount_rial != null) {
              const rial = Number(opt.line_amount_rial)
              if (Number.isFinite(rial) && rial > 0) {
                amountHint = `${Math.round(rial / 10).toLocaleString('fa-IR')} تومان`
              }
            }
            return (
              <label key={String(v)} className="psf-check-row" style={{ display: 'flex', gap: '0.35rem', alignItems: 'flex-start' }}>
                <input type="checkbox" checked={selected.includes(v)} disabled={disabled} onChange={() => toggle(v)} />
                <span>
                  {lab}
                  {amountHint ? (
                    <span className="muted" style={{ display: 'block', fontSize: '0.78rem', marginTop: '0.1rem' }}>
                      شهریه این درس: {amountHint}
                    </span>
                  ) : null}
                </span>
              </label>
            )
          })}
        </div>
        <FieldErrorMsg message={fieldError} />
      </div>
    )
  }

  if (t === 'number') {
    const rules = field.validation || {}
    const isRial = field.format === 'rial' || (field.label_fa || '').includes('ریال')
    if (isRial) {
      return (
        <RialNumberField
          id={id}
          labelEl={labelEl}
          field={field}
          value={value}
          onChange={onChange}
          disabled={disabled}
          rules={rules}
          fieldError={fieldError}
        />
      )
    }
    return (
      <label className={shellCls} htmlFor={id}>
        {labelEl}
        {field.note_fa && <p className="psf-hint">{field.note_fa}</p>}
        <input id={id} type="number" className="psf-input form-input" min={rules.min ?? field.min} max={rules.max ?? field.max} value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
        <FieldErrorMsg message={fieldError} />
      </label>
    )
  }

  if (t === 'checkbox') {
    const href = field.rules_link_href
    const isExternal = typeof href === 'string' && /^https?:\/\//i.test(href)
    const linkText = field.rules_link_label_fa || 'قوانین'
    return (
      <div className={shellCls}>
        <label className="psf-check" style={{ display: 'flex', gap: '0.4rem' }}>
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
        <FieldErrorMsg message={fieldError} />
      </div>
    )
  }

  if (t === 'file' || t === 'file_upload') {
    return (
      <div className={shellCls}>
        {labelEl}
        <FileField field={field} value={value} onChange={onChange} disabled={disabled} onUploadFile={onUploadFile} showToast={showToast} />
        <FieldErrorMsg message={fieldError} />
      </div>
    )
  }

  if (t === 'date' || t === 'date_picker') {
    return (
      <div className={shellCls}>
        {labelEl}
        <ShamsiDateFieldBridge
          value={value ?? ''}
          onChange={onChange}
          disabled={disabled}
          idPrefix={id}
          fieldName={name}
        />
        <FieldErrorMsg message={fieldError} />
      </div>
    )
  }

  if (t === 'time' || t === 'time_picker') {
    return (
      <label className={shellCls} htmlFor={id}>
        {labelEl}
        <input id={id} type="time" dir="ltr" className="psf-input form-input" value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
        <FieldErrorMsg message={fieldError} />
      </label>
    )
  }

  if (t === 'multi_select') {
    return (
      <div className={shellCls}>
        {labelEl}
        {field.note_fa && <p className="psf-hint">{field.note_fa}</p>}
        <MultiSelectField field={field} value={value} onChange={onChange} disabled={disabled} showToast={showToast} />
        <FieldErrorMsg message={fieldError} />
      </div>
    )
  }

  if (t === 'step_otp') {
    return (
      <StepOtpField
        instanceId={instanceId}
        value={value}
        onChange={onChange}
        disabled={disabled}
        labelFa={field.label_fa || name}
        required={!!field.required}
        verified={!!values?.step_otp_verified}
        onVerifiedChange={(v) => onFieldChange('step_otp_verified', v)}
      />
    )
  }

  if (t === 'dynamic_list') {
    return (
      <div className={shellCls}>
        {labelEl}
        {field.note_fa && <p className="psf-hint">{field.note_fa}</p>}
        <DynamicListField field={field} value={value} onChange={onChange} disabled={disabled} />
        <FieldErrorMsg message={fieldError} />
      </div>
    )
  }

  if (t === 'table') {
    return (
      <div className={shellCls} data-testid={`uf-table-${name}`}>
        {labelEl}
        {field.note_fa && <p className="psf-hint">{field.note_fa}</p>}
        <EditableTableField field={field} value={value} onChange={onChange} disabled={disabled} showToast={showToast} onRosterMemberCreated={onRosterMemberCreated} />
        <FieldErrorMsg message={fieldError} />
      </div>
    )
  }

  if (t === 'date_range_list') {
    return (
      <div className={shellCls} data-testid={`uf-range-${name}`}>
        {labelEl}
        <DateRangeListField value={value} onChange={onChange} disabled={disabled} listFieldName={name} />
        <FieldErrorMsg message={fieldError} />
      </div>
    )
  }

  if (t === 'datetime') {
    return (
      <div className={shellCls}>
        {labelEl}
        {field.description_fa && <p className="psf-hint">{field.description_fa}</p>}
        <ShamsiDateTimeFieldBridge value={value ?? ''} onChange={onChange} disabled={disabled} idPrefix={id} />
        <FieldErrorMsg message={fieldError} />
      </div>
    )
  }

  // text | email | tel fallback
  const inputType = t === 'email' ? 'email' : t === 'tel' ? 'tel' : 'text'
  const dir = field.dir === 'ltr' || inputType !== 'text' ? 'ltr' : 'rtl'
  return (
    <label className={shellCls} htmlFor={id} data-testid={fieldTestId}>
      {labelEl}
      {field.description_fa && <p className="psf-hint">{field.description_fa}</p>}
      <input id={id} type={inputType} className="psf-input form-input" dir={dir} data-testid={inputTestId} value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
      <FieldErrorMsg message={fieldError} />
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
  /**
   * در صورت ارائه، فقط فیلدهایی که نامشان در این فهرست/Set است قابل ویرایش‌اند
   * و بقیه فقط-خواندنی می‌شوند (علاوه بر disabled سراسری).
   */
  editableFieldNames = null,
  instanceId = null,
  /** نگاشت نام فیلد → پیام خطا (پس از اعتبارسنجی ناموفق) */
  fieldErrors = null,
  /** پس از افزودن مدرس/کمک‌مدرس جدید — برای همگام‌سازی همهٔ کشویی‌ها */
  onRosterMemberCreated = null,
}) {
  const filtered = useMemo(() => filterSchemaForRole(schemaJson || { fields: [] }, role), [schemaJson, role])
  const fields = filtered.fields || []

  const editableSet = useMemo(() => {
    if (editableFieldNames == null) return null
    return editableFieldNames instanceof Set ? editableFieldNames : new Set(editableFieldNames)
  }, [editableFieldNames])

  const setVal = useCallback(
    (name, v) => onChange({ ...values, [name]: v }),
    [values, onChange],
  )

  return (
    <div
      className="unified-form-renderer psf-fields"
      style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', width: '100%', maxWidth: '100%', minWidth: 0 }}
    >
      {fields.map((field) => {
        if (!field?.name) return null
        if (!fieldVisible(field, values)) return null
        const fieldDisabled = disabled || (editableSet ? !editableSet.has(field.name) : false)
        const fieldError = fieldErrors?.[field.name] || null
        return (
          <UnifiedField
            key={field.name}
            field={field}
            values={values}
            onFieldChange={setVal}
            disabled={fieldDisabled}
            onUploadFile={onUploadFile}
            showToast={showToast}
            instanceId={instanceId}
            fieldError={fieldError}
            onRosterMemberCreated={onRosterMemberCreated}
          />
        )
      })}
    </div>
  )
}
