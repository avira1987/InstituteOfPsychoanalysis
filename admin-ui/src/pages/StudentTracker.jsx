import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { studentApi, processExecApi, processApi, userApi, semesterPrepApi } from '../services/api'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import { notesPayload } from '../utils/decisionPayload'
import { labelProcess, labelState, formatStudentCodeDisplay, formatStudentFullNameFa } from '../utils/processDisplay'
import OperatorInstanceContextSummary from '../components/OperatorInstanceContextSummary'
import ProcessRestartSection from '../components/ProcessRestartSection'
import DecisionNotesBlock from '../components/DecisionNotesBlock'
import { useToast } from '../contexts/ToastContext'
import ResolvedProcessHistoryBanner from '../components/ResolvedProcessHistoryBanner'
import OperatorCourseSelectionEditor from '../components/OperatorCourseSelectionEditor'
import RegistrationCourseTypeEditor from '../components/RegistrationCourseTypeEditor'
import { isInstituteLevelProcess } from '../utils/instituteProcesses'
import { getManualStartScope } from '../utils/processStartScope'
import {
  INSTITUTE_OPS_LABEL_FA,
  isInstituteOperationalStudent,
} from '../utils/instituteOperationalAnchor'
import { sortProcessNavItems } from '../utils/processNavOrder'
import { groupProcessNavItemsByCategory } from '../utils/processNavCategories'

const TRACKER_TABS = [
  { id: 'students', label: 'دانشجویان' },
  { id: 'institute', label: 'آماده‌سازی ترم' },
]

const PREP_PROCESS_LABELS = {
  fall_semester_preparation: 'آماده‌سازی ترم پاییز',
  winter_semester_preparation: 'آماده‌سازی ترم زمستان',
}

export default function StudentTracker() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTab = searchParams.get('tab') === 'institute' ? 'institute' : 'students'
  const [activeTab, setActiveTab] = useState(initialTab)
  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [restartBusy, setRestartBusy] = useState(false)

  const [selectedStudent, setSelectedStudent] = useState(null)
  const [selectedStudentMeta, setSelectedStudentMeta] = useState(null)
  const [instances, setInstances] = useState([])
  const [instanceStatus, setInstanceStatus] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')

  const [anchorMeta, setAnchorMeta] = useState(null)
  const [prepStatus, setPrepStatus] = useState(null)
  const [prepLoading, setPrepLoading] = useState(false)
  const [prepError, setPrepError] = useState(null)

  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    user_id: '', student_code: '', course_type: 'comprehensive', is_intern: false, term_count: 1, current_term: 1, weekly_sessions: 1,
  })

  const [showStartProcess, setShowStartProcess] = useState(false)
  const [processDefinitions, setProcessDefinitions] = useState([])
  const [startForm, setStartForm] = useState({ process_code: '', student_id: '' })

  const [users, setUsers] = useState([])
  const { showToast } = useToast()

  const closeStudentDetail = useCallback(() => {
    setSelectedStudent(null)
    setSelectedStudentMeta(null)
    setInstances([])
    setInstanceStatus(null)
    setAvailableTransitions([])
    setDecisionNotes('')
  }, [])

  const switchTab = useCallback((tabId) => {
    setActiveTab(tabId)
    closeStudentDetail()
    const next = new URLSearchParams(searchParams)
    if (tabId === 'institute') next.set('tab', 'institute')
    else next.delete('tab')
    next.delete('student_id')
    next.delete('instance_id')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams, closeStudentDetail])

  const loadStudents = async () => {
    try {
      setError(null)
      const res = await studentApi.list({ tracker_summary: true })
      const rows = Array.isArray(res.data) ? res.data : []
      setStudents(rows.filter((s) => !isInstituteOperationalStudent(s)))
    } catch (err) {
      console.error('Failed to load students:', err)
      setError('خطا در بارگذاری لیست دانشجویان: ' + (err.response?.data?.detail || err.message))
      setStudents([])
    } finally {
      setLoading(false)
    }
  }

  const loadPrepStatus = useCallback(async () => {
    setPrepLoading(true)
    setPrepError(null)
    try {
      const statusRes = await semesterPrepApi.getStatus()
      const data = statusRes.data || {}
      const sid = data.anchor_student_id
      const code = data.anchor_student_code || data.anchor?.student_code
      setPrepStatus(data)
      setAnchorMeta({
        id: sid,
        student_code: code,
        extra_data: { institute_operational_anchor: true },
        ...(data.anchor || {}),
      })
      return sid
    } catch (err) {
      console.error('Failed to load institute prep status:', err)
      setPrepError(err.response?.data?.detail || err.message || 'خطا در بارگذاری وضعیت آماده‌سازی ترم')
      setPrepStatus(null)
      return null
    } finally {
      setPrepLoading(false)
    }
  }, [])

  useEffect(() => {
    loadStudents()
  }, [])

  useEffect(() => {
    if (activeTab === 'institute') {
      loadPrepStatus()
    }
  }, [activeTab, loadPrepStatus])

  const loadStudentInstances = async (studentId) => {
    try {
      const [instRes, studentRes] = await Promise.all([
        processExecApi.studentInstances(studentId),
        studentApi.get(studentId).catch(() => null),
      ])
      const meta = studentRes?.data || null
      if (isInstituteOperationalStudent(meta)) {
        switchTab('institute')
        await loadPrepStatus()
        return false
      }
      const rows = Array.isArray(instRes.data?.instances) ? instRes.data.instances : []
      setInstances(rows.filter((i) => !isInstituteLevelProcess(i.process_code)))
      setSelectedStudent(studentId)
      setSelectedStudentMeta(meta)
      setInstanceStatus(null)
      setAvailableTransitions([])
      return true
    } catch (err) {
      console.error('Failed to load instances:', err)
      return false
    }
  }

  const loadInstanceStatus = async (instanceId) => {
    try {
      const [statusRes, transRes] = await Promise.all([
        processExecApi.status(instanceId),
        processExecApi.transitions(instanceId),
      ])
      if (isInstituteLevelProcess(statusRes.data?.process_code)) {
        const code = statusRes.data.process_code
        switchTab('institute')
        await loadPrepStatus()
        navigate(`/panel/semester-prep/workbench?process_code=${encodeURIComponent(code)}`)
        return
      }
      setInstanceStatus(statusRes.data)
      setAvailableTransitions(transRes.data.transitions || [])
      setDecisionNotes('')
    } catch (err) {
      console.error('Failed to load status:', err)
    }
  }

  useEffect(() => {
    const tab = searchParams.get('tab')
    const sid = searchParams.get('student_id')
    const iid = searchParams.get('instance_id')
    if (tab === 'institute' && !sid) {
      setActiveTab('institute')
      return
    }
    if (!sid) return
    let cancelled = false
    ;(async () => {
      try {
        const studentRes = await studentApi.get(sid).catch(() => null)
        if (cancelled) return
        if (isInstituteOperationalStudent(studentRes?.data)) {
          setActiveTab('institute')
          await loadPrepStatus()
          if (cancelled) return
          closeStudentDetail()
          if (iid) {
            const statusRes = await processExecApi.status(iid).catch(() => null)
            const code = statusRes?.data?.process_code
            if (code && isInstituteLevelProcess(code)) {
              navigate(`/panel/semester-prep/workbench?process_code=${encodeURIComponent(code)}`)
            }
          }
          return
        }
        setActiveTab('students')
        const opened = await loadStudentInstances(sid)
        if (cancelled || !opened || !iid) return
        await loadInstanceStatus(iid)
      } catch (err) {
        console.error(err)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

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
        if (selectedStudent) {
          await loadStudentInstances(selectedStudent)
        }
      } else {
        showToast('خطا: ' + (res.data.error || 'انتقال انجام نشد'), 'error')
      }
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const handleProcessRestart = async (reason) => {
    if (!instanceStatus?.instance_id) return false
    const instanceId = instanceStatus.instance_id
    setRestartBusy(true)
    try {
      const res = await processExecApi.restart(instanceId, {
        reason: reason || undefined,
        confirm: true,
      })
      if (res.data?.success) {
        const newId = res.data.new_instance_id
        showToast('فرایند از ابتدا با پروندهٔ جدید باز شد')
        if (selectedStudent) {
          await loadStudentInstances(selectedStudent)
        }
        await loadInstanceStatus(newId)
        return true
      }
      showToast(res.data?.error || 'شروع دوباره انجام نشد', 'error')
      return false
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
      return false
    } finally {
      setRestartBusy(false)
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
      await processExecApi.start(startForm)
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
      const active = (Array.isArray(res.data) ? res.data : []).filter(
        (p) => p.is_active && getManualStartScope(p.code) === 'student',
      )
      setProcessDefinitions(
        sortProcessNavItems(
          active.map((p) => ({
            ...p,
            process_code: p.code,
            label_fa: p.name_fa,
            sop_order: p.sop_order,
          })),
        ),
      )
    } catch (err) {
      console.error(err)
    }
    setShowStartProcess(true)
  }

  const startProcessGroups = useMemo(
    () => groupProcessNavItemsByCategory(processDefinitions),
    [processDefinitions],
  )

  const openCreateStudent = async () => {
    try {
      const res = await userApi.list()
      setUsers(res.data.filter((u) => u.is_active))
    } catch (err) {
      console.error(err)
    }
    setShowCreate(true)
  }

  const courseTypeLabel = (type) => {
    switch (type) {
      case 'comprehensive': return 'جامع'
      case 'introductory': return 'آشنایی'
      default: return type
    }
  }

  const filteredStudents = (Array.isArray(students) ? students : []).filter((s) => {
    if (isInstituteOperationalStudent(s)) return false
    if (!search) return true
    const q = search.toLowerCase()
    return (
      (s.student_code || '').toLowerCase().includes(q)
      || (s.full_name_fa || '').toLowerCase().includes(q)
    )
  })

  const prepProcessEntries = useMemo(() => {
    const processes = prepStatus?.processes || {}
    return ['fall_semester_preparation', 'winter_semester_preparation'].map((code) => {
      const entry = processes[code] || {}
      return { code, entry }
    })
  }, [prepStatus])

  const detailOpen = Boolean(selectedStudent)

  return (
    <div>
      <ResolvedProcessHistoryBanner
        instanceDetail={instanceStatus}
        availableTransitions={availableTransitions}
      />

      {error && activeTab === 'students' && (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '8px', padding: '1rem', marginBottom: '1.5rem', color: '#991b1b' }}>
          <strong>خطا: </strong>{error}
          <button onClick={loadStudents} style={{ marginRight: '1rem', padding: '0.25rem 0.75rem', background: '#ef4444', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>تلاش مجدد</button>
        </div>
      )}

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
                    {startProcessGroups.map((group) => (
                      <optgroup key={group.id} label={group.label}>
                        {group.items.map((p) => (
                          <option key={p.code} value={p.code}>
                            {p.name_fa} ({p.code})
                          </option>
                        ))}
                      </optgroup>
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
          <p className="page-subtitle">
            دانشجویان واقعی و آماده‌سازی ترم در تب‌های جدا
            {activeTab === 'students' ? ` | مجموع: ${students.length} دانشجو` : ''}
            {' · '}
            کار روزمرهٔ ترم در{' '}
            <Link to="/panel/semester-prep">هاب آماده‌سازی ترم</Link>
            {' '}است.
          </p>
        </div>
        {activeTab === 'students' && (
          <button className="btn btn-primary" onClick={openCreateStudent}>
            + دانشجوی جدید
          </button>
        )}
      </div>

      <div className="tabs" style={{ marginBottom: '1.25rem' }} role="tablist">
        {TRACKER_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`tab-item ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => switchTab(tab.id)}
            data-testid={`tracker-tab-${tab.id}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {showCreate && activeTab === 'students' && (
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

      {activeTab === 'students' && (
        <>
          <div style={{ marginBottom: '1.5rem' }}>
            <input
              className="form-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجو با نام یا کد دانشجویی..."
              style={{ maxWidth: '350px' }}
            />
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title">لیست دانشجویان</h3>
            </div>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>کد</th>
                    <th>نام</th>
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
                    <tr><td colSpan="9" style={{ textAlign: 'center', padding: '2rem' }}>در حال بارگذاری...</td></tr>
                  ) : filteredStudents.length === 0 ? (
                    <tr><td colSpan="9" style={{ textAlign: 'center', padding: '2rem' }}>دانشجویی یافت نشد</td></tr>
                  ) : (
                    filteredStudents.map((s) => (
                      <tr key={s.id} style={{ background: selectedStudent === s.id ? 'var(--primary-light)' : '' }}>
                        <td><strong>{formatStudentCodeDisplay(s.student_code)}</strong></td>
                        <td>{formatStudentFullNameFa(s.full_name_fa)}</td>
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
        </>
      )}

      {activeTab === 'institute' && (
        <div className="card" data-testid="tracker-institute-tab">
          <div className="card-header" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <h3 className="card-title" style={{ marginBottom: '0.25rem' }}>
                {INSTITUTE_OPS_LABEL_FA}
              </h3>
              <p className="muted" style={{ margin: 0, fontSize: '0.85rem', lineHeight: 1.6 }}>
                خلاصهٔ وضعیت آماده‌سازی ترم روی رکورد سیستمی
                {anchorMeta?.student_code ? (
                  <>
                    {' '}
                    <code style={{ direction: 'ltr' }}>{anchorMeta.student_code}</code>
                  </>
                ) : null}
                .
                {' '}
                نمونه‌های خام فرایند (شامل بایگانی ریست) اینجا لیست نمی‌شوند؛ کار روی میزکار انجام می‌شود.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <Link className="btn btn-primary btn-sm" to="/panel/semester-prep">
                هاب آماده‌سازی ترم
              </Link>
              <button type="button" className="btn btn-outline btn-sm" onClick={loadPrepStatus} disabled={prepLoading}>
                تازه‌سازی
              </button>
            </div>
          </div>

          {prepError && (
            <div style={{ margin: '1rem', padding: '0.85rem 1rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', color: '#991b1b' }}>
              {String(prepError)}
            </div>
          )}

          {prepLoading ? (
            <div className="empty-state" style={{ padding: '2rem' }}>در حال بارگذاری...</div>
          ) : (
            <div style={{ padding: '0.75rem 1rem 1.25rem', display: 'grid', gap: '0.85rem' }}>
              {prepProcessEntries.map(({ code, entry }) => {
                const active = Boolean(entry.active && entry.instance_id)
                const completed = Boolean(!active && entry.completed_instance_id)
                const stateLabel = active
                  ? (entry.state_name_fa || labelState(entry.current_state))
                  : completed
                    ? (entry.completed_state_name_fa || labelState(entry.completed_current_state) || 'تکمیل‌شده')
                    : 'شروع نشده'
                return (
                  <div
                    key={code}
                    style={{
                      border: '1px solid var(--border)',
                      borderRadius: '10px',
                      padding: '0.9rem 1rem',
                      background: '#fff',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
                      <div>
                        <strong>{PREP_PROCESS_LABELS[code] || labelProcess(code)}</strong>
                        <div style={{ marginTop: '0.35rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                          وضعیت:
                          {' '}
                          <span className={`badge ${active ? 'badge-warning' : completed ? 'badge-success' : 'badge-info'}`}>
                            {active ? 'در جریان' : completed ? 'تکمیل' : 'بدون نمونه فعال'}
                          </span>
                          {' · '}
                          {stateLabel}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap' }}>
                        {(active || completed) ? (
                          <Link
                            className="btn btn-primary btn-sm"
                            to={`/panel/semester-prep/workbench?process_code=${encodeURIComponent(code)}`}
                          >
                            {active ? 'ادامه در میزکار' : 'مشاهده در میزکار'}
                          </Link>
                        ) : (
                          <Link className="btn btn-secondary btn-sm" to="/panel/semester-prep">
                            شروع از هاب
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {detailOpen && activeTab === 'students' && (
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
              {selectedStudent
                && !isInstituteLevelProcess(instanceStatus?.process_code)
                && !(instances.length > 0 && instances.every((i) => isInstituteLevelProcess(i.process_code))) && (
                <RegistrationCourseTypeEditor
                  studentId={selectedStudent}
                  initialCourseType={
                    selectedStudentMeta?.course_type
                    || students.find((s) => s.id === selectedStudent)?.course_type
                    || 'introductory'
                  }
                  showToast={showToast}
                  compact
                  onSaved={() => {
                    loadStudents()
                    if (instanceStatus?.instance_id) {
                      loadInstanceStatus(instanceStatus.instance_id)
                    }
                  }}
                />
              )}
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
                    <div
                      key={inst.instance_id}
                      className="instance-card"
                      onClick={() => loadInstanceStatus(inst.instance_id)}
                      style={{
                        cursor: 'pointer',
                        border: `2px solid ${inst.is_completed ? 'var(--success)' : inst.is_cancelled ? 'var(--danger)' : 'var(--info)'}`,
                        background: instanceStatus?.instance_id === inst.instance_id ? 'var(--primary-light)' : 'var(--bg)',
                      }}
                    >
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

                  <OperatorCourseSelectionEditor
                    instanceId={instanceStatus.instance_id}
                    processCode={instanceStatus.process_code}
                    currentState={instanceStatus.current_state}
                    contextData={instanceStatus.context_data}
                    isCompleted={instanceStatus.is_completed}
                    isCancelled={instanceStatus.is_cancelled}
                    showToast={showToast}
                    onUpdated={() => loadInstanceStatus(instanceStatus.instance_id)}
                  />

                  <OperatorInstanceContextSummary
                    user={user}
                    instanceDetail={instanceStatus}
                    availableTransitions={availableTransitions}
                    title="پرونده و سابقه (زمینهٔ تصمیم)"
                  />

                  <ProcessRestartSection
                    user={user}
                    instanceDetail={instanceStatus}
                    onRestart={handleProcessRestart}
                    busy={restartBusy}
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
