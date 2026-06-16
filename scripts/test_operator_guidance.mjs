/**
 * Smoke tests for buildOperatorGuidance — run from repo root:
 *   node scripts/test_operator_guidance.mjs
 */
import { buildOperatorGuidance } from '../admin-ui/src/utils/operatorProcessGuidance.js'
import { portalRoleCanActOnState } from '../admin-ui/src/utils/portalRoleAccess.js'

function assert(cond, msg) {
  if (!cond) {
    console.error('FAIL:', msg)
    process.exit(1)
  }
}

const therapistDef = {
  process: {
    code: 'extra_session',
    description: 'درخواست جلسه اضافه',
    name_fa: 'جلسه اضافه',
  },
  states: [{
    code: 'therapist_review',
    name_fa: 'بررسی درمانگر',
    assigned_role: 'therapist',
    metadata: {
      operator_task_fa: 'بررسی درخواست؛ فرم را تکمیل و دکمه تصمیم را بزنید.',
    },
  }],
}

const detail = {
  process_code: 'extra_session',
  current_state: 'therapist_review',
  is_completed: false,
  is_cancelled: false,
}

assert(portalRoleCanActOnState('therapist', 'therapist'), 'therapist can act on therapist state')
assert(!portalRoleCanActOnState('staff', 'therapist'), 'staff cannot act on therapist state')
assert(portalRoleCanActOnState('admin', 'therapist'), 'admin can act on any state')

const therapistGuidance = buildOperatorGuidance({
  definition: therapistDef,
  detail,
  transitions: [{ trigger_event: 'approve', to_state: 'done' }],
  forms: [],
  portalRole: 'therapist',
})
assert(therapistGuidance.taskFa.includes('بررسی'), `expected seeded task, got: ${therapistGuidance.taskFa}`)
assert(therapistGuidance.canAct === true, 'therapist canAct')

const staffView = buildOperatorGuidance({
  definition: therapistDef,
  detail,
  transitions: [],
  forms: [],
  portalRole: 'staff',
})
assert(
  staffView.taskFa.includes('نقش دیگر') || staffView.taskFa.includes('مشاهده'),
  `expected view-only for staff, got: ${staffView.taskFa}`,
)

const staffDef = {
  process: { code: 'introductory_course_registration', description: 'ثبت‌نام', name_fa: 'ثبت‌نام' },
  states: [{
    code: 'documents_review',
    name_fa: 'بررسی مدارک',
    assigned_role: 'admissions_officer',
    metadata: {},
  }],
}

const staffGuidance = buildOperatorGuidance({
  definition: staffDef,
  detail: { ...detail, process_code: 'introductory_course_registration', current_state: 'documents_review' },
  transitions: [{ trigger_event: 'approve', description: 'تأیید', to_state: 'next' }],
  forms: [{ code: 'f1', fields: [] }],
  portalRole: 'staff',
})
assert(
  staffGuidance.taskFa.includes('مدارک') || staffGuidance.taskFa.includes('فرم') || staffGuidance.taskFa.includes('تصمیم'),
  `expected staff fallback/seed task, got: ${staffGuidance.taskFa}`,
)

const completed = buildOperatorGuidance({
  definition: therapistDef,
  detail: { ...detail, is_completed: true },
  transitions: [],
  forms: [],
  portalRole: 'therapist',
})
assert(completed.taskFa === '', 'completed instance has no task')

console.log('test_operator_guidance.mjs: ok')
