import { PROCESS_LABELS_FA, STATE_LABELS_FA } from './processMetadataLabels'
import { parseStepFileUploadValue, resolveUploadPublicUrl } from './uploadPublicUrl'

/** برچسب‌های ثابت برای کلیدهای رایج در context_data */
export const CONTEXT_KEY_LABELS = {
  notes: 'یادداشت ثبت‌شده',
  interview_result: 'نتیجهٔ مصاحبه',
  weekly_sessions: 'تعداد جلسات هفتگی',
  from_state: 'مرحلهٔ قبل از انتقال',
  to_state: 'مرحلهٔ بعد از انتقال',
  termination_requests: 'درخواست‌های خاتمه',
  reminder_45_48_sent_at: 'زمان ارسال یادآور (۴۵–۴۸ ساعت)',
  student_status: 'وضعیت دانشجو (در پرونده)',
  amount: 'مبلغ',
  decision: 'تصمیم',
  interview_result_submitted: 'ثبت نتیجهٔ مصاحبه',
  return_reminder_at: 'یادآور بازگشت',
  return_deadline_at: 'مهلت ثبت‌نام پس از یادآوری',
  leave_schedule_set_at: 'زمان تنظیم تقویم بازگشت',
  committee_meeting_at: 'زمان جلسه کمیته (ثبت‌شده در سامانه)',
  committee_meeting_mode: 'نحوهٔ جلسه کمیته',
  committee_meeting_link: 'لینک جلسه آنلاین',
  committee_meeting_location_fa: 'محل یا آدرس جلسه',
  student_portal_alert_fa: 'هشدار نمایش داده‌شده به دانشجو',
  logged_at: 'زمان ثبت',
  payload: 'جزئیات',
  admission_type: 'نوع پذیرش',
  allowed_course_count: 'تعداد دروس مجاز',
  therapist_id: 'شناسه درمانگر',
  new_supervisor_id: 'شناسه سوپروایزر جدید',
  session_credit_balance: 'موجودی اعتبار جلسه',
  supervision_attendance_recorded: 'ثبت حضور در سوپرویژن',
  session_payment_forfeited: 'جلسه بدون بازپرداخت (مصادره)',
  forfeit_amount: 'مبلغ باقی‌ماندهٔ غیرقابل‌بازگشت',
  invoice_amount: 'مبلغ فاکتور',
  last_session_link: 'لینک جلسه آنلاین',
  therapy_session_id: 'شناسهٔ جلسهٔ درمان (ثبت‌شده)',
  payment_amount_rial: 'مبلغ پرداخت (ریال)',
  agreed_session_date: 'تاریخ توافق‌شدهٔ جلسه',
  agreed_session_time: 'ساعت توافق‌شدهٔ جلسه',
  extra_session_calendar_summary_fa: 'خلاصهٔ ثبت تقویم (جلسه اضافی)',
  extra_session_calendar_noted_at: 'زمان یادداشت تقویم',
  therapy_status: 'وضعیت درمان آموزشی',
  payment_unlocked_for_50th_session: 'امکان پرداخت جلسه ۵۰ام فعال شد',
  supervisor_slot_removed_from_available: 'حذف از وقت‌های آزاد سوپروایزر',
  accumulated_therapy_hours: 'ساعت‌های تجمعی درمان',
  payment_method: 'روش پرداخت',
  payment_method_selected: 'انتخاب روش پرداخت',
  installment_count: 'تعداد اقساط',
  pending_installments_remaining: 'تعداد اقساط باقی‌مانده',
  next_installment_due_at: 'سررسید قسط بعدی',
  term_start_date: 'تاریخ شروع ترم',
  total_score: 'نمرهٔ کل',
  result_status: 'نتیجه (قبول/مردود)',
  average_score: 'میانگین نمره',
  participation_rate: 'میزان مشارکت',
  grade: 'نمره',
  course_name: 'نام درس',
  selected_courses: 'دروس انتخاب‌شده',
  source: 'منبع ثبت در سامانه',
  parent_start_therapy_instance_id: 'شناسهٔ فرایند آغاز درمان (فنی)',
  parent_instance_id: 'فرایند مرتبط (والد)',
  parent_process_code: 'کد فرایند والد',
  therapy_changes_next_step_fa: 'گام پیشنهادی بعد از این فرایند',
  ui_completion_summary_fa: 'خلاصهٔ نتیجه (تعیین تکلیف هزینه جلسه)',
  fee_settlement_mode: 'نحوهٔ تسویهٔ مالی',
  fee_settlement_amount: 'مبلغ تسویه‌شده',
  reason: 'علت',
  photo: 'عکس پرسنلی',
  id_card: 'تصویر شناسنامه',
  national_card: 'تصویر کارت ملی',
  bachelor_degree: 'مدرک کارشناسی / پزشکی عمومی',
  master_degree: 'مدرک کارشناسی ارشد',
  latest_certificate: 'آخرین مدرک تحصیلی',
  digital_commitment: 'تعهدنامه دیجیتال (کد پیامکی)',
  selected_timeslot: 'زمان مصاحبه انتخاب‌شده',
}

const INTERVIEW_RESULT_LABELS = {
  conditional_therapy: 'درمان شرطی',
  single_course: 'تک‌درس / محدود',
  full_admission: 'پذیرش کامل',
  rejected: 'رد',
}

/** مقادیر رشته‌ای رایج در context که در متادیتای مرحله‌ها نیستند */
export const CONTEXT_VALUE_LABELS = {
  cash: 'نقدی',
  installment: 'اقساطی',
  full: 'ثبت‌نام/پرداخت کامل',
  PASS: 'قبول',
  FAIL: 'مردود',
  pass: 'قبول',
  fail: 'مردود',
  pending: 'در انتظار',
  completed: 'تکمیل‌شده',
  cancelled: 'لغو شده',
  approved: 'تایید شده',
  rejected: 'رد شده',
  therapy_interruption_long: 'وقفهٔ طولانی درمان',
  after_start_therapy_complete: 'پس از تکمیل آغاز درمان',
  theory_1: 'درس تئوری ۱',
  theory_2: 'درس تئوری ۲',
  online: 'آنلاین',
  in_person: 'حضوری',
}

/**
 * @param {unknown[]} forms
 * @returns {Map<string, string>}
 */
export function buildFieldLabelMap(forms) {
  const m = new Map()
  for (const f of forms || []) {
    for (const field of f.fields || []) {
      const name = field.name
      if (name && field.label_fa) m.set(name, field.label_fa)
    }
  }
  return m
}

export function prettyKeyFallback(key) {
  if (key.startsWith('__')) return null
  if (CONTEXT_KEY_LABELS[key]) return CONTEXT_KEY_LABELS[key]
  return key.replace(/_/g, ' ')
}

/**
 * @param {string} key
 * @param {Map<string, string>|null|undefined} fieldLabelMap
 */
export function resolveContextRowLabel(key, fieldLabelMap) {
  if (CONTEXT_KEY_LABELS[key]) return CONTEXT_KEY_LABELS[key]
  if (fieldLabelMap && fieldLabelMap.has(key)) return fieldLabelMap.get(key)
  return prettyKeyFallback(key)
}

function formatIsoMaybe(s) {
  if (typeof s !== 'string') return s
  const t = Date.parse(s)
  if (Number.isNaN(t)) return s
  try {
    return new Date(s).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return s
  }
}

function looksLikeIso(s) {
  return typeof s === 'string' && (/^\d{4}-\d{2}-\d{2}/.test(s) || (s.includes('T') && s.includes(':')))
}

/** رشتهٔ تک‌مقدار در context: تاریخ، یا برچسب فارسی از CONTEXT_VALUE_LABELS */
export function formatContextStringForDisplay(value) {
  if (typeof value !== 'string') return null
  if (looksLikeIso(value)) return formatIsoMaybe(value)
  if (CONTEXT_VALUE_LABELS[value]) return CONTEXT_VALUE_LABELS[value]
  return null
}

export function formatInterviewResultDisplay(value, labelState) {
  if (typeof value !== 'string') return null
  return INTERVIEW_RESULT_LABELS[value] || (labelState ? labelState(value) : value)
}

const MAX_DEPTH = 5

/**
 * اگر مقدار شبیه خروجی فیلد file_upload باشد، پیش‌نمایش تصویر/PDF در پنل ادمین/کارمند.
 * @param {typeof import('react')} React
 * @returns {import('react').ReactNode | null}
 */
function renderIfProcessStepFileUpload(React, value) {
  const { url, mime, isLocalPlaceholder, fileName } = parseStepFileUploadValue(value)
  if (url) {
    const src = resolveUploadPublicUrl(url)
    const showImage = mime.startsWith('image/')
    const showPdf = mime === 'application/pdf'
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', alignItems: 'flex-start' }}>
        {showImage && (
          <a href={src} target="_blank" rel="noopener noreferrer">
            <img
              src={src}
              alt=""
              style={{
                maxWidth: 'min(100%, 280px)',
                maxHeight: '200px',
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                display: 'block',
                objectFit: 'contain',
              }}
            />
          </a>
        )}
        {showPdf && (
          <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline">
            باز کردن PDF
          </a>
        )}
        {!showImage && !showPdf && (
          <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline">
            باز کردن فایل
          </a>
        )}
        <span style={{ fontSize: '0.72rem', color: '#64748b', direction: 'ltr', wordBreak: 'break-all' }}>{url}</span>
      </div>
    )
  }
  if (isLocalPlaceholder) {
    return (
      <span style={{ color: '#b45309', fontSize: '0.82rem' }}>
        فایل روی سرور ثبت نشده (نام محلی: {fileName || '—'})
      </span>
    )
  }
  return null
}

/**
 * @param {typeof import('react')} React
 * @param {Map<string, string>|null|undefined} fieldLabelMap
 * @param {(s: string) => string} labelState
 */
export function renderFriendlyContextValue(React, value, fieldLabelMap, labelState, depth = 0) {
  if (depth > MAX_DEPTH) return '…'
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'بله' : 'خیر'
  if (typeof value === 'number') return String(value)
  if (typeof value === 'string') {
    const asDisplay = formatContextStringForDisplay(value)
    if (asDisplay !== null) return asDisplay
    const fileFromString = renderIfProcessStepFileUpload(React, value)
    if (fileFromString !== null) return fileFromString
    return value
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return '—'
    const allPrimitive = value.every(x => x === null || x === undefined
      || typeof x === 'string' || typeof x === 'number' || typeof x === 'boolean')
    if (allPrimitive) {
      return value.map(x => (x === null || x === undefined ? '—' : String(x))).join('، ')
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
        {value.map((item, i) => (
          <div
            key={i}
            style={{
              padding: '0.45rem 0.55rem',
              background: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              fontSize: '0.8rem',
            }}
          >
            {renderFriendlyContextValue(React, item, fieldLabelMap, labelState, depth + 1)}
          </div>
        ))}
      </div>
    )
  }
  if (typeof value === 'object') {
    const filePreview = renderIfProcessStepFileUpload(React, value)
    if (filePreview !== null) return filePreview
    const entries = Object.entries(value)
    if (entries.length === 0) return '—'
    return (
      <div style={{ paddingRight: depth ? '0.35rem' : 0 }}>
        {entries.map(([k, v]) => {
          const subLabel = resolveContextRowLabel(k, fieldLabelMap) || k
          return (
            <div
              key={k}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(88px, 32%) 1fr',
                gap: '0.4rem',
                fontSize: depth ? '0.78rem' : '0.82rem',
                marginBottom: '0.35rem',
                alignItems: 'start',
              }}
            >
              <span style={{ color: '#6b7280', fontWeight: 600 }}>{subLabel}</span>
              <span style={{ color: '#111827', lineHeight: 1.5 }}>
                {renderFriendlyContextValue(React, v, fieldLabelMap, labelState, depth + 1)}
              </span>
            </div>
          )
        })}
      </div>
    )
  }
  return String(value)
}
