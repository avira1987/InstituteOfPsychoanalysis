import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import Layout from './components/Layout'
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
import SupervisorPortal from './pages/SupervisorPortal'

// Error Boundary to catch rendering errors and show them instead of white screen
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
        <div style={{ padding: '2rem', direction: 'rtl', fontFamily: 'Tahoma, sans-serif' }}>
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
              onClick={() => { this.setState({ hasError: false, error: null, errorInfo: null }); window.location.href = (import.meta.env.BASE_URL || '/').replace(/\/$/, '') || '/' }}
              style={{
                marginTop: '1rem', padding: '0.75rem 1.5rem', background: '#3b82f6', color: '#fff',
                border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '1rem'
              }}
            >
              بازگشت به داشبورد
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <div className="loading-spinner" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="processes" element={<ProcessList />} />
          <Route path="processes/:processId" element={<ProcessEditor />} />
          <Route path="rules" element={<RuleManager />} />
          <Route path="students" element={<StudentTracker />} />
          <Route path="users" element={<UserManagement />} />
          <Route path="audit" element={<AuditViewer />} />
          <Route path="portal/student" element={<StudentPortal />} />
          <Route path="portal/supervisor" element={<SupervisorPortal />} />
          <Route path="guide" element={<GuidePage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}
