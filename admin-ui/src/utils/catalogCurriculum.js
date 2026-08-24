/**
 * Payload و نرمال‌سازی فیلدهای برنامهٔ درسی کاتالوگ (از جمله پیش‌نیاز ساخت‌یافته).
 */

export const SYSTEM_PREREQUISITES = [
  {
    code: 'internship_started',
    label_fa: 'شروع انترنی',
    enforced: false,
  },
  {
    code: 'clinical_hours_500',
    label_fa: '۵۰۰ ساعت کسب تجربه بالینی',
    enforced: false,
  },
  {
    code: 'individual_supervision_50h',
    label_fa: 'خاتمه ۵۰ ساعت سوپرویژن فردی',
    enforced: false,
  },
  {
    code: 'individual_supervision_100h',
    label_fa: 'خاتمه ۱۰۰ ساعت سوپرویژن فردی',
    enforced: false,
  },
]

export const SYSTEM_PREREQUISITE_CODES = SYSTEM_PREREQUISITES.map((item) => item.code)

export function systemPrerequisiteLabel(code) {
  const found = SYSTEM_PREREQUISITES.find((item) => item.code === code)
  return found?.label_fa || code
}

export function isUnenforcedSystemPrerequisite(code) {
  const found = SYSTEM_PREREQUISITES.find((item) => item.code === String(code || '').trim())
  return Boolean(found && found.enforced !== true)
}

export function emptyCurriculum() {
  return {
    units: '2',
    curriculum_term: '',
    program_kind: 'introductory',
    class_hours: '',
    retake_exam: false,
    prerequisite_notes: '',
    prerequisite_codes: [],
    system_prerequisite_codes: [],
    subtitle_fa: '',
    single_course_allowed: false,
  }
}

export function curriculumFromCourse(course) {
  return {
    units: course?.units != null ? String(course.units) : '',
    curriculum_term: course?.curriculum_term != null ? String(course.curriculum_term) : '',
    program_kind: course?.program_kind || '',
    class_hours: course?.class_hours || '',
    retake_exam: Boolean(course?.retake_exam),
    prerequisite_notes: course?.prerequisite_notes || '',
    prerequisite_codes: Array.isArray(course?.prerequisite_codes)
      ? course.prerequisite_codes.map((c) => String(c).trim()).filter(Boolean)
      : [],
    system_prerequisite_codes: Array.isArray(course?.system_prerequisite_codes)
      ? course.system_prerequisite_codes.map((c) => String(c).trim()).filter(Boolean)
      : [],
    subtitle_fa: course?.subtitle_fa || '',
    single_course_allowed: Boolean(course?.single_course_allowed),
  }
}

export function normalizePrerequisiteCodes(raw) {
  if (!Array.isArray(raw)) return []
  const out = []
  const seen = new Set()
  for (const item of raw) {
    const code = String(item || '').trim()
    if (!code || seen.has(code)) continue
    seen.add(code)
    out.push(code)
  }
  return out
}

export function togglePrerequisiteCode(codes, value) {
  const list = normalizePrerequisiteCodes(codes)
  const code = String(value || '').trim()
  if (!code) return list
  if (list.includes(code)) return list.filter((c) => c !== code)
  return [...list, code]
}

export function curriculumPayload(fields) {
  const body = {}
  const units = Number(fields.units)
  if (Number.isFinite(units) && units >= 1) body.units = units
  const term = Number(fields.curriculum_term)
  if (Number.isFinite(term) && term >= 1) body.curriculum_term = term
  if (fields.program_kind) body.program_kind = fields.program_kind
  if (String(fields.class_hours || '').trim()) body.class_hours = String(fields.class_hours).trim()
  body.retake_exam = Boolean(fields.retake_exam)
  body.prerequisite_codes = normalizePrerequisiteCodes(fields.prerequisite_codes)
  body.system_prerequisite_codes = normalizePrerequisiteCodes(fields.system_prerequisite_codes)
  if (String(fields.prerequisite_notes || '').trim()) {
    body.prerequisite_notes = String(fields.prerequisite_notes).trim()
  }
  if (String(fields.subtitle_fa || '').trim()) body.subtitle_fa = String(fields.subtitle_fa).trim()
  body.single_course_allowed = Boolean(fields.single_course_allowed)
  return body
}
