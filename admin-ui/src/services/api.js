import axios from 'axios'

// API base. Override با VITE_API_BASE در .env در صورت نیاز.
export function getApiBase() {
  // فرانت فقط روی پورت 3000؛ آدرس API هم روی 3000 (یک پورت واحد).
  if (typeof window !== 'undefined') {
    const port = window.location.port
    const host = window.location.hostname
    if (port === '3000' && (host === 'localhost' || host === '127.0.0.1')) {
      const base = import.meta.env.VITE_API_BASE
        ? import.meta.env.VITE_API_BASE.replace(/\/?$/, '/')
        : 'http://localhost:3000/api/'
      return base
    }
    if (host === 'localhost' || host === '127.0.0.1') {
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
        origin === 'http://localhost:3000' || origin === 'http://127.0.0.1:3000'
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
        window.location.href = (import.meta.env.BASE_URL || '') + 'login'
      }
    }
    return Promise.reject(error)
  }
)

// مسیر پایه اپ (بدون /api) برای endpointهای غیر-API مثل debug
export function getAppBasePath() {
  const base = (import.meta.env.BASE_URL || '/anistito/').replace(/\/$/, '') || ''
  return (base ? base + '/' : '/')
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
}

// ─── Processes ─────────────────────────────────────────────────
// Backend routes have NO trailing slash - avoid 307 redirect (causes Mixed Content)
export const processApi = {
  list: (params) => api.get('admin/processes', { params }),
  get: (id) => api.get(`admin/processes/${id}`),
  create: (data) => api.post('admin/processes', data),
  update: (id, data) => api.patch(`admin/processes/${id}`, data),
  delete: (id) => api.delete(`admin/processes/${id}`),
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
  // endpoint دیباگ بدون نیاز به توکن (همان الگوی لاگین - بدون auth)
  debugProcessCount: () =>
    fetch(`${window.location.origin}${getAppBasePath()}debug/process-count`).then((r) =>
      r.ok ? r.json() : Promise.reject(new Error('debug failed'))
    ),
}

// ─── Students ──────────────────────────────────────────────────
export const studentApi = {
  list: () => api.get('students'),
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
  studentInstances: (studentId, params) =>
    api.get(`process/instances/student/${studentId}`, { params }),
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

export default api
