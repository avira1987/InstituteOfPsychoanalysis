import { resolvePendingInstanceId } from './operatorFollowupDeepLinks'

/**
 * ادغام آیتم‌های process از my-operator-followup با فهرست pending محلی (بدون تکرار).
 * @param {Array} inboxItems
 * @param {Array} localPending
 * @returns {Array}
 */
export function mergeProcessInboxIntoPending(inboxItems, localPending) {
  const inboxProcess = (inboxItems || []).filter((i) => i.kind === 'process')
  const ordered = []
  const seen = new Set()
  for (const i of inboxProcess) {
    ordered.push({
      instance_id: i.instance_id,
      student_id: i.student_id,
      student_code: i.student_code,
      current_state: i.state_code,
      process_code: i.process_code,
      responsible_role_code: i.responsible_role_code,
      is_completed: false,
      is_cancelled: false,
    })
    seen.add(i.instance_id)
  }
  for (const p of localPending || []) {
    const pid = resolvePendingInstanceId(p)
    if (pid && !seen.has(pid)) ordered.push(p)
  }
  return ordered
}
