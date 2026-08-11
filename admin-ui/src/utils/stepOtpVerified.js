/** وضعیت فعلی که OTP مرحله برایش روی سرور تأیید شده (هم‌تراز backend) */
export const CTX_STEP_OTP_VERIFIED_STATE = '__step_otp_verified_state'

/**
 * آیا OTP مرحله برای همین وضعیت روی سرور (یا فلگ فرم) تأیید شده است؟
 * @param {Record<string, unknown>|null|undefined} values
 * @param {Record<string, unknown>|null|undefined} contextData
 * @param {string|null|undefined} currentState
 */
export function isStepOtpAlreadyVerified(values, contextData, currentState) {
  if (values?.step_otp_verified === true) return true
  const stamped = contextData?.[CTX_STEP_OTP_VERIFIED_STATE]
  if (!stamped || typeof stamped !== 'string') return false
  if (!currentState) return true
  return stamped === currentState
}
