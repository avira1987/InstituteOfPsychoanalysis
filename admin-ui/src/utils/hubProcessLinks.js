/** لینک‌های عمیق هاب‌های برش ۱ (تخلف / مالی / ارجاع). */

export const HUB_VIOLATION = 'violation_registration'
export const HUB_FEE = 'fee_determination'
export const HUB_REFERRAL = 'patient_referral'

function qs(params) {
  const u = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && v !== '') u.set(k, String(v))
  })
  const s = u.toString()
  return s ? `?${s}` : ''
}

export function studentProcessInstanceHref({ processCode, instanceId, studentId } = {}) {
  return `/panel/portal/student${qs({
    tab: 'processes',
    process_code: processCode,
    instance_id: instanceId,
    student_id: studentId,
  })}`
}

export function violationCommitteeKind(stateCode, roleCode) {
  const state = String(stateCode || '').toLowerCase()
  const role = String(roleCode || '').toLowerCase()
  if (state === 'referred_to_education_committee' || role === 'education_committee') {
    return 'education'
  }
    return 'supervision'
}

export function patientReferralCommitteeHref({ instanceId, studentId } = {}) {
  return `/panel/portal/committee/supervision${qs({
    tab: 'reviews',
    instance_id: instanceId,
    student_id: studentId,
    process_code: HUB_REFERRAL,
  })}`
}

export function violationCommitteeHref({
  instanceId,
  studentId,
  stateCode,
  roleCode,
} = {}) {
  const kind = violationCommitteeKind(stateCode, roleCode)
  const path = kind === 'education'
    ? '/panel/portal/committee/education'
    : '/panel/portal/committee/supervision'
  return `${path}${qs({
    tab: 'reviews',
    instance_id: instanceId,
    student_id: studentId,
    process_code: HUB_VIOLATION,
  })}`
}
