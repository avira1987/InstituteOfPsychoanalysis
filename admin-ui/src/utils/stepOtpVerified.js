/** وضعیت فعلی که OTP مرحله برایش روی سرور تأیید شده (هم‌تراز backend) */
export const CTX_STEP_OTP_VERIFIED_STATE = '__step_otp_verified_state'

/**
 * آیا OTP مرحله قبلاً تأیید شده است؟
 * فلگ ماندگار context.step_otp_verified بعد از ثبت موفق فرم می‌ماند
 * (مثلاً اصلاح مدارک ردشده نباید دوباره کد بخواهد).
 * @param {Record<string, unknown>|null|undefined} values
 * @param {Record<string, unknown>|null|undefined} contextData
 * @param {string|null|undefined} currentState
 */
export function isStepOtpAlreadyVerified(values, contextData, currentState) {
  if (values?.step_otp_verified === true) return true
  if (contextData?.step_otp_verified === true) return true
  const stamped = contextData?.[CTX_STEP_OTP_VERIFIED_STATE]
  if (!stamped || typeof stamped !== 'string') return false
  if (!currentState) return true
  return stamped === currentState
}
