/**
 * مرحلهٔ یکپارچهٔ «مصاحبه‌ها» در آماده‌سازی ترم (ادغام گام‌های ۷ و ۸).
 * توابع خالص برای اعتبارسنجی و پیش‌نمایش نوبت‌ها — هم‌تراز با
 * app/services/semester_prep_interview_setup_service.py
 */

export const INTERVIEW_COURSE_TYPES = ['comprehensive', 'introductory']

export const INTERVIEW_COURSE_LABELS_FA = {
  comprehensive: 'دوره جامع',
  introductory: 'دوره آشنایی',
}

export const MIN_SESSION_MINUTES = 10
export const MAX_SESSION_MINUTES = 240
export const DEFAULT_SESSION_MINUTES = 45
export const MAX_GENERATED_SLOTS = 400

export const SESSION_MINUTE_OPTIONS = [20, 30, 45, 60, 90]

export function emptyInterviewGroup() {
  return {
    interviewerIds: [],
    dates: [],
    startTime: '09:00',
    endTime: '13:00',
    sessionMinutes: DEFAULT_SESSION_MINUTES,
  }
}

export function emptyInterviewSetup() {
  return {
    interviewMode: '',
    interviewLocationFa: '',
    comprehensive: emptyInterviewGroup(),
    introductory: emptyInterviewGroup(),
  }
}

/** «09:30» → دقیقه از نیمه‌شب؛ نامعتبر → null */
export function timeToMinutes(raw) {
  const s = String(raw || '').trim()
  const m = /^(\d{1,2}):(\d{2})$/.exec(s)
  if (!m) return null
  const hour = Number(m[1])
  const minute = Number(m[2])
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null
  return hour * 60 + minute
}

/** تعداد نوبت‌های یک دوره: روزها × مصاحبه‌گرها × نوبت در هر روز */
export function countGroupSessions(group) {
  const start = timeToMinutes(group?.startTime)
  const end = timeToMinutes(group?.endTime)
  const minutes = Number(group?.sessionMinutes)
  if (start == null || end == null || !minutes || end <= start) return 0
  const perDay = Math.floor((end - start) / minutes)
  const days = (group?.dates || []).length
  const interviewers = (group?.interviewerIds || []).length
  return perDay * days * interviewers
}

export function countSetupSessions(setup) {
  return INTERVIEW_COURSE_TYPES.reduce(
    (total, key) => total + countGroupSessions(setup?.[key]),
    0,
  )
}

export function interviewGroupErrors(group, labelFa) {
  const errors = []
  if (!(group?.interviewerIds || []).length) {
    errors.push(`برای ${labelFa} حداقل یک مصاحبه‌گر انتخاب کنید.`)
  }
  if (!(group?.dates || []).length) {
    errors.push(`برای ${labelFa} حداقل یک روز مصاحبه انتخاب کنید.`)
  }
  const start = timeToMinutes(group?.startTime)
  const end = timeToMinutes(group?.endTime)
  if (start == null || end == null) {
    errors.push(`ساعت شروع و پایان مصاحبه ${labelFa} را وارد کنید.`)
  } else if (end <= start) {
    errors.push(`ساعت پایان مصاحبه ${labelFa} باید بعد از ساعت شروع باشد.`)
  }
  const minutes = Number(group?.sessionMinutes)
  if (!minutes || minutes < MIN_SESSION_MINUTES || minutes > MAX_SESSION_MINUTES) {
    errors.push(
      `مدت هر نوبت مصاحبه ${labelFa} باید بین ${MIN_SESSION_MINUTES} تا ${MAX_SESSION_MINUTES} دقیقه باشد.`,
    )
  } else if (start != null && end != null && end > start && end - start < minutes) {
    errors.push(`بازهٔ ساعت مصاحبه ${labelFa} کوتاه‌تر از مدت یک نوبت است.`)
  }
  return errors
}

export function interviewSetupErrors(setup) {
  const errors = []
  const mode = String(setup?.interviewMode || '').trim()
  if (mode !== 'حضوری' && mode !== 'آنلاین') {
    errors.push('نوع برگزاری مصاحبه را مشخص کنید (حضوری یا آنلاین).')
  } else if (mode === 'حضوری' && !String(setup?.interviewLocationFa || '').trim()) {
    errors.push('برای مصاحبهٔ حضوری، آدرس یا محل برگزاری را وارد کنید.')
  }
  for (const key of INTERVIEW_COURSE_TYPES) {
    errors.push(...interviewGroupErrors(setup?.[key], INTERVIEW_COURSE_LABELS_FA[key]))
  }
  if (!errors.length) {
    const total = countSetupSessions(setup)
    if (total === 0) {
      errors.push('با تنظیمات فعلی هیچ نوبت مصاحبه‌ای ساخته نمی‌شود.')
    } else if (total > MAX_GENERATED_SLOTS) {
      errors.push(
        `تعداد نوبت‌ها (${total}) از سقف ${MAX_GENERATED_SLOTS} بیشتر است؛ روزها یا مصاحبه‌گرهای کمتری انتخاب کنید.`,
      )
    }
  }
  return errors
}

function groupToBody(group) {
  return {
    interviewer_ids: [...(group?.interviewerIds || [])],
    dates: [...(group?.dates || [])],
    start_time: group?.startTime || '',
    end_time: group?.endTime || '',
    session_minutes: Number(group?.sessionMinutes) || DEFAULT_SESSION_MINUTES,
  }
}

export function buildInterviewSetupBody(setup, instanceId) {
  return {
    instance_id: instanceId,
    interview_mode: String(setup?.interviewMode || '').trim(),
    interview_location_fa: String(setup?.interviewLocationFa || '').trim(),
    comprehensive: groupToBody(setup?.comprehensive),
    introductory: groupToBody(setup?.introductory),
  }
}

function groupFromSavedPlan(saved) {
  const base = emptyInterviewGroup()
  if (!saved || typeof saved !== 'object') return base
  return {
    interviewerIds: Array.isArray(saved.interviewer_ids)
      ? saved.interviewer_ids.map(String)
      : base.interviewerIds,
    dates: Array.isArray(saved.dates) ? saved.dates.map(String) : base.dates,
    startTime: saved.start_time || base.startTime,
    endTime: saved.end_time || base.endTime,
    sessionMinutes: Number(saved.session_minutes) || base.sessionMinutes,
  }
}

/** بازیابی طرح ذخیره‌شده از context برای ویرایش مجدد مرحله */
export function interviewSetupFromContext(contextData) {
  const ctx = contextData && typeof contextData === 'object' ? contextData : {}
  const plan = ctx.interview_setup_plan && typeof ctx.interview_setup_plan === 'object'
    ? ctx.interview_setup_plan
    : {}
  const setup = {
    interviewMode: String(ctx.interview_mode || '').trim(),
    interviewLocationFa: String(ctx.interview_location_fa || '').trim(),
    comprehensive: groupFromSavedPlan(plan.comprehensive),
    introductory: groupFromSavedPlan(plan.introductory),
  }
  for (const key of INTERVIEW_COURSE_TYPES) {
    if (setup[key].interviewerIds.length) continue
    const legacy = ctx[`${key}_interviewers`]
    if (Array.isArray(legacy)) {
      setup[key].interviewerIds = legacy
        .map(String)
        .filter((v) => /^[0-9a-f-]{36}$/i.test(v))
    }
  }
  return setup
}

/** خلاصهٔ خوانا برای نمایش زیر هر دوره */
export function describeGroupPlan(group) {
  const total = countGroupSessions(group)
  if (!total) return ''
  const days = (group?.dates || []).length
  const interviewers = (group?.interviewerIds || []).length
  return `${total} نوبت — ${days} روز × ${interviewers} مصاحبه‌گر × ${group.sessionMinutes} دقیقه`
}
