// ارزیابی شرط‌های مبتنی بر شیء — هم‌تراز app/services/forms/condition.py
// گزاره: { field, op: 'eq|neq|in|nin|truthy|falsy|gt|lt|gte|lte|contains', value }
// سازگاری قدیمی: { field, equals }
// عبارت رشته‌ای metadata: visible_when / required_when (مثل "payment_method == 'installment'")

function toNumber(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const RE_EQ = /^\s*(\w+)\s*==\s*'([^']*)'\s*$/
const RE_NEQ = /^\s*(\w+)\s*!=\s*'([^']*)'\s*$/
const RE_IN = /^\s*(\w+)\s+in\s+\[(.*)\]\s*$/
const RE_NIN = /^\s*(\w+)\s+not\s+in\s+\[(.*)\]\s*$/
const RE_TRUTHY = /^\s*(\w+)\s*$/

function parseList(raw) {
  const out = []
  const re = /'([^']*)'/g
  let m
  while ((m = re.exec(raw)) !== null) out.push(m[1])
  return out
}

/** عبارت رشته‌ای metadata ⇒ گزارهٔ { field, op, value }؛ در صورت غیرقابل‌تجزیه null */
export function exprToPredicate(expr) {
  if (expr == null) return null
  if (typeof expr === 'object' && !Array.isArray(expr)) return expr
  if (typeof expr !== 'string') return null
  const s = expr.trim()
  if (!s) return null

  let m = RE_EQ.exec(s)
  if (m) return { field: m[1], op: 'eq', value: m[2] }
  m = RE_NEQ.exec(s)
  if (m) return { field: m[1], op: 'neq', value: m[2] }
  m = RE_IN.exec(s)
  if (m) return { field: m[1], op: 'in', value: parseList(m[2]) }
  m = RE_NIN.exec(s)
  if (m) return { field: m[1], op: 'nin', value: parseList(m[2]) }
  m = RE_TRUTHY.exec(s)
  if (m) return { field: m[1], op: 'truthy' }
  return { raw: s }
}

export function evaluatePredicate(pred, answers) {
  if (!pred || typeof pred !== 'object') return true
  if (pred.raw) return true
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

function resolveShowPredicate(field) {
  if (field.show_if) return field.show_if
  if (typeof field.visible_when === 'string') {
    const pred = exprToPredicate(field.visible_when)
    if (pred && !pred.raw) return pred
  }
  return null
}

function resolveRequiredPredicate(field) {
  if (field.required_if && typeof field.required_if === 'object') return field.required_if
  if (typeof field.required_when === 'string') {
    const pred = exprToPredicate(field.required_when)
    if (pred && !pred.raw) return pred
  }
  return null
}

export function fieldVisible(field, answers) {
  const showPred = resolveShowPredicate(field)
  if (showPred) return evaluatePredicate(showPred, answers)
  // متادیتای فرایندها (مثل آماده‌سازی ترم): visible_if به‌صورت نگاشت { field: value }
  if (field.visible_if && typeof field.visible_if === 'object') {
    const a = answers || {}
    return Object.entries(field.visible_if).every(([k, v]) => a[k] === v)
  }
  return true
}

export function fieldRequired(field, answers) {
  const reqPred = resolveRequiredPredicate(field)
  if (reqPred) {
    return !!(field.required ?? true) && evaluatePredicate(reqPred, answers)
  }
  return !!field.required
}
