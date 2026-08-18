import axios from 'axios'
import { getRouterBasename } from '../utils/routerBasename'
import { emitSimulatedSmsFromApi } from '../utils/simulatedSmsBridge'
import { dispatchPanelNotificationsChanged } from '../utils/panelNotifications'

// API base. Override با VITE_API_BASE در .env در صورت نیاز.
export function getApiBase() {
  // روی localhost همیشه نسبی /api/ تا در dev پروکسی Vite به uvicorn (مثلاً 3000) برود؛
  // روی همان 3000 با Docker هم /api/ همان سرور FastAPI است (بدون حلقهٔ پروکسی به خود Vite).
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (host === 'localhost' || host === '127.0.0.1') {
      if (import.meta.env.VITE_API_BASE) {
        return import.meta.env.VITE_API_BASE.replace(/\/?$/, '/')
      }
      return '/api/'
    }
  }
  if (import.meta.env.VITE_API_BASE) return import.meta.env.VITE_API_BASE.replace(/\/?$/, '/')
  if (typeof window === 'undefined') {
    const base = (import.meta.env.BASE_URL || '/anistito/').replace(/\/$/, '') || ''
    return (base ? base + '/' : '/') + 'api/'
  }
  const base = (import.meta.env.BASE_URL || '/anistito/').replace(/\/$/, '') || ''
  return (base ? base + '/' : '/') + 'api/'
}

const api = axios.create({
  baseURL: '/api/', // مقدار پیش‌فرض؛ در اینترسپتور زیر همیشه با origin فعلی به‌روز می‌شود
  headers: { 'Content-Type': 'application/json' },
  // شبکه کند یا پاسخ ندادن: حداکثر ~۱ دقیقه؛ عملیات طولانی (مثلاً seed دمو) در همان endpoint timeout جدا دارد
  timeout: 60000,
})

// Add auth token + همیشه baseURL را از آدرس فعلی صفحه بگیر
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const base = getApiBase()
    config.baseURL = base
    if (import.meta.env.DEV && !window.__anistito_api_base_logged) {
      window.__anistito_api_base_logged = true
      console.log('[anistito] API baseURL:', base, '| صفحه:', window.location.href)
    }
  }
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401: ریدایرکت فقط برای درخواست‌های احراز‌شده. درخواست‌های صفحهٔ لاگین هرگز ریدایرکت نکن تا خطا همان‌جا بماند.
// اگر config نبود (خطای شبکه و...) ریدایرکت نکن تا خطا در همان صفحه نمایش داده شود.
api.interceptors.response.use(
  (response) => {
    try {
      emitSimulatedSmsFromApi(response?.data)
    } catch (_) {
      /* ignore */
    }
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      const config = error.config
      const pathname = typeof window !== 'undefined' ? window.location.pathname : ''
      const isLoginPage = pathname.includes('/login')
      const isAuthMe = config?.url && /auth\/me$/i.test(String(config.url).replace(/^\//, ''))
      const origin = typeof window !== 'undefined' ? window.location.origin : ''
      const isDevFrontend =
        origin === 'http://localhost:3000' ||
        origin === 'http://127.0.0.1:3000' ||
        origin === 'http://localhost:5173' ||
        origin === 'http://127.0.0.1:5173'
      const skipRedirect =
        !config ||
        config._skipAuthRedirect === true ||
        isLoginPage ||
        isAuthMe ||
        isDevFrontend ||
        /login-json|login-challenge|otp\/(request|verify)/i.test((config.baseURL || '') + (config.url || '')) ||
        /login-json|login-challenge|otp\/request|otp\/verify/.test(config.url || '')
      if (!skipRedirect) {
        localStorage.removeItem('token')
        const rb = getRouterBasename()
        window.location.href = (rb ? `${rb}/` : '/') + 'login'
      }
    }
    return Promise.reject(error)
  }
)

// مسیر پایه اپ (بدون /api) برای endpointهای غیر-API مثل debug
export function getAppBasePath() {
  const rb = getRouterBasename()
  return rb ? `${rb}/` : '/'
}

// ─── Auth ──────────────────────────────────────────────────────
// درخواست‌های لاگین با _skipAuthRedirect تا در صورت 401 ریدایرکت نشود و خطا همان‌جا نمایش داده شود
/** Base URL for uploads (avatars). Same origin as API but without /api path. */
export function getUploadsBase() {
  const base = getApiBase()
  return base.replace(/\/api\/?$/, '') || (typeof window !== 'undefined' ? window.location.origin + '/' : '')
}

/** Full URL for avatar path (e.g. /uploads/avatars/xxx.jpg). */
export function getAvatarUrl(avatarPath) {
  if (!avatarPath) return null
  if (avatarPath.startsWith('http')) return avatarPath
  const origin = getUploadsBase().replace(/\/$/, '')
  return `${origin}${avatarPath.startsWith('/') ? '' : '/'}${avatarPath}`
}

export const authApi = {
  login: (username, password, challengeId, challengeAnswer) =>
    api.post('auth/login-json', {
      username,
      password,
      challenge_id: challengeId,
      challenge_answer: challengeAnswer,
    }, { _skipAuthRedirect: true }),
  me: () => api.get('auth/me'),
  updateMe: (data) => api.patch('auth/me', data),
  uploadAvatar: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('auth/me/avatar', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  register: (data) => api.post('auth/register', data),
  otpRequest: (phone) => api.post('auth/otp/request', { phone }, { _skipAuthRedirect: true }),
  otpVerify: (phone, code) => api.post('auth/otp/verify', { phone, code }, { _skipAuthRedirect: true }),
  getLoginChallenge: () => api.post('auth/login-challenge', {}, { _skipAuthRedirect: true }),
  home: () => api.get('auth/home'),
}

// ─── Processes ─────────────────────────────────────────────────
// Backend routes have NO trailing slash - avoid 307 redirect (causes Mixed Content)
export const processApi = {
  list: (params) => api.get('admin/processes', { params }),
  get: (id) => api.get(`admin/processes/${id}`),
  create: (data) => api.post('admin/processes', data),
  update: (id, data) => api.patch(`admin/processes/${id}`, data),
  delete: (id) => api.delete(`admin/processes/${id}`),
  /** بارگذاری تصویر فلوچارت (PNG/JPEG/GIF/WebP، حداکثر ~۵ مگابایت) */
  uploadFlowchart: (processId, file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`admin/processes/${processId}/flowchart`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteFlowchart: (processId) => api.delete(`admin/processes/${processId}/flowchart`),
  /**
   * بارگذاری/به‌روزرسانی سند SOP بر اساس عنوان (تکراری = فقط متن و تصویر).
   * FormData: name_fa (الزامی)، اختیاری: source_text، code، initial_state_code، name_en، description، sop_order، file
   */
  sopDocUpsert: (formData) =>
    api.post('admin/processes/sop-doc-upsert', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  // States
  getStates: (processId) => api.get(`admin/processes/${processId}/states`),
  createState: (processId, data) => api.post(`admin/processes/${processId}/states`, data),
  updateState: (stateId, data) => api.patch(`admin/states/${stateId}`, data),
  deleteState: (stateId) => api.delete(`admin/states/${stateId}`),
  // Transitions
  getTransitions: (processId) => api.get(`admin/processes/${processId}/transitions`),
  createTransition: (processId, data) => api.post(`admin/processes/${processId}/transitions`, data),
  updateTransition: (transitionId, data) => api.patch(`admin/transitions/${transitionId}`, data),
  deleteTransition: (transitionId) => api.delete(`admin/transitions/${transitionId}`),
}

// ─── Rules ─────────────────────────────────────────────────────
export const ruleApi = {
  list: (params) => api.get('admin/rules', { params }),
  get: (id) => api.get(`admin/rules/${id}`),
  create: (data) => api.post('admin/rules', data),
  update: (id, data) => api.patch(`admin/rules/${id}`, data),
  delete: (id) => api.delete(`admin/rules/${id}`),
}

// ─── Audit ─────────────────────────────────────────────────────
export const auditApi = {
  list: (params) => api.get('admin/audit-logs', { params }),
}

// ─── System (admin) ────────────────────────────────────────────
export const systemApi = {
  /** اسنپ‌شات منابع کانتینر/میزبان (RAM, CPU load, RSS, disk) — فقط ادمین. */
  resourceSnapshot: () => api.get('admin/system/resource-snapshot'),
  /** فهرست بکاپ‌های روزانه روی هاست — فقط ادمین. */
  listBackups: () => api.get('admin/system/backups'),
  /** جزئیات / verify یک بکاپ تاریخ‌دار (YYYY-MM-DD). */
  getBackup: (date, { verify = false } = {}) =>
    api.get(`admin/system/backups/${encodeURIComponent(date)}`, {
      params: verify ? { verify: true } : undefined,
    }),
  /** URL دانلود db یا uploads (نیاز به توکن در هدر — از downloadBackup استفاده کنید). */
  backupDownloadPath: (date, kind) =>
    `admin/system/backups/${encodeURIComponent(date)}/download/${encodeURIComponent(kind)}`,
  downloadBackup: (date, kind) =>
    api.get(`admin/system/backups/${encodeURIComponent(date)}/download/${encodeURIComponent(kind)}`, {
      responseType: 'blob',
    }),
}

/** تقویم آموزشی و اتوماسیون زمان‌محور */
export const schedulerApi = {
  getActiveCalendar: () => api.get('admin/academic-calendar/active'),
  saveActiveCalendar: (data) => api.put('admin/academic-calendar/active', data),
  getAutomationIndex: () => api.get('admin/scheduler/automation-index'),
  runPass: () => api.post('admin/scheduler/run-pass', {}, { timeout: 120000 }),
  getDailyOverdueRuns: (limit = 30) => api.get('admin/scheduler/daily-overdue-runs', { params: { limit } }),
  runDailyOverdue: () => api.post('admin/scheduler/run-daily-overdue', {}, { timeout: 120000 }),
}

export const semesterPrepApi = {
  getStatus: () => api.get('admin/semester-prep/status'),
  getReadiness: () => api.get('admin/semester-prep/readiness'),
  getActivityLicense: () => api.get('admin/semester-prep/activity-license'),
  patchActivityLicense: (body) => api.patch('admin/semester-prep/activity-license', body),
  start: (processCode) => api.post('admin/semester-prep/start', { process_code: processCode }),
  getSlaWarnings: () => api.get('admin/semester-prep/sla-warnings'),
  /** استخر مصاحبه‌کنندگان پیش‌آماده‌سازی برای مرحلهٔ مصاحبه‌ها */
  getInterviewCandidates: () =>
    api.get('admin/semester-prep/interview-candidates', {
      params: { _ts: Date.now() },
      headers: { 'Cache-Control': 'no-store', Pragma: 'no-cache' },
    }),
  /** مرحلهٔ یکپارچهٔ مصاحبه‌ها: مصاحبه‌گرها + روز و ساعت در یک ثبت */
  saveInterviewSetup: (body) => api.post('admin/semester-prep/interview-setup', body),
}

export const interviewerApi = {
  list: (params) =>
    api.get('admin/interviewers', {
      params: { ...params, _ts: Date.now() },
      headers: { 'Cache-Control': 'no-store', Pragma: 'no-cache' },
    }),
  create: (body) => api.post('admin/interviewers', body),
  update: (id, body) => api.patch(`admin/interviewers/${id}`, body),
  remove: (id) => api.delete(`admin/interviewers/${id}`),
}

// ─── Dashboard ─────────────────────────────────────────────────
export const dashboardApi = {
  stats: () => api.get('admin/dashboard/stats'),
  syncMetadata: () => api.post('admin/sync-metadata'),
  /** همان seed_demo_process_matrix — روی دیتابیس همین API (برای Docker/Postgres)؛ ممکن است چند دقیقه طول بکشد */
  seedDemoMatrix: (body) =>
    api.post('admin/seed-demo-matrix', body || {}, { timeout: 600000 }),
  // endpoint دیباگ بدون نیاز به توکن (همان الگوی لاگین - بدون auth)
  debugProcessCount: () =>
    fetch(`${window.location.origin}${getAppBasePath()}debug/process-count`).then((r) =>
      r.ok ? r.json() : Promise.reject(new Error('debug failed'))
    ),
}

// ─── Students ──────────────────────────────────────────────────
export const studentApi = {
  /** @param {{ tracker_summary?: boolean }} [params] */
  list: (params) => api.get('students', { params }),
  me: () => api.get('students/me'),
  myFinance: () => api.get('students/me/finance'),
  actionInbox: () => api.get('students/me/action-inbox'),
  ensureConditionalTherapyStart: () => api.post('students/me/conditional-therapy/ensure-start'),
  get: (id) => api.get(`students/${id}`),
  create: (data) => api.post('students', data),
  update: (id, data) => api.patch(`students/${id}`, data),
  /** پس از ورود با OTP؛ شماره از حساب کاربری است */
  completeRegistration: (data) => api.post('students/complete-registration', data),
  /** فهرست درمانگران آموزشی برای انتخاب (نام نمایشی + شناسه) */
  therapists: () => api.get('students/therapists'),
  /** شیت وقت‌های آزاد درمانگران — گروه‌بندی‌شده */
  therapistSlotsAvailable: (courseType) =>
    api.get('educational-therapist-slots/available', {
      params: courseType ? { course_type: courseType } : {},
    }),
  getRegistrationProfileByUser: (userId) => api.get(`students/by-user/${userId}/registration-profile`),
  updateRegistrationProfileByUser: (userId, data) =>
    api.patch(`students/by-user/${userId}/registration-profile`, data),
  /** ادمین/پذیرش: تغییر نوع دورهٔ فرم اولیهٔ ثبت‌نام */
  updateRegistrationCourseType: (studentId, data) =>
    api.patch(`students/${studentId}/registration-course-type`, data),
  updateRegistrationCourseTypeByUser: (userId, data) =>
    api.patch(`students/by-user/${userId}/registration-course-type`, data),
  taPortfolio: () => api.get('students/me/ta-portfolio'),
  taPortfolioFor: (studentId) => api.get(`students/${studentId}/ta-portfolio`),
}

// ─── Process Execution ─────────────────────────────────────────
export const processExecApi = {
  definitions: () => api.get('process/definitions'),
  getDefinition: (code) => api.get(`process/definitions/${code}`),
  /** متادیتای فرم‌ها برای یک وضعیت (مثلاً documents_upload) — برای گالری مدارک در پروفایل */
  getProcessFormsForState: (processCode, state, instanceId) =>
    api.get(`process/definitions/${processCode}/forms`, {
      params: {
        ...(state ? { state } : {}),
        ...(instanceId ? { instance_id: instanceId } : {}),
      },
    }),
  start: (data) => api.post('process/start', data),
  trigger: async (instanceId, data) => {
    const res = await api.post(`process/${instanceId}/trigger`, data)
    if (res.data?.success) {
      dispatchPanelNotificationsChanged()
    }
    return res
  },
  /** بازگشت به مرحلهٔ قبل (فقط مدیر سامانه / معاون آموزش) */
  rollback: (instanceId, body) => api.post(`process/${instanceId}/rollback`, body || {}),
  restart: (instanceId, body) => api.post(`process/${instanceId}/restart`, body || {}),
  status: (instanceId) => api.get(`process/${instanceId}/status`),
  transitions: (instanceId) => api.get(`process/${instanceId}/transitions`),
  /** وضعیت + انتقال‌ها + فرم‌های مرحلهٔ فعلی (مثل بارگذاری داشبورد فرایند در UI) */
  dashboard: (instanceId) => api.get(`process/${instanceId}/dashboard`),
  studentInstances: (studentId, params) =>
    api.get(`process/instances/student/${studentId}`, { params }),
  /** کارنامه‌ها و گواهی‌های قابل نمایش در پورتال */
  studentArtifacts: (studentId) => api.get(`process/student/${studentId}/artifacts`),
  /** محتوای یک کارنامه/گواهی برای نمایش/دانلود */
  studentDocument: (studentId, docId) =>
    api.get(`process/student/${studentId}/documents/${docId}`),
  /** دانلود PDF کارنامه/گواهی/سند رسمی */
  async downloadStudentDocumentPdf(studentId, docId, fallbackFilename = 'document.pdf') {
    const res = await api.get(`process/student/${studentId}/documents/${docId}.pdf`, {
      responseType: 'blob',
    })
    const blob = res.data
    const cd = res.headers['content-disposition'] || res.headers['Content-Disposition']
    let filename = fallbackFilename
    if (cd && /filename/i.test(cd)) {
      const m = cd.match(/filename\*?=(?:UTF-8'')?["']?([^";\n]+)["']?/i)
      if (m) filename = decodeURIComponent(m[1].trim())
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  },
  /** دانشجو: ثبت فرم مرحله (قفل تا باز شدن توسط کارمند) */
  registerStudentStepForms: (instanceId, body) =>
    api.post(`process/${instanceId}/student-step-forms/register`, body),
  /** دانشجو: آپلود فایل مدرک (multipart؛ field_name در FormData) */
  uploadStudentStepFile: (instanceId, formData) =>
    api.post(`process/${instanceId}/student-step-forms/upload-file`, formData, {
      timeout: 120000,
      // بدون این، Content-Type پیش‌فرض application/json باعث می‌شود axios FormData را به JSON تبدیل کند و فایل به سرور نرسد.
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  /** کارمند/اداری: اجازهٔ ویرایش مجدد فرم مرحله برای دانشجو */
  unlockStudentStepFormsEdit: (instanceId, body) =>
    api.post(`process/${instanceId}/student-step-forms/unlock-edit`, body || {}),
  /** ادمین/پذیرش: تغییر مستقیم دروس انتخاب‌شده در پرونده */
  operatorUpdateSelectedCourses: (instanceId, body) =>
    api.post(`process/${instanceId}/operator-step-forms/update-selected-courses`, body),
  /** اپراتور: ثبت فرم مرحلهٔ فعلی فرایند (مثل آماده‌سازی ترم پاییز/زمستان) */
  registerOperatorStepForms: (instanceId, body) =>
    api.post(`process/${instanceId}/operator-step-forms/register`, body),
  /** خروجی PDF بستهٔ کمپین بازاریابی (فعالیت‌های ۱، ۲، ۵) برای انتقال به مدیر مارکتینگ */
  async downloadMarketingCampaignPack(instanceId) {
    const res = await api.get(`process/${instanceId}/marketing-campaign-pack.pdf`, {
      responseType: 'blob',
    })
    const blob = res.data
    const cd = res.headers['content-disposition'] || res.headers['Content-Disposition']
    let filename = 'marketing_campaign.pdf'
    if (cd && /filename=/i.test(cd)) {
      const m = cd.match(/filename\*?=(?:UTF-8'')?["']?([^";\n]+)["']?/i)
      if (m) filename = decodeURIComponent(m[1].trim())
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  },
  /** دانشجو: درخواست ویرایش مرحلهٔ ثبت‌شده (ایجاد تیکت) */
  createEditRequest: (instanceId, body) =>
    api.post(`process/${instanceId}/edit-requests`, body),
  requestStudentStepOtp: (instanceId) =>
    api.post(`process/${instanceId}/student-step-forms/step-otp/request`),
  verifyStudentStepOtp: (instanceId, body) =>
    api.post(`process/${instanceId}/student-step-forms/step-otp/verify`, body),
  /** لایهٔ عمومی: دادهٔ ثبت‌شدهٔ فرایند برای مشاهده/ویرایش بر اساس نقش */
  getProcessData: (instanceId) => api.get(`process/${instanceId}/data`),
  /** لایهٔ عمومی: به‌روزرسانی دادهٔ ثبت‌شده (فقط فیلدهای مجاز نقش) */
  updateProcessData: (instanceId, body) =>
    api.post(`process/${instanceId}/data/update`, body),
}

// ─── پرداخت (درگاه سپ / زبال و mock در بک‌اند) ───────────────
/** amount به ریال (شاپرک). */
export const paymentApi = {
  /** درخواست به زیبال روی سرور انجام می‌شود؛ timeout کوتاه‌تر از کلاینت عمومی */
  create: (body) =>
    api.post('payment/create', body, { timeout: 30000 }),
}

// ─── وقت مصاحبه (پذیرش / دانشجو) ───────────────────────────
export const interviewSlotsApi = {
  available: (courseType) =>
    api.get('interview-slots/available', {
      params: courseType ? { course_type: courseType } : {},
    }),
  book: (body) => api.post('interview-slots/book', body),
  myBookings: (includePast) =>
    api.get('interview-slots/my-bookings', { params: { include_past: !!includePast } }),
  myAssigned: (includePast) =>
    api.get('interview-slots/my-assigned', { params: { include_past: !!includePast } }),
  /** رزروهای انجام‌شده با اطلاعات دانشجو — مصاحبه‌گر / دفتر */
  bookings: (includePast) =>
    api.get('interview-slots/bookings', { params: { include_past: !!includePast } }),
  resultQueue: (includePast) =>
    api.get('interview-slots/result-queue', { params: { include_past: !!includePast } }),
  manageList: (includePast) =>
    api.get('interview-slots/manage', { params: { include_past: !!includePast } }),
  manageCreate: (body) => api.post('interview-slots/manage', body),
  manageUpdate: (id, body) => api.patch(`interview-slots/manage/${id}`, body),
  reschedule: (id, body) => api.patch(`interview-slots/manage/${id}/reschedule`, body),
  manageDelete: (id) => api.delete(`interview-slots/manage/${id}`),
  /** مصاحبه‌گر: الگوی هفتگی برای ساخت خودکار وقت */
  recurringRulesList: () => api.get('interview-slots/recurring-rules'),
  /** فقط ادمین — کاربرانی که می‌توانند مالک الگوی تکراری باشند */
  recurringRuleCandidateOwners: () => api.get('interview-slots/recurring-rules/candidate-owners'),
  recurringRuleCreate: (body) => api.post('interview-slots/recurring-rules', body),
  recurringRuleUpdate: (id, body) => api.patch(`interview-slots/recurring-rules/${id}`, body),
  recurringRuleDelete: (id) => api.delete(`interview-slots/recurring-rules/${id}`),
}

// ─── شیت وقت آزاد درمانگران آموزشی ─────────────────────────
export const educationalTherapistSlotsApi = {
  available: (courseType, role) =>
    api.get('educational-therapist-slots/available', {
      params: {
        ...(courseType ? { course_type: courseType } : {}),
        ...(role ? { role } : {}),
      },
    }),
  book: (body) => api.post('educational-therapist-slots/book', body),
  manageList: (includeBooked = true, therapistUserId) =>
    api.get('educational-therapist-slots/manage', {
      params: {
        include_booked: !!includeBooked,
        ...(therapistUserId ? { therapist_user_id: therapistUserId } : {}),
      },
    }),
  /** فهرست درمانگران برای نقش‌های مدیریت شیت (از جمله کمیته نظارت) */
  manageTherapists: () => api.get('educational-therapist-slots/manage/therapists'),
  manageCreate: (body) => api.post('educational-therapist-slots/manage', body),
  manageUpdate: (id, body) => api.patch(`educational-therapist-slots/manage/${id}`, body),
  manageDelete: (id) => api.delete(`educational-therapist-slots/manage/${id}`),
  manageRelease: (id) => api.post(`educational-therapist-slots/manage/${id}/release`),
}

// ─── Therapy sessions (student / therapist) ───────────────────
export const therapyApi = {
  mySessions: () => api.get('therapy-sessions/me'),
  myTherapyProgress: () => api.get('therapy-sessions/me/therapy-progress'),
  myFeeDeterminationSummary: () => api.get('therapy-sessions/me/fee-determination-summary'),
  forTherapist: () => api.get('therapy-sessions/for-therapist'),
  attendanceWorkbench: (params) => api.get('therapy-sessions/attendance-workbench', { params }),
  forStudent: (studentId) => api.get(`therapy-sessions/for-student/${studentId}`),
  patchSession: (sessionId, data) => api.patch(`therapy-sessions/${sessionId}`, data),
  workbenchSummary: (params) => api.get('therapy-workbench/summary', { params }),
  workbenchSessions: (params) => api.get('therapy-workbench/sessions', { params }),
  workbenchRepair: (studentId) => api.post(`therapy-workbench/repair/${studentId}`),
}

export const alocomApi = {
  provisionTherapySession: (sessionId, body) =>
    api.post(`integrations/alocom/therapy-sessions/${sessionId}/provision`, body),
  provisionInterviewSlot: (slotId, body = {}) =>
    api.post(`integrations/alocom/interview-slots/${slotId}/provision`, body),
}

// ─── Finance (اپراتور مالی / مدیر) ─────────────────────────────
export const financeApi = {
  summary: () => api.get('finance/summary'),
  context: () => api.get('finance/context'),
  installmentSettings: () => api.get('finance/installment-settings'),
  patchInstallmentSettings: (body) => api.patch('finance/installment-settings', body),
  programFinancialDefaults: () => api.get('finance/program-defaults'),
  patchProgramFinancialDefaults: (body) => api.patch('finance/program-defaults', body),
  transactions: (params) => api.get('finance/transactions', { params }),
  studentBalances: (params) => api.get('finance/student-balances', { params }),
  tuitionVouchers: (params) => api.get('finance/tuition-vouchers', { params }),
  patchTuitionVoucher: (id, body) => api.patch(`finance/tuition-vouchers/${id}`, body),
  async exportCsv() {
    const token = localStorage.getItem('token')
    const base = getApiBase()
    const res = await fetch(`${base}finance/export.csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('Export failed')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'financial_records.csv'
    a.click()
    URL.revokeObjectURL(url)
  },
}

// ─── Assignments ────────────────────────────────────────────────
export const assignmentApi = {
  create: (data) => api.post('assignments', data),
  mine: () => api.get('assignments/me'),
  getSubmission: (assignmentId) => api.get(`assignments/${assignmentId}/submission`),
  submit: (assignmentId, body) => api.post(`assignments/${assignmentId}/submit`, body),
}

// ─── تیکتینگ داخلی (کارکنان) ──────────────────────────────────
export const ticketApi = {
  triage: () => api.get('tickets/triage'),
  assignableUsers: () => api.get('tickets/assignable-users'),
  list: (params) => api.get('tickets', { params }),
  get: (id) => api.get(`tickets/${id}`),
  create: (data) => api.post('tickets', data),
  patch: (id, data) => api.patch(`tickets/${id}`, data),
  processEditDecision: (id, data) => api.post(`tickets/${id}/process-edit-decision`, data),
  addComment: (id, body) => api.post(`tickets/${id}/comments`, body),
}

// ─── Users ─────────────────────────────────────────────────────
export const userApi = {
  /** از کش مرورگر/پروکسی جلوگیری می‌کند تا بعد از حذف/ویرایش لیست تازه برگردد */
  list: (params) => {
    const p = params && typeof params === 'object' ? params : {}
    return api.get('admin/users', {
      params: { ...p, _ts: Date.now() },
      headers: { 'Cache-Control': 'no-store', Pragma: 'no-cache' },
    })
  },
  create: (data) => api.post('auth/register', data),
  update: (id, data) => api.patch(`admin/users/${id}`, data),
  setPassword: (id, password) => api.post(`admin/users/${id}/password`, { password }),
  /** بدون params: غیرفعال‌سازی. با `{ params: { permanent: true } }`: حذف دائمی از پایگاه. */
  delete: (id, config) => api.delete(`admin/users/${id}`, config),
}

// ─── Blog (Public) ──────────────────────────────────────────────
export const blogApi = {
  list: (params) => api.get('blog/posts', { params }),
  get: (slug) => api.get(`blog/posts/${slug}`),
  adminList: (params) => api.get('blog/admin/posts', { params }),
  adminCreate: (data) => api.post('blog/admin/posts', data),
  adminUpdate: (id, data) => api.patch(`blog/admin/posts/${id}`, data),
  adminDelete: (id) => api.delete(`blog/admin/posts/${id}`),
}

// ─── پنل نقش‌ها ──────────────────────────────────────────────────
export const panelApi = {
  /** صندوق نمونهٔ فرایند باز برای نقش فعلی (JWT) */
  myProcessInbox: (params) => api.get('panel/my-process-inbox', { params }),
  /** کارتابل فرایند + هشدار آمادگی نقش (وقت مصاحبه، جلسات درمان، …) */
  myOperatorFollowup: (params) => api.get('panel/my-operator-followup', { params }),
  /** تقویم آموزشی فعال (read-only — دانشجو و سایر نقش‌ها) */
  activeAcademicCalendar: () => api.get('panel/academic-calendar/active'),
  /** لیست یکپارچهٔ جلسات و لینک‌های آنلاین دانشجو */
  myOnlineSessions: (includePast = false) =>
    api.get('panel/my-online-sessions', { params: { include_past: !!includePast } }),
  mySemesterCourses: () => api.get('panel/my-semester-courses'),
  instructorCourseRoster: (courseCode, options = {}) =>
    api.get('panel/instructor/course-roster', {
      params: {
        course_code: courseCode,
        ...(options.enrichFilmReports ? { enrich_film_reports: true } : {}),
        ...(options.enrichLiveTherapyReports ? { enrich_live_therapy_reports: true } : {}),
      },
    }),
  classCancellationPreview: (courseCode, sessionKey = null) =>
    api.get('panel/instructor/class-cancellation-preview', {
      params: {
        course_code: courseCode,
        ...(sessionKey ? { session_key: sessionKey } : {}),
      },
    }),
  liveSupervisionProgress: (courseCode) =>
    api.get(`panel/instructor/live-supervision/${encodeURIComponent(courseCode)}/progress`),
  skillsCourseGradesPreview: (courseCode, instanceId = null) =>
    api.get(`panel/instructor/skills-course/${encodeURIComponent(courseCode)}/grades-preview`, {
      params: instanceId ? { instance_id: instanceId } : {},
    }),
  theoryCourseGradesPreview: (courseCode, instanceId = null) =>
    api.get(`panel/instructor/theory-course/${encodeURIComponent(courseCode)}/grades-preview`, {
      params: instanceId ? { instance_id: instanceId } : {},
    }),
  groupSupervisionGradesPreview: (courseCode, instanceId = null) =>
    api.get(`panel/instructor/group-supervision/${encodeURIComponent(courseCode)}/grades-preview`, {
      params: instanceId ? { instance_id: instanceId } : {},
    }),
  studentInstructorEvaluationCourses: (instanceId) =>
    api.get(`panel/student/instructor-evaluation/${encodeURIComponent(instanceId)}/courses`),
  submitStudentInstructorEvaluation: (instanceId, courseCode, body) =>
    api.post(
      `panel/student/instructor-evaluation/${encodeURIComponent(instanceId)}/courses/${encodeURIComponent(courseCode)}`,
      body,
    ),
  instructorEvaluationResults: (params) =>
    api.get('panel/instructor/evaluation-results', { params }),
  committeeEvaluationResults: (params) =>
    api.get('panel/committee/evaluation-results', { params }),
  navPendingCounts: () => api.get('panel/nav-pending-counts'),
  processNavItems: () => api.get('panel/process-nav-items'),
  /** فید اعلان‌های اقدام (زنگوله + صفحهٔ همه اعلان‌ها) */
  actionNotifications: (params) => api.get('panel/action-notifications', { params }),
  /** بستن یک اعلان از فید (کار انجام‌شده یا حذف دستی) */
  dismissActionNotification: (notificationId) =>
    api.post('panel/action-notifications/dismiss', { notification_id: notificationId }),
  /** ثبت پیام پاپ‌آپ UI برای مرور در پنل اعلان‌ها */
  createFlashMessage: (body) => api.post('panel/flash-messages', body),
  /** صندوق پیگیری سراسری — نقش admin */
  operatorFollowupInbox: (params) => api.get('panel/operator-followup-inbox', { params }),
  /** پیامک شبیه‌سازی‌شده (SMS_PROVIDER=log) برای شمارهٔ موبایل کاربر */
  simulatedSms: (params) => api.get('panel/simulated-sms', { params }),
  dismissSimulatedSms: (id) => api.post(`panel/simulated-sms/${encodeURIComponent(id)}/dismiss`),
  /** تاریخچهٔ پیامک‌های ارسالی به دانشجو (بدون کد ورود) */
  studentSmsHistory: (params) => api.get('panel/student-sms-history', { params }),
}

// ─── فرم‌های داینامیک (DB) ─────────────────────────────────────
export const dynamicFormsApi = {
  listTemplates: () => api.get('dynamic-forms/templates'),
  createTemplate: (data) => api.post('dynamic-forms/templates', data),
  getTemplate: (id) => api.get(`dynamic-forms/templates/${id}`),
  patchTemplate: (id, data) => api.patch(`dynamic-forms/templates/${id}`, data),
  publishVersion: (templateId, data) => api.post(`dynamic-forms/templates/${templateId}/versions`, data),
  listAssignments: (params) => api.get('dynamic-forms/assignments', { params }),
  createAssignment: (data) => api.post('dynamic-forms/assignments', data),
  patchAssignment: (id, data) => api.patch(`dynamic-forms/assignments/${id}`, data),
  openForInstance: (instanceId) => api.get(`dynamic-forms/open-for-instance/${instanceId}`),
  createResponse: (data) => api.post('dynamic-forms/responses', data),
  listResponses: (params) => api.get('dynamic-forms/responses', { params }),
  uploadResponseFile: (formData) =>
    api.post('dynamic-forms/responses/upload-file', formData, {
      timeout: 120000,
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  approveResponse: (responseId, data) => api.post(`dynamic-forms/responses/${responseId}/approve`, data || {}),
  rejectResponse: (responseId, data) => api.post(`dynamic-forms/responses/${responseId}/reject`, data || {}),
  unlockResponseFields: (responseId, data) => api.post(`dynamic-forms/responses/${responseId}/unlock-fields`, data || {}),
  getPortalNavDynamic: () => api.get('panel/portal-nav-dynamic'),
  putPortalNavDynamic: (role, data) => api.put(`panel/portal-nav-dynamic/${encodeURIComponent(role)}`, data),
}

// ─── Public ─────────────────────────────────────────────────────
export const publicApi = {
  stats: () => api.get('public/stats'),
  processes: () => api.get('public/processes'),
  portalConfig: () => api.get('public/portal-config'),
  smsSimulationStatus: () => api.get('public/sms-simulation-status'),
  /** مسیر تحصیلی و نقش‌ها؛ دریافت عمومی بدون ورود */
  studentLifecycleMatrix: () => api.get('public/student-lifecycle-matrix'),
  instituteInfo: () => api.get('public/institute-info'),
  register: (data) => api.post('public/register', data),
}

// ─── گزارشات مدیریتی (اکسل / CSV / PDF) — همان axios و baseURL پنل ─────────
export const reportsApi = {
  shamsiToday: () => api.get('reports/shamsi-today'),
  /**
   * @param {1|2|3|4|5} reportKey
   * @param {number} shamsiYear
   * @param {number} shamsiMonth
   * @param {'xlsx'|'csv'|'pdf'} [exportFormat] پیش‌فرض: اکسل
   * @param {boolean} [includeSampleData] پیش‌فرض: false — رکوردهای نمونه آموزشی در گزارش نیایند
   */
  async downloadMonthly(reportKey, shamsiYear, shamsiMonth, exportFormat = 'pdf', includeSampleData = false) {
    const paths = {
      1: 'reports/monthly/1-violations',
      2: 'reports/monthly/2-debt',
      3: 'reports/monthly/3-dropout',
      4: 'reports/monthly/4-sla-delays',
      5: 'reports/monthly/5-cancellations',
    }
    const path = paths[reportKey]
    if (!path) throw new Error('گزارش نامعتبر است')
    const fmt = ['csv', 'xlsx', 'pdf'].includes(exportFormat) ? exportFormat : 'xlsx'
    try {
      const res = await api.get(path, {
        params: {
          shamsi_year: shamsiYear,
          shamsi_month: shamsiMonth,
          format: fmt,
          include_sample_data: includeSampleData === true,
        },
        responseType: 'blob',
      })
      const blob = res.data
      const cd = res.headers['content-disposition'] || res.headers['Content-Disposition']
      let filename = `report_${shamsiYear}_${String(shamsiMonth).padStart(2, '0')}.${fmt === 'pdf' ? 'pdf' : fmt === 'xlsx' ? 'xlsx' : 'csv'}`
      if (cd && /filename=/i.test(cd)) {
        const m = cd.match(/filename\*?=(?:UTF-8'')?["']?([^";\n]+)["']?/i)
        if (m) filename = decodeURIComponent(m[1].trim())
      }
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      const res = err.response
      if (res?.data instanceof Blob) {
        const text = await res.data.text()
        let msg = text
        try {
          const j = JSON.parse(text)
          msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
        } catch (_) {
          /* متن خام خطا */
        }
        throw new Error(msg || err.message || 'خطا در دریافت گزارش')
      }
      throw err
    }
  },
}

// ─── چارت کمیته دروس ─────────────────────────────────────────────
export const courseCommitteeRosterApi = {
  listTracks: () => api.get('admin/course-committee-roster/tracks'),
  getDetail: (track) =>
    api.get('admin/course-committee-roster/detail', { params: { track } }),
  listMembers: (params) => api.get('admin/course-committee-roster', { params }),
  listCourses: () => api.get('admin/course-catalog'),
  createTrack: (body) => api.post('admin/course-committee-roster/tracks', body),
  deleteTrack: (trackCode) =>
    api.delete(`admin/course-committee-roster/tracks/${encodeURIComponent(trackCode)}`),
  createCourse: (body) => api.post('admin/course-catalog', body),
  updateCourse: (courseValue, body) =>
    api.patch(`admin/course-catalog/${encodeURIComponent(courseValue)}`, body),
  deleteCourse: (courseValue) =>
    api.delete(`admin/course-catalog/${encodeURIComponent(courseValue)}`),
  createMember: (body) => api.post('admin/course-committee-roster/members', body),
  linkMember: (body) => api.post('admin/course-committee-roster/members/link', body),
  updateMember: (userId, body) =>
    api.patch(`admin/course-committee-roster/members/${userId}`, body),
  updateMemberCourses: (body) =>
    api.patch('admin/course-committee-roster/members/courses', body),
  updateMemberKind: (body) =>
    api.patch('admin/course-committee-roster/members/kind', body),
  deleteMember: (body) =>
    api.delete('admin/course-committee-roster/members', { params: body, data: body }),
}

export default api
