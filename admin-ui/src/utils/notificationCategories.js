/** دسته‌بندی اعلان‌های اقدام و پیام‌های پاپ‌آپ/سیستم برای زنگوله و صفحهٔ اعلان‌ها. */

export const BELL_TABS = [
  { id: 'all', label: 'همه' },
  { id: 'actions', label: 'اعلان‌ها' },
  { id: 'popup', label: 'پاپ‌آپ' },
  { id: 'system', label: 'سیستم' },
]

export const ACTION_GROUPS = [
  { id: 'process', label: 'فرآیند', hint: 'کارتابل و مراحل باز' },
  { id: 'interview', label: 'مصاحبه', hint: 'نوبت و پرداخت مصاحبه' },
  { id: 'assignment', label: 'تکلیف', hint: 'تصحیح و ثبت نمره' },
  { id: 'semester', label: 'آماده‌سازی ترم', hint: 'تقویم و مهلت کمیته' },
  { id: 'alert', label: 'هشدار و مهلت', hint: 'آمادگی و سررسید روزانه' },
]

const ACTION_GROUP_BY_KIND = {
  process: 'process',
  interview_booking: 'interview',
  interview_booking_pending: 'interview',
  assignment_grading: 'assignment',
  semester_prep_sla: 'semester',
  readiness: 'alert',
  daily_overdue: 'alert',
}

export function isFlashItem(it) {
  return it?.kind === 'flash_message'
}

export function flashCategory(it) {
  return it?.category === 'system' ? 'system' : 'popup'
}

export function actionGroupId(it) {
  const kind = String(it?.kind || '').trim().toLowerCase()
  if (ACTION_GROUP_BY_KIND[kind]) return ACTION_GROUP_BY_KIND[kind]
  const processCode = String(it?.process_code || '').trim().toLowerCase()
  if (processCode.includes('semester_preparation')) return 'semester'
  return 'process'
}

export function actionGroupMeta(it) {
  const id = actionGroupId(it)
  return ACTION_GROUPS.find((g) => g.id === id) || ACTION_GROUPS[0]
}

export function classifyNotifications(items) {
  const actions = []
  const popups = []
  const systems = []
  const actionGroups = Object.fromEntries(ACTION_GROUPS.map((g) => [g.id, []]))
  for (const it of items || []) {
    if (!isFlashItem(it)) {
      actions.push(it)
      actionGroups[actionGroupId(it)].push(it)
    } else if (flashCategory(it) === 'system') {
      systems.push(it)
    } else {
      popups.push(it)
    }
  }
  return { actions, popups, systems, actionGroups }
}

export function itemsForTab(tab, classified, allItems) {
  if (tab === 'actions') return classified.actions
  if (tab === 'popup') return classified.popups
  if (tab === 'system') return classified.systems
  return allItems || []
}

export function tabCount(tabId, classified) {
  if (tabId === 'actions') return classified.actions.length
  if (tabId === 'popup') return classified.popups.length
  if (tabId === 'system') return classified.systems.length
  return classified.actions.length + classified.popups.length + classified.systems.length
}
