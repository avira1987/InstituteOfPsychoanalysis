/**
 * حل کردن گزینه‌های checkbox_list از روی source و context_data نمونه فرایند.
 */
import { INTRODUCTORY_TERM1_COURSES } from './introCourseCatalog'

/** نرمال‌سازی نوع پذیرش از پرونده */
function resolveAdmissionKind(contextData) {
  const ctx = contextData && typeof contextData === 'object' ? contextData : {}
  const ir = ctx.interview_result
  const at = ctx.admission_type
  if (ir === 'single_course' || at === 'single_course') return 'single_course'
  if (ir === 'conditional_therapy' || at === 'conditional_therapy') return 'conditional_therapy'
  if (ir === 'full_admission' || at === 'full_admission' || at === 'full') return 'full_admission'
  return null
}

function parseAllowedCount(ctx) {
  const n = ctx.allowed_course_count
  if (n == null || n === '') return null
  const x = typeof n === 'number' ? n : parseInt(String(n), 10)
  return Number.isFinite(x) && x > 0 ? x : null
}

/**
 * @returns {{ options: Array<{value: string, label_fa: string}>|null, maxSelect: number|null, hint: string|null, useFallback: boolean }}
 */
export function resolveCheckboxListOptions(field, contextData) {
  const src = field?.source
  if (src === 'available_courses_by_admission_type') {
    const ctx = contextData && typeof contextData === 'object' ? contextData : {}
    const kind = resolveAdmissionKind(ctx)
    const all = INTRODUCTORY_TERM1_COURSES
    const offeredRaw = ctx.available_courses || ctx.lms?.available_courses
    const offeredSet =
      Array.isArray(offeredRaw) && offeredRaw.length
        ? new Set(offeredRaw.map((c) => String(c)))
        : null
    let options
    let maxSelect
    let hint = null

    if (!kind) {
      return {
        options: [],
        maxSelect: null,
        hint: 'نتیجهٔ مصاحبه در پرونده ثبت نشده است؛ تا زمان ثبت نتیجه توسط مصاحبه‌گر انتخاب درس ممکن نیست.',
        useFallback: true,
      }
    }

    if (kind === 'single_course') {
      options = all.filter(o => o.value === 'theory_1')
      maxSelect = 1
    } else if (kind === 'conditional_therapy' || kind === 'full_admission') {
      options = [...all]
      const cap = parseAllowedCount(ctx)
      maxSelect = cap != null ? cap : 5
    } else {
      options = []
      maxSelect = null
      hint = 'نوع پذیرش شناخته نشد.'
      return { options, maxSelect, hint, useFallback: true }
    }

    if (offeredSet) {
      options = options.filter((o) => offeredSet.has(o.value))
      if (!options.length) {
        return {
          options: [],
          maxSelect: null,
          hint: 'لیست دروس این ترم از آماده‌سازی ترم منتشر نشده یا با نوع پذیرش شما هم‌خوان نیست.',
          useFallback: true,
        }
      }
    }

    return { options, maxSelect, hint, useFallback: false }
  }

  if (src === 'filtered_courses_by_admission_type_and_prerequisites') {
    return {
      options: null,
      maxSelect: null,
      hint: 'لیست دروس این ترم از سامانهٔ آموزشی بارگذاری نشده؛ در صورت نیاز مقدار را دستی ثبت کنید یا با پذیرش هماهنگ کنید.',
      useFallback: true,
    }
  }

  if (src === 'lms_available_courses') {
    const ctx = contextData && typeof contextData === 'object' ? contextData : {}
    const lms = ctx.lms && typeof ctx.lms === 'object' ? ctx.lms : {}
    const raw =
      lms.available_courses ||
      lms.enrolled_courses ||
      ctx.available_courses ||
      ctx.selected_courses ||
      []
    const codes = Array.isArray(raw) ? raw : []
    const options = codes
      .filter(x => x != null && String(x).trim() !== '')
      .map(code => {
        const s = String(code)
        return { value: s, label_fa: s }
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
          ? 'هنوز درسی در پروندهٔ آموزشی شما ثبت نشده؛ پس از ثبت‌نام ترم یا با پذیرش هماهنگ کنید.'
          : null,
      useFallback: options.length === 0,
    }
  }

  if (src === 'therapy_reduction_upcoming_sessions') {
    const ctx = contextData && typeof contextData === 'object' ? contextData : {}
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
    const ctx = contextData && typeof contextData === 'object' ? contextData : {}
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
    const ctx = contextData && typeof contextData === 'object' ? contextData : {}
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
    const ctx = contextData && typeof contextData === 'object' ? contextData : {}
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
    const ctx = contextData && typeof contextData === 'object' ? contextData : {}
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
    const ctx = contextData && typeof contextData === 'object' ? contextData : {}
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
    const ctx = contextData && typeof contextData === 'object' ? contextData : {}
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
    return raw.filter(x => x != null && String(x).trim() !== '').map(x => String(x))
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
    return s.split(/[,،]/).map(x => x.trim()).filter(Boolean)
  }
  return []
}
