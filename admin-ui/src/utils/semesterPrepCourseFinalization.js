function isEffectivelyEmptyCourseTable(rows) {
  if (!Array.isArray(rows) || !rows.length) return true
  return rows.every((row) => !String(row?.course_name || '').trim())
}

function courseRowMatchKey(row) {
  return {
    code: String(row?.course_code || '').trim().toLowerCase(),
    name: String(row?.course_name || '').trim().toLowerCase(),
    track: String(row?.track_code || row?.track || '').trim().toLowerCase(),
  }
}

function findMatchingFinalizedRow(newRow, existingRows, used) {
  const { code, name, track } = courseRowMatchKey(newRow)
  if (code) {
    for (let i = 0; i < existingRows.length; i += 1) {
      if (used.has(i)) continue
      const oldCode = String(existingRows[i]?.course_code || '').trim().toLowerCase()
      if (oldCode && oldCode === code) return i
    }
  }
  if (name) {
    for (let i = 0; i < existingRows.length; i += 1) {
      if (used.has(i)) continue
      const oldName = String(existingRows[i]?.course_name || '').trim().toLowerCase()
      if (!oldName || oldName !== name) continue
      const oldTrack = String(existingRows[i]?.track_code || existingRows[i]?.track || '')
        .trim()
        .toLowerCase()
      if (track && oldTrack && track !== oldTrack) continue
      return i
    }
  }
  return -1
}

export function buildCoursesFinalizedFromDraft(courses) {
  if (!Array.isArray(courses) || !courses.length) return []
  return courses
    .filter((row) => row && String(row.course_name || '').trim())
    .map((row) => {
      const out = {
        course_name: row.course_name || '',
        track: row.track || '',
        day: row.proposed_day || row.day || '',
        time: row.proposed_time || row.time || '',
        instructor: row.instructor || '',
        teaching_assistant: row.teaching_assistant || '',
        classroom_location: row.classroom_location || '',
        instructor_coordinated: Boolean(row.instructor_coordinated),
      }
      if (row.track_code) out.track_code = row.track_code
      if (row.course_code) out.course_code = row.course_code
      if (row.instructor_id) out.instructor_id = row.instructor_id
      if (row.teaching_assistant_id) out.teaching_assistant_id = row.teaching_assistant_id
      if (row.units != null && row.units !== '') out.units = row.units
      return out
    })
}

export function syncCoursesFinalizedFromDraft(draft, existing) {
  const built = buildCoursesFinalizedFromDraft(draft)
  if (!built.length) return []
  const existingRows = Array.isArray(existing) ? existing.filter((r) => r && typeof r === 'object') : []
  if (!existingRows.length) return built
  const used = new Set()
  return built.map((newRow) => {
    const idx = findMatchingFinalizedRow(newRow, existingRows, used)
    if (idx < 0) return newRow
    used.add(idx)
    const old = existingRows[idx]
    const merged = { ...newRow }
    if (old.classroom_location) merged.classroom_location = old.classroom_location
    if (old.instructor_coordinated) merged.instructor_coordinated = true
    return merged
  })
}

export function applyCourseFinalizationPrefill(init, ctx, processCode) {
  if (processCode === 'fall_semester_preparation') {
    const draftPairs = [
      ['courses_finalized_fall', 'courses_fall'],
      ['courses_finalized_winter', 'courses_winter'],
    ]
    for (const [finalName, draftName] of draftPairs) {
      let draft = ctx[draftName]
      if ((!draft || !draft.length) && draftName === 'courses_fall') {
        draft = ctx.courses
      }
      if (!isEffectivelyEmptyCourseTable(draft)) {
        init[finalName] = syncCoursesFinalizedFromDraft(draft, init[finalName])
      }
    }
  }
  if (processCode === 'winter_semester_preparation') {
    if (!isEffectivelyEmptyCourseTable(ctx.courses)) {
      init.courses_finalized = syncCoursesFinalizedFromDraft(ctx.courses, init.courses_finalized)
    }
  }
  return init
}

export function hasCourseFinalizationDraftSource(ctx) {
  if (!ctx || typeof ctx !== 'object') return false
  return (
    !isEffectivelyEmptyCourseTable(ctx.courses_fall)
    || !isEffectivelyEmptyCourseTable(ctx.courses_winter)
    || !isEffectivelyEmptyCourseTable(ctx.courses)
  )
}

const CTX_SUBMITTED = '__student_forms_submitted_states'

/** آیا فرم مرحلهٔ آماده‌سازی ترم ثبت شده و دکمهٔ پیشروی باید فعال باشد؟ */
export function isSemesterPrepStepFormSubmitted(contextData, currentState, locallySubmittedState) {
  if (!currentState) return true
  if (locallySubmittedState && locallySubmittedState === currentState) return true
  const submitted = contextData?.[CTX_SUBMITTED]
  if (!submitted || typeof submitted !== 'object' || Array.isArray(submitted)) return false
  return Boolean(submitted[currentState])
}
