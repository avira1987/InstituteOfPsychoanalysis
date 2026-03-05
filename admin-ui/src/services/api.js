import axios from 'axios'

// API base: same pattern as login - relative URL in production (prevents Mixed Content)
// Override via VITE_API_BASE in .env when frontend/backend are on different origins
export function getApiBase() {
  if (import.meta.env.VITE_API_BASE) return import.meta.env.VITE_API_BASE.replace(/\/?$/, '/')
  if (typeof window === 'undefined') {
    const base = (import.meta.env.BASE_URL || '/anistito/').replace(/\/$/, '') || ''
    return (base ? base + '/' : '/') + 'api/'
  }
  const h = window.location.hostname
  const p = window.location.port
  if (h === 'localhost' || h === '127.0.0.1') {
    if (p === '8000' || p === '') return '/api/'
    return 'http://localhost:8000/api/'
  }
  // Production: use same base path as app (from Vite base config)
  const base = (import.meta.env.BASE_URL || '/anistito/').replace(/\/$/, '') || ''
  return (base ? base + '/' : '/') + 'api/'
}
const API_BASE = getApiBase()

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = (import.meta.env.BASE_URL || '') + 'login'
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
export const authApi = {
  login: (username, password, securityAnswer, challengeId, challengeAnswer) =>
    api.post('auth/login-json', {
      username,
      password,
      security_answer: securityAnswer || undefined,
      challenge_id: challengeId,
      challenge_answer: challengeAnswer,
    }),
  me: () => api.get('auth/me'),
  register: (data) => api.post('auth/register', data),
  otpRequest: (phone) => api.post('auth/otp/request', { phone }),
  otpVerify: (phone, code) => api.post('auth/otp/verify', { phone, code }),
  setSecurityQuestion: (question, answer) =>
    api.post('auth/set-security-question', { question, answer }),
  getSecurityQuestion: (username) =>
    api.post('auth/security-question-preview', { username }),
  getLoginChallenge: () => api.post('auth/login-challenge'),
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
