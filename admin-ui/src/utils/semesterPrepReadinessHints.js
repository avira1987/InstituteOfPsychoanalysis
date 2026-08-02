/** راهنمای گام‌محور بر اساس وضعیت آمادگی پیش‌نیازها */
export function semesterPrepStepReadinessHint(currentState, readiness) {
  if (!currentState || !readiness?.items) return null
  const byKey = Object.fromEntries((readiness.items || []).map((i) => [i.key, i]))

  if (
    (currentState === 'course_list_creation' || currentState === 'course_list_review' || currentState === 'course_finalization') &&
    !byKey.course_catalog?.complete
  ) {
    return 'کاتالوگ دروس هنوز خالی است — می‌توانید از همین فرم درس جدید بسازید یا از صفحهٔ آمادگی پیش‌نیازها کاتالوگ را پر کنید.'
  }
  if (
    (currentState === 'course_list_creation' || currentState === 'course_list_review' || currentState === 'course_finalization') &&
    !byKey.course_roster?.complete
  ) {
    return 'روستر مدرسین ناقص است — می‌توانید نام مدرس/کمک‌مدرس را در جدول تایپ کنید یا از صفحهٔ آمادگی پیش‌نیازها چارت را تکمیل کنید.'
  }
  if (currentState === 'interviewer_assignment' && !byKey.interviewers?.complete) {
    return 'مصاحبه‌گرها از میان کارمندان اتوماسیون انتخاب می‌شوند — اگر کارمند موردنظر در فهرست نیست، ابتدا کاربر او را در مدیریت کاربران بسازید.'
  }
  if (currentState === 'license_check' && !byKey.license?.complete) {
    return 'وضعیت پروانه هنوز ثبت نشده — وضعیت را بررسی و در همین مرحله ثبت کنید تا در فرم پذیرش منعکس شود.'
  }
  return null
}
