/**
 * مرحلهٔ یکپارچهٔ «مصاحبه‌ها» در آماده‌سازی ترم (ادغام گام‌های ۷ و ۸).
 * توابع خالص برای اعتبارسنجی و پیش‌نمایش نوبت‌ها — هم‌تراز با
 * app/services/semester_prep_interview_setup_service.py
 *
 * هر مصاحبه‌گر می‌تواند روزها و بازهٔ ساعت مستقل داشته باشد.
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

export function emptyInterviewerSchedule(interviewerId = '') {
  return {
    interviewerId: interviewerId || '',
    dates: [],
    startTime: '09:00',
    endTime: '13:00',
  }
}

export function emptyInterviewGroup() {
  return {
    interviewers: [],
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

/** تعداد نوبت‌های یک برنامهٔ مصاحبه‌گر: روزها × نوبت در هر روز */
export function countScheduleSessions(schedule, sessionMinutes) {
  const start = timeToMinutes(schedule?.startTime)
  const end = timeToMinutes(schedule?.endTime)
  const minutes = Number(sessionMinutes)
  if (start == null || end == null || !minutes || end <= start) return 0
  const perDay = Math.floor((end - start) / minutes)
  const days = (schedule?.dates || []).length
  return perDay * days
}

/** تعداد نوبت‌های یک دوره: جمع برنامه‌های مصاحبه‌گرها */
export function countGroupSessions(group) {
  const minutes = group?.sessionMinutes
  return (group?.interviewers || []).reduce(
    (total, schedule) => total + countScheduleSessions(schedule, minutes),
    0,
  )
}

export function countSetupSessions(setup) {
  return INTERVIEW_COURSE_TYPES.reduce(
    (total, key) => total + countGroupSessions(setup?.[key]),
    0,
  )
}

export function interviewerScheduleErrors(schedule, labelFa, who, sessionMinutes) {
  const errors = []
  if (!String(schedule?.interviewerId || '').trim()) {
    errors.push(`برای ${labelFa} شناسهٔ ${who} معتبر نیست.`)
    return errors
  }
  if (!(schedule?.dates || []).length) {
    errors.push(`برای ${labelFa} (${who}) حداقل یک روز مصاحبه انتخاب کنید.`)
  }
  const start = timeToMinutes(schedule?.startTime)
  const end = timeToMinutes(schedule?.endTime)
  if (start == null || end == null) {
    errors.push(`ساعت شروع و پایان مصاحبه ${labelFa} (${who}) را وارد کنید.`)
  } else if (end <= start) {
    errors.push(`ساعت پایان مصاحبه ${labelFa} (${who}) باید بعد از ساعت شروع باشد.`)
  }
  const minutes = Number(sessionMinutes)
  if (minutes && start != null && end != null && end > start && end - start < minutes) {
    errors.push(`بازهٔ ساعت مصاحبه ${labelFa} (${who}) کوتاه‌تر از مدت یک نوبت است.`)
  }
  return errors
}

export function interviewGroupErrors(group, labelFa) {
  const errors = []
  const schedules = group?.interviewers || []
  if (!schedules.length) {
    errors.push(`برای ${labelFa} حداقل یک مصاحبه‌گر انتخاب کنید.`)
  }
  const minutes = Number(group?.sessionMinutes)
  if (!minutes || minutes < MIN_SESSION_MINUTES || minutes > MAX_SESSION_MINUTES) {
    errors.push(
      `مدت هر نوبت مصاحبه ${labelFa} باید بین ${MIN_SESSION_MINUTES} تا ${MAX_SESSION_MINUTES} دقیقه باشد.`,
    )
  }
  schedules.forEach((schedule, index) => {
    errors.push(
      ...interviewerScheduleErrors(
        schedule,
        labelFa,
        `مصاحبه‌گر ${index + 1}`,
        minutes,
      ),
    )
  })
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

function scheduleToBody(schedule) {
  return {
    interviewer_id: schedule?.interviewerId || '',
    dates: [...(schedule?.dates || [])],
    start_time: schedule?.startTime || '',
    end_time: schedule?.endTime || '',
  }
}

function groupToBody(group) {
  return {
    interviewers: (group?.interviewers || []).map(scheduleToBody),
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

function scheduleFromSaved(saved) {
  const base = emptyInterviewerSchedule()
  if (!saved || typeof saved !== 'object') return base
  const id = saved.interviewer_id || saved.interviewerId || ''
  return {
    interviewerId: id ? String(id) : '',
    dates: Array.isArray(saved.dates) ? saved.dates.map(String) : base.dates,
    startTime: saved.start_time || saved.startTime || base.startTime,
    endTime: saved.end_time || saved.endTime || base.endTime,
  }
}

function groupFromSavedPlan(saved) {
  const base = emptyInterviewGroup()
  if (!saved || typeof saved !== 'object') return base
  const sessionMinutes = Number(saved.session_minutes) || base.sessionMinutes

  if (Array.isArray(saved.interviewers) && saved.interviewers.length) {
    const seen = new Set()
    const interviewers = []
    for (const item of saved.interviewers) {
      const schedule = scheduleFromSaved(item)
      if (!schedule.interviewerId || seen.has(schedule.interviewerId)) continue
      seen.add(schedule.interviewerId)
      interviewers.push(schedule)
    }
    return { interviewers, sessionMinutes }
  }

  // فرمت قدیمی: روز/ساعت مشترک برای همهٔ مصاحبه‌گرها
  const ids = Array.isArray(saved.interviewer_ids)
    ? saved.interviewer_ids.map(String)
    : []
  const dates = Array.isArray(saved.dates) ? saved.dates.map(String) : []
  const startTime = saved.start_time || base.interviewers[0]?.startTime || '09:00'
  const endTime = saved.end_time || '13:00'
  return {
    interviewers: ids.map((id) => ({
      interviewerId: id,
      dates: [...dates],
      startTime,
      endTime,
    })),
    sessionMinutes,
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
    if (setup[key].interviewers.length) continue
    const legacy = ctx[`${key}_interviewers`]
    if (Array.isArray(legacy)) {
      setup[key].interviewers = legacy
        .map(String)
        .filter((v) => /^[0-9a-f-]{36}$/i.test(v))
        .map((id) => emptyInterviewerSchedule(id))
    }
  }
  return setup
}

/** افزودن/حذف مصاحبه‌گر با برنامهٔ اختصاصی */
export function toggleInterviewerInGroup(group, interviewerId) {
  const id = String(interviewerId || '')
  if (!id) return group
  const existing = group?.interviewers || []
  const has = existing.some((s) => s.interviewerId === id)
  return {
    ...group,
    interviewers: has
      ? existing.filter((s) => s.interviewerId !== id)
      : [...existing, emptyInterviewerSchedule(id)],
  }
}

export function patchInterviewerSchedule(group, interviewerId, patch) {
  const id = String(interviewerId || '')
  return {
    ...group,
    interviewers: (group?.interviewers || []).map((s) =>
      s.interviewerId === id ? { ...s, ...patch } : s,
    ),
  }
}

/** خلاصهٔ خوانا برای نمایش زیر هر دوره */
export function describeGroupPlan(group) {
  const total = countGroupSessions(group)
  if (!total) return ''
  const interviewers = (group?.interviewers || []).length
  return `${total} نوبت — ${interviewers} مصاحبه‌گر با برنامهٔ جداگانه × ${group.sessionMinutes} دقیقه`
}

export function describeSchedulePlan(schedule, sessionMinutes, nameFa) {
  const total = countScheduleSessions(schedule, sessionMinutes)
  if (!total) return ''
  const days = (schedule?.dates || []).length
  const label = nameFa || 'مصاحبه‌گر'
  return `${label}: ${total} نوبت — ${days} روز`
}
