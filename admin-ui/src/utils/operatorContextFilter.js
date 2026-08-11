/**
 * کلیدهای context_data که برای اپراتور غیرفنی نباید نمایش داده شوند
 * (لاگ یکپارچه‌سازی، شناسه‌های داخلی، …).
 */
export const OPERATOR_HIDDEN_CONTEXT_KEYS = [
  'integration_events',
  /** راهنمای فنی UI برای اکشن‌های یکپارچه‌سازی (scheduled_notification و…)؛ دادهٔ پرونده نیست */
  'ui_hints',
  /** ارجاع داخلی به نمونهٔ start_therapy؛ برای کارمند کاربردی نیست */
  'parent_start_therapy_instance_id',
  'parent_instance_id',
  'parent_process_code',
  'grandparent_process_code',
  'payload',
  'source',
  /** شناسهٔ خام اسلات — به‌جایش تاریخ/ساعت/محل مصاحبه نمایش داده می‌شود */
  'selected_timeslot',
  'slot_created_by',
  'interview_detail_tail',
  /** تکرار خام تاریخ/ساعت (نسخهٔ interview_* کافی است) */
  'date',
  'time',
  /** ردپای انتقال ماشین‌حالت — برای اپراتور غیرفنی شلوغ است */
  'from_state',
  'to_state',
]

/**
 * فقط فیلدهای کاربری مرتبط با مصاحبه (پنل ثبت نتیجهٔ مصاحبه‌گر).
 * بقیهٔ context (مدارک، پرداخت، فلگ‌های داخلی، …) پنهان می‌شود.
 */
export const INTERVIEWER_USER_CONTEXT_KEYS = new Set([
  'interview_date',
  'interview_time',
  'interview_type',
  'interview_mode',
  'interview_link',
  'interview_location',
  'interview_location_fa',
  'interview_location_or_link',
  'interview_result',
  'interviewer_notes',
  'allowed_course_count',
  'rejection_reason',
  'evaluation_notes',
  'suggestion_text',
  'admission_type',
  'student_name',
  'student_name_fa',
])

/** کلیدهای داخلی مفید برای اپراتور (فرم/مدرک) — بقیهٔ __* پنهان می‌شوند */
export const OPERATOR_ALLOWED_INTERNAL_KEYS = new Set([
  '__student_forms_submitted_states',
  '__student_forms_edit_unlock',
  '__documents_resubmit_fields',
  '__document_field_status',
  '__document_field_rejection_notes',
])

/**
 * آیا این کلید برای اپراتور غیرفنی پنهان شود؟
 * @param {string} key
 * @param {Record<string, unknown>} [_ctx]
 */
export function isOperatorHiddenContextKey(key, _ctx = {}) {
  if (!key || typeof key !== 'string') return true
  if (OPERATOR_HIDDEN_CONTEXT_KEYS.includes(key)) return true
  if (key.startsWith('__') && !OPERATOR_ALLOWED_INTERNAL_KEYS.has(key)) return true
  if (key.startsWith('parent_') || key.startsWith('grandparent_')) return true
  if (key.endsWith('_instance_id')) return true
  // همهٔ شناسه‌های خام برای اپراتور غیرفنی پنهان‌اند (برچسب‌های *_name / *_label جدا می‌مانند)
  if (key.endsWith('_id')) return true
  return false
}

/**
 * کپی کم‌عمق از context بدون کلیدهای فنی.
 * @param {object|null|undefined} contextData
 * @param {{ technical?: boolean, audience?: 'interviewer'|null }} [options]
 * @returns {object}
 */
export function filterContextForOperators(contextData, options = {}) {
  if (!contextData || typeof contextData !== 'object' || Array.isArray(contextData)) {
    return {}
  }
  if (options.technical) {
    return { ...contextData }
  }
  const out = { ...contextData }
  for (const k of Object.keys(out)) {
    if (isOperatorHiddenContextKey(k, out)) {
      delete out[k]
      continue
    }
    if (options.audience === 'interviewer' && !INTERVIEWER_USER_CONTEXT_KEYS.has(k)) {
      delete out[k]
    }
  }
  return out
}
