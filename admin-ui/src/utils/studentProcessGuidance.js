import { filterFormsForStudent } from './processFormsStudent'
import { labelState } from './processDisplay'

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
}) {
  const proc = definition?.process || {}
  const overviewFa = (proc.description && String(proc.description).trim()) || ''
  const st = findStateDefinition(definition, detail?.current_state)
  const meta = st?.metadata || {}
  const shortFa = (meta.student_short_fa || meta.student_guidance_fa || '').trim()
    || (st?.name_fa || detail?.current_state || '')
  const role = st?.assigned_role
  const done = detail?.is_completed || detail?.is_cancelled

  const studentForms = filterFormsForStudent(forms || [])
  const nTrans = transitions?.length || 0
  const hasForms = studentForms.length > 0
  const hasStudentWork = nTrans > 0 || hasForms

  let taskFa = ''
  if (!done && st) {
    const customTask = (meta.student_task_fa || '').trim()
    if (customTask) {
      taskFa = customTask
    } else if (role === 'student' && hasStudentWork) {
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
    } else if (role === 'student' && !hasStudentWork) {
      taskFa = 'در این لحظه کاری از داخل پنل برای شما پیش‌بینی نشده؛ اگر پیامی دریافت کردید طبق آن عمل کنید؛ در غیر این صورت بعداً همین صفحه را تازه کنید.'
    } else if (role && role !== 'student') {
      taskFa = 'در این مرحله اقدام مستقیم از پنل شما لازم نیست؛ منتظر بررسی یا اقدام همکاران بمانید و بعداً همین صفحه را تازه کنید.'
    } else {
      taskFa = 'در این مرحله اقدام مستقیم از پنل شما لازم نیست؛ منتظر پیگیری بمانید.'
    }
  }

  return {
    overviewFa,
    shortFa,
    taskFa: taskFa || '',
    role,
    done,
  }
}
