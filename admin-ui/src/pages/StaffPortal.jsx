import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { processExecApi, studentApi, userApi, auditApi } from '../services/api'

const processLabels = {
  educational_leave: 'مرخصی آموزشی',
  start_therapy: 'آغاز درمان آموزشی',
  extra_session: 'جلسه اضافی',
  session_payment: 'پرداخت جلسات',
  therapy_changes: 'تغییرات درمان',
  attendance_tracking: 'حضور و غیاب',
  fee_determination: 'تعیین تکلیف هزینه',
  therapy_session_increase: 'افزایش جلسات',
  therapy_session_reduction: 'کاهش جلسات',
  therapy_interruption: 'وقفه درمان',
  therapy_completion: 'تکمیل درمان',
  therapy_early_termination: 'قطع زودرس درمان',
  student_session_cancellation: 'کنسل جلسه دانشجو',
  therapist_session_cancellation: 'کنسل جلسه درمانگر',
  supervision_block_transition: 'آغاز سوپرویژن بعدی',
  supervision_50h_completion: 'تکمیل ۵۰ ساعته',
  introductory_course_registration: 'ثبت‌نام دوره آشنایی',
  comprehensive_course_registration: 'ثبت‌نام دوره جامع',
  comprehensive_term_start: 'آغاز ترم جامع',
  comprehensive_term_end: 'پایان ترم جامع',
  introductory_course_completion: 'تکمیل دوره آشنایی',
  student_non_registration: 'عدم ثبت‌نام',
  unannounced_absence_reaction: 'غیبت بدون اطلاع',
}

const staffReviewStates = [
  'staff_review', 'staff_verification', 'pending_staff',
  'office_review', 'payment_verification', 'payment_required',
  'awaiting_payment', 'document_check',
]

export default function StaffPortal() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('dashboard')
  const [allStudents, setAllStudents] = useState([])
  const [allUsers, setAllUsers] = useState([])
  const [pendingActions, setPendingActions] = useState([])
  const [allActiveInstances, setAllActiveInstances] = useState([])
  const [recentLogs, setRecentLogs] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [triggerPayload, setTriggerPayload] = useState('{}')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [studentSearch, setStudentSearch] = useState('')
  const [showNewStudent, setShowNewStudent] = useState(false)
  const [newStudent, setNewStudent] = useState({
    user_id: '', student_code: '', course_type: 'introductory',
    weekly_sessions: 1, term_count: 1, current_term: 1,
  })

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    try {
      const [studentsRes, usersRes, logsRes] = await Promise.all([
        studentApi.list().catch(() => ({ data: [] })),
        userApi.list().catch(() => ({ data: [] })),
        auditApi.list({ limit: 10, offset: 0 }).catch(() => ({ data: { logs: [] } })),
      ])
      const students = studentsRes.data || []
      setAllStudents(students)
      setAllUsers(usersRes.data || [])
      setRecentLogs(logsRes.data?.logs || [])

      const pending = []
      const allActive = []
      for (const s of students) {
        try {
          const instRes = await processExecApi.studentInstances(s.id)
          const instances = instRes.data?.instances || []
          for (const inst of instances) {
            if (!inst.is_completed && !inst.is_cancelled) {
              allActive.push({ ...inst, student_code: s.student_code, student_id: s.id })
              if (isWaitingForStaff(inst.current_state)) {
                pending.push({ ...inst, student_code: s.student_code, student_id: s.id })
              }
            }
          }
        } catch { /* skip */ }
      }
      setPendingActions(pending)
      setAllActiveInstances(allActive)
    } catch (err) {
      console.error('Load error:', err)
    } finally {
      setLoading(false)
    }
  }

  const isWaitingForStaff = (state) => {
    if (!state) return false
    return staffReviewStates.some(rs => state.includes(rs)) ||
           state.includes('staff') || state.includes('payment') || state.includes('office')
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

  const handleCreateStudent = async () => {
    try {
      await studentApi.create(newStudent)
      showToast('دانشجو با موفقیت ایجاد شد')
      setShowNewStudent(false)
      setNewStudent({ user_id: '', student_code: '', course_type: 'introductory', weekly_sessions: 1, term_count: 1, current_term: 1 })
      loadData()
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا در ایجاد دانشجو', 'error')
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '4rem' }}>
        <div className="loading-spinner" />
      </div>
    )
  }

  const studentUserIds = new Set(allStudents.map(s => s.user_id))
  const nonStudentUsers = allUsers.filter(u => !studentUserIds.has(u.id) && u.role === 'student')

  const filteredStudents = allStudents.filter(s => {
    if (!studentSearch) return true
    return s.student_code?.includes(studentSearch) || s.course_type?.includes(studentSearch)
  })

  const tabs = [
    { id: 'dashboard', label: 'داشبورد', icon: '📊' },
    { id: 'pending', label: `وظایف (${pendingActions.length})`, icon: '📥' },
    { id: 'students', label: 'دانشجویان', icon: '👨‍🎓' },
    { id: 'processes', label: 'فرایندها', icon: '🔄' },
    { id: 'activity', label: 'فعالیت‌ها', icon: '📝' },
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
          <h1 className="page-title">پنل کارمند دفتر</h1>
          <p className="page-subtitle">
            {user?.full_name_fa || user?.username} | مدیریت دانشجویان و پرداخت‌ها
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
              onClick={() => setActiveTab('pending')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('pending') } }}
              title="مشاهده وظایف منتظر"
            >
              <div className="stat-icon warning">📥</div>
              <div>
                <div className="stat-value">{pendingActions.length}</div>
                <div className="stat-label">وظایف منتظر</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('students')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('students') } }}
              title="مشاهده لیست دانشجویان"
            >
              <div className="stat-icon info">👨‍🎓</div>
              <div>
                <div className="stat-value">{allStudents.length}</div>
                <div className="stat-label">تعداد دانشجویان</div>
              </div>
            </div>
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
                <div className="stat-value">{allActiveInstances.length}</div>
                <div className="stat-label">فرایند فعال</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('activity')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('activity') } }}
              title="مشاهده فعالیت‌های اخیر"
            >
              <div className="stat-icon success">👥</div>
              <div>
                <div className="stat-value">{allUsers.length}</div>
                <div className="stat-label">کاربران سیستم</div>
              </div>
            </div>
          </div>

          <div className="dashboard-grid">
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">وظایف فوری</h3>
                {pendingActions.length > 0 && (
                  <button className="btn btn-outline btn-sm" onClick={() => setActiveTab('pending')}>
                    مشاهده همه
                  </button>
                )}
              </div>
              {pendingActions.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>✅</div>
                  <p>وظیفه منتظری وجود ندارد</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {pendingActions.slice(0, 6).map(p => (
                    <button
                      key={p.instance_id}
                      onClick={() => { viewInstance(p.instance_id); setActiveTab('pending') }}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.6rem 0.75rem', borderRadius: '6px', cursor: 'pointer',
                        textAlign: 'right', border: '1px solid #fde68a', background: '#fffbeb',
                        fontSize: '0.85rem',
                      }}
                    >
                      <div>
                        <span style={{ fontWeight: 500 }}>{processLabels[p.process_code] || p.process_code}</span>
                        <span style={{ fontSize: '0.7rem', color: '#6b7280', marginRight: '0.5rem' }}>
                          | {p.student_code}
                        </span>
                      </div>
                      <span className="badge badge-warning" style={{ fontSize: '0.65rem' }}>منتظر</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-header">
                <h3 className="card-title">فعالیت‌های اخیر</h3>
              </div>
              {recentLogs.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <p>فعالیتی ثبت نشده</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  {recentLogs.slice(0, 8).map(log => (
                    <div key={log.id} className="activity-item" style={{ paddingTop: '0.5rem', paddingBottom: '0.5rem' }}>
                      <div className="activity-dot" />
                      <div style={{ flex: 1, fontSize: '0.82rem' }}>
                        <span className={`badge ${log.action_type === 'transition' ? 'badge-info' : 'badge-primary'}`}
                          style={{ fontSize: '0.65rem', marginLeft: '0.5rem' }}>
                          {log.action_type === 'transition' ? 'انتقال' : log.action_type}
                        </span>
                        <span style={{ fontWeight: 500 }}>{log.process_code}</span>
                        {log.from_state && (
                          <span style={{ color: '#6b7280', fontSize: '0.75rem' }}>
                            {' '}{log.from_state} → {log.to_state}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="card" style={{ marginTop: '1.5rem' }}>
            <div className="card-header">
              <h3 className="card-title">دسترسی سریع</h3>
            </div>
            <div className="quick-actions-grid">
              <button className="quick-action-btn" onClick={() => { setActiveTab('students'); setShowNewStudent(true) }}>
                <span className="quick-action-icon">➕</span>
                <span>ایجاد دانشجو</span>
              </button>
              <button className="quick-action-btn" onClick={() => setActiveTab('pending')}>
                <span className="quick-action-icon">📥</span>
                <span>بررسی وظایف</span>
              </button>
              <button className="quick-action-btn" onClick={() => setActiveTab('students')}>
                <span className="quick-action-icon">👨‍🎓</span>
                <span>لیست دانشجویان</span>
              </button>
              <button className="quick-action-btn" onClick={() => setActiveTab('processes')}>
                <span className="quick-action-icon">🔄</span>
                <span>فرایندهای فعال</span>
              </button>
            </div>
          </div>
        </>
      )}

      {/* Pending Tab */}
      {activeTab === 'pending' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">وظایف منتظر ({pendingActions.length})</h3>
            </div>
            {pendingActions.length === 0 ? (
              <div className="empty-state" style={{ padding: '3rem' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>✅</div>
                <p>همه وظایف انجام شده‌اند</p>
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
                        دانشجو: {p.student_code} | وضعیت: {p.current_state}
                      </div>
                    </div>
                    <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>منتظر</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {instanceDetail && <DetailPanel
            instanceDetail={instanceDetail}
            availableTransitions={availableTransitions}
            triggerPayload={triggerPayload}
            setTriggerPayload={setTriggerPayload}
            triggerTransition={triggerTransition}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
          />}
        </div>
      )}

      {/* Students Tab */}
      {activeTab === 'students' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">مدیریت دانشجویان ({allStudents.length})</h3>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type="text"
                placeholder="جستجو..."
                value={studentSearch}
                onChange={e => setStudentSearch(e.target.value)}
                className="form-input"
                style={{ width: '180px' }}
              />
              <button className="btn btn-primary btn-sm" onClick={() => setShowNewStudent(!showNewStudent)}>
                {showNewStudent ? 'لغو' : '+ دانشجوی جدید'}
              </button>
            </div>
          </div>

          {showNewStudent && (
            <div style={{
              padding: '1.5rem', background: 'var(--bg)', borderRadius: '10px',
              marginBottom: '1.5rem', border: '1px solid var(--border)',
            }}>
              <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '1rem' }}>ایجاد دانشجوی جدید</h4>
              <div className="inline-form">
                <div className="form-group">
                  <label className="form-label">کاربر</label>
                  <select className="form-input" value={newStudent.user_id}
                    onChange={e => setNewStudent({ ...newStudent, user_id: e.target.value })}>
                    <option value="">انتخاب کنید...</option>
                    {nonStudentUsers.map(u => (
                      <option key={u.id} value={u.id}>{u.full_name_fa || u.username} ({u.username})</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">کد دانشجویی</label>
                  <input className="form-input" value={newStudent.student_code}
                    onChange={e => setNewStudent({ ...newStudent, student_code: e.target.value })}
                    placeholder="مثلاً: STU-001" />
                </div>
                <div className="form-group">
                  <label className="form-label">نوع دوره</label>
                  <select className="form-input" value={newStudent.course_type}
                    onChange={e => setNewStudent({ ...newStudent, course_type: e.target.value })}>
                    <option value="introductory">آشنایی</option>
                    <option value="comprehensive">جامع</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">جلسات هفتگی</label>
                  <input className="form-input" type="number" min="1" max="7"
                    value={newStudent.weekly_sessions}
                    onChange={e => setNewStudent({ ...newStudent, weekly_sessions: parseInt(e.target.value) || 1 })} />
                </div>
              </div>
              <button className="btn btn-success" style={{ marginTop: '1rem' }} onClick={handleCreateStudent}>
                ایجاد دانشجو
              </button>
            </div>
          )}

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>کد دانشجویی</th>
                  <th>نوع دوره</th>
                  <th>ترم</th>
                  <th>جلسات</th>
                  <th>درمان</th>
                  <th>کارآموز</th>
                  <th>عملیات</th>
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
                    <td>{s.current_term}/{s.term_count}</td>
                    <td>{s.weekly_sessions}</td>
                    <td>
                      <span className={`badge ${s.therapy_started ? 'badge-success' : 'badge-warning'}`}>
                        {s.therapy_started ? 'فعال' : 'آغاز نشده'}
                      </span>
                    </td>
                    <td>{s.is_intern ? 'بله' : 'خیر'}</td>
                    <td>
                      <button className="btn btn-outline btn-sm" onClick={() => {
                        setActiveTab('processes')
                        // Filter will show processes for this student
                      }}>
                        فرایندها
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Processes Tab */}
      {activeTab === 'processes' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">فرایندهای فعال ({allActiveInstances.length})</h3>
            </div>
            {allActiveInstances.length === 0 ? (
              <div className="empty-state" style={{ padding: '2rem' }}>
                <p>فرایند فعالی وجود ندارد</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '600px', overflowY: 'auto' }}>
                {allActiveInstances.map(p => (
                  <button
                    key={p.instance_id}
                    onClick={() => viewInstance(p.instance_id)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '0.65rem 0.75rem', borderRadius: '8px', cursor: 'pointer',
                      textAlign: 'right',
                      border: selectedInstance === p.instance_id ? '2px solid var(--primary)' : '1px solid var(--border)',
                      background: selectedInstance === p.instance_id ? 'var(--primary-light)' : '#fff',
                      fontSize: '0.85rem',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 500 }}>{processLabels[p.process_code] || p.process_code}</div>
                      <div style={{ fontSize: '0.7rem', color: '#6b7280' }}>
                        {p.student_code} | {p.current_state}
                      </div>
                    </div>
                    <span className={`badge ${isWaitingForStaff(p.current_state) ? 'badge-warning' : 'badge-info'}`}
                      style={{ fontSize: '0.65rem' }}>
                      {isWaitingForStaff(p.current_state) ? 'منتظر شما' : 'در جریان'}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {instanceDetail && <DetailPanel
            instanceDetail={instanceDetail}
            availableTransitions={availableTransitions}
            triggerPayload={triggerPayload}
            setTriggerPayload={setTriggerPayload}
            triggerTransition={triggerTransition}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
          />}
        </div>
      )}

      {/* Activity Tab */}
      {activeTab === 'activity' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">سوابق فعالیت</h3>
          </div>
          {recentLogs.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <p>فعالیتی ثبت نشده</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>نوع</th>
                    <th>فرایند</th>
                    <th>از وضعیت</th>
                    <th>به وضعیت</th>
                    <th>بازیگر</th>
                    <th>زمان</th>
                  </tr>
                </thead>
                <tbody>
                  {recentLogs.map(log => (
                    <tr key={log.id}>
                      <td>
                        <span className={`badge ${log.action_type === 'transition' ? 'badge-info' : 'badge-primary'}`}>
                          {log.action_type === 'transition' ? 'انتقال' : log.action_type}
                        </span>
                      </td>
                      <td style={{ fontWeight: 500 }}>
                        {processLabels[log.process_code] || log.process_code}
                      </td>
                      <td style={{ fontSize: '0.82rem' }}>{log.from_state || '-'}</td>
                      <td style={{ fontSize: '0.82rem' }}>{log.to_state || '-'}</td>
                      <td style={{ fontSize: '0.82rem' }}>{log.actor_name || log.actor_role || '-'}</td>
                      <td style={{ fontSize: '0.78rem', color: '#6b7280' }}>
                        {new Date(log.timestamp).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DetailPanel({ instanceDetail, availableTransitions, triggerPayload, setTriggerPayload, triggerTransition, onClose }) {
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
          <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>تاریخ شروع</label>
          <div>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
        </div>
      </div>

      {instanceDetail.context_data && Object.keys(instanceDetail.context_data).length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '0.5rem' }}>داده‌ها</label>
          <pre style={{
            fontSize: '0.75rem', background: '#1e293b', color: '#e2e8f0', padding: '1rem',
            borderRadius: '8px', direction: 'ltr', textAlign: 'left', maxHeight: '100px', overflow: 'auto',
          }}>
            {JSON.stringify(instanceDetail.context_data, null, 2)}
          </pre>
        </div>
      )}

      {availableTransitions.length > 0 && (
        <div style={{
          padding: '1.25rem', background: 'var(--info-light)',
          borderRadius: '10px', marginBottom: '1.5rem', borderRight: '4px solid var(--info)',
        }}>
          <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--info)' }}>اقدامات</h4>
          <textarea
            value={triggerPayload}
            onChange={e => setTriggerPayload(e.target.value)}
            placeholder='{"key": "value"}'
            style={{
              width: '100%', minHeight: '50px', padding: '0.5rem', borderRadius: '6px',
              border: '1px solid #d1d5db', fontFamily: 'monospace', fontSize: '0.8rem',
              direction: 'ltr', textAlign: 'left', marginBottom: '0.75rem', resize: 'vertical',
            }}
          />
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {availableTransitions.map((t, idx) => {
              const isApproval = t.trigger_event?.includes('approved') || t.trigger_event?.includes('confirm') || t.trigger_event?.includes('verified')
              const isReject = t.trigger_event?.includes('reject') || t.trigger_event?.includes('decline')
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
