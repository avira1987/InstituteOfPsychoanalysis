/** فرم‌های متادیتا — فیلتر برای نقش دانشجو و اعتبارسنجی قبل از انتقال */

import {
  resolveCheckboxListOptions,
  normalizeSelectedCoursesValue,
} from './resolveCourseFieldOptions'
// منطق شرط‌ها یکپارچه است: همان ارزیاب شیئی فرم یکپارچه.
import { fieldVisible as unifiedVisible, fieldRequired as unifiedRequired } from './formConditions'
import { checkRules } from './unifiedFormValidation'

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

// شرط نمایش/الزام: show_if / required_if شیئی، یا visible_when / required_when رشته‌ای metadata
function fieldVisible(field, values) {
  return unifiedVisible(field, values)
}

function fieldRequired(field, values) {
  return unifiedRequired(field, values)
}

function isEmpty(v) {
  if (v === undefined || v === null) return true
  if (typeof v === 'string' && v.trim() === '') return true
  if (typeof v === 'boolean') return false
  if (typeof v === 'number') return false
  if (typeof v === 'object' && (v.file_name !== undefined || v.url !== undefined)) {
    return !(v.file_name || v.url)
  }
  return false
}

/**
 * @param {{ resubmitFieldNames?: string[], contextData?: object }} [opts] — contextData برای لیست دروس پویا
 * @returns {{ ok: boolean, missing: string[] }}
 */
export function validateStepForms(forms, values, opts = {}) {
  const resubmit = opts.resubmitFieldNames
  const resubmitSet = Array.isArray(resubmit) && resubmit.length ? new Set(resubmit) : null
  const contextData = opts.contextData
  const filtered = filterFormsForStudent(forms)
  const missing = []
  for (const form of filtered) {
    for (const field of form.fields || []) {
      const t = field.type || 'text'
      const isRulesGate = t === 'checkbox' && !!field.rules_link_href
      if (resubmitSet && !resubmitSet.has(field.name) && t !== 'step_otp' && !isRulesGate) continue
      if (!fieldVisible(field, values)) continue
      if (!fieldRequired(field, values)) continue
      if (t === 'hidden') {
        if (fieldRequired(field, values)) {
          const v = values[field.name]
          const empty = Array.isArray(v) ? v.length === 0 : isEmpty(v)
          if (empty) missing.push(field.label_fa || field.name)
        }
        continue
      }
      if (t === 'therapist_slot_picker') {
        if (!fieldRequired(field, values)) continue
        const therapistVal = values[field.name]
        const slotIds = values.slot_ids
        if (isEmpty(therapistVal)) {
          missing.push(field.label_fa || field.name)
        }
        const weekly = Number(values.weekly_sessions)
        const slotCount = Array.isArray(slotIds) ? slotIds.length : 0
        if (weekly > 0 && slotCount !== weekly) {
          missing.push(`انتخاب ${weekly} اسلات هفتگی از شیت وقت‌های آزاد`)
        } else if (slotCount === 0) {
          missing.push('اسلات‌های هفتگی')
        }
        continue
      }
      if (t === 'radio_list' || t === 'checkbox_list') {
        const raw = values[field.name]
        const ack = values[`${field.name}_ack`]
        if (t === 'checkbox_list' && contextData) {
          const res = resolveCheckboxListOptions(field, contextData)
          if (res.options && res.options.length > 0 && !res.useFallback) {
            const arr = normalizeSelectedCoursesValue(raw)
            if (field.required && arr.length === 0) {
              missing.push(field.label_fa || field.name)
            }
            if (res.maxSelect != null && arr.length > res.maxSelect) {
              missing.push(`${field.label_fa || field.name} (حداکثر ${res.maxSelect} درس)`)
            }
            if (res.minSelect != null && arr.length < res.minSelect) {
              missing.push(`${field.label_fa || field.name} (حداقل ${res.minSelect} مورد)`)
            }
            continue
          }
        }
        if (field.required && !ack && (raw === undefined || raw === null || String(raw).trim() === '')) {
          missing.push(field.label_fa || field.name)
        }
        continue
      }
      if (t === 'step_otp') {
        if (isEmpty(values[field.name])) {
          missing.push(field.label_fa || field.name)
        } else if (values.step_otp_verified !== true) {
          missing.push(`${field.label_fa || field.name} (تأیید کد الزامی است)`)
        }
        continue
      }
      if (t === 'checkbox') {
        if (!values[field.name]) {
          missing.push(field.label_fa || field.name)
        }
        continue
      }
      if (isEmpty(values[field.name])) {
        missing.push(field.label_fa || field.name)
        continue
      }
      const ruleErr = checkRules(field, values[field.name])
      if (ruleErr) missing.push(ruleErr)
    }
  }
  return { ok: missing.length === 0, missing }
}

/** هم‌نام با backend: app/meta/student_step_forms.py */
export const CTX_STUDENT_FORMS_SUBMITTED = '__student_forms_submitted_states'
export const CTX_STUDENT_FORMS_UNLOCK = '__student_forms_edit_unlock'
/** پس از رد جزئی مدارک توسط پذیرش */
export const CTX_DOCUMENTS_RESUBMIT_FIELDS = '__documents_resubmit_fields'

export { CTX_STEP_OTP_VERIFIED_STATE, isStepOtpAlreadyVerified } from './stepOtpVerified'

/** فرم روش پرداخت تا قبل از پرداخت درگاه قابل ویرایش می‌ماند */
export const PAYMENT_METHOD_EDITABLE_STATES = new Set([
  'payment',
  'payment_method',
  'payment_choice',
  'payment_processing',
])

/** فرم این مرحله ثبت شده و مسئول هنوز ویرایش را باز نکرده → در UI مخفی */
export function isStudentStepFormLocked(contextData, currentState) {
  if (!currentState || !contextData) return false
  // تا قبل از پرداخت موفق، دانشجو باید بتواند روش/تعداد اقساط را عوض کند
  if (PAYMENT_METHOD_EDITABLE_STATES.has(currentState)) return false
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
  // بدهی جلسه ⇒ تسویه در همین پرداخت الزامی است (هم‌تراز بک‌اند)
  if (keySet.has('debt_settlement_included')) {
    const debt = Number(ctx.debt_sessions_count)
    if (Number.isFinite(debt) && debt > 0) {
      out.debt_settlement_included = true
    }
  }
  return out
}

/** هم‌نام با app/services/student_service._EDUCATION_CODE_TO_FA */
const EDUCATION_CODE_TO_FA = {
  bachelor: 'کارشناسی',
  master: 'کارشناسی ارشد',
  phd: 'دکتری',
  specialist: 'تخصص/فوق تخصص',
}

function isEmptyFormValue(v) {
  if (v === undefined || v === null) return true
  if (typeof v === 'string' && v.trim() === '') return true
  return false
}

/**
 * اگر فرم «پذیرش» در مرحلهٔ اول فرایند است و context خالی است، فیلدها را از پروفایل
 * کاربر / دانشجو پر می‌کند (همان دادهٔ ثبت‌نام وب‌سایت یا تکمیل ثبت‌نام).
 */
export function mergeAdmissionFormDefaultsFromProfile(forms, contextData, user, studentProfile) {
  const picked = pickFormValuesFromContext(forms, contextData)
  if (!user) return picked
  const formsForStudent = filterFormsForStudent(forms || [])
  const hasAdmission = formsForStudent.some(f => f && f.code === 'admission_form')
  if (!hasAdmission) return picked

  const extra = studentProfile?.extra_data || {}
  const out = { ...picked }

  const setIfEmpty = (key, val) => {
    if (isEmptyFormValue(val)) return
    if (!isEmptyFormValue(out[key])) return
    out[key] = val
  }

  setIfEmpty('full_name', user.full_name_fa)
  setIfEmpty('phone', user.phone)
  setIfEmpty('email', user.email)
  const rawEl = extra.education_level
  const edu =
    typeof rawEl === 'string' && EDUCATION_CODE_TO_FA[rawEl] ? EDUCATION_CODE_TO_FA[rawEl] : rawEl
  setIfEmpty('education_level', edu)
  setIfEmpty('field_of_study', extra.field_of_study)
  setIfEmpty('motivation', extra.motivation)
  setIfEmpty('national_code', extra.national_code)

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
 * @param {{ lockedSubmitted?: boolean, resubmitFieldNames?: string[] }} [opts] — اگر فرم ثبت شده و قفل است، انتقال را به‌خاطر فرم ناقص متوقف نکن
 */
export function stepFormsBlockTransition(forms, values, opts = {}) {
  if (opts.lockedSubmitted) return false
  const f = filterFormsForStudent(forms || [])
  if (f.length === 0) return false
  const r = validateStepForms(forms, values, {
    resubmitFieldNames: opts.resubmitFieldNames,
    contextData: opts.contextData,
  })
  return !r.ok
}
