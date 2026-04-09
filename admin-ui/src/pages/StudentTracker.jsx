import React, { useState, useEffect } from 'react'
import { studentApi, processExecApi, processApi, userApi } from '../services/api'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import { notesPayload } from '../utils/decisionPayload'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import InstanceContextSummary from '../components/InstanceContextSummary'
import DecisionNotesBlock from '../components/DecisionNotesBlock'

export default function StudentTracker() {
  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [toast, setToast] = useState(null)

  // Selected student
  const [selectedStudent, setSelectedStudent] = useState(null)
  const [instances, setInstances] = useState([])
  const [instanceStatus, setInstanceStatus] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')

  // Create student form
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    user_id: '', student_code: '', course_type: 'comprehensive', is_intern: false, term_count: 1, current_term: 1, weekly_sessions: 1,
  })

  // Start process form
  const [showStartProcess, setShowStartProcess] = useState(false)
  const [processDefinitions, setProcessDefinitions] = useState([])
  const [startForm, setStartForm] = useState({ process_code: '', student_id: '' })

  // Users for user_id selection
  const [users, setUsers] = useState([])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    loadStudents()
  }, [])

  const loadStudents = async () => {
    try {
      setError(null)
      const res = await studentApi.list({ tracker_summary: true })
      setStudents(Array.isArray(res.data) ? res.data : [])
    } catch (err) {
      console.error('Failed to load students:', err)
      setError('خطا در بارگذاری لیست دانشجویان: ' + (err.response?.data?.detail || err.message))
      setStudents([])
    } finally {
      setLoading(false)
    }
  }

  const loadStudentInstances = async (studentId) => {
    try {
      const res = await processExecApi.studentInstances(studentId)
      setInstances(res.data.instances || [])
      setSelectedStudent(studentId)
      setInstanceStatus(null)
      setAvailableTransitions([])
    } catch (err) {
      console.error('Failed to load instances:', err)
    }
  }

  const loadInstanceStatus = async (instanceId) => {
    try {
      const [statusRes, transRes] = await Promise.all([
        processExecApi.status(instanceId),
        processExecApi.transitions(instanceId),
      ])
      setInstanceStatus(statusRes.data)
      setAvailableTransitions(transRes.data.transitions || [])
      setDecisionNotes('')
    } catch (err) {
      console.error('Failed to load status:', err)
    }
  }

  const handleTrigger = async (instanceId, transition) => {
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    try {
      let payload = notesPayload(decisionNotes)
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
      if (toState) payload.to_state = toState
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
      })
      if (res.data.success) {
        showToast(`انتقال موفق: ${labelState(res.data.from_state)} → ${labelState(res.data.to_state)}`)
        await loadInstanceStatus(instanceId)
        await loadStudentInstances(selectedStudent)
      } else {
        showToast('خطا: ' + (res.data.error || 'انتقال انجام نشد'), 'error')
      }
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const handleCreateStudent = async (e) => {
    e.preventDefault()
    try {
      await studentApi.create(createForm)
      showToast('دانشجو با موفقیت ایجاد شد')
      setShowCreate(false)
      setCreateForm({ user_id: '', student_code: '', course_type: 'comprehensive', is_intern: false, term_count: 1, current_term: 1, weekly_sessions: 1 })
      loadStudents()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const handleStartProcess = async (e) => {
    e.preventDefault()
    try {
      const res = await processExecApi.start(startForm)
      showToast(`فرایند «${labelProcess(startForm.process_code)}» شروع شد`)
      setShowStartProcess(false)
      if (selectedStudent) {
        loadStudentInstances(selectedStudent)
      }
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const openStartProcess = async (studentId) => {
    setStartForm({ process_code: '', student_id: studentId })
    try {
      const res = await processApi.list()
      setProcessDefinitions(res.data.filter((p) => p.is_active))
    } catch (err) {
      console.error(err)
    }
    setShowStartProcess(true)
  }

  const openCreateStudent = async () => {
    try {
      const res = await userApi.list()
      setUsers(res.data.filter((u) => u.is_active))
    } catch (err) {
      console.error(err)
    }
    setShowCreate(true)
  }

  const closeStudentDetail = () => {
    setSelectedStudent(null)
    setInstances([])
    setInstanceStatus(null)
    setAvailableTransitions([])
    setDecisionNotes('')
  }

  const courseTypeLabel = (type) => {
    switch (type) {
      case 'comprehensive': return 'جامع'
      case 'introductory': return 'آشنایی'
      default: return type
    }
  }

  const filteredStudents = (Array.isArray(students) ? students : []).filter((s) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (s.student_code || '').toLowerCase().includes(q)
  })

  return (
    <div>
      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}

      {/* Error display */}
      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '8px', padding: '1rem', marginBottom: '1.5rem', color: '#991b1b' }}>
          <strong>خطا: </strong>{error}
          <button onClick={loadStudents} style={{ marginRight: '1rem', padding: '0.25rem 0.75rem', background: '#ef4444', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>تلاش مجدد</button>
        </div>
      )}

      {/* Start Process Modal */}
      {showStartProcess && (
        <div className="modal-overlay" onClick={() => setShowStartProcess(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>شروع فرایند جدید</h3>
              <button className="modal-close" onClick={() => setShowStartProcess(false)}>&times;</button>
            </div>
            <div className="modal-body">
              <form onSubmit={handleStartProcess}>
                <div className="form-group">
                  <label className="form-label">فرایند</label>
                  <select className="form-input" value={startForm.process_code} onChange={(e) => setStartForm({ ...startForm, process_code: e.target.value })} required>
                    <option value="">انتخاب فرایند...</option>
                    {processDefinitions.map((p) => (
                      <option key={p.code} value={p.code}>{p.name_fa} ({p.code})</option>
                    ))}
                  </select>
                </div>
                <button className="btn btn-primary" type="submit" style={{ marginTop: '1rem' }}>شروع فرایند</button>
              </form>
            </div>
          </div>
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">ردیابی دانشجو</h1>
          <p className="page-subtitle">نمایش وضعیت هر دانشجو در تمام فرایندها | مجموع: {students.length} دانشجو</p>
        </div>
        <button className="btn btn-primary" onClick={openCreateStudent}>
          + دانشجوی جدید
        </button>
      </div>

      {/* Create Student Form */}
      {showCreate && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <h3 className="card-title">ایجاد پروفایل دانشجو</h3>
            <button className="btn btn-outline btn-sm" onClick={() => setShowCreate(false)}>لغو</button>
          </div>
          <form onSubmit={handleCreateStudent} className="form-grid-responsive-3">
            <div className="form-group">
              <label className="form-label">کاربر</label>
              <select className="form-input" value={createForm.user_id} onChange={(e) => setCreateForm({ ...createForm, user_id: e.target.value })} required>
                <option value="">انتخاب کاربر...</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>{u.full_name_fa || u.username} ({u.role})</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">کد دانشجویی</label>
              <input className="form-input" value={createForm.student_code} onChange={(e) => setCreateForm({ ...createForm, student_code: e.target.value })} required style={{ direction: 'ltr' }} />
            </div>
            <div className="form-group">
              <label className="form-label">نوع دوره</label>
              <select className="form-input" value={createForm.course_type} onChange={(e) => setCreateForm({ ...createForm, course_type: e.target.value })}>
                <option value="comprehensive">جامع</option>
                <option value="introductory">آشنایی</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">تعداد ترم</label>
              <input className="form-input" type="number" min="1" value={createForm.term_count} onChange={(e) => setCreateForm({ ...createForm, term_count: parseInt(e.target.value) })} />
            </div>
            <div className="form-group">
              <label className="form-label">ترم فعلی</label>
              <input className="form-input" type="number" min="1" value={createForm.current_term} onChange={(e) => setCreateForm({ ...createForm, current_term: parseInt(e.target.value) })} />
            </div>
            <div className="form-group">
              <label className="form-label">جلسات هفتگی</label>
              <input className="form-input" type="number" min="1" value={createForm.weekly_sessions} onChange={(e) => setCreateForm({ ...createForm, weekly_sessions: parseInt(e.target.value) })} />
            </div>
            <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', paddingTop: '1.5rem' }}>
              <input type="checkbox" id="is_intern" checked={createForm.is_intern} onChange={(e) => setCreateForm({ ...createForm, is_intern: e.target.checked })} />
              <label htmlFor="is_intern" style={{ fontSize: '0.9rem' }}>انترن</label>
            </div>
            <div><button className="btn btn-primary" type="submit">ایجاد</button></div>
          </form>
        </div>
      )}

      {/* Search */}
      <div style={{ marginBottom: '1.5rem' }}>
        <input
          className="form-input"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="جستجو با کد دانشجویی..."
          style={{ maxWidth: '350px' }}
        />
      </div>

      <div>
        {/* Students List */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">لیست دانشجویان</h3>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>کد</th>
                  <th>دوره</th>
                  <th>ترم</th>
                  <th>پیشرفت مسیر</th>
                  <th>اقدام معلق (از دید دانشجو)</th>
                  <th>انترن</th>
                  <th>درمان</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan="8" style={{ textAlign: 'center', padding: '2rem' }}>در حال بارگذاری...</td></tr>
                ) : filteredStudents.length === 0 ? (
                  <tr><td colSpan="8" style={{ textAlign: 'center', padding: '2rem' }}>دانشجویی یافت نشد</td></tr>
                ) : (
                  filteredStudents.map((s) => (
                    <tr key={s.id} style={{ background: selectedStudent === s.id ? 'var(--primary-light)' : '' }}>
                      <td><strong>{formatStudentCodeDisplay(s.student_code)}</strong></td>
                      <td>{courseTypeLabel(s.course_type)}</td>
                      <td>{s.current_term}/{s.term_count}</td>
                      <td style={{ minWidth: '120px' }}>
                        {s.graduation_progress_pct != null ? (
                          <div>
                            <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>{s.graduation_progress_pct}%</div>
                            <div
                              style={{
                                height: '6px',
                                borderRadius: '4px',
                                background: '#e5e7eb',
                                overflow: 'hidden',
                              }}
                              title={s.primary_process_name_fa || ''}
                            >
                              <div
                                style={{
                                  height: '100%',
                                  width: `${Math.min(100, s.graduation_progress_pct)}%`,
                                  background: 'var(--primary)',
                                  borderRadius: '4px',
                                }}
                              />
                            </div>
                            {s.primary_process_name_fa && (
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }} title={s.primary_current_state ? labelState(s.primary_current_state) : ''}>
                                {s.primary_process_name_fa}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>—</span>
                        )}
                      </td>
                      <td style={{ maxWidth: '280px', fontSize: '0.85rem', lineHeight: 1.45 }}>
                        {s.pending_action_fa ? (
                          <span title={s.pending_action_fa}>{s.pending_action_fa}</span>
                        ) : (
                          <span style={{ color: 'var(--text-secondary)' }}>—</span>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${s.is_intern ? 'badge-success' : 'badge-info'}`}>
                          {s.is_intern ? 'بله' : 'خیر'}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${s.therapy_started ? 'badge-success' : 'badge-warning'}`}>
                          {s.therapy_started ? 'شروع شده' : 'شروع نشده'}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button className="btn btn-outline btn-sm" onClick={() => loadStudentInstances(s.id)}>
                            مشاهده
                          </button>
                          <button className="btn btn-primary btn-sm" onClick={() => openStartProcess(s.id)}>
                            شروع فرایند
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Student processes + detail — modal popup */}
      {selectedStudent && (
        <div className="modal-overlay" onClick={closeStudentDetail}>
          <div
            className="modal modal-wide"
            style={{ maxWidth: 'min(92vw, 920px)', width: '100%' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3>فرایندهای دانشجو</h3>
              <button type="button" className="modal-close" onClick={closeStudentDetail} aria-label="بستن">&times;</button>
            </div>
            <div className="modal-body" style={{ paddingTop: 0 }}>
              <div className="card" style={{ marginBottom: '1.5rem', boxShadow: 'none', border: '1px solid var(--border)' }}>
                <div className="card-header" style={{ paddingTop: '0.75rem' }}>
                  <h3 className="card-title" style={{ fontSize: '1rem' }}>لیست فرایندها</h3>
                </div>
                {instances.length === 0 ? (
                  <div className="empty-state" style={{ padding: '2rem' }}>
                    <p>فرایندی برای این دانشجو یافت نشد</p>
                  </div>
                ) : (
                  instances.map((inst) => (
                    <div key={inst.instance_id} className="instance-card" onClick={() => loadInstanceStatus(inst.instance_id)}
                      style={{
                        cursor: 'pointer',
                        border: `2px solid ${inst.is_completed ? 'var(--success)' : inst.is_cancelled ? 'var(--danger)' : 'var(--info)'}`,
                        background: instanceStatus?.instance_id === inst.instance_id ? 'var(--primary-light)' : 'var(--bg)',
                      }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <strong>{labelProcess(inst.process_code)}</strong>
                        <span className={`badge ${inst.is_completed ? 'badge-success' : inst.is_cancelled ? 'badge-danger' : 'badge-warning'}`}>
                          {inst.is_completed ? 'تکمیل' : inst.is_cancelled ? 'لغو' : 'در جریان'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                        <div>وضعیت فعلی: <span className="badge badge-info">{labelState(inst.current_state)}</span></div>
                        <div>شروع: {inst.started_at ? new Date(inst.started_at).toLocaleDateString('fa-IR') : '-'}</div>
                        {inst.completed_at && <div>پایان: {new Date(inst.completed_at).toLocaleDateString('fa-IR')}</div>}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {instanceStatus && (
                <div className="card" style={{ boxShadow: 'none', border: '1px solid var(--border)' }}>
                  <div className="card-header">
                    <h3 className="card-title">جزئیات فرایند</h3>
                  </div>

                  <div className="form-grid-responsive-2">
                    <div className="detail-item">
                      <span className="detail-label">فرایند:</span>
                      <span>{labelProcess(instanceStatus.process_code)}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">وضعیت فعلی:</span>
                      <span className="badge badge-info">{labelState(instanceStatus.current_state)}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">وضعیت:</span>
                      <span className={`badge ${instanceStatus.is_completed ? 'badge-success' : instanceStatus.is_cancelled ? 'badge-danger' : 'badge-warning'}`}>
                        {instanceStatus.is_completed ? 'تکمیل شده' : instanceStatus.is_cancelled ? 'لغو شده' : 'در جریان'}
                      </span>
                    </div>
                  </div>

                  <InstanceContextSummary
                    contextData={instanceStatus.context_data}
                    history={instanceStatus.history}
                    title="پرونده و سابقه (زمینهٔ تصمیم)"
                  />

                  {availableTransitions.length > 0 && !instanceStatus.is_completed && !instanceStatus.is_cancelled && (
                    <div style={{ marginBottom: '1.5rem' }}>
                      <h4 style={{ marginBottom: '0.75rem', fontSize: '0.9rem' }}>انتقال‌های قابل اجرا:</h4>
                      <DecisionNotesBlock
                        value={decisionNotes}
                        onChange={setDecisionNotes}
                        title="توضیح همراه انتقال (اختیاری)"
                        hint="برای ثبت یادداشت همراه همان دکمهٔ انتقال."
                      />
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        {availableTransitions.map((t, idx) => (
                          <button
                            key={`${t.trigger_event}-${t.to_state || idx}`}
                            className="btn btn-primary btn-sm"
                            onClick={() => handleTrigger(instanceStatus.instance_id, t)}
                            title={t.description || `${t.trigger_event} → ${labelState(t.to_state)}`}
                          >
                            {t.description || t.trigger_event}
                            <span style={{ fontSize: '0.7rem', opacity: 0.8, marginRight: '0.25rem' }}>→ {labelState(t.to_state)}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
