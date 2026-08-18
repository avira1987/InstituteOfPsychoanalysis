/** راهنمای گام‌محور بر اساس وضعیت آمادگی پیش‌نیازها */
export function semesterPrepStepReadinessHint(currentState, readiness) {
  if (!currentState || !readiness?.items) return null
  const byKey = Object.fromEntries((readiness.items || []).map((i) => [i.key, i]))

  if (
    (currentState === 'course_list_creation' || currentState === 'course_list_review') &&
    !byKey.course_catalog?.complete
  ) {
    return 'کاتالوگ دروس هنوز خالی است — می‌توانید در همین جدول درس جدید بسازید، یا از صفحهٔ آمادگی پیش‌نیازها کاتالوگ را پر کنید.'
  }
  if (
    (currentState === 'course_list_creation' || currentState === 'course_list_review') &&
    !byKey.course_roster?.complete
  ) {
    return 'روستر مدرسین ناقص است — می‌توانید در همین جدول مدرس یا کمک‌مدرس جدید بسازید، یا از صفحهٔ آمادگی پیش‌نیازها چارت را تکمیل کنید.'
  }
  if (currentState === 'course_finalization' && !byKey.course_catalog?.complete) {
    return 'کاتالوگ دروس هنوز خالی است — ابتدا از صفحهٔ آمادگی پیش‌نیازها یا مرحلهٔ لیست دروس کاتالوگ را پر کنید.'
  }
  if (currentState === 'course_finalization' && !byKey.course_roster?.complete) {
    return 'روستر مدرسین ناقص است — ابتدا از صفحهٔ آمادگی پیش‌نیازها یا مرحلهٔ لیست دروس چارت را تکمیل کنید.'
  }
  if (currentState === 'interviewer_assignment' && !byKey.interviewers?.complete) {
    return 'مصاحبه‌گر فعالی در استخر پیش‌آماده‌سازی نیست — ابتدا در صفحهٔ آمادگی پیش‌نیازها مصاحبه‌گر اضافه کنید.'
  }
  if (currentState === 'license_check' && !byKey.license?.complete) {
    return 'وضعیت پروانه هنوز ثبت نشده — وضعیت را بررسی و در همین مرحله ثبت کنید تا در فرم پذیرش منعکس شود. ویرایش بعدی شماره از صفحهٔ پیش‌نیازها هم ممکن است.'
  }
  return null
}
