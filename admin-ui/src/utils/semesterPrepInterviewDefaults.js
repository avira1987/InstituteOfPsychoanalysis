/**
 * پیش‌فرض‌های اسلات مصاحبه از context فرم مرحلهٔ interview_scheduling آماده‌سازی ترم.
 * @param {Record<string, unknown> | null | undefined} contextData
 * @returns {{ mode: 'online' | 'in_person', locationFa: string, lockMode: boolean } | null}
 */
export function interviewSlotDefaultsFromContext(contextData) {
  const modeFa = contextData?.interview_mode
  if (modeFa !== 'آنلاین' && modeFa !== 'حضوری') {
    return null
  }
  const isOnline = modeFa === 'آنلاین'
  const locationFa = isOnline
    ? ''
    : String(
        contextData?.interview_location_fa
          || contextData?.interview_location_or_link
          || '',
      ).trim()
  return {
    mode: isOnline ? 'online' : 'in_person',
    locationFa,
    lockMode: true,
  }
}
