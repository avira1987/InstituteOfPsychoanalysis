// اعتبارسنجی فرم یکپارچه در فرانت — هم‌تراز app/services/forms/validate.py
import { fieldVisible, fieldRequired } from './formConditions'

function normRole(r) {
  return (r || '').trim().toLowerCase()
}

function isEmpty(v) {
  if (v === undefined || v === null) return true
  if (typeof v === 'string' && v.trim() === '') return true
  if (typeof v === 'boolean' || typeof v === 'number') return false
  if (Array.isArray(v)) return v.length === 0
  if (typeof v === 'object') {
    if ('file_name' in v || 'url' in v || 'content_base64' in v) {
      return !(v.file_name || v.url || v.content_base64)
    }
    return Object.keys(v).length === 0
  }
  return false
}

export function filterSchemaForRole(schema, role) {
  const fields = Array.isArray(schema?.fields) ? schema.fields : []
  const r = normRole(role)
  const formVisibleTo = Array.isArray(schema?.visible_to) ? schema.visible_to.map(normRole) : null
  if (formVisibleTo?.length && r && !formVisibleTo.includes(r)) {
    return { ...(schema || {}), fields: [] }
  }
  const out = fields.filter((f) => {
    if (!f || typeof f !== 'object') return false
    if (r === 'student' && f.confidential) return false
    if (Array.isArray(f.visible_to) && f.visible_to.length) {
      const allowed = f.visible_to.map(normRole)
      if (r && !allowed.includes(r)) return false
    }
    return true
  })
  return { ...(schema || {}), fields: out }
}

export function collectSchemaKeys(schema) {
  const keys = new Set()
  for (const f of schema?.fields || []) {
    if (!f?.name) continue
    keys.add(f.name)
    const t = (f.type || '').toLowerCase()
    if (t === 'radio_list' || t === 'checkbox_list') keys.add(`${f.name}_ack`)
  }
  return keys
}

export function checkRules(field, val) {
  let rules = field.validation
  if (!rules || typeof rules !== 'object') {
    rules = {}
    if (field.min !== undefined) rules.min = field.min
    if (field.max !== undefined) rules.max = field.max
    if (!Object.keys(rules).length) return null
  }
  const label = field.label_fa || field.name
  if (typeof val === 'number') {
    if (rules.min != null && val < rules.min) return `${label}: حداقل ${rules.min}`
    if (rules.max != null && val > rules.max) return `${label}: حداکثر ${rules.max}`
  }
  if (typeof val === 'string') {
    if (rules.min_len != null && val.trim().length < rules.min_len) return `${label}: حداقل ${rules.min_len} نویسه`
    if (rules.max_len != null && val.length > rules.max_len) return `${label}: حداکثر ${rules.max_len} نویسه`
    if (rules.pattern) {
      try {
        const re = new RegExp(`^(?:${rules.pattern})$`)
        if (!re.test(val)) return `${label}: قالب نامعتبر`
      } catch {
        /* الگوی نامعتبر را نادیده بگیر */
      }
    }
  }
  if (Array.isArray(val) && rules.max_selection != null && val.length > rules.max_selection) {
    return `${label}: حداکثر ${rules.max_selection} انتخاب`
  }
  if (Array.isArray(val) && rules.min_selection != null && val.length < rules.min_selection) {
    return `${label}: حداقل ${rules.min_selection} انتخاب لازم است`
  }
  return null
}

export function isEffectivelyEmptyCourseTableRow(row, columns) {
  if (!row || typeof row !== 'object') return true
  if (Array.isArray(columns) && columns.length) {
    return columns.every((col) => {
      const ct = (col.type || 'text').toLowerCase()
      const v = row[col.name]
      if (ct === 'checkbox') return !v
      return isEmpty(v)
    })
  }
  return isEmpty(row.course_name)
}

/** جدول دروس خالی است یا فقط ردیف placeholder دارد. */
export function isEffectivelyEmptyCourseTable(rows, columns) {
  if (!Array.isArray(rows) || rows.length === 0) return true
  return rows.every((r) => isEffectivelyEmptyCourseTableRow(r, columns))
}

function isTableRowEmpty(row, columns) {
  return isEffectivelyEmptyCourseTableRow(row, columns)
}

export function validateTableField(field, val) {
  const label = field.label_fa || field.name
  const columns = Array.isArray(field.columns) ? field.columns : []
  const rows = Array.isArray(val) ? val : []
  const filledRows = rows.filter((r) => !isTableRowEmpty(r, columns))
  if (field.required && filledRows.length === 0) {
    return `${label}: حداقل یک ردیف کامل لازم است`
  }
  for (let i = 0; i < filledRows.length; i += 1) {
    const row = filledRows[i]
    for (const col of columns) {
      if (col.auto_fill) continue
      const ct = (col.type || 'text').toLowerCase()
      if (ct === 'checkbox') continue
      const v = row[col.name]
      if (isEmpty(v)) {
        return `${label} — ردیف ${i + 1}: «${col.label_fa || col.name}» خالی است`
      }
    }
  }
  return null
}

export function validateDateRangeList(val, label = 'بازه تاریخ') {
  const ranges = Array.isArray(val) ? val : []
  for (let i = 0; i < ranges.length; i += 1) {
    const r = ranges[i]
    const start = r?.start
    const end = r?.end
    if (start && end && String(end) <= String(start)) {
      return `${label} — بازه ${i + 1}: تاریخ پایان باید بعد از شروع باشد`
    }
  }
  return null
}

/**
 * @param {object} schema { fields: [...] }
 * @param {object} answers
 * @param {{ role?: string, allowedFieldNames?: string[] }} [opts]
 * @returns {{ ok: boolean, missing: string[] }}
 */
export function validateUnifiedAnswers(schema, answers, opts = {}) {
  const vals = answers || {}
  const src = opts.role ? filterSchemaForRole(schema, opts.role) : schema
  const fields = Array.isArray(src?.fields) ? src.fields : []
  const allow = Array.isArray(opts.allowedFieldNames) && opts.allowedFieldNames.length
    ? new Set(opts.allowedFieldNames)
    : null
  const missing = []
  for (const field of fields) {
    if (!field?.name) continue
    if (allow && !allow.has(field.name)) continue
    if (!fieldVisible(field, vals)) continue
    const t = (field.type || 'text').toLowerCase()
    const val = vals[field.name]
    if (fieldRequired(field, vals)) {
      if (t === 'checkbox') {
        if (!val) { missing.push(field.label_fa || field.name); continue }
      } else if (t === 'radio_list' || t === 'checkbox_list') {
        const ack = vals[`${field.name}_ack`]
        if (Array.isArray(val)) {
          if (val.length === 0 && !ack) { missing.push(field.label_fa || field.name); continue }
        } else if (isEmpty(val) && !ack) { missing.push(field.label_fa || field.name); continue }
      } else if (t === 'table') {
        const err = validateTableField(field, val)
        if (err) { missing.push(err); continue }
      } else if (isEmpty(val)) {
        missing.push(field.label_fa || field.name); continue
      }
    }
    if (!isEmpty(val)) {
      if (t === 'date_range_list') {
        const err = validateDateRangeList(val, field.label_fa || field.name)
        if (err) { missing.push(err); continue }
      }
      const err = checkRules(field, val)
      if (err) missing.push(err)
    }
  }
  return { ok: missing.length === 0, missing }
}
