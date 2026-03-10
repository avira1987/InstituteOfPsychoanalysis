import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { processExecApi, studentApi } from '../services/api'

const processLabels = {
  attendance_tracking: 'حضور و غیاب',
  unannounced_absence_reaction: 'واکنش به غیبت بدون اطلاع',
  therapist_session_cancellation: 'کنسل جلسه درمانگر',
  student_session_cancellation: 'کنسل جلسه دانشجو',
  fee_determination: 'تعیین تکلیف هزینه جلسه',
  start_therapy: 'آغاز درمان آموزشی',
  therapy_changes: 'تغییرات درمان',
  therapy_interruption: 'وقفه درمان',
  therapy_completion: 'تکمیل درمان',
  extra_session: 'جلسه اضافی',
  session_payment: 'پرداخت جلسات',
  educational_leave: 'مرخصی آموزشی',
  supervisor_session_cancellation: 'کنسل جلسه سوپروایزر',
}

const siteManagerReviewStates = [
  'site_manager_review', 'site_manager_followup', 'pending_site_manager',
  'attendance_check', 'followup_required', 'site_review',
]

export default function SiteManagerPortal() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('dashboard')
  const [allStudents, setAllStudents] = useState([])
  const [pendingActions, setPendingActions] = useState([])
  const [attendanceAlerts, setAttendanceAlerts] = useState([])
  const [allActiveInstances, setAllActiveInstances] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [triggerPayload, setTriggerPayload] = useState('{}')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    try {
      const studentsRes = await studentApi.list().catch(() => ({ data: [] }))
      const students = studentsRes.data || []
      setAllStudents(students)

      const pending = []
      const alerts = []
      const allActive = []
      for (const s of students) {
        try {
          const instRes = await processExecApi.studentInstances(s.id)
          const instances = instRes.data?.instances || []
          for (const inst of instances) {
            if (!inst.is_completed && !inst.is_cancelled) {
              allActive.push({ ...inst, student_code: s.student_code, student_id: s.id })
              if (isWaitingForSiteManager(inst.current_state)) {
                pending.push({ ...inst, student_code: s.student_code, student_id: s.id })
              }
              if (isAttendanceRelated(inst.process_code, inst.current_state)) {
                alerts.push({ ...inst, student_code: s.student_code, student_id: s.id })
              }
            }
          }
        } catch { /* skip */ }
      }
      setPendingActions(pending)
      setAttendanceAlerts(alerts)
      setAllActiveInstances(allActive)
    } catch (err) {
      console.error('Load error:', err)
    } finally {
      setLoading(false)
    }
  }

  const isWaitingForSiteManager = (state) => {
    if (!state) return false
    return siteManagerReviewStates.some(rs => state.includes(rs)) ||
           state.includes('site_manager') || state.includes('followup')
  }

  const isAttendanceRelated = (processCode, state) => {
    return processCode?.includes('attendance') || processCode?.includes('absence') ||
           state?.includes('attendance') || state?.includes('absence')
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
        trigger_event: triggerEvent, payload,
      })
      if (res.data.success) {
        showToast(`عملیات انجام شد: ${res.data.to_state}`)
        viewInstance(selectedInstance)
        loadData()
      } else {
        showToast(res.data.error || 'خطا', 'error')
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
    { id: 'alerts', label: `هشدارها (${attendanceAlerts.length})`, icon: '🔔' },
    { id: 'pending', label: `پیگیری‌ها (${pendingActions.length})`, icon: '📋' },
    { id: 'overview', label: 'نمای کلی', icon: '👁️' },
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

      <div className="page-header">
        <div>
          <h1 className="page-title">پنل مسئول سایت</h1>
          <p className="page-subtitle">
            {user?.full_name_fa || user?.username} | نظارت بر حضور و غیاب و پیگیری‌ها
          </p>
        </div>
      </div>

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

      {/* Dashboard */}
      {activeTab === 'dashboard' && (
        <>
          <div className="stats-grid">
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('alerts')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('alerts') } }}
              title="مشاهده هشدارهای حضور و غیاب"
            >
              <div className="stat-icon danger">🔔</div>
              <div>
                <div className="stat-value">{attendanceAlerts.length}</div>
                <div className="stat-label">هشدار حضور و غیاب</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('pending')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('pending') } }}
              title="مشاهده پیگیری‌های منتظر"
            >
              <div className="stat-icon warning">📋</div>
              <div>
                <div className="stat-value">{pendingActions.length}</div>
                <div className="stat-label">پیگیری منتظر</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('overview')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('overview') } }}
              title="مشاهده نمای کلی و دانشجویان"
            >
              <div className="stat-icon info">👨‍🎓</div>
              <div>
                <div className="stat-value">{allStudents.length}</div>
                <div className="stat-label">دانشجویان</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('overview')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('overview') } }}
              title="مشاهده فرایندهای فعال"
            >
              <div className="stat-icon primary">🔄</div>
              <div>
                <div className="stat-value">{allActiveInstances.length}</div>
                <div className="stat-label">فرایند فعال</div>
              </div>
            </div>
          </div>

          <div className="dashboard-grid">
            {/* Attendance Alerts */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">هشدارهای حضور و غیاب</h3>
                {attendanceAlerts.length > 0 && (
                  <button className="btn btn-outline btn-sm" onClick={() => setActiveTab('alerts')}>
                    همه
                  </button>
                )}
              </div>
              {attendanceAlerts.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>✅</div>
                  <p>هشداری وجود ندارد</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {attendanceAlerts.slice(0, 5).map(a => (
                    <button
                      key={a.instance_id}
                      onClick={() => { viewInstance(a.instance_id); setActiveTab('alerts') }}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                        textAlign: 'right', border: '1px solid #fca5a5', background: '#fef2f2',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>
                          {processLabels[a.process_code] || a.process_code}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                          دانشجو: {a.student_code} | {a.current_state}
                        </div>
                      </div>
                      <span className="badge badge-danger" style={{ fontSize: '0.7rem' }}>هشدار</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Pending Follow-ups */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">پیگیری‌های منتظر</h3>
              </div>
              {pendingActions.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>📭</div>
                  <p>پیگیری منتظری وجود ندارد</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {pendingActions.slice(0, 5).map(p => (
                    <button
                      key={p.instance_id}
                      onClick={() => { viewInstance(p.instance_id); setActiveTab('pending') }}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                        textAlign: 'right', border: '1px solid #fde68a', background: '#fffbeb',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>
                          {processLabels[p.process_code] || p.process_code}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                          دانشجو: {p.student_code}
                        </div>
                      </div>
                      <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>منتظر</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Alerts Tab */}
      {activeTab === 'alerts' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">هشدارهای حضور و غیاب ({attendanceAlerts.length})</h3>
            </div>
            {attendanceAlerts.length === 0 ? (
              <div className="empty-state" style={{ padding: '3rem' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>✅</div>
                <p>هشداری وجود ندارد</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {attendanceAlerts.map(a => (
                  <button
                    key={a.instance_id}
                    onClick={() => viewInstance(a.instance_id)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                      textAlign: 'right',
                      border: selectedInstance === a.instance_id ? '2px solid var(--danger)' : '1px solid #fca5a5',
                      background: selectedInstance === a.instance_id ? 'var(--danger-light)' : '#fef2f2',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 500 }}>{processLabels[a.process_code] || a.process_code}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                        دانشجو: {a.student_code} | {a.current_state}
                      </div>
                    </div>
                    <span className="badge badge-danger" style={{ fontSize: '0.7rem' }}>هشدار</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {instanceDetail && <ActionPanel
            instanceDetail={instanceDetail}
            availableTransitions={availableTransitions}
            triggerPayload={triggerPayload}
            setTriggerPayload={setTriggerPayload}
            triggerTransition={triggerTransition}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
          />}
        </div>
      )}

      {/* Pending Tab */}
      {activeTab === 'pending' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">پیگیری‌ها ({pendingActions.length})</h3>
            </div>
            {pendingActions.length === 0 ? (
              <div className="empty-state" style={{ padding: '3rem' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>✅</div>
                <p>پیگیری منتظری وجود ندارد</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {pendingActions.map(p => (
                  <button
                    key={p.instance_id}
                    onClick={() => viewInstance(p.instance_id)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                      textAlign: 'right',
                      border: selectedInstance === p.instance_id ? '2px solid var(--primary)' : '1px solid var(--border)',
                      background: selectedInstance === p.instance_id ? 'var(--primary-light)' : '#fff',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 500 }}>{processLabels[p.process_code] || p.process_code}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                        دانشجو: {p.student_code} | {p.current_state}
                      </div>
                    </div>
                    <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>منتظر</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {instanceDetail && <ActionPanel
            instanceDetail={instanceDetail}
            availableTransitions={availableTransitions}
            triggerPayload={triggerPayload}
            setTriggerPayload={setTriggerPayload}
            triggerTransition={triggerTransition}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
          />}
        </div>
      )}

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">نمای کلی فرایندها ({allActiveInstances.length})</h3>
          </div>
          {allActiveInstances.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <p>فرایند فعالی وجود ندارد</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>فرایند</th>
                    <th>دانشجو</th>
                    <th>وضعیت</th>
                    <th>تاریخ شروع</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {allActiveInstances.map(p => (
                    <tr key={p.instance_id}>
                      <td style={{ fontWeight: 500 }}>{processLabels[p.process_code] || p.process_code}</td>
                      <td>{p.student_code}</td>
                      <td>
                        <span className={`badge ${isWaitingForSiteManager(p.current_state) ? 'badge-warning' : 'badge-info'}`}>
                          {p.current_state}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.82rem', color: '#6b7280' }}>
                        {p.started_at ? new Date(p.started_at).toLocaleDateString('fa-IR') : '-'}
                      </td>
                      <td>
                        <button className="btn btn-outline btn-sm" onClick={() => viewInstance(p.instance_id)}>
                          مشاهده
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {instanceDetail && (
            <div style={{ marginTop: '1.5rem' }}>
              <ActionPanel
                instanceDetail={instanceDetail}
                availableTransitions={availableTransitions}
                triggerPayload={triggerPayload}
                setTriggerPayload={setTriggerPayload}
                triggerTransition={triggerTransition}
                onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ActionPanel({ instanceDetail, availableTransitions, triggerPayload, setTriggerPayload, triggerTransition, onClose }) {
  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          {processLabels[instanceDetail.process_code] || instanceDetail.process_code}
        </h3>
        <button onClick={onClose} className="btn btn-outline btn-sm">بستن</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
          <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت</label>
          <div style={{ fontWeight: 700, color: 'var(--primary)' }}>{instanceDetail.current_state}</div>
        </div>
        <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
          <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>تاریخ</label>
          <div>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
        </div>
      </div>

      {availableTransitions.length > 0 && (
        <div style={{
          padding: '1.25rem', background: 'var(--warning-light)',
          borderRadius: '10px', marginBottom: '1.5rem', borderRight: '4px solid var(--warning)',
        }}>
          <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem' }}>اقدامات</h4>
          <textarea
            value={triggerPayload}
            onChange={e => setTriggerPayload(e.target.value)}
            placeholder='{"notes": "توضیحات..."}'
            style={{
              width: '100%', minHeight: '50px', padding: '0.5rem', borderRadius: '6px',
              border: '1px solid #d1d5db', fontFamily: 'monospace', fontSize: '0.8rem',
              direction: 'ltr', textAlign: 'left', marginBottom: '0.75rem', resize: 'vertical',
            }}
          />
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {availableTransitions.map((t, idx) => {
              const isApproval = t.trigger_event?.includes('done') || t.trigger_event?.includes('confirm')
              const isReject = t.trigger_event?.includes('reject') || t.trigger_event?.includes('escalate')
              return (
                <button
                  key={idx}
                  onClick={() => triggerTransition(t.trigger_event)}
                  style={{
                    padding: '0.6rem 1.2rem', borderRadius: '8px', border: 'none',
                    cursor: 'pointer', fontWeight: 500, fontSize: '0.85rem',
                    background: isApproval ? 'var(--success)' : isReject ? 'var(--danger)' : 'var(--primary)',
                    color: '#fff',
                  }}
                >
                  {t.description || t.trigger_event}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {instanceDetail.history && instanceDetail.history.length > 0 && (
        <div>
          <h4 style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem' }}>تاریخچه</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            {instanceDetail.history.map((h, idx) => (
              <div key={idx} style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.4rem 0.75rem', background: 'var(--bg)', borderRadius: '6px', fontSize: '0.8rem',
              }}>
                <span style={{ color: '#9ca3af', fontWeight: 600 }}>{idx + 1}.</span>
                <span style={{ color: '#6b7280' }}>{h.from_state || 'شروع'}</span>
                <span>→</span>
                <span style={{ fontWeight: 500 }}>{h.to_state}</span>
                <span style={{ color: '#9ca3af', marginRight: 'auto', fontSize: '0.7rem' }}>
                  {h.trigger_event} | {h.actor_role}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
