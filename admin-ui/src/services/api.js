import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
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
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ─── Auth ──────────────────────────────────────────────────────
export const authApi = {
  login: (username, password) =>
    api.post('/auth/login', new URLSearchParams({ username, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  me: () => api.get('/auth/me'),
  register: (data) => api.post('/auth/register', data),
}

// ─── Processes ─────────────────────────────────────────────────
export const processApi = {
  list: (params) => api.get('/admin/processes/', { params }),
  get: (id) => api.get(`/admin/processes/${id}`),
  create: (data) => api.post('/admin/processes/', data),
  update: (id, data) => api.patch(`/admin/processes/${id}`, data),
  delete: (id) => api.delete(`/admin/processes/${id}`),
  // States
  getStates: (processId) => api.get(`/admin/processes/${processId}/states/`),
  createState: (processId, data) => api.post(`/admin/processes/${processId}/states/`, data),
  updateState: (stateId, data) => api.patch(`/admin/states/${stateId}`, data),
  deleteState: (stateId) => api.delete(`/admin/states/${stateId}`),
  // Transitions
  getTransitions: (processId) => api.get(`/admin/processes/${processId}/transitions/`),
  createTransition: (processId, data) => api.post(`/admin/processes/${processId}/transitions/`, data),
  updateTransition: (transitionId, data) => api.patch(`/admin/transitions/${transitionId}`, data),
  deleteTransition: (transitionId) => api.delete(`/admin/transitions/${transitionId}`),
}

// ─── Rules ─────────────────────────────────────────────────────
export const ruleApi = {
  list: (params) => api.get('/admin/rules/', { params }),
  get: (id) => api.get(`/admin/rules/${id}`),
  create: (data) => api.post('/admin/rules/', data),
  update: (id, data) => api.patch(`/admin/rules/${id}`, data),
  delete: (id) => api.delete(`/admin/rules/${id}`),
}

// ─── Audit ─────────────────────────────────────────────────────
export const auditApi = {
  list: (params) => api.get('/admin/audit-logs/', { params }),
}

// ─── Dashboard ─────────────────────────────────────────────────
export const dashboardApi = {
  stats: () => api.get('/admin/dashboard/stats'),
}

// ─── Students ──────────────────────────────────────────────────
export const studentApi = {
  list: () => api.get('/students/'),
  get: (id) => api.get(`/students/${id}`),
  create: (data) => api.post('/students/', data),
  update: (id, data) => api.patch(`/students/${id}`, data),
}

// ─── Process Execution ─────────────────────────────────────────
export const processExecApi = {
  definitions: () => api.get('/process/definitions/'),
  getDefinition: (code) => api.get(`/process/definitions/${code}`),
  start: (data) => api.post('/process/start', data),
  trigger: (instanceId, data) => api.post(`/process/${instanceId}/trigger`, data),
  status: (instanceId) => api.get(`/process/${instanceId}/status`),
  transitions: (instanceId) => api.get(`/process/${instanceId}/transitions`),
  studentInstances: (studentId, params) =>
    api.get(`/process/instances/student/${studentId}`, { params }),
}

// ─── Users ─────────────────────────────────────────────────────
export const userApi = {
  list: (params) => api.get('/admin/users/', { params }),
  create: (data) => api.post('/auth/register', data),
  update: (id, data) => api.patch(`/admin/users/${id}`, data),
  delete: (id) => api.delete(`/admin/users/${id}`),
}

export default api
