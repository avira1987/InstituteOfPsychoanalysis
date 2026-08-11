import { filterFormsForStudent } from './processFormsStudent'
import { labelState } from './processDisplay'
import { STUDENT_TASK_LABELS_FA, PROCESS_STUDENT_TASK_LABELS_FA, PROCESS_STATE_LABELS_FA } from './processMetadataLabels'

export const INTRO_REG_ADMISSION_RESULT_STATES = new Set([
  'result_conditional_therapy',
  'result_single_course',
  'result_full_admission',
])

export function findStateDefinition(definition, stateCode) {
  if (!definition?.states || !stateCode) return null
  return definition.states.find(s => s.code === stateCode) || null
}

/**
 * متن راهنمای دانشجو از روی تعریف فرایند، وضعیت فعلی، انتقال‌های مجاز و فرم‌ها.
 * در JSON هر state می‌توان در metadata فیلدهای student_guidance_fa، student_short_fa، student_task_fa گذاشت.
 */
export function buildStudentGuidance({
  definition,
  detail,
  transitions,
  forms,
  stepFormLocked,
  registrationGate = null,
}) {
  const proc = definition?.process
  const procCode = proc?.code
  const overviewFa = (proc?.description && String(proc.description).trim()) || ''
  const st = findStateDefinition(definition, detail?.current_state)
  const meta = st?.metadata || {}
  const ctx = detail?.context_data || {}
  const shortFa = (meta.student_short_fa || meta.student_guidance_fa || '').trim()
    || (procCode && PROCESS_STATE_LABELS_FA[procCode]?.[detail?.current_state])
    || (st?.name_fa || detail?.current_state || '')
  const whyFa = (meta.student_why_fa || '').trim()
  const role = st?.assigned_role
  const done = detail?.is_completed || detail?.is_cancelled

  const studentForms = filterFormsForStudent(forms || [])
  const nTrans = transitions?.length || 0
  const hasForms = studentForms.length > 0
  const hasStudentWork = nTrans > 0 || hasForms
  const studentOrApplicant = role === 'student' || role === 'applicant'

  let taskFa = ''
  if (!done && st) {
    const stateCode = detail?.current_state
    const customTask = (
      (procCode && PROCESS_STUDENT_TASK_LABELS_FA[procCode]?.[stateCode])
      || (stateCode && STUDENT_TASK_LABELS_FA[stateCode])
      || meta.student_task_fa
      || ''
    ).trim()
    if (customTask) {
      taskFa = customTask
    } else if (studentOrApplicant && hasStudentWork) {
      if (hasForms && !stepFormLocked) {
        taskFa = 'فرم‌های همین صفحه را تکمیل و ثبت کنید؛ سپس دکمهٔ «ادامه و ثبت مرحله» را بزنید تا به مرحلهٔ بعد بروید. پرداخت یا پیامک در صورت نیاز توسط سامانه انجام می‌شود.'
      } else if (nTrans > 0) {
        if (nTrans === 1) {
          const next = labelState(transitions[0]?.to_state)
          taskFa = `پس از انجام کارهای همین صفحه، دکمهٔ «ادامه و ثبت مرحله» را بزنید تا به «${next}» بروید. پرداخت یا پیامک در صورت نیاز توسط سامانه انجام می‌شود؛ متن روی دکمه فقط ثبت مرحله است.`
        } else {
          taskFa = 'پس از انجام کارهای همین صفحه، یکی از دکمه‌های «ادامه به …» را بزنید تا به همان مرحلهٔ انتخابی بروید. پرداخت یا پیامک در صورت نیاز توسط سامانه انجام می‌شود.'
        }
      } else if (hasForms && stepFormLocked) {
        taskFa = 'اطلاعات این مرحله قبلاً ثبت شده است؛ اگر دکمهٔ «ادامه و ثبت مرحله» را می‌بینید همان را بزنید؛ در غیر این صورت منتظر اقدام اداری بمانید.'
      }
    } else if (studentOrApplicant && !hasStudentWork) {
      taskFa = 'در این لحظه کاری از داخل پنل برای شما پیش‌بینی نشده؛ اگر پیامی دریافت کردید طبق آن عمل کنید؛ در غیر این صورت بعداً همین صفحه را تازه کنید.'
    } else if (role && role !== 'student' && role !== 'applicant') {
      taskFa = 'در این مرحله اقدام مستقیم از پنل شما لازم نیست؛ منتظر بررسی یا اقدام همکاران بمانید و بعداً همین صفحه را تازه کنید.'
    } else {
      taskFa = 'در این مرحله اقدام مستقیم از پنل شما لازم نیست؛ منتظر پیگیری بمانید.'
    }
  }

  const ctxOverride = (ctx.student_next_action_fa || '').trim()
  if (!done && ctxOverride) {
    taskFa = ctxOverride
  }

  const introGateClosed =
    procCode === 'introductory_course_registration'
    && registrationGate
    && registrationGate.allowed === false
  if (
    !done
    && introGateClosed
    && INTRO_REG_ADMISSION_RESULT_STATES.has(detail?.current_state)
  ) {
    taskFa =
      registrationGate.reason_fa
      || 'پذیرش شما ثبت شد. آپلود مدارک پس از باز شدن پنجرهٔ ثبت‌نام ترم فعال می‌شود؛ همین صفحه را بعد از اعلام باز شدن ثبت‌نام تازه کنید.'
  }

  return {
    overviewFa,
    shortFa,
    taskFa: taskFa || '',
    whyFa,
    role,
    done,
  }
}
