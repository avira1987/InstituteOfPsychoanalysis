import { labelRoleFa } from './roleLabels.js'

const PREP_PROCESSES = new Set(['fall_semester_preparation', 'winter_semester_preparation'])

/** مرحلهٔ یکپارچهٔ مصاحبه‌ها — مسئول نمایشی: مدیر داخلی */
export const PREP_INTERNAL_MANAGER_STATES = new Set([
  'interviewer_assignment',
  'interview_scheduling',
])

export function isSemesterPrepInternalManagerState(processCode, stateCode) {
  return PREP_PROCESSES.has(processCode) && PREP_INTERNAL_MANAGER_STATES.has(stateCode)
}

/** کد assigned_role برای تطبیق دسترسی UI (معادل staff). */
export function effectiveSemesterPrepAssignedRole(processCode, stateCode, assignedRole) {
  if (isSemesterPrepInternalManagerState(processCode, stateCode)) return 'staff'
  return assignedRole
}

export function semesterPrepResponsibleRoleLabelFa(processCode, stateCode, assignedRole) {
  if (isSemesterPrepInternalManagerState(processCode, stateCode)) {
    return labelRoleFa('internal_manager')
  }
  return labelRoleFa(assignedRole)
}
