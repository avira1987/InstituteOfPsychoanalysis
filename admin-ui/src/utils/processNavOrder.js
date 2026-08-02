/**
 * ترتیب نمایش فرایندها در سایدبار — اولویت راه‌اندازی اتوماسیون و گردشکار مرکز.
 * هم‌راستا با app/meta/process_nav_order.py و docs/institute_onboarding_test_guide_fa.md
 */

/** @type {readonly string[]} */
const WAVE1_ORDER = [
  'fall_semester_preparation',
  'winter_semester_preparation',
  'introductory_course_registration',
  'introductory_term_end',
  'comprehensive_course_registration',
  'comprehensive_term_start',
  'comprehensive_term_end',
  'start_therapy',
  'session_payment',
  'attendance_tracking',
  'supervision_block_transition',
  'class_attendance',
  'thesis_defense_request',
]

/** @type {readonly string[]} */
const WAVE2_ORDER = [
  'violation_registration',
  'educational_leave',
  'full_education_leave',
  'therapy_completion',
  'supervision_50h_completion',
  'internship_readiness_consultation',
  'theory_course_completion',
  'student_non_registration',
]

const WAVE1_INDEX = Object.fromEntries(WAVE1_ORDER.map((code, idx) => [code, idx]))
const WAVE2_INDEX = Object.fromEntries(WAVE2_ORDER.map((code, idx) => [code, idx]))

/**
 * @param {string} processCode
 * @param {string} [labelFa]
 * @param {number | null | undefined} [sopOrder]
 */
export function processNavSortKey(processCode, labelFa = '', sopOrder = null) {
  const code = String(processCode || '').trim().toLowerCase()
  if (code in WAVE1_INDEX) return [0, WAVE1_INDEX[code], code]
  if (code in WAVE2_INDEX) return [1, WAVE2_INDEX[code], code]
  if (typeof sopOrder === 'number' && Number.isFinite(sopOrder)) return [2, sopOrder, code]
  return [3, String(labelFa || code), code]
}

/**
 * @param {string} processCode
 * @param {string} [labelFa]
 * @param {number | null | undefined} [sopOrder]
 * @returns {0 | 1 | 2 | 3}
 */
export function processNavUsageTier(processCode, labelFa = '', sopOrder = null) {
  return processNavSortKey(processCode, labelFa, sopOrder)[0]
}

/**
 * @param {Array<{ processCode?: string, process_code?: string, label?: string, label_fa?: string, sop_order?: number | null }>} items
 */
export function sortProcessNavItems(items) {
  const list = Array.isArray(items) ? [...items] : []
  return list.sort((a, b) => {
    const codeA = (a.processCode || a.process_code || '').trim().toLowerCase()
    const codeB = (b.processCode || b.process_code || '').trim().toLowerCase()
    const labelA = (a.label || a.label_fa || '').trim()
    const labelB = (b.label || b.label_fa || '').trim()
    const keyA = processNavSortKey(codeA, labelA, a.sop_order)
    const keyB = processNavSortKey(codeB, labelB, b.sop_order)
    for (let i = 0; i < keyA.length; i += 1) {
      if (keyA[i] < keyB[i]) return -1
      if (keyA[i] > keyB[i]) return 1
    }
    return 0
  })
}
