import {
  OPERATOR_TASK_LABELS_FA,
  PROCESS_OPERATOR_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
  STATE_LABELS_FA,
} from './processMetadataLabels.js'
import { normalizeAssignedRole, portalRoleCanActOnState } from './portalRoleAccess.js'
import { labelRoleFa } from './roleLabels.js'

function findStateDefinition(definition, stateCode) {
  if (!definition?.states || !stateCode) return null
  return definition.states.find(s => s.code === stateCode) || null
}

function labelState(code) {
  return STATE_LABELS_FA[code] || code || ''
}

/** برچسب فارسی assigned_role — از منبع واحد roleLabels.js */
export function assignedRoleLabelFa(roleCode) {
  return labelRoleFa(roleCode)
}

export function buildWaitingForRoleTaskFa(assignedRole) {
  const label = assignedRoleLabelFa(assignedRole)
  if (label) {
    return (
      `در این مرحله فرایند منتظر «${label}» است — شما فقط می‌توانید مشاهده کنید. `
      + 'تکمیل و پاس به نقش بعدی فقط با مسئول همین مرحله است؛ '
      + 'بازگشت به مرحلهٔ قبل یا شروع دوباره فقط برای مدیر سامانه و معاون آموزش مجاز است.'
    )
  }
  return (
    'این مرحله در انتظار نقش دیگر است؛ فقط مشاهده. '
    + 'بازگشت/شروع دوباره فقط مدیر سامانه و معاون آموزش.'
  )
}

const OPERATOR_FALLBACK_BY_ROLE = {
  therapist: 'بررسی درخواست؛ فرم را تکمیل و دکمه تصمیم را بزنید.',
  supervisor: 'ثبت/بررسی جلسه سوپرویژن؛ سپس دکمه تأیید.',
  admissions_officer: 'بررسی مدارک/پرونده؛ تأیید، نقص، یا ادامه.',
  interviewer: 'ثبت نتیجه مصاحبه در فرم محرمانه.',
  progress_committee: 'بررسی پرونده و ثبت تصمیم جلسه.',
  progress_committee_project: 'بررسی پروژه و ثبت تصمیم کمیته پیشرفت.',
  supervision_committee: 'بررسی/صدور مجوز طبق دستور کار.',
  instructor: 'ثبت نمره/حضور/تأیید TA.',
  teaching_assistant: 'هماهنگی با مدرس؛ ثبت اطلاعات یا تأیید درخواست.',
  teaching_assistant_or_instructor: 'بررسی و ثبت تصمیم طبق نقش شما (مدرس یا TA).',
  site_manager: 'بررسی درخواست و ثبت تصمیم.',
  deputy_education: 'بررسی پرونده و تأیید یا ارجاع.',
  deputy_education_director: 'بررسی پرونده و ثبت تصمیم مدیریتی.',
  education_committee: 'بررسی پرونده در جلسه کمیته آموزش.',
  course_committee: 'بررسی موضوع در کمیته دروس.',
  course_committee_scientific: 'بررسی علمی و ثبت نظر.',
  course_committee_executive: 'هماهنگی اجرایی و ثبت تصمیم.',
  scientific_officer_course_committee: 'بررسی علمی و ثبت نظر.',
  monitoring_committee_officer: 'بررسی گزارش و ثبت اقدام.',
  specialized_commission: 'بررسی پرونده و ثبت رأی.',
  therapy_committee_chair: 'بررسی پرونده درمان و ثبت تصمیم.',
  therapy_committee_executor: 'اجرا و پیگیری تصمیم کمیته درمان.',
  therapy_education_coordinator: 'هماهنگی آموزش درمان و ثبت اطلاعات.',
}

function fallbackOperatorTask(role, transitions, forms, stepFormLocked) {
  const nTrans = transitions?.length || 0
  const hasForms = (forms?.length || 0) > 0
  const roleFallback = OPERATOR_FALLBACK_BY_ROLE[normalizeAssignedRole(role)]
  if (roleFallback && !hasForms && nTrans === 0) return roleFallback
  if (hasForms && nTrans > 0 && !stepFormLocked) {
    return 'فرم‌های همین صفحه را تکمیل کنید؛ سپس دکمهٔ تصمیم یا ادامه را بزنید.'
  }
  if (hasForms && !stepFormLocked) {
    return 'فرم‌های همین صفحه را تکمیل و ثبت کنید.'
  }
  if (nTrans === 1) {
    const next = labelState(transitions[0]?.to_state)
    return `پس از بررسی پرونده، دکمهٔ «${transitions[0]?.description || transitions[0]?.trigger_event || 'ادامه'}» را بزنید${next ? ` تا به «${next}» بروید` : ''}.`
  }
  if (nTrans > 1) {
    return 'پس از بررسی پرونده، یکی از دکمه‌های تصمیم پایین صفحه را انتخاب کنید.'
  }
  if (roleFallback) return roleFallback
  return 'این مرحله در انتظار اقدام شماست؛ جزئیات را در پرونده ببینید.'
}

/**
 * متن راهنمای اپراتور از روی تعریف فرایند، وضعیت فعلی، انتقال‌ها و فرم‌ها.
 */
export function buildOperatorGuidance({
  definition,
  detail,
  transitions,
  forms,
  portalRole,
  stepFormLocked = false,
}) {
  const proc = definition?.process
  const procCode = proc?.code
  const overviewFa = (proc?.description && String(proc.description).trim()) || ''
  const st = findStateDefinition(definition, detail?.current_state)
  const meta = st?.metadata || {}
  const shortFa = (meta.operator_short_fa || '').trim()
    || (procCode && PROCESS_STATE_LABELS_FA[procCode]?.[detail?.current_state])
    || (st?.name_fa || detail?.current_state || '')
  const role = st?.assigned_role
  const done = detail?.is_completed || detail?.is_cancelled
  const canAct = portalRoleCanActOnState(portalRole, role)

  let taskFa = ''
  if (!done && st) {
    const stateCode = detail?.current_state
    const customTask = (
      (procCode && PROCESS_OPERATOR_TASK_LABELS_FA[procCode]?.[stateCode])
      || (stateCode && OPERATOR_TASK_LABELS_FA[stateCode])
      || meta.operator_task_fa
      || ''
    ).trim()
    if (!canAct && portalRole !== 'admin') {
      taskFa = buildWaitingForRoleTaskFa(role)
    } else if (customTask) {
      taskFa = customTask
    } else if (canAct || portalRole === 'admin') {
      taskFa = fallbackOperatorTask(role, transitions, forms, stepFormLocked)
    }
  }

  return {
    overviewFa,
    shortFa,
    taskFa: taskFa || '',
    role,
    waitingRoleLabelFa: !canAct && !done ? assignedRoleLabelFa(role) : '',
    done,
    canAct,
  }
}
