import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { processExecApi, studentApi } from '../services/api'

const processLabels = {
  educational_leave: 'مرخصی آموزشی',
  start_therapy: 'آغاز درمان آموزشی',
  extra_session: 'جلسه اضافی درمان آموزشی',
  session_payment: 'پرداخت جلسات',
  therapy_changes: 'تغییرات درمان آموزشی',
  therapy_session_increase: 'افزایش جلسات هفتگی درمان',
  therapy_session_reduction: 'کاهش جلسات هفتگی درمان',
  therapy_interruption: 'وقفه در درمان آموزشی',
  therapy_completion: 'تکمیل درمان آموزشی',
  therapy_early_termination: 'قطع زودرس درمان',
  student_session_cancellation: 'کنسل کردن جلسه درمان',
  supervision_block_transition: 'آغاز سوپرویژن بعدی',
  supervision_50h_completion: 'تکمیل دوره ۵۰ ساعته سوپرویژن',
  supervision_session_increase: 'افزایش جلسات سوپرویژن',
  extra_supervision_session: 'جلسه اضافی سوپرویژن',
  supervision_session_reduction: 'کاهش جلسات سوپرویژن',
  supervision_interruption: 'وقفه سوپرویژن',
  introductory_course_registration: 'ثبت‌نام دوره آشنایی',
  introductory_course_completion: 'تکمیل دوره آشنایی',
  comprehensive_course_registration: 'ثبت‌نام دوره جامع',
  comprehensive_term_start: 'آغاز ترم جامع',
  comprehensive_term_end: 'پایان ترم جامع',
  attendance_tracking: 'حضور و غیاب',
  fee_determination: 'تعیین تکلیف هزینه جلسه',
  upgrade_to_ta: 'ارتقا به دستیار آموزشی',
  internship_readiness_consultation: 'مشاوره آمادگی کارآموزی',
  student_non_registration: 'عدم ثبت‌نام دانشجو',
  mentor_private_sessions: 'جلسات خصوصی منتور',
}

const studentProcessCodes = [
  'educational_leave', 'start_therapy', 'extra_session', 'session_payment',
  'therapy_changes', 'therapy_session_increase', 'therapy_session_reduction',
  'therapy_interruption', 'student_session_cancellation', 'supervision_block_transition',
  'extra_supervision_session', 'supervision_session_increase', 'supervision_session_reduction',
  'introductory_course_registration', 'comprehensive_course_registration',
  'fee_determination', 'upgrade_to_ta', 'internship_readiness_consultation',
]

export default function StudentPortal() {
  const { user } = useAuth()
  const [studentProfile, setStudentProfile] = useState(null)
  const [activeProcesses, setActiveProcesses] = useState([])
  const [completedProcesses, setCompletedProcesses] = useState([])
  const [cancelledProcesses, setCancelledProcesses] = useState([])
  const [availableProcesses, setAvailableProcesses] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [triggerPayload, setTriggerPayload] = useState('{}')
  const [activeTab, setActiveTab] = useState('dashboard')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [processFilter, setProcessFilter] = useState('')

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    try {
      const defsRes = await processExecApi.definitions()
      let myProfile = null
      try {
        const meRes = await studentApi.me()
        myProfile = meRes.data
      } catch {
        if (user?.role === 'admin' || user?.role === 'staff') {
          const listRes = await studentApi.list().catch(() => ({ data: [] }))
          myProfile = listRes.data?.find(s => s.user_id === user?.id)
        }
      }
      setStudentProfile(myProfile)

      if (myProfile) {
        const instancesRes = await processExecApi.studentInstances(myProfile.id)
        const instances = instancesRes.data?.instances || []
        setActiveProcesses(instances.filter(i => !i.is_completed && !i.is_cancelled))
        setCompletedProcesses(instances.filter(i => i.is_completed))
        setCancelledProcesses(instances.filter(i => i.is_cancelled))

        // اگر primary_instance_id روی پروفایل تنظیم شده، این اینستنس را به‌صورت خودکار باز کن
        const primaryId = myProfile.extra_data?.primary_instance_id
        if (primaryId) {
          try {
            await viewInstance(primaryId)
            setActiveTab('processes')
          } catch (err) {
            console.error('Failed to auto-open primary instance:', err)
          }
        }
      }

      const allDefs = defsRes.data?.processes || []
      setAvailableProcesses(allDefs.filter(p =>
        studentProcessCodes.includes(p.code) || p.code?.includes('student')
      ))
    } catch (err) {
      console.error('Load error:', err)
    } finally {
      setLoading(false)
    }
  }

  const startProcess = async (processCode) => {
    if (!studentProfile) return showToast('پروفایل دانشجو یافت نشد', 'error')
    try {
      const res = await processExecApi.start({
        process_code: processCode,
        student_id: studentProfile.id,
      })
      showToast(`فرایند ${processLabels[processCode] || processCode} آغاز شد`)
      loadData()
      viewInstance(res.data.instance_id)
      setActiveTab('processes')
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا در آغاز فرایند', 'error')
    }
  }

  const viewInstance = async (instanceId) => {
    setSelectedInstance(instanceId)
    try {
      const [statusRes, transRes] = await Promise.all([
        processExecApi.status(instanceId),
        processExecApi.transitions(instanceId),
      ])
      setInstanceDetail(statusRes.data)
      setAvailableTransitions(transRes.data?.transitions || [])
    } catch (err) {
      console.error('View error:', err)
    }
  }

  const triggerTransition = async (triggerEvent) => {
    if (!selectedInstance) return
    try {
      let payload = {}
      try { payload = JSON.parse(triggerPayload) } catch { payload = {} }
      const res = await processExecApi.trigger(selectedInstance, {
        trigger_event: triggerEvent,
        payload,
      })
      if (res.data.success) {
        showToast(`انتقال انجام شد: ${res.data.to_state}`)
        viewInstance(selectedInstance)
        loadData()
      } else {
        showToast(res.data.error || 'خطا در انتقال', 'error')
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا', 'error')
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '4rem' }}>
        <div className="loading-spinner" />
      </div>
    )
  }

  const tabs = [
    { id: 'dashboard', label: 'داشبورد', icon: '📊' },
    { id: 'processes', label: 'فرایندها', icon: '🔄' },
    { id: 'requests', label: 'ثبت درخواست', icon: '📝' },
    { id: 'profile', label: 'پروفایل', icon: '👤' },
  ]

  return (
    <div>
      {toast && (
        <div style={{
          position: 'fixed', top: '1rem', left: '50%', transform: 'translateX(-50%)',
          padding: '0.75rem 1.5rem', borderRadius: '8px', zIndex: 1000, fontWeight: 500,
          background: toast.type === 'error' ? '#fef2f2' : '#f0fdf4',
          color: toast.type === 'error' ? '#dc2626' : '#16a34a',
          border: `1px solid ${toast.type === 'error' ? '#fca5a5' : '#86efac'}`,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        }}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">پنل دانشجو</h1>
          <p className="page-subtitle">
            {studentProfile
              ? `${user?.full_name_fa || user?.username} | کد دانشجویی: ${studentProfile.student_code} | دوره: ${studentProfile.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'}`
              : 'پروفایل دانشجو یافت نشد — لطفاً با مدیریت تماس بگیرید'}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="tab-bar">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`tab-item ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span style={{ marginLeft: '0.35rem' }}>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Dashboard Tab */}
      {activeTab === 'dashboard' && (
        <>
          <div className="stats-grid">
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('processes')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('processes') } }}
              title="مشاهده فرایندهای فعال"
            >
              <div className="stat-icon primary">🔄</div>
              <div>
                <div className="stat-value">{activeProcesses.length}</div>
                <div className="stat-label">فرایند فعال</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('processes')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('processes') } }}
              title="مشاهده فرایندهای تکمیل‌شده"
            >
              <div className="stat-icon success">✅</div>
              <div>
                <div className="stat-value">{completedProcesses.length}</div>
                <div className="stat-label">تکمیل‌شده</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('profile')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('profile') } }}
              title="مشاهده پروفایل و ترم فعلی"
            >
              <div className="stat-icon info">📅</div>
              <div>
                <div className="stat-value">{studentProfile?.current_term || '-'}</div>
                <div className="stat-label">ترم فعلی</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('profile')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('profile') } }}
              title="مشاهده پروفایل و جلسات هفتگی"
            >
              <div className="stat-icon warning">🗓️</div>
              <div>
                <div className="stat-value">{studentProfile?.weekly_sessions || '-'}</div>
                <div className="stat-label">جلسه / هفته</div>
              </div>
            </div>
          </div>

          <div className="dashboard-grid">
            {/* Active Processes */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">فرایندهای فعال</h3>
                <span className="badge badge-warning">{activeProcesses.length}</span>
              </div>
              {activeProcesses.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>📭</div>
                  <p>فرایند فعالی ندارید</p>
                  <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={() => setActiveTab('requests')}>
                    ثبت درخواست جدید
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {activeProcesses.map(p => (
                    <button
                      key={p.instance_id}
                      onClick={() => { viewInstance(p.instance_id); setActiveTab('processes') }}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                        textAlign: 'right', border: '1px solid #e5e7eb', background: '#fff',
                        transition: 'all 0.2s',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                          {processLabels[p.process_code] || p.process_code}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.25rem' }}>
                          وضعیت: {p.current_state}
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.25rem' }}>
                        <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>در حال بررسی</span>
                        {p.started_at && (
                          <span style={{ fontSize: '0.65rem', color: '#9ca3af' }}>
                            {new Date(p.started_at).toLocaleDateString('fa-IR')}
                          </span>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Recent Completed */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">آخرین فعالیت‌ها</h3>
              </div>
              {completedProcesses.length === 0 && cancelledProcesses.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>📋</div>
                  <p>هنوز فرایندی تکمیل نشده است</p>
                </div>
              ) : (
                <div className="timeline" style={{ paddingRight: '1.5rem' }}>
                  {[...completedProcesses, ...cancelledProcesses].slice(0, 8).map((p, idx) => (
                    <div key={p.instance_id} className="timeline-item">
                      <div className="timeline-dot" style={{
                        background: p.is_completed ? 'var(--success)' : 'var(--danger)',
                        boxShadow: `0 0 0 2px var(--bg-white), 0 0 0 4px ${p.is_completed ? 'var(--success)' : 'var(--danger)'}`,
                      }} />
                      <div className="timeline-content">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 500, fontSize: '0.85rem' }}>
                            {processLabels[p.process_code] || p.process_code}
                          </span>
                          <span className={`badge ${p.is_completed ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '0.65rem' }}>
                            {p.is_completed ? 'تکمیل' : 'لغو'}
                          </span>
                        </div>
                        {p.completed_at && (
                          <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.25rem' }}>
                            {new Date(p.completed_at).toLocaleDateString('fa-IR')}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Quick Actions */}
          {studentProfile && (
            <div className="card" style={{ marginTop: '1.5rem' }}>
              <div className="card-header">
                <h3 className="card-title">دسترسی سریع</h3>
              </div>
              <div className="quick-actions-grid">
                <button className="quick-action-btn" onClick={() => startProcess('session_payment')}>
                  <span className="quick-action-icon">💳</span>
                  <span>پرداخت جلسات</span>
                </button>
                <button className="quick-action-btn" onClick={() => startProcess('educational_leave')}>
                  <span className="quick-action-icon">🏖️</span>
                  <span>درخواست مرخصی</span>
                </button>
                <button className="quick-action-btn" onClick={() => startProcess('extra_session')}>
                  <span className="quick-action-icon">➕</span>
                  <span>جلسه اضافی</span>
                </button>
                <button className="quick-action-btn" onClick={() => startProcess('student_session_cancellation')}>
                  <span className="quick-action-icon">🚫</span>
                  <span>کنسل جلسه</span>
                </button>
                <button className="quick-action-btn" onClick={() => setActiveTab('requests')}>
                  <span className="quick-action-icon">📝</span>
                  <span>سایر درخواست‌ها</span>
                </button>
                <button className="quick-action-btn" onClick={() => setActiveTab('profile')}>
                  <span className="quick-action-icon">👤</span>
                  <span>مشاهده پروفایل</span>
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Processes Tab */}
      {activeTab === 'processes' && (
        <div style={{ display: 'grid', gridTemplateColumns: selectedInstance ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">همه فرایندها</h3>
            </div>

            {activeProcesses.length > 0 && (
              <>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--warning)', marginBottom: '0.5rem' }}>
                  فعال ({activeProcesses.length})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
                  {activeProcesses.map(p => (
                    <button
                      key={p.instance_id}
                      onClick={() => viewInstance(p.instance_id)}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                        textAlign: 'right',
                        border: selectedInstance === p.instance_id ? '2px solid var(--primary)' : '1px solid #e5e7eb',
                        background: selectedInstance === p.instance_id ? 'var(--primary-light)' : '#fff',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 500 }}>{processLabels[p.process_code] || p.process_code}</div>
                        <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>وضعیت: {p.current_state}</div>
                      </div>
                      <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>فعال</span>
                    </button>
                  ))}
                </div>
              </>
            )}

            {completedProcesses.length > 0 && (
              <>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--success)', marginBottom: '0.5rem' }}>
                  تکمیل‌شده ({completedProcesses.length})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginBottom: '1rem' }}>
                  {completedProcesses.slice(0, 10).map(p => (
                    <button
                      key={p.instance_id}
                      onClick={() => viewInstance(p.instance_id)}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.5rem 0.75rem', borderRadius: '6px', cursor: 'pointer',
                        textAlign: 'right', border: '1px solid #d1fae5', background: '#f0fdf4',
                        fontSize: '0.85rem',
                      }}
                    >
                      <span>{processLabels[p.process_code] || p.process_code}</span>
                      <span className="badge badge-success" style={{ fontSize: '0.65rem' }}>تکمیل</span>
                    </button>
                  ))}
                </div>
              </>
            )}

            {activeProcesses.length === 0 && completedProcesses.length === 0 && (
              <div className="empty-state" style={{ padding: '2rem' }}>
                <p>فرایندی ثبت نشده است</p>
              </div>
            )}
          </div>

          {/* Instance Detail Panel */}
          {instanceDetail && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">
                  {processLabels[instanceDetail.process_code] || instanceDetail.process_code}
                </h3>
                <button onClick={() => { setSelectedInstance(null); setInstanceDetail(null) }}
                  className="btn btn-outline btn-sm">بستن</button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت فعلی</label>
                  <div style={{ fontWeight: 700, color: 'var(--primary)', fontSize: '0.95rem' }}>{instanceDetail.current_state}</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>تاریخ شروع</label>
                  <div style={{ fontWeight: 500 }}>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت کلی</label>
                  {instanceDetail.is_completed
                    ? <span className="badge badge-success">تکمیل‌شده</span>
                    : instanceDetail.is_cancelled
                      ? <span className="badge badge-danger">لغو شده</span>
                      : <span className="badge badge-warning">در جریان</span>
                  }
                </div>
              </div>

              {/* Available Actions */}
              {availableTransitions.length > 0 && (
                <div style={{
                  padding: '1.25rem', background: 'linear-gradient(135deg, var(--primary-light) 0%, #f0f4ff 100%)',
                  borderRadius: '10px', marginBottom: '1.5rem', borderRight: '4px solid var(--primary)',
                }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--primary)' }}>
                    اقدامات ممکن
                  </h4>
                  <div style={{ marginBottom: '0.75rem' }}>
                    <textarea
                      value={triggerPayload}
                      onChange={e => setTriggerPayload(e.target.value)}
                      placeholder='{"key": "value"}'
                      style={{
                        width: '100%', minHeight: '50px', padding: '0.5rem', borderRadius: '6px',
                        border: '1px solid #d1d5db', fontFamily: 'monospace', fontSize: '0.8rem',
                        direction: 'ltr', textAlign: 'left', resize: 'vertical',
                      }}
                    />
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {availableTransitions.map((t, idx) => (
                      <button
                        key={idx}
                        onClick={() => triggerTransition(t.trigger_event)}
                        className="btn btn-primary"
                        style={{ fontSize: '0.85rem' }}
                      >
                        {t.description || t.trigger_event}
                        <span style={{ fontSize: '0.7rem', marginRight: '0.5rem', opacity: 0.7 }}>
                          → {t.to_state}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* History Timeline */}
              {instanceDetail.history && instanceDetail.history.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.75rem' }}>تاریخچه انتقالات</h4>
                  <div className="timeline">
                    {instanceDetail.history.map((h, idx) => (
                      <div key={idx} className="timeline-item">
                        <div className="timeline-dot" />
                        <div className="timeline-content">
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                            <span>
                              <span style={{ color: '#6b7280' }}>{h.from_state || 'شروع'}</span>
                              {' → '}
                              <span style={{ fontWeight: 600 }}>{h.to_state}</span>
                            </span>
                            <span style={{ fontSize: '0.7rem', color: '#9ca3af' }}>{h.actor_role}</span>
                          </div>
                          <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.2rem' }}>
                            {h.trigger_event}
                            {h.entered_at && ` | ${new Date(h.entered_at).toLocaleDateString('fa-IR')}`}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Request Tab */}
      {activeTab === 'requests' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">ثبت درخواست جدید</h3>
            <input
              type="text"
              placeholder="جستجوی فرایند..."
              value={processFilter}
              onChange={e => setProcessFilter(e.target.value)}
              className="form-input"
              style={{ width: '250px' }}
            />
          </div>
          {!studentProfile ? (
            <div className="empty-state" style={{ padding: '3rem' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⚠️</div>
              <p style={{ fontSize: '1.1rem', fontWeight: 500 }}>پروفایل دانشجو یافت نشد</p>
              <p style={{ marginTop: '0.5rem' }}>لطفاً با بخش اداری تماس بگیرید تا پروفایل شما ایجاد شود.</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
              {availableProcesses
                .filter(p => {
                  if (!processFilter) return true
                  const label = processLabels[p.code] || p.name_fa || p.code
                  return label.includes(processFilter) || p.code.includes(processFilter)
                })
                .map(p => {
                  const hasActive = activeProcesses.some(a => a.process_code === p.code)
                  return (
                    <div
                      key={p.code || p.id}
                      style={{
                        padding: '1.25rem', borderRadius: '10px',
                        border: hasActive ? '2px solid var(--warning)' : '1px solid var(--border)',
                        background: hasActive ? 'var(--warning-light)' : 'var(--bg-white)',
                        transition: 'all 0.2s',
                      }}
                    >
                      <div style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.95rem' }}>
                        {processLabels[p.code] || p.name_fa || p.code}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.75rem' }}>
                        {p.description || `کد: ${p.code}`}
                      </div>
                      {hasActive ? (
                        <span className="badge badge-warning">فرایند فعال دارید</span>
                      ) : (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => startProcess(p.code)}
                        >
                          آغاز فرایند
                        </button>
                      )}
                    </div>
                  )
                })}
              {availableProcesses.length === 0 && (
                <div className="empty-state" style={{ padding: '2rem', gridColumn: '1 / -1' }}>
                  <p>فرایندی تعریف نشده است</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">اطلاعات شخصی</h3>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <ProfileField label="نام و نام خانوادگی" value={user?.full_name_fa || '-'} />
              <ProfileField label="نام کاربری" value={user?.username || '-'} />
              <ProfileField label="ایمیل" value={user?.email || '-'} dir="ltr" />
              <ProfileField label="شماره تماس" value={user?.phone || '-'} dir="ltr" />
              <ProfileField label="نقش" value="دانشجو" />
            </div>
          </div>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">اطلاعات تحصیلی</h3>
            </div>
            {studentProfile ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <ProfileField label="کد دانشجویی" value={studentProfile.student_code} />
                <ProfileField label="نوع دوره" value={studentProfile.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'} />
                <ProfileField label="ترم فعلی" value={`${studentProfile.current_term} از ${studentProfile.term_count}`} />
                <ProfileField label="جلسات هفتگی" value={`${studentProfile.weekly_sessions} جلسه`} />
                <ProfileField label="درمان آغاز شده" value={studentProfile.therapy_started ? 'بله' : 'خیر'} />
                <ProfileField label="کارآموز" value={studentProfile.is_intern ? 'بله' : 'خیر'} />
              </div>
            ) : (
              <div className="empty-state" style={{ padding: '2rem' }}>
                <p>پروفایل دانشجو هنوز ایجاد نشده است</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function ProfileField({ label, value, dir }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '0.75rem 1rem', background: 'var(--bg)', borderRadius: '8px',
    }}>
      <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{label}</span>
      <span style={{ fontWeight: 600, direction: dir || 'rtl' }}>{value}</span>
    </div>
  )
}
