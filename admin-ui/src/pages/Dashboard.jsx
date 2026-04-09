import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { dashboardApi, processApi, auditApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import { labelProcess, labelState } from '../utils/processDisplay'
import { resolveProcessSopOrder } from '../utils/processSopOrder'

function processCardInitial(nameFa) {
  if (!nameFa || typeof nameFa !== 'string') return '؟'
  const t = nameFa.trim()
  return t.length ? t[0] : '؟'
}

const portalByRole = {
  student: { path: '/panel/portal/student', label: 'پنل دانشجو', icon: '🎓' },
  therapist: { path: '/panel/portal/therapist', label: 'پنل درمانگر', icon: '💊' },
  supervisor: { path: '/panel/portal/supervisor', label: 'پنل سوپروایزر', icon: '👁️' },
  staff: { path: '/panel/portal/staff', label: 'پنل کارمند', icon: '🏢' },
  site_manager: { path: '/panel/portal/site-manager', label: 'پنل مسئول سایت', icon: '🏗️' },
  progress_committee: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  education_committee: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  supervision_committee: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  specialized_commission: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  therapy_committee_chair: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  therapy_committee_executor: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  deputy_education: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
  monitoring_committee_officer: { path: '/panel/portal/committee', label: 'پنل کمیته', icon: '📋' },
}

function PortalQuickLink({ role, navigate }) {
  const portal = role ? portalByRole[role] : null
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
  const [processes, setProcesses] = useState([])
  const [recentLogs, setRecentLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [debugCount, setDebugCount] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [seedingDemo, setSeedingDemo] = useState(false)

  const handleSyncMetadata = async () => {
    setSyncing(true)
    try {
      const res = await dashboardApi.syncMetadata()
      const msg = res.data?.message || `${res.data?.added ?? 0} فرایند اضافه شد`
      alert(msg)
      loadAll()
    } catch (err) {
      alert(err.response?.data?.detail || 'خطا در همگام‌سازی')
    } finally {
      setSyncing(false)
    }
  }

  const handleSeedDemoMatrix = async () => {
    if (
      !window.confirm(
        'بارگذاری دادهٔ دمو (حدود ۶۰+ دانشجو و کاربر تست) در همین دیتابیس سرور؟ ممکن است ۲ تا ۵ دقیقه طول بکشد. ادامه؟'
      )
    ) {
      return
    }
    setSeedingDemo(true)
    try {
      const res = await dashboardApi.seedDemoMatrix({
        matrix: true,
        scenarios: true,
        force: true,
      })
      const m = res.data?.matrix
      const ok = m?.ok_count
      const stuck = m?.stuck_count
      alert(
        `پایان.\nفرایندهای تکمیل‌شده در ماتریس: ${ok ?? '—'}\nگیرکرده: ${stuck ?? '—'}\nورود ادمین: admin / admin123 (تب رمز عبور + چالش)`
      )
      loadAll()
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'خطا در بارگذاری دمو')
    } finally {
      setSeedingDemo(false)
    }
  }

  useEffect(() => {
    loadAll()
  }, [user?.role])

  const loadAll = async () => {
    setLoadError(null)
    setDebugCount(null)
    const isAdmin = user?.role === 'admin'
    const isAdminOrStaff = isAdmin || user?.role === 'staff'
    try {
      // فقط برای ادمین/کارمند: آمار و لاگ و فرایندها را بگیر؛ کاربر غیرادمین این APIها را ندارد
      if (!isAdminOrStaff) {
        setStats(null)
        setRecentLogs([])
        setProcesses([])
        return
      }
      // هر endpoint جدا: اگر یکی ۵۰۰ بدهد بقیهٔ داشبورد خالی نشود (قبلاً Promise.all همه را می‌انداخت)
      const settled = await Promise.allSettled([
        dashboardApi.stats(),
        isAdmin ? auditApi.list({ limit: 8, offset: 0 }) : Promise.resolve({ data: { logs: [] } }),
        isAdmin ? processApi.list() : Promise.resolve({ data: [] }),
      ])
      const failedLabels = []
      if (settled[0].status === 'fulfilled') {
        setStats(settled[0].value.data)
      } else {
        setStats(null)
        failedLabels.push('آمار کلی')
        console.error('dashboard stats failed:', settled[0].reason)
      }
      if (settled[1].status === 'fulfilled') {
        setRecentLogs(settled[1].value.data?.logs || [])
      } else {
        setRecentLogs([])
        if (isAdmin) failedLabels.push('فعالیت‌های اخیر')
        console.error('audit list failed:', settled[1].reason)
      }
      if (settled[2].status === 'fulfilled') {
        const d = settled[2].value.data
        setProcesses(Array.isArray(d) ? d : [])
      } else {
        setProcesses([])
        if (isAdmin) failedLabels.push('لیست فرایندها')
        console.error('process list failed:', settled[2].reason)
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
      setProcesses([])
      setRecentLogs([])
      try {
        const d = await dashboardApi.debugProcessCount()
        setDebugCount(d.process_count)
      } catch (_) {}
    } finally {
      setLoading(false)
    }
  }

  const actionTypeLabel = (type) => {
    switch (type) {
      case 'transition': return { label: 'انتقال', cls: 'badge-info' }
      case 'process_start': return { label: 'شروع فرایند', cls: 'badge-success' }
      case 'process_updated': return { label: 'ویرایش فرایند', cls: 'badge-warning' }
      case 'rule_change': return { label: 'تغییر قانون', cls: 'badge-warning' }
      default: return { label: type, cls: 'badge-primary' }
    }
  }

  const quickActions = useMemo(() => {
    const u = user?.role
    const items = []
    if (u === 'student') {
      items.push({ key: 'student', icon: '🎓', label: 'پنل دانشجو', hint: 'پرونده، فرایندها و تکالیف', onClick: () => navigate('/panel/portal/student') })
    }
    if (u === 'therapist' || u === 'admin') {
      items.push({ key: 'therapist', icon: '💊', label: 'پنل درمانگر', hint: 'جلسات و پرونده‌های درمانی', onClick: () => navigate('/panel/portal/therapist') })
    }
    if (u === 'supervisor' || u === 'admin') {
      items.push({ key: 'supervisor', icon: '👁️', label: 'پنل سوپروایزر', hint: 'سوپرویژن و بازخورد', onClick: () => navigate('/panel/portal/supervisor') })
    }
    if (u === 'staff' || u === 'admin') {
      items.push({ key: 'staff', icon: '🏢', label: 'پنل کارمند', hint: 'کارتابل و امور اداری', onClick: () => navigate('/panel/portal/staff') })
    }
    if (u === 'site_manager' || u === 'admin') {
      items.push({ key: 'site', icon: '🏗️', label: 'پنل مسئول سایت', hint: 'هماهنگی و برنامه‌ریزی', onClick: () => navigate('/panel/portal/site-manager') })
    }
    if (['progress_committee', 'education_committee', 'supervision_committee', 'specialized_commission', 'therapy_committee_chair', 'therapy_committee_executor', 'deputy_education', 'monitoring_committee_officer', 'admin'].includes(u)) {
      items.push({ key: 'committee', icon: '📋', label: 'پنل کمیته', hint: 'جلسات و تصمیمات کمیته', onClick: () => navigate('/panel/portal/committee') })
    }
    if (u === 'admin') {
      items.push({ key: 'processes', icon: '⚙️', label: 'مدیریت فرایندها', hint: 'تعریف و ویرایش SOP', onClick: () => navigate('/panel/processes') })
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
    if (u === 'admin') {
      items.push({ key: 'users', icon: '👥', label: 'مدیریت کاربران', hint: 'نقش‌ها و دسترسی‌ها', onClick: () => navigate('/panel/users') })
    }
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

      {loadError && (
        <div className="toast toast-error" style={{ marginBottom: '1rem' }}>
          {loadError}
          {debugCount != null && ` | سرور ${debugCount} فرایند دارد — رفرش یا ورود مجدد`}
        </div>
      )}

      {!loadError && user?.role === 'admin' && !loading && stats && stats.total_students === 0 && (
        <div className="toast toast-error" style={{ marginBottom: '1rem' }}>
          هنوز هیچ دانشجویی در دیتابیس سرور ثبت نیست. اگر با Docker کار می‌کنید، بعد از به‌روزرسانی کد،{' '}
          <code style={{ direction: 'ltr', display: 'inline' }}>docker compose up -d --build api</code>
          {' '}بزنید تا با استارت اولیهٔ خالی، دادهٔ دمو (در صورت فعال بودن در compose) پر شود؛ یا همین‌جا از دکمهٔ «بارگذاری دادهٔ دمو» استفاده کنید.
        </div>
      )}

      {/* کارت‌های آمار فقط برای ادمین و کارمند نمایش داده می‌شود */}
      {(user?.role === 'admin' || user?.role === 'staff') && (
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

      <div className="dashboard-grid">
        {/* برای ادمین: فرایندهای SOP | برای بقیه: کارت مرتبط با نقش کاربر */}
        {user?.role === 'admin' ? (
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">فرایندهای SOP تعریف‌شده</h3>
                <p className="card-subtitle">برای ویرایش یا جزئیات، روی کارت فرایند کلیک کنید.</p>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button className="btn btn-outline btn-sm" onClick={handleSyncMetadata} disabled={syncing}>
                  {syncing ? '...' : 'همگام‌سازی از JSON'}
                </button>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={handleSeedDemoMatrix}
                  disabled={seedingDemo}
                  title="پر کردن دیتابیس همین سرور (برای Docker حتماً از اینجا یا API استفاده کنید)"
                >
                  {seedingDemo ? '...' : 'بارگذاری دادهٔ دمو (ماتریس + سناریوها)'}
                </button>
                <button className="btn btn-outline btn-sm" onClick={() => navigate('/panel/processes')}>
                  مدیریت
                </button>
              </div>
            </div>
            <div>
              {loading ? (
                <div className="empty-state" style={{ padding: '2rem' }}>در حال بارگذاری...</div>
              ) : processes.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>فرایندی تعریف نشده</div>
              ) : (
                <div className="dashboard-process-grid">
                  {processes.map((p) => (
                    <button
                      type="button"
                      key={p.id}
                      className="dashboard-process-card"
                      onClick={() => navigate(`/panel/processes/${p.id}`)}
                    >
                      <div className="dashboard-process-card-icon" aria-hidden>
                        {processCardInitial(p.name_fa)}
                      </div>
                      <div className="dashboard-process-card-body">
                        <div className="dashboard-process-card-title">{p.name_fa}</div>
                        {p.name_en ? (
                          <div className="dashboard-process-card-en">{p.name_en}</div>
                        ) : null}
                        <div className="dashboard-process-card-meta">
                          {resolveProcessSopOrder(p) != null ? (
                            <span className="badge" style={{ background: 'var(--surface-alt)', color: 'var(--text-secondary)' }} title="شماره مرحله در سند SOP">
                              SOP {resolveProcessSopOrder(p)}
                            </span>
                          ) : null}
                          <span className="badge badge-primary">{p.code}</span>
                          <span className={`badge ${p.is_active ? 'badge-success' : 'badge-danger'}`}>
                            {p.is_active ? 'فعال' : 'غیرفعال'}
                          </span>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-light)' }}>نسخه {p.version}</span>
                        </div>
                      </div>
                      <span className="dashboard-process-card-arrow" aria-hidden>‹</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
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
        )}

        {/* فعالیت‌های اخیر فقط برای ادمین (دسترسی به audit) */}
        {user?.role === 'admin' && (
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">فعالیت‌های اخیر</h3>
              <button className="btn btn-outline btn-sm" onClick={() => navigate('/panel/audit')}>
                مشاهده همه
              </button>
            </div>
            <div>
              {loading ? (
                <div className="empty-state" style={{ padding: '2rem' }}>در حال بارگذاری...</div>
              ) : recentLogs.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>هنوز فعالیتی ثبت نشده</div>
              ) : (
                <div className="activity-feed">
                  {recentLogs.map((log) => {
                    const at = actionTypeLabel(log.action_type)
                    return (
                      <div key={log.id} className="activity-item">
                        <div className="activity-dot" aria-hidden />
                        <div className="activity-item-text">
                          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                            <span className={`badge ${at.cls}`}>{at.label}</span>
                            {log.process_code && (
                              <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>{labelProcess(log.process_code)}</span>
                            )}
                          </div>
                          {log.from_state && log.to_state && (
                            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                              {labelState(log.from_state)} → {labelState(log.to_state)}
                            </div>
                          )}
                          <div className="activity-item-time">
                            {new Date(log.timestamp).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* دسترسی سریع: برای همه نمایش داده می‌شود؛ دکمه‌ها بر اساس نقش کاربر فیلتر می‌شوند */}
      <div className="card" style={{ marginTop: '1.5rem' }}>
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
    </div>
  )
}
