import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { processExecApi, studentApi } from '../services/api'

const processLabels = {
  start_therapy: 'آغاز درمان آموزشی',
  extra_session: 'جلسه اضافی درمان آموزشی',
  therapy_changes: 'تغییرات درمان آموزشی',
  therapy_session_increase: 'افزایش جلسات هفتگی',
  therapy_session_reduction: 'کاهش جلسات هفتگی',
  therapy_interruption: 'وقفه در درمان آموزشی',
  therapy_completion: 'تکمیل درمان آموزشی',
  therapy_early_termination: 'قطع زودرس درمان',
  therapist_session_cancellation: 'کنسل جلسه توسط درمانگر',
  student_session_cancellation: 'کنسل جلسه توسط دانشجو',
  attendance_tracking: 'حضور و غیاب',
  fee_determination: 'تعیین تکلیف هزینه جلسه',
  session_payment: 'پرداخت جلسات',
  unannounced_absence_reaction: 'واکنش به غیبت بدون اطلاع',
  educational_leave: 'مرخصی آموزشی',
}

const reviewStates = [
  'therapist_review', 'therapist_decision', 'awaiting_therapist',
  'therapist_confirmation', 'pending_therapist', 'waiting_therapist',
]

export default function TherapistPortal() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('dashboard')
  const [allStudents, setAllStudents] = useState([])
  const [pendingActions, setPendingActions] = useState([])
  const [myActiveInstances, setMyActiveInstances] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [triggerPayload, setTriggerPayload] = useState('{}')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [studentSearch, setStudentSearch] = useState('')

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
      const allActive = []
      for (const s of students) {
        try {
          const instRes = await processExecApi.studentInstances(s.id)
          const instances = instRes.data?.instances || []
          for (const inst of instances) {
            if (!inst.is_completed && !inst.is_cancelled) {
              allActive.push({ ...inst, student_code: s.student_code, student_id: s.id })
              if (isWaitingForTherapist(inst.current_state)) {
                pending.push({ ...inst, student_code: s.student_code, student_id: s.id })
              }
            }
          }
        } catch { /* skip */ }
      }
      setPendingActions(pending)
      setMyActiveInstances(allActive)
    } catch (err) {
      console.error('Load error:', err)
    } finally {
      setLoading(false)
    }
  }

  const isWaitingForTherapist = (state) => {
    if (!state) return false
    return reviewStates.some(rs => state.includes(rs)) ||
           state.includes('therapist') ||
           state.includes('review')
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
        showToast(`تصمیم ثبت شد: ${res.data.to_state}`)
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

  const filteredStudents = allStudents.filter(s => {
    if (!studentSearch) return true
    return s.student_code?.includes(studentSearch) || s.course_type?.includes(studentSearch)
  })

  const tabs = [
    { id: 'dashboard', label: 'داشبورد', icon: '📊' },
    { id: 'pending', label: `درخواست‌ها (${pendingActions.length})`, icon: '📥' },
    { id: 'students', label: 'دانشجویان', icon: '👨‍🎓' },
    { id: 'active', label: 'فرایندها', icon: '🔄' },
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
          <h1 className="page-title">پنل درمانگر</h1>
          <p className="page-subtitle">
            {user?.full_name_fa || user?.username} | مدیریت جلسات و دانشجویان
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
            <div className="stat-card">
              <div className="stat-icon warning">📥</div>
              <div>
                <div className="stat-value">{pendingActions.length}</div>
                <div className="stat-label">منتظر تصمیم شما</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon info">👨‍🎓</div>
              <div>
                <div className="stat-value">{allStudents.length}</div>
                <div className="stat-label">تعداد دانشجویان</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon primary">🔄</div>
              <div>
                <div className="stat-value">{myActiveInstances.length}</div>
                <div className="stat-label">فرایند فعال</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon success">✅</div>
              <div>
                <div className="stat-value">{allStudents.filter(s => s.therapy_started).length}</div>
                <div className="stat-label">دانشجو با درمان فعال</div>
              </div>
            </div>
          </div>

          <div className="dashboard-grid">
            {/* Urgent Pending */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">درخواست‌های فوری</h3>
                {pendingActions.length > 0 && (
                  <button className="btn btn-outline btn-sm" onClick={() => setActiveTab('pending')}>
                    مشاهده همه
                  </button>
                )}
              </div>
              {pendingActions.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>✅</div>
                  <p>درخواست منتظری وجود ندارد</p>
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
                          دانشجو: {p.student_code} | {p.current_state}
                        </div>
                      </div>
                      <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>منتظر</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Students Quick View */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">دانشجویان اخیر</h3>
                <button className="btn btn-outline btn-sm" onClick={() => setActiveTab('students')}>
                  همه
                </button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', maxHeight: '350px', overflowY: 'auto' }}>
                {allStudents.slice(0, 10).map(s => (
                  <div key={s.id} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '0.6rem 0.75rem', background: 'var(--bg)', borderRadius: '6px',
                    fontSize: '0.85rem',
                  }}>
                    <div>
                      <span style={{ fontWeight: 500 }}>{s.student_code}</span>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <span className={`badge ${s.course_type === 'comprehensive' ? 'badge-primary' : 'badge-info'}`}
                        style={{ fontSize: '0.65rem' }}>
                        {s.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                        {s.weekly_sessions} جلسه/هفته
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Pending Actions Tab */}
      {activeTab === 'pending' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">درخواست‌های منتظر تصمیم ({pendingActions.length})</h3>
            </div>
            {pendingActions.length === 0 ? (
              <div className="empty-state" style={{ padding: '3rem' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>✅</div>
                <p>همه درخواست‌ها بررسی شده‌اند</p>
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
                      border: selectedInstance === p.instance_id ? '2px solid var(--warning)' : '1px solid var(--border)',
                      background: selectedInstance === p.instance_id ? 'var(--warning-light)' : '#fff',
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

          {/* Detail Panel */}
          {instanceDetail && <InstanceDetailPanel
            instanceDetail={instanceDetail}
            availableTransitions={availableTransitions}
            triggerPayload={triggerPayload}
            setTriggerPayload={setTriggerPayload}
            triggerTransition={triggerTransition}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
            accentColor="var(--warning)"
          />}
        </div>
      )}

      {/* Students Tab */}
      {activeTab === 'students' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">لیست دانشجویان ({allStudents.length})</h3>
            <input
              type="text"
              placeholder="جستجوی دانشجو..."
              value={studentSearch}
              onChange={e => setStudentSearch(e.target.value)}
              className="form-input"
              style={{ width: '250px' }}
            />
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>کد دانشجویی</th>
                  <th>نوع دوره</th>
                  <th>ترم</th>
                  <th>جلسات هفتگی</th>
                  <th>وضعیت درمان</th>
                  <th>کارآموز</th>
                </tr>
              </thead>
              <tbody>
                {filteredStudents.map(s => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 600 }}>{s.student_code}</td>
                    <td>
                      <span className={`badge ${s.course_type === 'comprehensive' ? 'badge-primary' : 'badge-info'}`}>
                        {s.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'}
                      </span>
                    </td>
                    <td>{s.current_term} از {s.term_count}</td>
                    <td>{s.weekly_sessions} جلسه</td>
                    <td>
                      <span className={`badge ${s.therapy_started ? 'badge-success' : 'badge-warning'}`}>
                        {s.therapy_started ? 'فعال' : 'آغاز نشده'}
                      </span>
                    </td>
                    <td>{s.is_intern ? 'بله' : 'خیر'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredStudents.length === 0 && (
              <div className="empty-state" style={{ padding: '2rem' }}>
                <p>دانشجویی یافت نشد</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Active Processes Tab */}
      {activeTab === 'active' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">فرایندهای فعال ({myActiveInstances.length})</h3>
            </div>
            {myActiveInstances.length === 0 ? (
              <div className="empty-state" style={{ padding: '2rem' }}>
                <p>فرایند فعالی وجود ندارد</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {myActiveInstances.map(p => (
                  <button
                    key={p.instance_id}
                    onClick={() => viewInstance(p.instance_id)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer', textAlign: 'right',
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
                    <span className={`badge ${isWaitingForTherapist(p.current_state) ? 'badge-warning' : 'badge-info'}`}
                      style={{ fontSize: '0.7rem' }}>
                      {isWaitingForTherapist(p.current_state) ? 'منتظر شما' : 'در جریان'}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {instanceDetail && <InstanceDetailPanel
            instanceDetail={instanceDetail}
            availableTransitions={availableTransitions}
            triggerPayload={triggerPayload}
            setTriggerPayload={setTriggerPayload}
            triggerTransition={triggerTransition}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
            accentColor="var(--primary)"
          />}
        </div>
      )}
    </div>
  )
}

function InstanceDetailPanel({ instanceDetail, availableTransitions, triggerPayload, setTriggerPayload, triggerTransition, onClose, accentColor }) {
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
          <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت فعلی</label>
          <div style={{ fontWeight: 700, color: accentColor }}>{instanceDetail.current_state}</div>
        </div>
        <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
          <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>تاریخ شروع</label>
          <div style={{ fontWeight: 500 }}>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
        </div>
      </div>

      {instanceDetail.context_data && Object.keys(instanceDetail.context_data).length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '0.5rem' }}>داده‌های درخواست</label>
          <pre style={{
            fontSize: '0.75rem', background: '#1e293b', color: '#e2e8f0', padding: '1rem',
            borderRadius: '8px', direction: 'ltr', textAlign: 'left', maxHeight: '120px', overflow: 'auto',
          }}>
            {JSON.stringify(instanceDetail.context_data, null, 2)}
          </pre>
        </div>
      )}

      {availableTransitions.length > 0 && (
        <div style={{
          padding: '1.25rem', background: 'var(--warning-light)',
          borderRadius: '10px', marginBottom: '1.5rem', borderRight: '4px solid var(--warning)',
        }}>
          <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--warning)' }}>
            تصمیم شما
          </h4>
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
              const isApproval = t.trigger_event?.includes('approved') || t.trigger_event?.includes('confirm') || t.trigger_event?.includes('accept')
              const isReject = t.trigger_event?.includes('reject') || t.trigger_event?.includes('decline') || t.trigger_event?.includes('unavailable')
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
