/** پیام خطا/انتظار برای ساخت لینک مصاحبهٔ آنلاین در پنل اپراتور. */
export function interviewMeetingLinkPreparingState(slot) {
  const status = slot?.meeting_link_provision_status
  const paid = !slot?.booking_payment_deadline_at
  const ready = Boolean(slot?.meeting_link_ready)

  if (slot?.interview_result_recorded) {
    return {
      preparing: false,
      preparingFailed: false,
      preparingText: '',
      resultRecorded: true,
    }
  }

  if (!paid) {
    return {
      preparing: false,
      preparingFailed: false,
      preparingText: 'پس از پرداخت دانشجو، لینک آنلاین تولید می‌شود.',
    }
  }

  if (ready) {
    return { preparing: false, preparingFailed: false, preparingText: '' }
  }

  if (status === 'alocom_not_configured') {
    return {
      preparing: true,
      preparingFailed: true,
      preparingText:
        'یکپارچه‌سازی الوکام روی سرور فعال نیست (ALOCOM_ENABLED و اطلاعات ورود). لینک آنلاین ساخته نمی‌شود تا مدیر سیستم آن را در .env تنظیم کند.',
    }
  }

  if (status === 'provisioning_failed') {
    return {
      preparing: true,
      preparingFailed: true,
      preparingText:
        'ساخت لینک آنلاین در الوکام ناموفق بود. لاگ سرور را بررسی کنید یا با پشتیبانی تماس بگیرید.',
    }
  }

  return {
    preparing: true,
    preparingFailed: false,
    preparingText: 'لینک آنلاین در حال آماده‌سازی است؛ همین صفحه را کمی بعد تازه کنید.',
  }
}
