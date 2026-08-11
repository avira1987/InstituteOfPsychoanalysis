/**
 * بارگذاری گزینه‌های داینامیک فرم اپراتور (users، چارت کمیته دروس).
 */
import { userApi } from '../services/api'
import api from '../services/api'

export async function resolveCourseClassRoster(courseCode) {
  const code = (courseCode || '').trim()
  if (!code) return []
  try {
    const res = await api.get('panel/instructor/course-roster', {
      params: { course_code: code, _ts: Date.now() },
      headers: { 'Cache-Control': 'no-store', Pragma: 'no-cache' },
    })
    const roster = res.data?.roster
    if (!Array.isArray(roster)) return []
    return roster.map((r) => ({
      value: r.student_id || r.student_code || r.name_fa,
      label_fa: r.name_fa || r.student_code || r.student_id || '—',
    }))
  } catch {
    return []
  }
}

export async function resolveUsersOptionsSource(source) {
  if (!source || source.type !== 'users') return []
  // options_source می‌تواند یک نقش (role) یا چند نقش (roles) داشته باشد
  const roles = Array.isArray(source.roles) && source.roles.length
    ? source.roles
    : [source.role || null]
  const baseParams = {}
  if (source.is_active != null) baseParams.is_active = source.is_active
  try {
    const responses = await Promise.all(
      roles.map((role) => userApi.list(role ? { ...baseParams, role } : baseParams)),
    )
    const seen = new Set()
    const options = []
    for (const res of responses) {
      for (const u of Array.isArray(res.data) ? res.data : []) {
        if (seen.has(u.id)) continue
        seen.add(u.id)
        options.push({ value: u.id, label_fa: u.full_name_fa || u.username || u.id })
      }
    }
    return options
  } catch {
    return []
  }
}

export async function resolveCourseCommitteeTracks() {
  try {
    const res = await api.get('admin/course-committee-roster/tracks', {
      params: { _ts: Date.now() },
      headers: { 'Cache-Control': 'no-store', Pragma: 'no-cache' },
    })
    const tracks = res.data?.tracks
    return Array.isArray(tracks) ? tracks : []
  } catch {
    return []
  }
}

export async function resolveCourseCommitteeRoster(track, kind, course) {
  const t = (track || '').trim()
  if (!t || !kind) return []
  try {
    const params = { track: t, kind, _ts: Date.now() }
    const courseVal = (course || '').trim()
    if (courseVal) params.course = courseVal
    const res = await api.get('admin/course-committee-roster', {
      params,
      headers: { 'Cache-Control': 'no-store', Pragma: 'no-cache' },
    })
    const members = res.data?.members
    return Array.isArray(members) ? members : []
  } catch {
    return []
  }
}

const _tracksCache = { promise: null }

export function invalidateFormOptionsCaches() {
  _tracksCache.promise = null
}

async function loadAllTrackCodes() {
  if (!_tracksCache.promise) {
    _tracksCache.promise = resolveCourseCommitteeTracks().then((opts) =>
      opts.map((o) => o.value).filter(Boolean),
    )
  }
  return _tracksCache.promise
}

export async function resolveCourseCatalog() {
  try {
    const res = await api.get('admin/course-catalog', {
      params: { _ts: Date.now() },
      headers: { 'Cache-Control': 'no-store', Pragma: 'no-cache' },
    })
    const courses = res.data?.courses
    return Array.isArray(courses) ? courses : []
  } catch {
    return []
  }
}

export async function createCourseCatalogEntry(nameFa, track) {
  const trackCode = String(track || '').trim()
  if (!trackCode) {
    throw new Error('ابتدا رسته را انتخاب کنید')
  }
  const res = await api.post('admin/course-catalog', { name_fa: nameFa, track: trackCode })
  return res.data?.course
}

export async function createCourseCommitteeTrack(nameFa) {
  const res = await api.post('admin/course-committee-roster/tracks', { name_fa: nameFa })
  invalidateFormOptionsCaches()
  return res.data?.track
}

export async function createCourseCommitteeMember({ track, kind, nameFa }) {
  const res = await api.post('admin/course-committee-roster/members', {
    track,
    kind,
    name_fa: nameFa,
  })
  invalidateFormOptionsCaches()
  return res.data?.member
}

/** کلید ذخیرهٔ گزینه‌های roster در _optionsByTrack — هم‌تراز با lookupRosterOptionsForRow */
export function resolveRosterTrackStorageKey(track, trackCol, optionsByTrack) {
  const raw = String(track || '').trim()
  if (!raw) return raw

  const opts = trackCol?.options || []
  const normalizedCodes = new Set()
  for (const opt of opts) {
    if (typeof opt !== 'object') continue
    const val = String(opt.value || '').trim()
    const lab = String(opt.label_fa || '').trim()
    if (val) normalizedCodes.add(val)
    if (raw === val || raw === lab) return val || raw
  }

  if (optionsByTrack && typeof optionsByTrack === 'object') {
    if (Array.isArray(optionsByTrack[raw])) return raw
    for (const k of Object.keys(optionsByTrack)) {
      if (String(k).trim() === raw) return k
    }
    for (const code of normalizedCodes) {
      if (Array.isArray(optionsByTrack[code])) return code
    }
  }

  return raw
}

function patchRosterColumnOptions(col, { kind, trackKey, members, member, mode }) {
  const src = col.options_source || {}
  if (src.type !== 'course_committee_roster') return col
  if ((src.kind || 'instructor') !== kind) return col

  const memberValue = member
    ? String(typeof member === 'object' ? member.value : member)
    : ''
  const appendOption = (options) => {
    const list = Array.isArray(options) ? [...options] : []
    if (!member || !memberValue) return list
    if (list.some((o) => String(typeof o === 'object' ? o.value : o) === memberValue)) {
      return list
    }
    return [...list, member]
  }

  const next = { ...col }
  if (next._optionsByTrack && typeof next._optionsByTrack === 'object') {
    const existing = next._optionsByTrack[trackKey]
    next._optionsByTrack = {
      ...next._optionsByTrack,
      [trackKey]: mode === 'replace' ? (members || []) : appendOption(existing),
    }
  }
  if (next._optionsByCourse && typeof next._optionsByCourse === 'object' && mode !== 'replace') {
    const updated = { ...next._optionsByCourse }
    for (const key of Object.keys(updated)) {
      updated[key] = appendOption(updated[key])
    }
    next._optionsByCourse = updated
  }
  if (Array.isArray(next.options) && next.options.length && mode !== 'replace') {
    next.options = appendOption(next.options)
  }
  return next
}

/** پس از افزودن مدرس/کمک‌مدرس جدید — به همهٔ ستون‌های roster در فرم اضافه شود */
export function propagateRosterMemberToForms(forms, member, { kind, track }) {
  if (!member || !track || !kind || !Array.isArray(forms)) return forms
  const trackInput = String(track).trim()
  const memberValue = String(typeof member === 'object' ? member.value : member)
  if (!trackInput || !memberValue) return forms

  return forms.map((form) => ({
    ...form,
    fields: (form.fields || []).map((field) => {
      if ((field.type || '').toLowerCase() !== 'table' || !Array.isArray(field.columns)) {
        return field
      }
      const trackCol = field.columns.find((c) => c.name === 'track')
      const trackKey = resolveRosterTrackStorageKey(
        trackInput,
        trackCol,
        field.columns.find((c) => {
          const src = c.options_source || {}
          return src.type === 'course_committee_roster' && (src.kind || 'instructor') === kind
        })?._optionsByTrack,
      )
      return {
        ...field,
        columns: field.columns.map((col) =>
          patchRosterColumnOptions(col, { kind, trackKey, member, mode: 'append' }),
        ),
      }
    }),
  }))
}

/** جایگزینی فهرست کامل مدرسین/کمک‌مدرسین یک رسته پس از همگام‌سازی با سرور */
export function replaceRosterTrackMembersInForms(forms, members, { kind, track }) {
  if (!track || !kind || !Array.isArray(forms) || !Array.isArray(members)) return forms
  const trackInput = String(track).trim()
  if (!trackInput) return forms

  return forms.map((form) => ({
    ...form,
    fields: (form.fields || []).map((field) => {
      if ((field.type || '').toLowerCase() !== 'table' || !Array.isArray(field.columns)) {
        return field
      }
      const trackCol = field.columns.find((c) => c.name === 'track')
      const rosterCol = field.columns.find((c) => {
        const src = c.options_source || {}
        return src.type === 'course_committee_roster' && (src.kind || 'instructor') === kind
      })
      const trackKey = resolveRosterTrackStorageKey(trackInput, trackCol, rosterCol?._optionsByTrack)
      return {
        ...field,
        columns: field.columns.map((col) =>
          patchRosterColumnOptions(col, { kind, trackKey, members, mode: 'replace' }),
        ),
      }
    }),
  }))
}

/** نگاشت نام/کد درس به کد رسته از گزینه‌های کاتالوگ */
export function resolveTrackForCourse(courseValue, catalogOptions) {
  const raw = String(courseValue || '').trim()
  if (!raw || !Array.isArray(catalogOptions)) return ''
  for (const opt of catalogOptions) {
    if (typeof opt !== 'object') continue
    const val = String(opt.value || '').trim()
    const lab = String(opt.label_fa || '').trim()
    if (val === raw || lab === raw) {
      return String(opt.track || '').trim()
    }
  }
  return ''
}

export async function resolveTraitCatalogOptions(kind) {
  const k = (kind || 'positive').trim().toLowerCase()
  try {
    const res = await api.get('panel/instructor/trait-catalog', {
      params: { kind: k, _ts: Date.now() },
      headers: { 'Cache-Control': 'no-store', Pragma: 'no-cache' },
    })
    const traits = res.data?.traits
    if (!Array.isArray(traits)) return []
    return traits.map((t) => ({
      value: t.value,
      label_fa: t.label_fa || t.value,
    }))
  } catch {
    return []
  }
}

/** resolve options_source برای فیلد یا ستون جدول */
export async function resolveFormOptionsSource(source, contextData = null) {
  if (!source || typeof source !== 'object') return { options: [], optionsByTrack: null, optionsByCourse: null }

  if (source.type === 'users') {
    const options = await resolveUsersOptionsSource(source)
    return { options, optionsByTrack: null, optionsByCourse: null }
  }

  if (source.type === 'course_catalog') {
    const options = await resolveCourseCatalog()
    return { options, optionsByTrack: null, optionsByCourse: null }
  }

  if (source.type === 'course_committee_tracks') {
    const options = await resolveCourseCommitteeTracks()
    return { options, optionsByTrack: null, optionsByCourse: null }
  }

  if (source.type === 'course_committee_roster') {
    const kind = source.kind || 'instructor'
    const filterCol = source.filter_by_column || 'track'

    const trackCodes = await loadAllTrackCodes()
    const optionsByTrack = {}
    await Promise.all(
      trackCodes.map(async (code) => {
        optionsByTrack[code] = await resolveCourseCommitteeRoster(code, kind)
      }),
    )

    let optionsByCourse = null
    if (filterCol === 'course_name') {
      const catalog = await resolveCourseCatalog()
      optionsByCourse = {}
      await Promise.all(
        catalog.map(async (courseOpt) => {
          const trackCode = (courseOpt.track || '').trim()
          const value = courseOpt.value
          const label = courseOpt.label_fa
          if (!trackCode || !value) return
          const members = await resolveCourseCommitteeRoster(trackCode, kind, value)
          optionsByCourse[value] = members
          if (label && label !== value) {
            optionsByCourse[label] = members
          }
        }),
      )
    }

    return { options: [], optionsByTrack, optionsByCourse }
  }

  if (source.type === 'course_class_roster') {
    const ctx = contextData && typeof contextData === 'object' ? contextData : {}
    const courseCode =
      source.course_code
      || ctx.course_id
      || ctx.course_code
      || ctx.lesson_course_label
      || ctx.course_name
    const options = await resolveCourseClassRoster(courseCode)
    return { options, optionsByTrack: null, optionsByCourse: null }
  }

  if (source.type === 'trait_catalog') {
    const options = await resolveTraitCatalogOptions(source.kind || 'positive')
    return { options, optionsByTrack: null, optionsByCourse: null }
  }

  return { options: [], optionsByTrack: null, optionsByCourse: null }
}

function lookupMapEntry(map, key) {
  if (!map || key == null || key === '') return []
  const raw = String(key).trim()
  if (!raw) return []
  const direct = map[raw]
  if (Array.isArray(direct) && direct.length) return direct
  for (const [k, opts] of Object.entries(map)) {
    if (String(k).trim() === raw && Array.isArray(opts) && opts.length) return opts
  }
  return []
}

/** گزینه‌های مدرس/کمک‌مدرس برای یک ردیف جدول — با fallback رسته و کاتالوگ درس */
export function lookupRosterOptionsForRow(col, row, columns = []) {
  if (!col || !row) return []

  const filterCol = col.filter_by_column || col.options_source?.filter_by_column

  if (col._optionsByCourse && row.course_name) {
    const byCourse = lookupMapEntry(col._optionsByCourse, row.course_name)
    if (byCourse.length) return byCourse
  }

  const trackKeys = []
  if (row.track) trackKeys.push(String(row.track).trim())
  const courseCol = (columns || []).find((c) => c.name === 'course_name')
  if (row.course_name && courseCol) {
    const derived = resolveTrackForCourse(row.course_name, courseCol.options || [])
    if (derived) trackKeys.push(derived)
  }

  if (col._optionsByTrack) {
    for (const tk of trackKeys) {
      if (!tk) continue
      const byTrack = lookupMapEntry(col._optionsByTrack, tk)
      if (byTrack.length) return byTrack
    }
  }

  if (filterCol && filterCol !== 'course_name' && col._optionsByTrack) {
    const byFilter = lookupMapEntry(col._optionsByTrack, row[filterCol])
    if (byFilter.length) return byFilter
  }

  return Array.isArray(col.options) ? col.options : []
}

/** آیا پیش‌نیاز فیلتر ستون مدرس/کمک‌مدرس برآورده شده است؟ */
export function rowMeetsRosterPrerequisite(col, row, columns = []) {
  const filterCol = col?.filter_by_column || col?.options_source?.filter_by_column
  if (!filterCol) return true
  if (String(row?.[filterCol] ?? '').trim()) return true
  if (filterCol === 'course_name') {
    return Boolean(resolveRosterTrackForRow(col, row, columns))
  }
  return false
}

/** کد رستهٔ مؤثر برای افزودن مدرس/کمک‌مدرس جدید */
export function resolveRosterTrackForRow(col, row, columns = []) {
  if (!row) return ''
  const track = String(row.track || '').trim()
  if (track) return track
  const courseCol = (columns || []).find((c) => c.name === 'course_name')
  if (row.course_name && courseCol) {
    const derived = resolveTrackForCourse(row.course_name, courseCol.options || [])
    if (derived) return derived
  }
  const filterCol = col?.options_source?.filter_by_column || col?.filter_by_column
  if (filterCol && filterCol !== 'course_name') {
    return String(row[filterCol] || '').trim()
  }
  return ''
}

/** نرمال‌سازی مقدار ذخیره‌شده ردیف جدول برای select مدرس/کمک‌مدرس */
export function rosterSelectValueFromRow(row, idKey, nameKey) {
  if (!row || typeof row !== 'object') return ''
  const id = row[idKey]
  if (id != null && String(id).trim() !== '') return String(id)
  const name = row[nameKey]
  return name != null ? String(name) : ''
}

/** قبل از ارسال به API: پر کردن نام نمایشی و شناسه کاربر */
export function denormalizeCourseRosterTableRows(tableField, rows) {
  if (!Array.isArray(rows) || !tableField?.columns) return rows
  const colByName = Object.fromEntries((tableField.columns || []).map((c) => [c.name, c]))
  const instructorCol = colByName.instructor
  const taCol = colByName.teaching_assistant

  const findLabel = (col, value) => {
    if (!col || value == null || value === '') return null
    const v = String(value)
    const byTrack = col._optionsByTrack
    if (byTrack && typeof byTrack === 'object') {
      for (const opts of Object.values(byTrack)) {
        const hit = (opts || []).find((o) => String(o.value) === v)
        if (hit) return hit.label_fa || v
      }
    }
    const byCourse = col._optionsByCourse
    if (byCourse && typeof byCourse === 'object') {
      for (const opts of Object.values(byCourse)) {
        const hit = (opts || []).find((o) => String(o.value) === v)
        if (hit) return hit.label_fa || v
      }
    }
    const flat = col.options || []
    const hit = flat.find((o) => String(typeof o === 'object' ? o.value : o) === v)
    if (hit) return typeof hit === 'object' ? hit.label_fa || v : hit
    return null
  }

  const isUuid = (s) =>
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(s))

  return rows.map((row) => {
    const next = { ...row }
    const courseCol = colByName.course_name
    if (courseCol && next.course_name != null && next.course_name !== '') {
      const raw = String(next.course_name)
      const catalogOpts = courseCol.options || []
      const hit = catalogOpts.find((o) => String(typeof o === 'object' ? o.value : o) === raw)
      if (hit) next.course_name = typeof hit === 'object' ? hit.label_fa || raw : hit
    }
    if (instructorCol && next.instructor != null && next.instructor !== '') {
      const raw = String(next.instructor)
      const label = findLabel(instructorCol, raw)
      if (isUuid(raw)) {
        next.instructor_id = raw
        next.instructor = label || raw
      }
    }
    if (taCol && next.teaching_assistant != null && next.teaching_assistant !== '') {
      const raw = String(next.teaching_assistant)
      const label = findLabel(taCol, raw)
      if (isUuid(raw)) {
        next.teaching_assistant_id = raw
        next.teaching_assistant = label || raw
      }
    }
    return next
  })
}

/** مقدار اولیه select از دادهٔ ذخیره‌شده (نام یا شناسه) */
export function normalizeCourseTableInitialRows(tableField, rows) {
  if (!Array.isArray(rows) || !tableField?.columns) return rows
  const names = new Set((tableField.columns || []).map((c) => c.name))
  return rows.map((row) => {
    if (!row || typeof row !== 'object') return row
    const next = { ...row }
    if (names.has('instructor')) {
      next.instructor = rosterSelectValueFromRow(row, 'instructor_id', 'instructor')
    }
    if (names.has('teaching_assistant')) {
      next.teaching_assistant = rosterSelectValueFromRow(row, 'teaching_assistant_id', 'teaching_assistant')
    }
    return next
  })
}
