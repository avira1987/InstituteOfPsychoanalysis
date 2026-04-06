import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { processExecApi, studentApi, therapyApi } from '../services/api'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import { notesPayload } from '../utils/decisionPayload'
import InstanceContextSummary from '../components/InstanceContextSummary'
import DecisionNotesBlock from '../components/DecisionNotesBlock'

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
  const [decisionNotes, setDecisionNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [studentSearch, setStudentSearch] = useState('')
  const [therapySessions, setTherapySessions] = useState([])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  useEffect(() => { loadData() }, [])

  const loadTherapySessions = async () => {
    try {
      const r = await therapyApi.forTherapist()
      setTherapySessions(Array.isArray(r.data) ? r.data : [])
    } catch {
      setTherapySessions([])
    }
  }

  useEffect(() => {
    if (activeTab === 'sessions') loadTherapySessions()
  }, [activeTab])

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
      const payload = notesPayload(decisionNotes)
      const res = await processExecApi.trigger(selectedInstance, {
        trigger_event: triggerEvent, payload,
      })
      if (res.data.success) {
        showToast(`تصمیم ثبت شد: ${labelState(res.data.to_state)}`)
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
    { id: 'sessions', label: 'جلسات آنلاین', icon: '🎥' },
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
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('pending')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('pending') } }}
              title="مشاهده درخواست‌های منتظر تصمیم"
            >
              <div className="stat-icon warning">📥</div>
              <div>
                <div className="stat-value">{pendingActions.length}</div>
                <div className="stat-label">منتظر تصمیم شما</div>
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
              onClick={() => setActiveTab('active')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('active') } }}
              title="مشاهده فرایندهای فعال"
            >
              <div className="stat-icon primary">🔄</div>
              <div>
                <div className="stat-value">{myActiveInstances.length}</div>
                <div className="stat-label">فرایند فعال</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('students')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('students') } }}
              title="مشاهده دانشجویان با درمان فعال"
            >
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
                          {labelProcess(p.process_code)}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                          دانشجو: {formatStudentCodeDisplay(p.student_code)} | {labelState(p.current_state)}
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
                      <span style={{ fontWeight: 500 }}>{formatStudentCodeDisplay(s.student_code)}</span>
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
                      <div style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                        دانشجو: {formatStudentCodeDisplay(p.student_code)} | {labelState(p.current_state)}
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
            decisionNotes={decisionNotes}
            setDecisionNotes={setDecisionNotes}
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
                    <td style={{ fontWeight: 600 }}>{formatStudentCodeDisplay(s.student_code)}</td>
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

      {activeTab === 'sessions' && (
        <TherapistSessionsPanel
          sessions={therapySessions}
          onReload={loadTherapySessions}
          showToast={showToast}
        />
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
                      <div style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                        دانشجو: {formatStudentCodeDisplay(p.student_code)} | {labelState(p.current_state)}
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
            decisionNotes={decisionNotes}
            setDecisionNotes={setDecisionNotes}
            triggerTransition={triggerTransition}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
            accentColor="var(--primary)"
          />}
        </div>
      )}
    </div>
  )
}

function TherapistSessionsPanel({ sessions, onReload, showToast }) {
  const [draft, setDraft] = useState({})
  const setField = (id, field, value) => {
    setDraft(prev => ({
      ...prev,
      [id]: { ...prev[id], [field]: value },
    }))
  }
  const save = async (s) => {
    const row = draft[s.id] || {}
    const meetingUrl = row.meeting_url !== undefined ? row.meeting_url : (s.meeting_url || '')
    const provider = row.meeting_provider !== undefined ? row.meeting_provider : (s.meeting_provider || 'manual')
    const scoreRaw = row.instructor_score !== undefined ? row.instructor_score : (s.instructor_score ?? '')
    const comment = row.instructor_comment !== undefined ? row.instructor_comment : (s.instructor_comment || '')
    try {
      const payload = {
        meeting_url: meetingUrl || null,
        meeting_provider: provider || 'manual',
        instructor_comment: comment || null,
      }
      if (scoreRaw !== '' && scoreRaw != null) {
        const n = Number(scoreRaw)
        if (!Number.isNaN(n)) payload.instructor_score = n
      }
      await therapyApi.patchSession(s.id, payload)
      showToast('ذخیره شد')
      onReload()
    } catch (e) {
      showToast(e.response?.data?.detail || 'خطا در ذخیره', 'error')
    }
  }
  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">جلسات آنلاین — لینک و نمره</h3>
      </div>
      {sessions.length === 0 ? (
        <div className="empty-state" style={{ padding: '2rem' }}>
          <p>هیچ جلسه‌ای در تقویم شما ثبت نشده است.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {sessions.map(s => {
            const row = draft[s.id] || {}
            const meetingUrl = row.meeting_url !== undefined ? row.meeting_url : (s.meeting_url || '')
            const provider = row.meeting_provider !== undefined ? row.meeting_provider : (s.meeting_provider || 'manual')
            const score = row.instructor_score !== undefined ? row.instructor_score : (s.instructor_score ?? '')
            const comment = row.instructor_comment !== undefined ? row.instructor_comment : (s.instructor_comment || '')
            return (
              <div
                key={s.id}
                style={{
                  padding: '1rem', borderRadius: '8px', border: '1px solid var(--border)',
                  display: 'grid', gap: '0.5rem',
                }}
              >
                <div style={{ fontWeight: 600 }}>
                  تاریخ {s.session_date} | دانشجو: {s.student_id?.slice(0, 8)}…
                </div>
                <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                  پرداخت: {s.payment_status} | وضعیت: {s.status} | لینک فعال: {s.links_unlocked ? 'بله' : 'خیر'}
                </div>
                <input
                  className="form-input"
                  placeholder="لینک ورود (اسکای‌روم / الوکام و …)"
                  dir="ltr"
                  style={{ textAlign: 'left' }}
                  value={meetingUrl}
                  onChange={e => setField(s.id, 'meeting_url', e.target.value)}
                />
                <select
                  className="form-input"
                  value={provider}
                  onChange={e => setField(s.id, 'meeting_provider', e.target.value)}
                >
                  <option value="manual">دستی</option>
                  <option value="skyroom">اسکای‌روم</option>
                  <option value="voicoom">الووکام</option>
                </select>
                <input
                  className="form-input"
                  type="number"
                  placeholder="نمره (اختیاری)"
                  dir="ltr"
                  value={score}
                  onChange={e => setField(s.id, 'instructor_score', e.target.value)}
                />
                <textarea
                  className="form-input"
                  placeholder="نظر و بازخورد"
                  rows={2}
                  value={comment}
                  onChange={e => setField(s.id, 'instructor_comment', e.target.value)}
                />
                <button type="button" className="btn btn-primary btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => save(s)}>
                  ذخیره
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function InstanceDetailPanel({ instanceDetail, availableTransitions, decisionNotes, setDecisionNotes, triggerTransition, onClose, accentColor }) {
  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          {labelProcess(instanceDetail.process_code)}
        </h3>
        <button onClick={onClose} className="btn btn-outline btn-sm">بستن</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
          <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت فعلی</label>
          <div style={{ fontWeight: 700, color: accentColor }}>{labelState(instanceDetail.current_state)}</div>
        </div>
        <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
          <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>تاریخ شروع</label>
          <div style={{ fontWeight: 500 }}>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
        </div>
      </div>

      <InstanceContextSummary
        contextData={instanceDetail.context_data}
        history={instanceDetail.history}
        title="پرونده و سابقه (قبل از تصمیم)"
      />

      {availableTransitions.length > 0 && (
        <div style={{
          padding: '1.25rem', background: 'var(--warning-light)',
          borderRadius: '10px', marginBottom: '1.5rem', borderRight: '4px solid var(--warning)',
        }}>
          <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--warning)' }}>
            تصمیم شما
          </h4>
          <DecisionNotesBlock
            value={decisionNotes}
            onChange={setDecisionNotes}
            title="توضیح یا نظر (اختیاری)"
            hint="این متن همراه همان دکمه‌ای که می‌زنید در پرونده ثبت می‌شود."
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
    </div>
  )
}
