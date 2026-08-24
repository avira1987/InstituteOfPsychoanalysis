/**
 * نوع فیلد مشترک بین رندرر دانشجو و اپراتور.
 * نام‌های مترادف متادیتا به یک نوع کانونی نگاشته می‌شوند.
 */

export const FIELD_TYPE_ALIASES = {
  text: 'text',
  email: 'email',
  tel: 'tel',
  textarea: 'textarea',
  hidden: 'hidden',
  number: 'number',
  select: 'select',
  radio: 'radio',
  radio_list: 'radio',
  checkbox: 'checkbox',
  checkbox_list: 'checkbox_list',
  file: 'file_upload',
  file_upload: 'file_upload',
  date: 'date',
  date_picker: 'date',
  shamsi_date: 'date',
  time: 'time',
  time_picker: 'time',
  datetime: 'datetime',
  step_otp: 'step_otp',
  therapist_select: 'therapist_select',
  therapist_slot_picker: 'therapist_slot_picker',
  user_select: 'user_select',
  multi_select: 'multi_select',
  dynamic_list: 'dynamic_list',
  table: 'table',
  date_range_list: 'date_range_list',
  readonly: 'readonly',
}

/** انواعی که هر دو مخاطب دانشجو و اپراتور باید بتوانند رندر کنند. */
export const SHARED_FIELD_TYPES = [
  'text',
  'email',
  'tel',
  'textarea',
  'hidden',
  'number',
  'select',
  'radio',
  'checkbox',
  'checkbox_list',
  'file_upload',
  'date',
  'time',
  'step_otp',
  'therapist_select',
  'therapist_slot_picker',
]

export function normalizeFieldType(type) {
  const t = String(type || 'text').toLowerCase().trim()
  return FIELD_TYPE_ALIASES[t] || t
}

/**
 * فرم مرحلهٔ دانشجو ({ code, name_fa, fields }) → schema_json رندرر یکپارچه.
 */
export function studentFormToSchemaJson(form) {
  if (!form || typeof form !== 'object') {
    return { fields: [] }
  }
  return {
    fields: Array.isArray(form.fields) ? form.fields : [],
    visible_to: form.visible_to,
    editable_by: form.editable_by,
    code: form.code,
    name_fa: form.name_fa,
    note_fa: form.note_fa,
  }
}
