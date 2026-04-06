import {
  labelProcess,
  labelState,
  labelTriggerEvent,
  formatActorRole,
} from './processDisplay'

const CHANGE_TYPE_FA = {
  created: 'ایجاد',
  updated: 'به‌روزرسانی',
  deactivated: 'غیرفعال‌سازی',
  therapist_change: 'تغییر درمانگر',
}

/** برچسب فارسی برای کلیدهای رایج در آبجکت details */
export const DETAIL_KEY_FA = {
  payload: 'داده‌های همراه عملیات',
  rule_code: 'کد قانون',
  change_type: 'نوع تغییر',
  old_value: 'مقدار قبلی',
  new_value: 'مقدار جدید',
  student_id: 'شناسه دانشجو',
  notes: 'یادداشت',
  context_data: 'اطلاعات تکمیلی پرونده',
  integration_events: 'رویدادهای یکپارچه‌سازی',
}

export function formatDetailKey(key) {
  if (key == null || key === '') return '—'
  return DETAIL_KEY_FA[key] || key.replace(/_/g, ' ')
}

function formatChangeType(v) {
  if (typeof v !== 'string') return String(v)
  return CHANGE_TYPE_FA[v] || v
}

/**
 * مقدار اتمی را برای نمایش غیرفنی آماده می‌کند (بدون JSON خام).
 */
export function formatDetailScalar(key, value) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'بله' : 'خیر'
  if (typeof value === 'number') return String(value)
  if (typeof value === 'bigint') return String(value)
  if (typeof value === 'string') {
    if (key === 'change_type') return formatChangeType(value)
    if (key === 'student_id' && /^[0-9a-f-]{36}$/i.test(value)) {
      return value
    }
    return value
  }
  return null
}

/**
 * یک جملهٔ خلاصهٔ فارسی برای بالای کارت جزئیات.
 */
export function buildAuditSummary(log) {
  const proc = labelProcess(log.process_code)
  const fromS = labelState(log.from_state)
  const toS = labelState(log.to_state)
  const trig = labelTriggerEvent(log.trigger_event)

  switch (log.action_type) {
    case 'transition':
      if (log.from_state && log.to_state) {
        return `در فرایند «${proc}»، پرونده از مرحلهٔ «${fromS}» به «${toS}» منتقل شد؛ علت سیستمی: «${trig}».`
      }
      return `رخداد مربوط به فرایند «${proc}».`
    case 'process_start':
      return `فرایند «${proc}» برای یک دانشجو آغاز شد.`
    case 'rule_change':
      return 'تنظیمات یک قانون در سیستم تغییر کرد (برای پیگیری جزئیات، بخش زیر را ببینید).'
    case 'process_updated':
      return `تعریف یا وضعیت فرایند «${proc}» در سیستم به‌روز شد.`
    case 'sla_breach':
      return `مهلت زمانی تعیین‌شده برای فرایند «${proc}» رعایت نشد (نقض SLA).`
    default:
      return `یک رویداد سیستمی ثبت شد (${log.action_type}).`
  }
}

export function formatActorLine(log) {
  const name = log.actor_name && String(log.actor_name).trim()
  const roleFa = formatActorRole(log.actor_role)
  if (name && log.actor_role) return `${name} (${roleFa})`
  if (name) return name
  if (log.actor_role) return roleFa
  return '—'
}
