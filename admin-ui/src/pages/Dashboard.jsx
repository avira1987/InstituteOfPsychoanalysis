import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { dashboardApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import PrimaryAdminOperatorFollowup from '../components/PrimaryAdminOperatorFollowup'
import { canManageInterviewSlots, interviewSlotsManagePath } from '../utils/interviewSlotAccess'
import { getPortalHomeHref, getPortalQuickLink } from '../utils/portalRoleHome'
import { staffLanesForPortalRole } from '../utils/portalStaffLanes'
import { committeeKindsForPortalRole } from '../utils/portalCommitteeKinds'
import { canViewSchedulerAutomation } from '../utils/portalRoleNav'
import { canonicalPortalRole, userHasRole } from '../utils/userRoles'

function PortalQuickLink({ role, navigate }) {
  const portal = role ? getPortalQuickLink(role) : null
  if (!portal) return null
  return (
    <button type="button" className="btn btn-primary" onClick={() => navigate(portal.path)}>
      <span style={{ marginLeft: '0.5rem' }}>{portal.icon}</span>
      {portal.label}
    </button>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [debugCount, setDebugCount] = useState(null)

  useEffect(() => {
    loadAll()
  }, [user?.role])

  const loadAll = async () => {
    setLoadError(null)
    setDebugCount(null)
    const isAdminOrStaff = userHasRole(user, 'staff')
    try {
      // فقط برای ادمین/کارمند: آمار را بگیر؛ کاربر غیرادمین این API را ندارد
      if (!isAdminOrStaff) {
        setStats(null)
        return
      }
      const settled = await Promise.allSettled([dashboardApi.stats()])
      const failedLabels = []
      if (settled[0].status === 'fulfilled') {
        setStats(settled[0].value.data)
      } else {
        setStats(null)
        failedLabels.push('آمار کلی')
        console.error('dashboard stats failed:', settled[0].reason)
      }
      if (failedLabels.length > 0) {
        const first = settled.find((s) => s.status === 'rejected')?.reason
        const status = first?.response?.status
        const detail = first?.response?.data?.detail
        const hint =
          status === 401
            ? 'لطفاً دوباره وارد شوید'
            : detail
              ? `${failedLabels.join('، ')}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`
              : `بارگذاری نشد: ${failedLabels.join('، ')}`
        setLoadError(hint)
        try {
          const d = await dashboardApi.debugProcessCount()
          setDebugCount(d.process_count)
        } catch (_) {}
      }
    } catch (err) {
      console.error('Failed to load dashboard:', err)
      setLoadError(err.response?.status === 401 ? 'لطفاً دوباره وارد شوید' : 'خطا در بارگذاری داشبورد')
      setStats(null)
      try {
        const d = await dashboardApi.debugProcessCount()
        setDebugCount(d.process_count)
      } catch (_) {}
    } finally {
      setLoading(false)
    }
  }

  const quickActions = useMemo(() => {
    const u = canonicalPortalRole(user?.role) || user?.role
    const items = []
    if (u === 'student' || u === 'admin') {
      items.push({ key: 'student', icon: '🎓', label: 'پنل آموزشی', hint: 'مسیر، فرایندها و کلاس', onClick: () => navigate('/panel/portal/student') })
    }
    if (u === 'therapist' || u === 'admin') {
      items.push({ key: 'therapist', icon: '💊', label: 'پنل درمانگر', hint: 'جلسات و پرونده‌های درمانی', onClick: () => navigate('/panel/portal/therapist') })
    }
    if (u === 'supervisor' || u === 'admin') {
      items.push({ key: 'supervisor', icon: '👁️', label: 'پنل سوپروایزر', hint: 'سوپرویژن و بازخورد', onClick: () => navigate('/panel/portal/supervisor') })
    }
    if (u === 'staff' || u === 'admin') {
      for (const lane of staffLanesForPortalRole(u)) {
        items.push({
          key: `staff-${lane.id}`,
          icon: lane.icon,
          label: lane.label,
          hint: lane.subtitle,
          onClick: () => navigate(`${lane.path}?tab=pending`),
        })
      }
    }
    if (u === 'interviewer' || u === 'admin') {
      items.push({
        key: 'staff-admissions-interviewer',
        icon: '🎤',
        label: 'پنل مصاحبه‌گر',
        hint: 'ثبت نتیجهٔ مصاحبه و اسلات',
        onClick: () => navigate('/panel/portal/interviewer'),
      })
    }
    if (u === 'interviewer') {
      items.push({
        key: 'staff-admissions',
        icon: '📥',
        label: 'پنل پذیرش',
        hint: 'ثبت نتیجهٔ مصاحبه و اسلات',
        onClick: () => navigate('/panel/portal/staff/admissions?tab=pending'),
      })
    }
    if (u === 'site_manager' || u === 'admin') {
      items.push({ key: 'site', icon: '🏗️', label: 'پنل مسئول سایت', hint: 'هماهنگی و برنامه‌ریزی', onClick: () => navigate('/panel/portal/site-manager') })
    }
    if (['progress_committee', 'education_committee', 'supervision_committee', 'specialized_commission', 'therapy_committee_chair', 'therapy_committee_executor', 'deputy_education', 'monitoring_committee_officer'].includes(u)) {
      const kind = committeeKindsForPortalRole(u)[0]
      if (kind) {
        items.push({
          key: 'committee',
          icon: '📋',
          label: kind.label,
          hint: 'جلسات و تصمیمات کمیته',
          onClick: () => navigate(`${kind.path}?tab=reviews`),
        })
      }
    }
    if (u === 'admin') {
      for (const kind of committeeKindsForPortalRole('admin')) {
        items.push({
          key: `committee-${kind.id}`,
          icon: '📋',
          label: kind.label,
          hint: 'پنل کمیته',
          onClick: () => navigate(`${kind.path}?tab=reviews`),
        })
      }
    }
    if (canManageInterviewSlots(user)) {
      items.push({
        key: 'interview-slots',
        icon: '📅',
        label: 'وقت مصاحبه',
        hint: 'تعریف، ویرایش و رزروهای مصاحبه',
        onClick: () => navigate(interviewSlotsManagePath),
      })
    }
    if (u === 'admin' || u === 'staff') {
      items.push({ key: 'students', icon: '👨‍🎓', label: 'ردیابی دانشجو', hint: 'جستجو و وضعیت دانشجویان', onClick: () => navigate('/panel/students') })
      items.push({
        key: 'reports-hub',
        icon: '📈',
        label: 'گزارشات',
        hint: 'چارچوب گزارش‌ها و قواعد رسمی',
        onClick: () => navigate('/panel/reports'),
      })
    }
    if (canViewSchedulerAutomation(u)) {
      items.push({
        key: 'automation-scheduler',
        icon: '⏱️',
        label: 'اتوماسیون زمان‌محور',
        hint: 'تقویم ترم، فرایندهای زمان‌دار و اجرای دستی',
        onClick: () => navigate('/panel/automation-scheduler'),
      })
    }
    if (u === 'admin') {
      items.push({ key: 'users', icon: '👥', label: 'مدیریت کاربران', hint: 'نقش‌ها و دسترسی‌ها', onClick: () => navigate('/panel/users') })
    }
    items.push({ key: 'profile', icon: '👤', label: 'پروفایل من', hint: 'اطلاعات شخصی و عکس', onClick: () => navigate('/panel/profile') })
    items.push({ key: 'guide', icon: '📖', label: 'راهنمای جامع', hint: 'آموزش گام‌به‌گام سامانه', onClick: () => navigate('/panel/guide') })
    return items
  }, [user?.role, navigate])

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">داشبورد</h1>
          <p className="page-subtitle">
            خوش آمدید، {user?.full_name_fa || user?.username} | نمای کلی سیستم اتوماسیون آموزشی
          </p>
        </div>
      </div>

      {/* دسترسی سریع: برای همه نمایش داده می‌شود؛ دکمه‌ها بر اساس نقش کاربر فیلتر می‌شوند */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <div>
            <h3 className="card-title">دسترسی سریع</h3>
            <p className="card-subtitle">میانبرهای پرکاربرد بر اساس نقش شما</p>
          </div>
        </div>
        <div className="quick-actions-grid">
          {quickActions.map((a) => (
            <button key={a.key} type="button" className="quick-action-btn" onClick={a.onClick}>
              <span className="quick-action-icon">{a.icon}</span>
              <span className="quick-action-label">{a.label}</span>
              <span className="quick-action-hint">{a.hint}</span>
            </button>
          ))}
        </div>
      </div>

      {loadError && (
        <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
          {loadError}
          {debugCount != null && ` | سرور ${debugCount} فرایند دارد — رفرش یا ورود مجدد`}
        </div>
      )}

      {/* کارت‌های آمار فقط برای ادمین و کارمند نمایش داده می‌شود */}
      {(userHasRole(user, 'staff')) && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon primary">⚙️</div>
            <div>
              <div className="stat-value">{loading ? '...' : stats?.active_processes ?? 0}</div>
              <div className="stat-label">فرایندهای فعال</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon success">📋</div>
            <div>
              <div className="stat-value">{loading ? '...' : stats?.active_rules ?? 0}</div>
              <div className="stat-label">قوانین فعال</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon info">👨‍🎓</div>
            <div>
              <div className="stat-value">{loading ? '...' : stats?.total_students ?? 0}</div>
              <div className="stat-label">تعداد دانشجویان</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon warning">🔄</div>
            <div>
              <div className="stat-value">{loading ? '...' : stats?.active_instances ?? 0}</div>
              <div className="stat-label">فرایندهای در جریان</div>
            </div>
          </div>
        </div>
      )}

      {user?.role === 'admin' && <PrimaryAdminOperatorFollowup />}

      {user?.role !== 'admin' && (
        <div className="dashboard-grid">
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">مربوط به شما</h3>
            </div>
            <div style={{ padding: '1.25rem' }}>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.95rem' }}>
                برای مشاهده فرایندها، کارتابل و کارهای مرتبط با نقش خود به پنل اختصاصی‌تان بروید.
              </p>
              <PortalQuickLink role={user?.role} navigate={navigate} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
