/** نرمال‌سازی context برای گزارش کمپین بازاریابی (هم‌راستا با semester_prep_marketing_pdf). */

function nonemptyTable(value) {
  if (!Array.isArray(value)) return []
  return value.filter(
    (row) => row && typeof row === 'object' && Object.values(row).some((v) => v != null && v !== '' && v !== false),
  )
}

export function draftRowToFinalized(row) {
  if (!row || typeof row !== 'object') return row
  return {
    course_name: row.course_name || '',
    track: row.track || '',
    day: row.day || row.proposed_day || '',
    time: row.time || row.proposed_time || '',
    instructor: row.instructor || '',
    teaching_assistant: row.teaching_assistant || '',
    classroom_location: row.classroom_location || '',
    instructor_coordinated: row.instructor_coordinated,
  }
}

export function resolveMarketingHandoffContext(processCode, ctx) {
  const raw = ctx && typeof ctx === 'object' ? ctx : {}
  const out = { ...raw }

  if (processCode === 'fall_semester_preparation') {
    let fallFinal = nonemptyTable(raw.courses_finalized_fall)
    if (!fallFinal.length) fallFinal = nonemptyTable(raw.courses_finalized)
    if (!fallFinal.length) fallFinal = nonemptyTable(raw.courses_fall)
    if (!fallFinal.length) fallFinal = nonemptyTable(raw.courses)
    if (fallFinal.length && !nonemptyTable(raw.courses_finalized_fall).length) {
      out.courses_finalized_fall = fallFinal.map((row) =>
        row.proposed_day || row.proposed_time ? draftRowToFinalized(row) : row,
      )
    }

    let winterFinal = nonemptyTable(raw.courses_finalized_winter)
    if (!winterFinal.length) winterFinal = nonemptyTable(raw.courses_winter)
    if (winterFinal.length && !nonemptyTable(raw.courses_finalized_winter).length) {
      out.courses_finalized_winter = winterFinal.map((row) =>
        row.proposed_day || row.proposed_time ? draftRowToFinalized(row) : row,
      )
    }
  } else if (processCode === 'winter_semester_preparation') {
    let winterFinal = nonemptyTable(raw.courses_finalized)
    if (!winterFinal.length) winterFinal = nonemptyTable(raw.courses_winter)
    if (!winterFinal.length) winterFinal = nonemptyTable(raw.courses)
    if (winterFinal.length && !nonemptyTable(raw.courses_finalized).length) {
      out.courses_finalized = winterFinal.map((row) =>
        row.proposed_day || row.proposed_time ? draftRowToFinalized(row) : row,
      )
    }
  }

  return out
}

export function fmtRialDisplay(value) {
  if (value == null || value === '') return null
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  return `${n.toLocaleString('fa-IR')} ریال`
}

const TUITION_KEYS = [
  'per_unit_cost_introductory',
  'per_unit_cost_comprehensive',
  'interview_fee_introductory',
  'interview_fee_comprehensive',
]

export function hasTuitionOrInterviewData(ctx) {
  return TUITION_KEYS.some((k) => ctx[k] != null && ctx[k] !== '')
}
