import React, { Suspense } from 'react'
import { lazyWithRetry as lazy } from './utils/lazyWithRetry'
import { Routes, Route, Navigate, useParams } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'

import Layout from './components/Layout'
import PublicLayout from './components/PublicLayout'

import { getRouterBasename } from './utils/routerBasename'
import { canAccessReportsHub } from './utils/reportsAccess'
import { getCommitteeHomePathForRole, getPortalHomeHref, getPortalHomePath } from './utils/portalRoleHome'
import { canAccessStaffLane } from './utils/portalStaffLanes'
import { canAccessCommitteeKind } from './utils/portalCommitteeKinds'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const ProcessEditor = lazy(() => import('./pages/ProcessEditor'))
const ProcessListPage = lazy(() => import('./pages/ProcessListPage'))
const RuleManager = lazy(() => import('./pages/RuleManager'))
const StudentTracker = lazy(() => import('./pages/StudentTracker'))
const AuditViewer = lazy(() => import('./pages/AuditViewer'))
const GuidePage = lazy(() => import('./pages/GuidePage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const UserManagement = lazy(() => import('./pages/UserManagement'))
const StudentPortal = lazy(() => import('./pages/StudentPortal'))
const TherapistPortal = lazy(() => import('./pages/TherapistPortal'))
const SupervisorPortal = lazy(() => import('./pages/SupervisorPortal'))
const StaffPortal = lazy(() => import('./pages/StaffPortal'))
const SiteManagerPortal = lazy(() => import('./pages/SiteManagerPortal'))
const CommitteePortal = lazy(() => import('./pages/CommitteePortal'))
const InterviewerPortal = lazy(() => import('./pages/InterviewerPortal'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const FinancialDashboard = lazy(() => import('./pages/FinancialDashboard'))
const ReportsHubPage = lazy(() => import('./pages/ReportsHubPage'))
const TicketsPage = lazy(() => import('./pages/TicketsPage'))
const DynamicFormsAdmin = lazy(() => import('./pages/DynamicFormsAdmin'))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))
const SystemResourcesPage = lazy(() => import('./pages/SystemResourcesPage'))
const AutomationSchedulerPage = lazy(() => import('./pages/AutomationSchedulerPage'))
const SemesterPrepPage = lazy(() => import('./pages/SemesterPrepPage'))
const SemesterPrepCalendarPage = lazy(() => import('./pages/SemesterPrepCalendarPage'))
const SemesterPrepWorkbenchPage = lazy(() => import('./pages/SemesterPrepWorkbenchPage'))
const SemesterPrepCourseListReviewPage = lazy(() => import('./pages/SemesterPrepCourseListReviewPage'))
const SemesterPrepSlaWarningsPage = lazy(() => import('./pages/SemesterPrepSlaWarningsPage'))
const HomePage = lazy(() => import('./pages/public/HomePage'))
const BlogList = lazy(() => import('./pages/public/BlogList'))
const BlogPost = lazy(() => import('./pages/public/BlogPost'))
const StudentGuide = lazy(() => import('./pages/public/StudentGuide'))
const StudentLifecycleMatrix = lazy(() => import('./pages/public/StudentLifecycleMatrix'))
const CompleteStudentRegistration = lazy(() => import('./pages/CompleteStudentRegistration'))

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

/** برای دانشجو/مالی/مصاحبه‌گر/اپراتور = پنل نقش؛ admin = داشبورد */
function PanelIndex() {
  const { user } = useAuth()
  if (!user?.role) return <Dashboard />
  const homePath = getPortalHomePath(user.role)
  if (homePath && user.role !== 'admin') {
    return <Navigate to={getPortalHomeHref(user.role)} replace />
  }
  return <Dashboard />
}

/** مصاحبه‌گر پذیرش — فهرست رزروها */
function RequireInterviewerPortalRole({ children }) {
  const { user, loading } = useAuth()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'interviewer' && user.role !== 'admin') return <Navigate to="/panel" replace />
  return children
}

/** فقط مدیر سیستم یا اپراتور مالی به داشبورد مالی دسترسی دارند */
function RequireFinanceRole({ children }) {
  const { user, loading } = useAuth()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'admin' && user.role !== 'finance') return <Navigate to="/panel" replace />
  return children
}

/** صفحات فقط مدیر سیستم (مثل منابع سرور) */
function RequireAdminRole({ children }) {
  const { user, loading } = useAuth()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'admin') return <Navigate to="/panel" replace />
  return children
}

/** آماده‌سازی ترم — admin/staff/deputy + مدیر سایت برای زمان‌بندی مصاحبه */
function RequireSemesterPrepRole({ children }) {
  const { user, loading } = useAuth()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  const ok = ['admin', 'staff', 'deputy_education', 'site_manager', 'course_committee'].includes(user.role)
  if (!ok) return <Navigate to="/panel" replace />
  return children
}

/** تقویم و اتوماسیون زمان‌محور — مشاهده برای staff/deputy؛ ویرایش فقط admin در خود صفحه */
function RequireSchedulerViewRole({ children }) {
  const { user, loading } = useAuth()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  const ok = ['admin', 'staff', 'deputy_education'].includes(user.role)
  if (!ok) return <Navigate to="/panel" replace />
  return children
}

/** گزارشات: مدیر سیستم، کارمند دفتر (مدیر داخلی)، معاون آموزش، مسئول کمیته نظارت، مالی */
function RequireReportsRole({ children }) {
  const { user, loading } = useAuth()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  if (!canAccessReportsHub(user.role)) return <Navigate to="/panel" replace />
  return children
}

function RequireStaffLane({ children }) {
  const { user, loading } = useAuth()
  const { lane } = useParams()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  if (!lane || !canAccessStaffLane(user.role, lane)) {
    return <Navigate to={getPortalHomeHref(user.role)} replace />
  }
  return children
}

function RequireCommitteeKind({ children }) {
  const { user, loading } = useAuth()
  const { kind } = useParams()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  if (!kind || !canAccessCommitteeKind(user.role, kind)) {
    return <Navigate to={getPortalHomeHref(user.role)} replace />
  }
  return children
}

function CommitteeHomeRedirect() {
  const { user, loading } = useAuth()
  if (loading) return panelLoading()
  if (!user) return <Navigate to="/login" replace />
  const path = getCommitteeHomePathForRole(user.role)
  return <Navigate to={`${path}?tab=reviews`} replace />
}

function StaffLegacyRedirect() {
  return <Navigate to="/panel/portal/staff/admissions" replace />
}

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={panelLoading()}>
      <Routes>
        {/* ─── Public Pages ─── */}
        <Route element={<PublicLayout />}>
          <Route index element={<HomePage />} />
          <Route path="blog" element={<BlogList />} />
          <Route path="blog/:slug" element={<BlogPost />} />
          <Route path="guide" element={<StudentGuide />} />
          <Route path="processes-info" element={<Navigate to="/student-lifecycle" replace />} />
          <Route path="student-lifecycle" element={<StudentLifecycleMatrix />} />
          <Route path="register" element={<Navigate to="/login" replace />} />
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
          <Route path="processes" element={<ProcessListPage />} />
          <Route path="processes/:processId" element={<ProcessEditor />} />
          <Route path="dynamic-forms" element={<DynamicFormsAdmin />} />
          <Route path="rules" element={<RuleManager />} />
          <Route path="students" element={<StudentTracker />} />
          <Route path="users" element={<UserManagement />} />
          <Route path="audit" element={<AuditViewer />} />
          <Route
            path="reports"
            element={
              <RequireReportsRole>
                <ReportsHubPage />
              </RequireReportsRole>
            }
          />
          <Route path="automation-reports" element={<Navigate to="/panel/reports" replace />} />
          <Route path="reports/automation" element={<Navigate to="/panel/reports" replace />} />
          <Route path="tickets" element={<TicketsPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route
            path="system-resources"
            element={
              <RequireAdminRole>
                <SystemResourcesPage />
              </RequireAdminRole>
            }
          />
          <Route
            path="semester-prep/calendar"
            element={
              <RequireSemesterPrepRole>
                <SemesterPrepCalendarPage />
              </RequireSemesterPrepRole>
            }
          />
          <Route
            path="semester-prep/course-list-review"
            element={
              <RequireSemesterPrepRole>
                <SemesterPrepCourseListReviewPage />
              </RequireSemesterPrepRole>
            }
          />
          <Route
            path="semester-prep/workbench"
            element={
              <RequireSemesterPrepRole>
                <SemesterPrepWorkbenchPage />
              </RequireSemesterPrepRole>
            }
          />
          <Route
            path="semester-prep/sla-warnings"
            element={
              <RequireSemesterPrepRole>
                <SemesterPrepSlaWarningsPage />
              </RequireSemesterPrepRole>
            }
          />
          <Route
            path="semester-prep"
            element={
              <RequireSemesterPrepRole>
                <SemesterPrepPage />
              </RequireSemesterPrepRole>
            }
          />
          <Route
            path="automation-scheduler"
            element={
              <RequireSchedulerViewRole>
                <AutomationSchedulerPage />
              </RequireSchedulerViewRole>
            }
          />
          <Route
            path="finance"
            element={
              <RequireFinanceRole>
                <FinancialDashboard />
              </RequireFinanceRole>
            }
          />
          <Route
            path="complete-registration"
            element={
              <RequireStudentRole>
                <CompleteStudentRegistration />
              </RequireStudentRole>
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
          <Route path="portal/staff" element={<StaffLegacyRedirect />} />
          <Route
            path="portal/staff/:lane"
            element={
              <RequireStaffLane>
                <StaffPortal />
              </RequireStaffLane>
            }
          />
          <Route
            path="portal/interviewer"
            element={
              <RequireInterviewerPortalRole>
                <InterviewerPortal />
              </RequireInterviewerPortalRole>
            }
          />
          <Route path="portal/site-manager" element={<SiteManagerPortal />} />
          <Route path="portal/committee" element={<CommitteeHomeRedirect />} />
          <Route
            path="portal/committee/:kind"
            element={
              <RequireCommitteeKind>
                <CommitteePortal />
              </RequireCommitteeKind>
            }
          />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="guide" element={<GuidePage />} />
        </Route>

        {/* ─── Fallback ─── */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
