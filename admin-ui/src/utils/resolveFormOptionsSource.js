/**
 * بارگذاری گزینه‌های داینامیک فرم اپراتور (users، چارت کمیته دروس).
 */
import { userApi } from '../services/api'
import api from '../services/api'

export async function resolveUsersOptionsSource(source) {
  if (!source || source.type !== 'users') return []
  const params = {}
  if (source.role) params.role = source.role
  if (source.is_active != null) params.is_active = source.is_active
  try {
    const res = await userApi.list(params)
    return (Array.isArray(res.data) ? res.data : []).map((u) => ({
      value: u.id,
      label_fa: u.full_name_fa || u.username || u.id,
    }))
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

export async function resolveCourseCommitteeRoster(track, kind) {
  const t = (track || '').trim()
  if (!t || !kind) return []
  try {
    const res = await api.get('admin/course-committee-roster', {
      params: { track: t, kind, _ts: Date.now() },
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

export async function createCourseCatalogEntry(nameFa) {
  const res = await api.post('admin/course-catalog', { name_fa: nameFa })
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
  return res.data?.member
}

/** resolve options_source برای فیلد یا ستون جدول */
export async function resolveFormOptionsSource(source) {
  if (!source || typeof source !== 'object') return { options: [], optionsByTrack: null }

  if (source.type === 'users') {
    const options = await resolveUsersOptionsSource(source)
    return { options, optionsByTrack: null }
  }

  if (source.type === 'course_catalog') {
    const options = await resolveCourseCatalog()
    return { options, optionsByTrack: null }
  }

  if (source.type === 'course_committee_tracks') {
    const options = await resolveCourseCommitteeTracks()
    return { options, optionsByTrack: null }
  }

  if (source.type === 'course_committee_roster') {
    const kind = source.kind || 'instructor'
    const trackCodes = await loadAllTrackCodes()
    const optionsByTrack = {}
    await Promise.all(
      trackCodes.map(async (code) => {
        optionsByTrack[code] = await resolveCourseCommitteeRoster(code, kind)
      }),
    )
    return { options: [], optionsByTrack }
  }

  return { options: [], optionsByTrack: null }
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
