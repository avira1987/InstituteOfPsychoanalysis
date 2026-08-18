/** نرمال‌سازی ردیف جدول دروس بدون وابستگی به API. */

function addTrackRef(refs, value) {
  const raw = String(value || '').trim()
  if (!raw) return
  refs.add(raw)
  refs.add(raw.toLowerCase())
}

/** کد و برچسب فارسی یک رسته را به مجموعهٔ کلیدهای معادل تبدیل می‌کند. */
export function collectTrackRefs(trackValue, trackCol) {
  const refs = new Set()
  addTrackRef(refs, trackValue)
  if (!refs.size) return refs
  const raw = String(trackValue || '').trim()
  for (const opt of trackCol?.options || []) {
    if (typeof opt !== 'object') continue
    const val = String(opt.value || '').trim()
    const lab = String(opt.label_fa || '').trim()
    if (raw === val || raw === lab) {
      addTrackRef(refs, val)
      addTrackRef(refs, lab)
    }
  }
  return refs
}

/** آیا دو مقدار رسته (کد انگلیسی یا برچسب فارسی) یکی هستند؟ */
export function tracksAreEquivalent(a, b, trackCol) {
  const sa = String(a || '').trim()
  const sb = String(b || '').trim()
  if (!sa && !sb) return true
  if (!sa || !sb) return false
  if (sa === sb || sa.toLowerCase() === sb.toLowerCase()) return true
  const left = collectTrackRefs(sa, trackCol)
  for (const r of collectTrackRefs(sb, trackCol)) {
    if (left.has(r)) return true
  }
  return false
}

/**
 * وقتی کاتالوگ رسته را به‌صورت کد برمی‌گرداند و ردیف برچسب فارسی دارد،
 * نباید رسته «عوض‌شده» محسوب شود — وگرنه مدرس/کمک‌مدرس پاک می‌شود.
 */
export function shouldReplaceRowTrackFromCatalog(row, expectedTrackCode, trackCol) {
  const expected = String(expectedTrackCode || '').trim()
  if (!expected) return false
  if (tracksAreEquivalent(row?.track, expected, trackCol)) return false
  if (tracksAreEquivalent(row?.track_code, expected, trackCol)) return false
  return true
}

export function isRosterSelectColumn(col) {
  if (!col || col.auto_fill) return false
  const t = (col.type || '').toLowerCase()
  return t === 'select' || t === 'creatable_select' || Boolean(col.creatable || col.searchable)
}

/** مقدار سلکت درس: برچسب ذخیره‌شده را به کد کاتالوگ برمی‌گرداند. */
export function catalogSelectValueFromRow(row, catalogOptions) {
  const raw = String(row?.course_name || '').trim()
  if (!raw || !Array.isArray(catalogOptions)) return raw
  for (const opt of catalogOptions) {
    if (typeof opt !== 'object') continue
    const val = String(opt.value || '').trim()
    const lab = String(opt.label_fa || '').trim()
    if (raw === val || raw === lab) return val || raw
  }
  return raw
}

/** نرمال‌سازی مقدار ذخیره‌شده ردیف جدول برای select مدرس/کمک‌مدرس */
export function rosterSelectValueFromRow(row, idKey, nameKey) {
  if (!row || typeof row !== 'object') return ''
  const id = row[idKey]
  if (id != null && String(id).trim() !== '') return String(id)
  const name = row[nameKey]
  return name != null ? String(name) : ''
}

/** مقدار اولیه select از دادهٔ ذخیره‌شده (نام یا شناسه) */
export function normalizeCourseTableInitialRows(tableField, rows) {
  if (!Array.isArray(rows) || !tableField?.columns) return rows
  const colByName = Object.fromEntries((tableField.columns || []).map((c) => [c.name, c]))
  return rows.map((row) => {
    if (!row || typeof row !== 'object') return row
    const next = { ...row }
    const instructorCol = colByName.instructor
    if (instructorCol && isRosterSelectColumn(instructorCol)) {
      next.instructor = rosterSelectValueFromRow(row, 'instructor_id', 'instructor')
    }
    const taCol = colByName.teaching_assistant
    if (taCol && isRosterSelectColumn(taCol)) {
      next.teaching_assistant = rosterSelectValueFromRow(row, 'teaching_assistant_id', 'teaching_assistant')
    }
    const courseCol = colByName.course_name
    if (courseCol && isRosterSelectColumn(courseCol)) {
      next.course_name = catalogSelectValueFromRow(row, courseCol.options || [])
    }
    return next
  })
}
