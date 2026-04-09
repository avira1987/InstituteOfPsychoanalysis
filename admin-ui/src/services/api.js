import axios from 'axios'
import { getRouterBasename } from '../utils/routerBasename'

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
  (response) => response,
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
  get: (id) => api.get(`students/${id}`),
  create: (data) => api.post('students', data),
  update: (id, data) => api.patch(`students/${id}`, data),
}

// ─── Process Execution ─────────────────────────────────────────
export const processExecApi = {
  definitions: () => api.get('process/definitions'),
  getDefinition: (code) => api.get(`process/definitions/${code}`),
  start: (data) => api.post('process/start', data),
  trigger: (instanceId, data) => api.post(`process/${instanceId}/trigger`, data),
  status: (instanceId) => api.get(`process/${instanceId}/status`),
  transitions: (instanceId) => api.get(`process/${instanceId}/transitions`),
  /** وضعیت + انتقال‌ها + فرم‌های مرحلهٔ فعلی (مثل بارگذاری داشبورد فرایند در UI) */
  dashboard: (instanceId) => api.get(`process/${instanceId}/dashboard`),
  studentInstances: (studentId, params) =>
    api.get(`process/instances/student/${studentId}`, { params }),
  /** دانشجو: ثبت فرم مرحله (قفل تا باز شدن توسط کارمند) */
  registerStudentStepForms: (instanceId, body) =>
    api.post(`process/${instanceId}/student-step-forms/register`, body),
  /** کارمند/اداری: اجازهٔ ویرایش مجدد فرم مرحله برای دانشجو */
  unlockStudentStepFormsEdit: (instanceId, body) =>
    api.post(`process/${instanceId}/student-step-forms/unlock-edit`, body || {}),
}

// ─── Therapy sessions (student / therapist) ───────────────────
export const therapyApi = {
  mySessions: () => api.get('therapy-sessions/me'),
  forTherapist: () => api.get('therapy-sessions/for-therapist'),
  patchSession: (sessionId, data) => api.patch(`therapy-sessions/${sessionId}`, data),
}

// ─── Finance (اپراتور مالی / مدیر) ─────────────────────────────
export const financeApi = {
  summary: () => api.get('finance/summary'),
  context: () => api.get('finance/context'),
  installmentSettings: () => api.get('finance/installment-settings'),
  patchInstallmentSettings: (body) => api.patch('finance/installment-settings', body),
  transactions: (params) => api.get('finance/transactions', { params }),
  studentBalances: (params) => api.get('finance/student-balances', { params }),
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
  addComment: (id, body) => api.post(`tickets/${id}/comments`, body),
}

// ─── Users ─────────────────────────────────────────────────────
export const userApi = {
  list: (params) => api.get('admin/users', { params }),
  create: (data) => api.post('auth/register', data),
  update: (id, data) => api.patch(`admin/users/${id}`, data),
  delete: (id) => api.delete(`admin/users/${id}`),
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

// ─── Public ─────────────────────────────────────────────────────
export const publicApi = {
  stats: () => api.get('public/stats'),
  processes: () => api.get('public/processes'),
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

export default api
