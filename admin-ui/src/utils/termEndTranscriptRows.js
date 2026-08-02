/** Shared helpers to resolve term transcript rows from context or LMS fallback. */

function courseName(entry) {
  if (typeof entry === 'string') return entry
  if (!entry || typeof entry !== 'object') return '—'
  return (
    entry.course_name
    || entry.name_fa
    || entry.title_fa
    || entry.code
    || entry.course_code
    || '—'
  )
}

function isFailed(entry) {
  if (!entry || typeof entry !== 'object') return false
  if (entry.incomplete || entry.status === 'I') return true
  const pf = (entry.pass_fail_status || entry.pass_fail || '').trim()
  if (pf === 'مردود' || pf === 'Fail' || pf === 'FAIL') return true
  const letter = String(entry.letter_grade || entry.grade || '').toUpperCase()
  if (letter === 'F' || letter === 'I' || letter === 'مردود') return true
  if (entry.passed === false || entry.pass === false) return true
  return false
}

function normalizeLmsCourses(extraData = {}) {
  const lms = extraData?.lms || {}
  const rows = []
  const push = (item) => {
    if (typeof item === 'object' && item) rows.push(item)
    else if (typeof item === 'string') rows.push({ code: item, course_name: item })
  }
  ;(lms.enrolled_courses || []).forEach(push)
  ;(lms.course_links || []).forEach(push)
  const seen = new Set()
  return rows.filter((r) => {
    const key = r.code || r.course_code || courseName(r)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function rowFromEntry(entry) {
  const failed = isFailed(entry)
  let units = Number(entry.units ?? entry.credit_hours ?? entry.credits ?? 1)
  if (!Number.isFinite(units)) units = 1
  if (failed) units = 0
  const numeric = entry.numeric_grade ?? entry.grade_numeric ?? entry.final_grade
  const letter = entry.letter_grade || entry.grade || (failed ? 'F' : '—')
  return {
    course_name: courseName(entry),
    course_code: entry.code || entry.course_code,
    units,
    numeric_grade: numeric != null && numeric !== '' ? Number(numeric) : null,
    letter_grade: letter,
    pass_fail_status: failed ? 'مردود' : 'قبول',
  }
}

export function resolveTermTranscriptRows(ctx = {}, extraData = {}) {
  const fromCtx = ctx.term_transcript_rows || ctx.termTranscriptRows
  if (Array.isArray(fromCtx) && fromCtx.length) {
    return fromCtx.map((r) => ({ ...r }))
  }
  return normalizeLmsCourses(extraData).map(rowFromEntry)
}

export function resolveDeclineFollowupRows(ctx = {}) {
  const rows = ctx.decline_followup_rows || ctx.declineFollowupRows
  if (Array.isArray(rows) && rows.length) return rows.map((r) => ({ ...r }))
  const failed = ctx.failed_courses || ctx.failedCourses || []
  if (!failed.length) return []
  return [{
    student_name: ctx.student_name || '—',
    student_phone: ctx.student_phone || '',
    failed_courses: Array.isArray(failed) ? failed.join('، ') : String(failed),
    followup_done: false,
  }]
}
