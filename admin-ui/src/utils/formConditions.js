// ارزیابی شرط‌های مبتنی بر شیء — هم‌تراز app/services/forms/condition.py
// گزاره: { field, op: 'eq|neq|in|nin|truthy|falsy|gt|lt|gte|lte|contains', value }
// سازگاری قدیمی: { field, equals }

function toNumber(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export function evaluatePredicate(pred, answers) {
  if (!pred || typeof pred !== 'object') return true
  const field = pred.field
  if (!field) return true
  const got = (answers || {})[field]

  if ('equals' in pred && !('op' in pred)) {
    return got === pred.equals
  }

  const op = (pred.op || 'eq').toLowerCase()
  const want = pred.value

  switch (op) {
    case 'eq':
      return got === want
    case 'neq':
      return got !== want
    case 'in':
      return Array.isArray(want) ? want.includes(got) : false
    case 'nin':
      return Array.isArray(want) ? !want.includes(got) : true
    case 'truthy':
      return !!got
    case 'falsy':
      return !got
    case 'contains':
      if (Array.isArray(got) || typeof got === 'string') return got.includes(want)
      return false
    case 'gt':
    case 'lt':
    case 'gte':
    case 'lte': {
      const a = toNumber(got)
      const b = toNumber(want)
      if (a === null || b === null) return false
      if (op === 'gt') return a > b
      if (op === 'lt') return a < b
      if (op === 'gte') return a >= b
      return a <= b
    }
    default:
      return true
  }
}

// سازگاری با metadata قدیمی: عبارت رشته‌ای visible_when/required_when نادیده گرفته می‌شود
// (پس از واردسازی، همه به show_if/required_if شیئی تبدیل شده‌اند).
export function fieldVisible(field, answers) {
  if (field.show_if) return evaluatePredicate(field.show_if, answers)
  // متادیتای فرایندها (مثل آماده‌سازی ترم): visible_if به‌صورت نگاشت { field: value }
  // یعنی همهٔ کلیدها باید با مقدار فعلی برابر باشند.
  if (field.visible_if && typeof field.visible_if === 'object') {
    const a = answers || {}
    return Object.entries(field.visible_if).every(([k, v]) => a[k] === v)
  }
  return true
}

export function fieldRequired(field, answers) {
  if (field.required_if && typeof field.required_if === 'object') {
    return !!(field.required ?? true) && evaluatePredicate(field.required_if, answers)
  }
  return !!field.required
}
