/** فیلدهای تکمیلی ثبت‌نام — هم‌خوان با app/services/student_registration_profile.py */

export const REGISTRATION_FIELD_LABELS = {
  first_name_fa: 'نام',
  last_name_fa: 'نام خانوادگی',
  age: 'سن',
  birth_certificate_number: 'شماره شناسنامه',
  birth_date: 'تاریخ تولد',
  residence_city: 'شهر محل سکونت',
  home_address: 'آدرس منزل',
  work_address: 'آدرس محل کار',
  home_phone: 'تلفن منزل',
  work_phone: 'تلفن محل کار',
  had_psychotherapy: 'تجربه درمان روان‌شناختی',
  used_psychiatric_meds: 'استفاده از داروهای اعصاب و روان',
  psychiatric_hospitalization_history: 'سابقه بستری روانپزشکی',
  has_work_permit: 'پروانه اشتغال به کار',
  has_university_degree: 'مدرک دانشگاهی',
  course_participation_mode: 'نحوه شرکت در دوره',
  referral_source: 'نحوه آشنایی با انستیتو',
  referral_inviter_name: 'نام شخص معرف',
  national_code: 'کد ملی',
  email: 'ایمیل',
  full_name_fa: 'نام و نام خانوادگی',
  phone: 'شماره تماس',
}

const YES_NO_LABELS = { yes: 'بله', no: 'خیر' }
const PARTICIPATION_LABELS = { in_person: 'حضوری', online: 'آنلاین' }
const REFERRAL_LABELS = {
  person_referral: 'معرفی شخص',
  website: 'وب‌سایت',
  social_media: 'شبکه‌های اجتماعی',
  search: 'جستجو در اینترنت',
  other: 'سایر',
}

export function emptyExtendedRegistrationFields() {
  return {
    first_name_fa: '',
    last_name_fa: '',
    age: '',
    birth_certificate_number: '',
    birth_date: '',
    residence_city: '',
    home_address: '',
    work_address: '',
    home_phone: '',
    work_phone: '',
    had_psychotherapy: '',
    used_psychiatric_meds: '',
    psychiatric_hospitalization_history: '',
    has_work_permit: '',
    has_university_degree: '',
    course_participation_mode: '',
    referral_source: '',
    referral_inviter_name: '',
  }
}

export function extendedFieldsFromExtra(data) {
  const base = emptyExtendedRegistrationFields()
  if (!data) return base
  const out = { ...base }
  for (const key of Object.keys(base)) {
    if (data[key] != null && data[key] !== '') {
      out[key] = String(data[key])
    }
  }
  return out
}

function digitsOnlyPhone(raw) {
  const d = String(raw || '').replace(/\D/g, '')
  if (!d) return ''
  return d.startsWith('0') ? d : `0${d}`
}

function isLandlineValid(raw) {
  const d = digitsOnlyPhone(raw)
  return /^0\d{10,11}$/.test(d)
}

function isBirthDateValid(raw) {
  return /^\d{4}\/\d{2}\/\d{2}$/.test(String(raw || '').trim())
}

/** @returns {string[]} */
export function validateExtendedRegistrationClient(form) {
  const errors = []
  if (!(form.first_name_fa || '').trim()) errors.push('نام را وارد کنید.')
  if (!(form.last_name_fa || '').trim()) errors.push('نام خانوادگی را وارد کنید.')

  const age = parseInt(String(form.age || '').replace(/\D/g, ''), 10)
  if (!Number.isFinite(age) || age < 6 || age > 120) {
    errors.push('لطفاً یک عدد مابین ۶ تا ۱۲۰ وارد کنید.')
  }
  if (!(form.birth_certificate_number || '').trim()) errors.push('شماره شناسنامه را وارد کنید.')
  if (!isBirthDateValid(form.birth_date)) {
    errors.push('تاریخ تولد را به فرمت شمسی وارد کنید (مثال: ۱۳۷۰/۰۱/۱۵).')
  }
  if (!(form.residence_city || '').trim()) errors.push('شهر محل سکونت را وارد کنید.')
  if (!(form.home_address || '').trim()) errors.push('آدرس منزل را وارد کنید.')
  if (!(form.work_address || '').trim()) errors.push('آدرس محل کار را وارد کنید.')
  if (!isLandlineValid(form.home_phone)) errors.push('تلفن منزل را با پیش‌شمارهٔ شهر وارد کنید.')
  if (!isLandlineValid(form.work_phone)) errors.push('تلفن محل کار را با پیش‌شمارهٔ شهر وارد کنید.')

  for (const key of [
    'had_psychotherapy',
    'used_psychiatric_meds',
    'psychiatric_hospitalization_history',
    'has_work_permit',
    'has_university_degree',
  ]) {
    if (form[key] !== 'yes' && form[key] !== 'no') {
      errors.push(`${REGISTRATION_FIELD_LABELS[key]} را انتخاب کنید.`)
      break
    }
  }
  if (form.course_participation_mode !== 'in_person' && form.course_participation_mode !== 'online') {
    errors.push('نحوه شرکت در دوره را انتخاب کنید.')
  }
  if (!form.referral_source) {
    errors.push('نحوه آشنایی با انستیتو را انتخاب کنید.')
  }
  if (form.referral_source === 'person_referral' && !(form.referral_inviter_name || '').trim()) {
    errors.push('نام شخص معرف را وارد کنید.')
  }
  return errors
}

export function buildRegistrationProfilePayload(form) {
  const age = parseInt(String(form.age || '').replace(/\D/g, ''), 10)
  const payload = {
    first_name_fa: (form.first_name_fa || '').trim(),
    last_name_fa: (form.last_name_fa || '').trim(),
    age: Number.isFinite(age) ? age : undefined,
    birth_certificate_number: (form.birth_certificate_number || '').trim(),
    birth_date: (form.birth_date || '').trim(),
    residence_city: (form.residence_city || '').trim(),
    home_address: (form.home_address || '').trim(),
    work_address: (form.work_address || '').trim(),
    home_phone: digitsOnlyPhone(form.home_phone),
    work_phone: digitsOnlyPhone(form.work_phone),
    had_psychotherapy: form.had_psychotherapy || undefined,
    used_psychiatric_meds: form.used_psychiatric_meds || undefined,
    psychiatric_hospitalization_history: form.psychiatric_hospitalization_history || undefined,
    has_work_permit: form.has_work_permit || undefined,
    has_university_degree: form.has_university_degree || undefined,
    course_participation_mode: form.course_participation_mode || undefined,
    referral_source: form.referral_source || undefined,
  }
  const inviter = (form.referral_inviter_name || '').trim()
  if (inviter) payload.referral_inviter_name = inviter
  return payload
}

export function formatRegistrationProfileValue(key, value) {
  if (value == null || value === '') return '—'
  if (key in YES_NO_LABELS) return YES_NO_LABELS[value] || value
  if (key === 'course_participation_mode') return PARTICIPATION_LABELS[value] || value
  if (key === 'referral_source') return REFERRAL_LABELS[value] || value
  return String(value)
}

/** ترتیب نمایش در پروفایل دانشجو */
export const REGISTRATION_PROFILE_DISPLAY_ORDER = [
  'first_name_fa',
  'last_name_fa',
  'age',
  'birth_certificate_number',
  'birth_date',
  'residence_city',
  'home_address',
  'work_address',
  'home_phone',
  'work_phone',
  'had_psychotherapy',
  'used_psychiatric_meds',
  'psychiatric_hospitalization_history',
  'has_work_permit',
  'has_university_degree',
  'course_participation_mode',
  'referral_source',
  'referral_inviter_name',
]
