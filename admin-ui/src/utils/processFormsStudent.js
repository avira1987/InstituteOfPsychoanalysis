/** فرم‌های متادیتا — فیلتر برای نقش دانشجو و اعتبارسنجی قبل از انتقال */

export function filterFormsForStudent(forms) {
  if (!Array.isArray(forms)) return []
  return forms.filter(f => {
    if (f.confidential) return false
    if (Array.isArray(f.visible_to) && f.visible_to.length && !f.visible_to.includes('student')) {
      return false
    }
    return true
  })
}

function fieldVisible(field, values) {
  if (!field.visible_when) return true
  return true
}

function fieldRequired(field, values) {
  if (field.required_when) return false
  return !!field.required
}

function isEmpty(v) {
  if (v === undefined || v === null) return true
  if (typeof v === 'string' && v.trim() === '') return true
  if (typeof v === 'boolean') return false
  if (typeof v === 'number') return false
  if (typeof v === 'object' && v.file_name !== undefined) return !v.file_name
  return false
}

/**
 * @returns {{ ok: boolean, missing: string[] }}
 */
export function validateStepForms(forms, values) {
  const filtered = filterFormsForStudent(forms)
  const missing = []
  for (const form of filtered) {
    for (const field of form.fields || []) {
      if (!fieldVisible(field, values)) continue
      if (!fieldRequired(field, values)) continue
      const t = field.type || 'text'
      if (t === 'radio_list' || t === 'checkbox_list') {
        const raw = values[field.name]
        const ack = values[`${field.name}_ack`]
        if (field.required && !ack && (raw === undefined || raw === null || String(raw).trim() === '')) {
          missing.push(field.label_fa || field.name)
        }
        continue
      }
      if (isEmpty(values[field.name])) {
        missing.push(field.label_fa || field.name)
      }
    }
  }
  return { ok: missing.length === 0, missing }
}

/** هم‌نام با backend: app/meta/student_step_forms.py */
export const CTX_STUDENT_FORMS_SUBMITTED = '__student_forms_submitted_states'
export const CTX_STUDENT_FORMS_UNLOCK = '__student_forms_edit_unlock'

/** فرم این مرحله ثبت شده و مسئول هنوز ویرایش را باز نکرده → در UI مخفی */
export function isStudentStepFormLocked(contextData, currentState) {
  if (!currentState || !contextData) return false
  const submitted = contextData[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const unlock = contextData[CTX_STUDENT_FORMS_UNLOCK] || {}
  if (!submitted[currentState]) return false
  return !unlock[currentState]
}

export function collectFormFieldKeys(forms) {
  const keys = new Set()
  const list = filterFormsForStudent(forms || [])
  for (const form of list) {
    for (const field of form.fields || []) {
      const t = field.type || 'text'
      keys.add(field.name)
      if (t === 'radio_list' || t === 'checkbox_list') {
        keys.add(`${field.name}_ack`)
      }
    }
  }
  return keys
}

/** مقدار اولیهٔ فیلدها از context_data نمونه (پس از ثبت یا انتقال) */
export function pickFormValuesFromContext(forms, contextData) {
  const keySet = collectFormFieldKeys(forms)
  const out = {}
  const ctx = contextData || {}
  for (const k of keySet) {
    if (Object.prototype.hasOwnProperty.call(ctx, k) && ctx[k] !== undefined) {
      out[k] = ctx[k]
    }
  }
  return out
}

/**
 * @param {string} decisionNotes — متن توضیح اختیاری (با فیلد notes در payload ادغام می‌شود)
 * @param {Record<string, unknown>} stepFormValues — فیلدهای فرم مرحله
 */
export function mergeFormPayload(decisionNotes, stepFormValues) {
  const n = typeof decisionNotes === 'string' && decisionNotes.trim()
    ? { notes: decisionNotes.trim() }
    : {}
  return { ...n, ...(stepFormValues || {}) }
}

/**
 * @param {{ lockedSubmitted?: boolean }} [opts] — اگر فرم ثبت شده و قفل است، انتقال را به‌خاطر فرم ناقص متوقف نکن
 */
export function stepFormsBlockTransition(forms, values, opts = {}) {
  if (opts.lockedSubmitted) return false
  const f = filterFormsForStudent(forms || [])
  if (f.length === 0) return false
  return !validateStepForms(forms, values).ok
}
