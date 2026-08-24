/**
 * حل کردن گزینه‌های checkbox_list از روی source و context_data نمونه فرایند.
 */
import { NO_OFFERINGS_HINT_FA, formatCourseOptionLabel, optionsFromContext } from './introCourseCatalog.js'
import { isUnenforcedSystemPrerequisite } from './catalogCurriculum.js'

const LEGACY_COURSE_CODE_MAP = {
  theory_1: 'theory_psychoanalysis_1',
  theory_2: 'theory_psychoanalysis_2',
  theory_3: 'theory_psychoanalysis_3',
  theory_4: 'theory_psychoanalysis_4',
  theory_5: 'theory_psychoanalysis_5',
}

const COURSE_NAME_ALIASES = {
  'تئوری روانکاوی ۱': 'theory_psychoanalysis_1',
  'تئوری روانکاوی (1)': 'theory_psychoanalysis_1',
  'تئوری روانکاوی یک': 'theory_psychoanalysis_1',
  'تئوری روانکاوی 1': 'theory_psychoanalysis_1',
  'تئوری تکنیک‌ها ۱': 'theory_technique_1',
  'تئوری تکنیک (1)': 'theory_technique_1',
  'تئوری تکنیک 1': 'theory_technique_1',
  'تئوری تکنیک یک': 'theory_technique_1',
  'تئوری تکنیک‌ها یک': 'theory_technique_1',
  'تئوری تکنیک ها 1': 'theory_technique_1',
  'تئوری روانکاوی ۲': 'theory_psychoanalysis_2',
  'تئوری روانکاوی (2)': 'theory_psychoanalysis_2',
  'تئوری تکنیک‌ها ۲': 'theory_technique_2',
  'تئوری تکنیک (2)': 'theory_technique_2',
}

const SINGLE_COURSE_BY_TERM = {
  1: 'theory_psychoanalysis_1',
  2: 'theory_psychoanalysis_2',
}

export const SINGLE_COURSE_MISSING_HINT_FA =
  'درس مجاز پذیرش تک‌درس در فهرست ارائه‌شدهٔ این ترم نیست.'

const COREQUISITE_NOTE_FA = 'هم‌نیاز: مردودی ترم قبل — قابل اخذ همزمان'
const UNMET_PREREQ_PREFIX_FA = 'پیش‌نیاز پاس‌نشده: '
const PASS_LABELS = new Set(['قبول', 'pass', 'passed', 'p', 'ok'])
const PASS_LETTERS = new Set(['A', 'A+', 'A-', 'B', 'B+', 'B-', 'C', 'C+', 'C-', 'D', 'D+', 'D-'])
const FAIL_LABELS = new Set(['مردود', 'fail', 'failed', 'f'])

export function normalizeCourseCode(code) {
  const s = String(code || '').trim()
  return LEGACY_COURSE_CODE_MAP[s] || COURSE_NAME_ALIASES[s] || s
}

export function singleCourseAllowedCode(termNumber) {
  const n = Number(termNumber)
  if (!Number.isFinite(n) || n <= 1) return SINGLE_COURSE_BY_TERM[1]
  return SINGLE_COURSE_BY_TERM[n] || null
}

const ADMISSION_KIND_ALIASES = {
  single_course: 'single_course',
  result_single_course: 'single_course',
  'تک درس': 'single_course',
  'تک‌درس': 'single_course',
  'پذیرش تک درس': 'single_course',
  'پذیرش تک‌درس': 'single_course',
  conditional_therapy: 'conditional_therapy',
  result_conditional_therapy: 'conditional_therapy',
  'مشروط به درمان': 'conditional_therapy',
  'پذیرش مشروط': 'conditional_therapy',
  full_admission: 'full_admission',
  result_full_admission: 'full_admission',
  full: 'full_admission',
  'پذیرش کامل': 'full_admission',
}

function canonicalAdmission(raw) {
  if (raw == null || raw === '') return null
  const key = String(raw).trim()
  return ADMISSION_KIND_ALIASES[key] || ADMISSION_KIND_ALIASES[key.toLowerCase()] || null
}

/** نرمال‌سازی نوع پذیرش از پرونده — سطح نمونه بر student تو در تو اولویت دارد */
function resolveAdmissionKind(contextData) {
  const ctx = contextData && typeof contextData === 'object' ? contextData : {}
  const nested = ctx.student && typeof ctx.student === 'object' ? ctx.student : {}
  return (
    canonicalAdmission(ctx.admission_type) ||
    canonicalAdmission(ctx.interview_result) ||
    canonicalAdmission(ctx.result) ||
    canonicalAdmission(nested.admission_type) ||
    canonicalAdmission(nested.interview_result) ||
    null
  )
}

function parseAllowedCount(ctx) {
  const n = ctx.allowed_course_count
  if (n == null || n === '') return null
  const x = typeof n === 'number' ? n : parseInt(String(n), 10)
  return Number.isFinite(x) && x > 0 ? x : null
}

function entryCode(item) {
  if (item && typeof item === 'object') {
    return normalizeCourseCode(item.code || item.course_code || item.value || '')
  }
  if (item != null) return normalizeCourseCode(item)
  return ''
}

function isFailedEntry(item) {
  if (!item || typeof item !== 'object') return false
  if (item.incomplete || item.status === 'I') return true
  const pf = String(item.pass_fail_status || item.pass_fail || '').trim()
  if (FAIL_LABELS.has(pf) || FAIL_LABELS.has(pf.toLowerCase())) return true
  const letter = String(item.letter_grade || item.grade || '').trim().toUpperCase()
  if (letter === 'F' || letter === 'I' || letter === 'مردود') return true
  if (item.passed === false || item.pass === false) return true
  return false
}

function isPassedEntry(item) {
  if (!item || typeof item !== 'object' || isFailedEntry(item)) return false
  if (item.passed === true || item.pass === true || item.completed === true) return true
  const pf = String(item.pass_fail_status || item.pass_fail || '').trim()
  if (PASS_LABELS.has(pf) || PASS_LABELS.has(pf.toLowerCase())) return true
  const letter = String(item.letter_grade || '').trim().toUpperCase()
  if (PASS_LETTERS.has(letter)) return true
  return false
}

function ingestRecords(records, passed, failed, stringsMean) {
  if (!Array.isArray(records)) return
  for (const item of records) {
    if (typeof item === 'string') {
      const code = normalizeCourseCode(item)
      if (!code) continue
      if (stringsMean === 'passed') {
        passed.add(code)
        failed.delete(code)
      } else if (stringsMean === 'failed') {
        failed.add(code)
        passed.delete(code)
      }
      continue
    }
    if (!item || typeof item !== 'object') continue
    const code = entryCode(item)
    if (!code) continue
    if (isFailedEntry(item)) {
      failed.add(code)
      passed.delete(code)
      continue
    }
    if (isPassedEntry(item)) {
      passed.add(code)
      failed.delete(code)
    }
  }
}

export function classifyCourseProgress(ctx) {
  const data = ctx && typeof ctx === 'object' ? ctx : {}
  const lms = data.lms && typeof data.lms === 'object' ? data.lms : {}
  const passed = new Set()
  const failed = new Set()
  ingestRecords(lms.enrolled_courses, passed, failed, null)
  ingestRecords(data.enrolled_courses, passed, failed, null)
  ingestRecords(data.failed_courses, passed, failed, 'failed')
  ingestRecords(lms.failed_courses, passed, failed, 'failed')
  ingestRecords(data.completed_courses, passed, failed, 'passed')
  return { passed, failed }
}

export function partitionByPrerequisites(options, passed, failed) {
  const allowed = []
  const blocked = []
  const neededCoreq = new Set()
  const allowedCodes = new Set()
  const list = Array.isArray(options) ? options : []
  for (const opt of list) {
    if (!opt || typeof opt !== 'object') continue
    const code = normalizeCourseCode(opt.value)
    if (!code) continue
    const prereqs = Array.isArray(opt.prerequisite_codes)
      ? opt.prerequisite_codes
          .map((p) => normalizeCourseCode(p))
          .filter((p) => p && !isUnenforcedSystemPrerequisite(p))
      : []
    const unmet = prereqs.filter((p) => !passed.has(p) && !failed.has(p))
    const coreq = prereqs.filter((p) => failed.has(p) && !passed.has(p))
    if (unmet.length) {
      const names = unmet.map((p) => {
        const found = list.find((o) => normalizeCourseCode(o.value) === p)
        return found?.label_fa || p
      })
      blocked.push({
        ...opt,
        value: code,
        selectable: false,
        lock_reason_fa: `${UNMET_PREREQ_PREFIX_FA}${names.join('، ')}`,
      })
      continue
    }
    const extra = { ...opt, value: code, selectable: true }
    if (coreq.length) {
      extra.corequisite_codes = coreq
      extra.corequisite_note_fa = COREQUISITE_NOTE_FA
      coreq.forEach((c) => neededCoreq.add(c))
    }
    allowed.push(extra)
    allowedCodes.add(code)
  }
  for (const code of neededCoreq) {
    if (allowedCodes.has(code)) {
      for (const opt of allowed) {
        if (normalizeCourseCode(opt.value) === code) {
          opt.is_corequisite = true
          opt.corequisite_note_fa = opt.corequisite_note_fa || COREQUISITE_NOTE_FA
        }
      }
      continue
    }
    allowed.push({
      value: code,
      label_fa: code,
      prerequisite_codes: [],
      selectable: true,
      is_corequisite: true,
      corequisite_note_fa: COREQUISITE_NOTE_FA,
    })
    allowedCodes.add(code)
  }
  return { allowed, blocked }
}

function optionMatchesSingleCourse(opt, termNumber) {
  const code = normalizeCourseCode(opt?.value)
  if (!code) return false
  if (opt?.single_course_allowed === true) return true
  return code === singleCourseAllowedCode(termNumber)
}

function applyAdmissionFilter(options, contextData, termNumber = 1) {
  const kind = resolveAdmissionKind(contextData)
  if (!kind) {
    return {
      options: [],
      maxSelect: null,
      hint: 'نتیجهٔ مصاحبه در پرونده ثبت نشده است؛ تا زمان ثبت نتیجه توسط مصاحبه‌گر انتخاب درس ممکن نیست.',
      useFallback: false,
    }
  }
  if (!options.length) {
    return {
      options: [],
      maxSelect: null,
      hint: contextData?.course_selection_hint_fa || NO_OFFERINGS_HINT_FA,
      useFallback: false,
    }
  }
  if (kind === 'single_course') {
    const allowedCode = singleCourseAllowedCode(termNumber)
    const pick = options
      .filter((o) => optionMatchesSingleCourse(o, termNumber))
      .map((o) => ({ ...o, value: normalizeCourseCode(o.value) || o.value }))
    if (!pick.length) {
      return {
        options: [],
        maxSelect: 1,
        hint: SINGLE_COURSE_MISSING_HINT_FA,
        useFallback: false,
      }
    }
    const coreq = new Set()
    for (const o of pick) {
      for (const c of o.corequisite_codes || []) {
        const n = normalizeCourseCode(c)
        if (n) coreq.add(n)
      }
    }
    const extras = options.filter((o) => {
      const code = normalizeCourseCode(o.value)
      return coreq.has(code) && code !== allowedCode
    })
    const combined = [...pick, ...extras]
    return { options: combined, maxSelect: Math.max(1, combined.length), hint: null, useFallback: false }
  }
  const cap = parseAllowedCount(contextData)
  const maxSelect = cap != null ? cap : options.length
  return { options: [...options], maxSelect, hint: null, useFallback: false }
}

function mergeBlocked(primary, fromCtx, kind, termNumber) {
  const map = new Map()
  for (const item of [...(primary || []), ...(fromCtx || [])]) {
    if (!item || !item.value) continue
    const code = normalizeCourseCode(item.value)
    if (!map.has(code)) map.set(code, { ...item, value: code })
  }
  let blocked = [...map.values()]
  if (kind === 'single_course') {
    blocked = blocked.filter((o) => optionMatchesSingleCourse(o, termNumber))
  }
  return blocked
}

function resolveWithPrereqAndAdmission(options, ctx, termNumber) {
  const { passed, failed } = classifyCourseProgress(ctx)
  const { allowed, blocked } = partitionByPrerequisites(options, passed, failed)
  const admission = applyAdmissionFilter(allowed, ctx, termNumber)
  const kind = resolveAdmissionKind(ctx)
  const ctxBlocked = Array.isArray(ctx.blocked_course_options) ? ctx.blocked_course_options : []
  const blockedOptions = mergeBlocked(blocked, ctxBlocked, kind, termNumber)
  let hint = admission.hint
  if (!admission.options.length && blockedOptions.length) {
    hint = blockedOptions[0].lock_reason_fa || hint
  }
  return {
    ...admission,
    hint,
    blockedOptions,
  }
}

export function withStudentAdmissionContext(contextData, studentProfile) {
  const ctx = contextData && typeof contextData === 'object' ? { ...contextData } : {}
  const extra = studentProfile?.extra_data && typeof studentProfile.extra_data === 'object'
    ? studentProfile.extra_data
    : {}
  const at = studentProfile?.admission_type || extra.admission_type
  const ir = extra.interview_result
  const kind = canonicalAdmission(at) || canonicalAdmission(ir)
  const ctxKind = canonicalAdmission(ctx.admission_type) || canonicalAdmission(ctx.interview_result)
  if (kind === 'single_course' || ctxKind === 'single_course') {
    ctx.admission_type = 'single_course'
    ctx.interview_result = 'single_course'
  } else if (kind && !ctxKind) {
    ctx.admission_type = kind
    ctx.interview_result = canonicalAdmission(ir) || kind
  }
  const finalKind = canonicalAdmission(ctx.admission_type) || canonicalAdmission(ctx.interview_result) || kind
  if (finalKind) {
    ctx.student = {
      ...(ctx.student && typeof ctx.student === 'object' ? ctx.student : {}),
      admission_type: finalKind,
    }
  }
  return ctx
}

/**
 * @returns {{ options: Array<{value: string, label_fa: string}>|null, maxSelect: number|null, hint: string|null, useFallback: boolean }}
 */
export function resolveCheckboxListOptions(field, contextData) {
  const src = field?.source
  const ctx = contextData && typeof contextData === 'object' ? contextData : {}

  if (src === 'available_courses_by_admission_type') {
    const options = optionsFromContext(ctx).map((o) => ({
      ...o,
      label_fa: o.display_label_fa || formatCourseOptionLabel(o) || o.label_fa,
    }))
    return resolveWithPrereqAndAdmission(options, ctx, 1)
  }

  if (src === 'filtered_courses_by_admission_type_and_prerequisites') {
    const options = optionsFromContext(ctx).map((o) => ({
      ...o,
      label_fa: o.display_label_fa || formatCourseOptionLabel(o) || o.label_fa,
    }))
    return resolveWithPrereqAndAdmission(options, ctx, 2)
  }

  if (src === 'lms_available_courses') {
    const lms = ctx.lms && typeof ctx.lms === 'object' ? ctx.lms : {}
    const raw =
      lms.available_courses ||
      lms.enrolled_courses ||
      ctx.available_courses ||
      ctx.selected_courses ||
      []
    const labelMap = ctx.course_labels || {}
    const options = (Array.isArray(raw) ? raw : [])
      .filter((x) => x != null && String(x).trim() !== '')
      .map((code) => {
        const s = String(code)
        return { value: s, label_fa: labelMap[s] || s }
      })
    const maxSelect =
      typeof field?.max_select === 'number' && field.max_select > 0
        ? field.max_select
        : field?.max_select === 1 || field?.maxSelect === 1
          ? 1
          : null
    return {
      options,
      maxSelect,
      hint:
        options.length === 0
          ? ctx.course_selection_hint_fa || lms.unavailable_reason_fa || NO_OFFERINGS_HINT_FA
          : null,
      useFallback: false,
    }
  }

  if (src === 'therapy_reduction_upcoming_sessions') {
    const raw = ctx.upcoming_therapy_sessions
    const options = Array.isArray(raw) ? raw : []
    const minR = ctx.therapy_reduction_min_remove_count
    const minSelect = typeof minR === 'number' && minR > 0 ? minR : 1
    return {
      options,
      maxSelect: options.length > 0 ? options.length : null,
      minSelect,
      hint:
        options.length === 0
          ? 'جلسهٔ آتی برنامه‌ریزی‌شده‌ای در تقویم نیست؛ با پشتیبانی تماس بگیرید.'
          : `حداقل ${minSelect} جلسه را برای لغو انتخاب کنید (با کاهش برنامه هم‌خوان باشد).`,
      useFallback: options.length === 0,
    }
  }

  if (src === 'supervision_reduction_upcoming_sessions') {
    const raw = ctx.upcoming_supervision_sessions
    const options = Array.isArray(raw) ? raw : []
    let weekly = ctx.supervision_weekly_sessions
    if (weekly == null) weekly = ctx.weekly_supervision_sessions
    const ws = typeof weekly === 'number' ? weekly : parseInt(String(weekly || '1'), 10)
    const maxRemove = Number.isFinite(ws) && ws > 1 ? ws - 1 : (options.length > 0 ? options.length - 1 : 0)
    const minR = ctx.supervision_reduction_min_remove_count
    const minSelect = typeof minR === 'number' && minR > 0 ? minR : 1
    return {
      options,
      maxSelect: maxRemove > 0 ? maxRemove : (options.length > 0 ? options.length - 1 : null),
      minSelect,
      hint:
        options.length === 0
          ? 'جلسهٔ هفتگی سوپرویژنی در لیست نیست؛ با پشتیبانی تماس بگیرید.'
          : `حداقل ${minSelect} و حداکثر ${maxRemove > 0 ? maxRemove : '—'} جلسه را برای حذف انتخاب کنید (حداقل یک جلسه در هفته باقی بماند).`,
      useFallback: options.length === 0,
    }
  }

  if (src === 'student_cancellation_upcoming_sessions') {
    const raw = ctx.upcoming_cancellation_sessions
    const options = Array.isArray(raw) ? raw : []
    return {
      options,
      maxSelect: options.length > 0 ? options.length : null,
      minSelect: 1,
      hint:
        options.length === 0
          ? 'جلسهٔ برنامه‌ریزی‌شده‌ای در ۳ هفتهٔ آینده نیست.'
          : 'جلسات مورد نظر را تیک بزنید. کنسل بیش از ۳ هفته متوالی از این مسیر مجاز نیست.',
      useFallback: options.length === 0,
    }
  }

  if (src === 'student_supervision_upcoming_sessions') {
    const raw = ctx.upcoming_cancellation_sessions
    const options = Array.isArray(raw) ? raw : []
    const supCount = ctx.active_supervisor_count != null ? Number(ctx.active_supervisor_count) : 1
    return {
      options,
      maxSelect: options.length > 0 ? options.length : null,
      minSelect: 1,
      hint:
        options.length === 0
          ? 'جلسهٔ سوپرویژن برنامه‌ریزی‌شده‌ای در ۳ هفتهٔ آینده نیست.'
          : supCount > 1
            ? 'جلسات هر سوپروایزر فعال در لیست نمایش داده می‌شوند. کنسل بیش از ۳ هفته متوالی مجاز نیست.'
            : 'جلسات سوپرویژن را تیک بزنید. کنسل بیش از ۳ هفته متوالی از این مسیر مجاز نیست.',
      useFallback: options.length === 0,
    }
  }

  if (src === 'supervisor_sessions_next_4_weeks') {
    const raw = ctx.supervisor_sessions_next_4_weeks
    const options = Array.isArray(raw) ? raw : []
    const maxSel =
      typeof field?.max_selection === 'number' && field.max_selection > 0
        ? field.max_selection
        : field?.maxSelect === 1 || field?.max_selection === 1
          ? 1
          : 1
    return {
      options,
      maxSelect: maxSel,
      minSelect: 1,
      hint:
        options.length === 0
          ? 'جلسهٔ سوپرویژن برنامه‌ریزی‌شده‌ای در ۴ هفتهٔ آینده نیست.'
          : 'در هر بار اجرا فقط امکان انتخاب ۱ جلسه وجود دارد.',
      useFallback: options.length === 0,
    }
  }

  if (src === 'assignable_courses') {
    const raw = ctx.assignable_courses
    const options = Array.isArray(raw) ? raw : []
    return {
      options,
      maxSelect: 1,
      minSelect: 1,
      hint:
        options.length === 0
          ? 'درسی به شما انتساب داده نشده است. با کمیته دروس هماهنگ کنید.'
          : 'درس مورد نظر را انتخاب کنید.',
      useFallback: options.length === 0,
    }
  }

  if (src === 'class_cancellable_sessions') {
    const raw = ctx.cancellable_sessions || ctx.upcoming_cancellable_sessions
    const options = (Array.isArray(raw) ? raw : []).filter((o) => o?.cancellable !== false)
    return {
      options,
      maxSelect: 1,
      minSelect: 1,
      hint:
        options.length === 0
          ? 'ابتدا درس را انتخاب و ثبت کنید؛ یا جلسهٔ قابل کنسلی برای این درس نیست.'
          : 'جلسهٔ کنسل‌شونده را انتخاب کنید. پس از کنسلی، حضور و غیاب این جلسه قفل می‌شود.',
      useFallback: options.length === 0,
    }
  }

  return { options: null, maxSelect: null, hint: null, useFallback: true }
}

/** مقدار ذخیره‌شده را به آرایهٔ کد درس تبدیل می‌کند */
export function normalizeSelectedCoursesValue(raw) {
  if (Array.isArray(raw)) {
    return raw.filter((x) => x != null && String(x).trim() !== '').map((x) => String(x))
  }
  if (raw == null || raw === '') return []
  if (typeof raw === 'string') {
    const s = raw.trim()
    if (s.startsWith('[')) {
      try {
        const p = JSON.parse(s)
        return Array.isArray(p) ? p.map(String) : []
      } catch {
        return []
      }
    }
    return s.split(/[,،]/).map((x) => x.trim()).filter(Boolean)
  }
  return []
}
