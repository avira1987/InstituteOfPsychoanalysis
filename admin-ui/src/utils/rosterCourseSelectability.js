/**
 * انتخاب‌پذیری مدرس/کمک‌مدرس برای یک درس.
 * عضو چارت بدون تیک درس در همان رسته دیده می‌شود؛ تیک صریح درس دیگر پنهان می‌شود.
 */

function optionRawValue(opt) {
  return String(typeof opt === 'object' ? (opt?.value ?? '') : opt)
}

export function courseValueRefs(courseValue, catalogOptions = []) {
  const raw = String(courseValue || '').trim()
  if (!raw) return new Set()
  const refs = new Set([raw])
  for (const opt of catalogOptions || []) {
    if (typeof opt !== 'object') {
      if (String(opt) === raw) refs.add(String(opt))
      continue
    }
    const val = String(opt.value || '').trim()
    const lab = String(opt.label_fa || '').trim()
    const aliases = Array.isArray(opt.aliases)
      ? opt.aliases.map((a) => String(a || '').trim()).filter(Boolean)
      : []
    if (val === raw || lab === raw || aliases.includes(raw)) {
      if (val) refs.add(val)
      if (lab) refs.add(lab)
      for (const a of aliases) refs.add(a)
    }
  }
  return refs
}

export function collectOptionGrants(opt) {
  if (!opt || typeof opt !== 'object') return []
  const lists = [
    opt.authorized_courses,
    opt.instructor_authorized_courses,
    opt.ta_authorized_courses,
  ]
  const out = []
  const seen = new Set()
  for (const list of lists) {
    if (!Array.isArray(list)) continue
    for (const item of list) {
      let val = ''
      if (typeof item === 'string') val = item
      else if (item && typeof item === 'object') {
        val = item.course_code || item.course_name || item.value || item.code || ''
      }
      val = String(val || '').trim()
      if (!val || seen.has(val)) continue
      seen.add(val)
      out.push(val)
    }
  }
  return out
}

export function grantsIncludeCourse(grants, courseValue, catalogOptions = []) {
  if (!Array.isArray(grants) || !grants.length) return false
  const refs = courseValueRefs(courseValue, catalogOptions)
  if (!refs.size) return false
  for (const item of grants) {
    let val = ''
    if (typeof item === 'string') val = item
    else if (item && typeof item === 'object') {
      val = item.course_code || item.course_name || item.value || item.code || ''
    }
    val = String(val || '').trim()
    if (!val) continue
    if (refs.has(val)) return true
    for (const r of courseValueRefs(val, catalogOptions)) {
      if (refs.has(r)) return true
    }
  }
  return false
}

export function isRosterOptionSelectableForCourse(opt, courseValue, extra = {}) {
  if (!String(courseValue || '').trim()) return true
  if (opt == null) return true
  if (typeof opt !== 'object') {
    return extra.authorizedValues instanceof Set
      ? extra.authorizedValues.has(String(opt))
      : true
  }
  if (opt.selectable === false) return false
  const grants = collectOptionGrants(opt)
  if (!grants.length) return true
  return grantsIncludeCourse(grants, courseValue, extra.catalogOptions || [])
}

const NOT_AUTHORIZED_SUFFIX = ' — مجاز برای این درس نیست'

export function rosterOptionDisplayLabel(opt) {
  const base = typeof opt === 'object' ? (opt.label_fa || opt.value || '') : String(opt ?? '')
  if (typeof opt === 'object' && opt.disabled) return `${base}${NOT_AUTHORIZED_SUFFIX}`
  return base
}

export function mergeRosterOptionLists(primary, extra) {
  const out = []
  const seen = new Set()
  for (const opt of [...(primary || []), ...(extra || [])]) {
    const v = optionRawValue(opt)
    if (!v || seen.has(v)) continue
    seen.add(v)
    out.push(opt)
  }
  return out
}

export function markRosterOptionsForCourse(options, courseValue, extra = {}) {
  const list = Array.isArray(options) ? options : []
  const hideUnauthorized = extra.hideUnauthorized === true
  if (!String(courseValue || '').trim()) return hideUnauthorized ? [] : list
  const kind = extra.kind || 'instructor'
  const catalogOptions = extra.catalogOptions || []
  const authorizedValues = extra.authorizedValues instanceof Set ? extra.authorizedValues : null

  const mapped = list.map((opt) => {
    if (opt == null) return opt
    if (typeof opt !== 'object') {
      const selectable = authorizedValues ? authorizedValues.has(String(opt)) : true
      return selectable
        ? opt
        : {
            value: opt,
            label_fa: String(opt),
            disabled: true,
            disabled_reason_fa: 'مجاز برای این درس نیست',
          }
    }
    const value = optionRawValue(opt)
    const selectable = authorizedValues
      ? authorizedValues.has(value) || isRosterOptionSelectableForCourse(opt, courseValue, { kind, catalogOptions })
      : isRosterOptionSelectableForCourse(opt, courseValue, { kind, catalogOptions })
    if (selectable) {
      return opt.disabled ? { ...opt, disabled: false } : opt
    }
    return {
      ...opt,
      disabled: true,
      disabled_reason_fa: opt.disabled_reason_fa || 'مجاز برای این درس نیست',
    }
  })

  const visible = hideUnauthorized
    ? mapped.filter((opt) => !(typeof opt === 'object' && opt && opt.disabled))
    : mapped

  if (hideUnauthorized) return visible

  return visible.sort((a, b) => {
    const da = typeof a === 'object' ? Boolean(a.disabled) : false
    const db = typeof b === 'object' ? Boolean(b.disabled) : false
    if (da === db) return 0
    return da ? 1 : -1
  })
}

/** گزینه‌های قابل نمایش مدرس/کمک‌مدرس پس از انتخاب درس در سطر جدول */
export function visibleRosterMembersForCourse(trackOptions, courseValue, extra = {}) {
  if (!String(courseValue || '').trim()) return []
  const base = mergeRosterOptionLists(trackOptions, extra.courseOptions || [])
  return markRosterOptionsForCourse(base, courseValue, {
    kind: extra.kind || 'instructor',
    catalogOptions: extra.catalogOptions || [],
    hideUnauthorized: extra.hideUnauthorized !== false,
  })
}
