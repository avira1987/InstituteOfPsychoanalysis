import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'

import Layout from './components/Layout'
import PublicLayout from './components/PublicLayout'

import Dashboard from './pages/Dashboard'
import ProcessList from './pages/ProcessList'
import ProcessEditor from './pages/ProcessEditor'
import RuleManager from './pages/RuleManager'
import StudentTracker from './pages/StudentTracker'
import AuditViewer from './pages/AuditViewer'
import GuidePage from './pages/GuidePage'
import LoginPage from './pages/LoginPage'
import UserManagement from './pages/UserManagement'
import StudentPortal from './pages/StudentPortal'
import TherapistPortal from './pages/TherapistPortal'
import SupervisorPortal from './pages/SupervisorPortal'
import StaffPortal from './pages/StaffPortal'
import SiteManagerPortal from './pages/SiteManagerPortal'
import CommitteePortal from './pages/CommitteePortal'
import ProfilePage from './pages/ProfilePage'
import FinancialDashboard from './pages/FinancialDashboard'

import { getRouterBasename } from './utils/routerBasename'
import HomePage from './pages/public/HomePage'
import BlogList from './pages/public/BlogList'
import BlogPost from './pages/public/BlogPost'
import StudentGuide from './pages/public/StudentGuide'
import ProcessesInfo from './pages/public/ProcessesInfo'
import StudentRegistration from './pages/public/StudentRegistration'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo })
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', direction: 'rtl', fontFamily: 'Vazirmatn, Tahoma, sans-serif' }}>
          <div style={{
            background: '#fef2f2', border: '2px solid #ef4444', borderRadius: '12px',
            padding: '2rem', maxWidth: '700px', margin: '2rem auto'
          }}>
            <h2 style={{ color: '#dc2626', marginBottom: '1rem' }}>خطا در بارگذاری صفحه</h2>
            <p style={{ marginBottom: '1rem' }}>متأسفانه یک خطای غیرمنتظره رخ داده است.</p>
            <details style={{ background: '#fff', padding: '1rem', borderRadius: '8px', direction: 'ltr', textAlign: 'left' }}>
              <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>Error Details</summary>
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', marginTop: '0.5rem', color: '#991b1b' }}>
                {this.state.error && this.state.error.toString()}
              </pre>
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.75rem', marginTop: '0.5rem', color: '#666' }}>
                {this.state.errorInfo && this.state.errorInfo.componentStack}
              </pre>
            </details>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null, errorInfo: null })
                const rb = getRouterBasename()
                window.location.href = rb ? `${rb}/` : '/'
              }}
              style={{
                marginTop: '1rem', padding: '0.75rem 1.5rem', background: '#3b82f6', color: '#fff',
                border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '1rem'
              }}
            >
              بازگشت به صفحه اصلی
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function panelLoading() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <div className="loading-spinner" />
    </div>
  )
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  return children
}

/** فقط کاربر با نقش دانشجو؛ بقیه به داشبورد هدایت می‌شوند */
function RequireStudentRole({ children }) {
  const { user, loading } = useAuth()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'student') return <Navigate to="/panel" replace />
  return children
}

/** برای دانشجو صفحهٔ اول پنل = پنل دانشجو؛ اپراتور مالی = داشبورد مالی؛ برای بقیه = داشبورد */
function PanelIndex() {
  const { user } = useAuth()
  if (user?.role === 'student') return <Navigate to="/panel/portal/student" replace />
  if (user?.role === 'finance') return <Navigate to="/panel/finance" replace />
  return <Dashboard />
}

/** فقط مدیر سیستم یا اپراتور مالی به داشبورد مالی دسترسی دارند */
function RequireFinanceRole({ children }) {
  const { user, loading } = useAuth()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'admin' && user.role !== 'finance') return <Navigate to="/panel" replace />
  return children
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        {/* ─── Public Pages ─── */}
        <Route element={<PublicLayout />}>
          <Route index element={<HomePage />} />
          <Route path="blog" element={<BlogList />} />
          <Route path="blog/:slug" element={<BlogPost />} />
          <Route path="guide" element={<StudentGuide />} />
          <Route path="processes-info" element={<ProcessesInfo />} />
          <Route path="register" element={<StudentRegistration />} />
        </Route>

        {/* ─── Login ─── */}
        <Route path="/login" element={<LoginPage />} />

        {/* ─── Admin Panel (Protected) ─── */}
        <Route
          path="/panel"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<PanelIndex />} />
          <Route path="processes" element={<ProcessList />} />
          <Route path="processes/:processId" element={<ProcessEditor />} />
          <Route path="rules" element={<RuleManager />} />
          <Route path="students" element={<StudentTracker />} />
          <Route path="users" element={<UserManagement />} />
          <Route path="audit" element={<AuditViewer />} />
          <Route
            path="finance"
            element={
              <RequireFinanceRole>
                <FinancialDashboard />
              </RequireFinanceRole>
            }
          />
          <Route
            path="portal/student"
            element={
              <RequireStudentRole>
                <StudentPortal />
              </RequireStudentRole>
            }
          />
          <Route path="portal/therapist" element={<TherapistPortal />} />
          <Route path="portal/supervisor" element={<SupervisorPortal />} />
          <Route path="portal/staff" element={<StaffPortal />} />
          <Route path="portal/site-manager" element={<SiteManagerPortal />} />
          <Route path="portal/committee" element={<CommitteePortal />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="guide" element={<GuidePage />} />
        </Route>

        {/* ─── Fallback ─── */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}
