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
    let options
    let maxSelect
    let hint = null

    if (kind === 'single_course') {
      options = all.filter(o => o.value === 'theory_1')
      maxSelect = 1
    } else if (kind === 'conditional_therapy' || kind === 'full_admission') {
      options = [...all]
      const cap = parseAllowedCount(ctx)
      maxSelect = cap != null ? cap : 5
    } else {
      options = [...all]
      maxSelect = 5
      hint =
        'نتیجهٔ مصاحبه در پرونده دیده نشد؛ فعلاً همهٔ دروس ممکن نمایش داده می‌شود. در صورت تناقض با پذیرش تماس بگیرید.'
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
