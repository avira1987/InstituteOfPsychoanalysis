import React, { useState, useEffect, useLayoutEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { processExecApi, studentApi, therapyApi, assignmentApi } from '../services/api'
import GamificationPanel from '../components/GamificationPanel'
import StudentQuestCard from '../components/StudentQuestCard'
import InstanceContextSummary from '../components/InstanceContextSummary'
import DecisionNotesBlock from '../components/DecisionNotesBlock'
import { buildRoadmapStates } from '../utils/studentRoadmap'
import { canStartProcess, hasActiveRegistrationProcess } from '../utils/studentProcessAccess'
import {
  mergeFormPayload,
  stepFormsBlockTransition,
  isStudentStepFormLocked,
  pickFormValuesFromContext,
  filterFormsForStudent,
} from '../utils/processFormsStudent'
import ProcessStepForms from '../components/ProcessStepForms'
import StudentProcessGuidancePanel from '../components/StudentProcessGuidancePanel'
import PanelRoleActionQueue from '../components/PanelRoleActionQueue'
import { buildStudentGuidance } from '../utils/studentProcessGuidance'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'

const studentProcessCodes = [
  'educational_leave', 'start_therapy', 'extra_session', 'session_payment',
  'therapy_changes', 'therapy_session_increase', 'therapy_session_reduction',
  'therapy_interruption', 'student_session_cancellation', 'student_supervision_cancellation', 'supervision_block_transition',
  'extra_supervision_session', 'supervision_session_increase', 'supervision_session_reduction',
  'introductory_course_registration', 'comprehensive_course_registration',
  'fee_determination', 'upgrade_to_ta', 'internship_readiness_consultation',
]

export default function StudentPortal() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [studentProfile, setStudentProfile] = useState(null)
  const [activeProcesses, setActiveProcesses] = useState([])
  const [completedProcesses, setCompletedProcesses] = useState([])
  const [cancelledProcesses, setCancelledProcesses] = useState([])
  const [availableProcesses, setAvailableProcesses] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')
  const [activeTab, setActiveTab] = useState('dashboard')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [processFilter, setProcessFilter] = useState('')
  const [processDefinition, setProcessDefinition] = useState(null)
  const [therapySessions, setTherapySessions] = useState([])
  const [assignments, setAssignments] = useState([])
  const [primaryJourney, setPrimaryJourney] = useState(null)
  const [primaryJourneyLoading, setPrimaryJourneyLoading] = useState(false)
  const [instanceForms, setInstanceForms] = useState([])
  const [stepFormValues, setStepFormValues] = useState({})
  const lastFormCtxRef = useRef('')
  const gamificationTabPanelRef = useRef(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  useEffect(() => { loadData() }, [])

  const loadTherapyAndAssignments = async () => {
    if (!studentProfile) return
    try {
      const [tRes, aRes] = await Promise.all([
        therapyApi.mySessions().catch(() => ({ data: [] })),
        assignmentApi.mine().catch(() => ({ data: [] })),
      ])
      setTherapySessions(Array.isArray(tRes.data) ? tRes.data : [])
      setAssignments(Array.isArray(aRes.data) ? aRes.data : [])
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    if (studentProfile && (activeTab === 'sessions' || activeTab === 'assignments')) {
      loadTherapyAndAssignments()
    }
  }, [studentProfile, activeTab])

  useEffect(() => {
    const sid = selectedInstance || studentProfile?.extra_data?.primary_instance_id
    const onProcessTab = activeTab === 'processes' && !!(selectedInstance && instanceDetail?.instance_id === selectedInstance)
    const st = onProcessTab
      ? instanceDetail?.current_state
      : primaryJourney?.detail?.current_state
    const ctx = onProcessTab
      ? instanceDetail?.context_data
      : primaryJourney?.detail?.context_data
    const forms = onProcessTab ? instanceForms : primaryJourney?.forms
    if (!sid || !st) return
    const k = `${sid}|${st}|${activeTab === 'processes' ? 'p' : 'd'}`
    if (lastFormCtxRef.current !== k) {
      lastFormCtxRef.current = k
      setStepFormValues(pickFormValuesFromContext(forms, ctx))
    }
  }, [
    activeTab,
    selectedInstance,
    instanceDetail?.instance_id,
    instanceDetail?.current_state,
    instanceDetail?.context_data,
    instanceForms,
    primaryJourney?.detail?.current_state,
    primaryJourney?.detail?.context_data,
    primaryJourney?.forms,
    studentProfile?.extra_data?.primary_instance_id,
  ])

  useEffect(() => {
    if (activeTab !== 'gamification') return
    let cancelled = false
    studentApi.me().then(r => {
      if (!cancelled) setStudentProfile(r.data)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [activeTab])

  /** جلوگیری از پرش ناخواستهٔ viewport به ابتدای صفحه هنگام باز شدن تب گیمیفیکیشن */
  useLayoutEffect(() => {
    if (activeTab !== 'gamification') return
    const el = gamificationTabPanelRef.current
    if (!el) return
    const id = window.requestAnimationFrame(() => {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
    return () => window.cancelAnimationFrame(id)
  }, [activeTab])

  const loadPrimaryJourney = async (instanceId) => {
    if (!instanceId) {
      setPrimaryJourney(null)
      return
    }
    setPrimaryJourneyLoading(true)
    try {
      const dashRes = await processExecApi.dashboard(instanceId)
      const status = dashRes.data?.status
      const transitions = dashRes.data?.transitions || []
      const forms = dashRes.data?.forms || []
      const pcode = status?.process_code
      let def = null
      if (pcode) {
        try {
          const defRes = await processExecApi.getDefinition(pcode)
          def = defRes.data
        } catch {
          def = null
        }
      }
      setPrimaryJourney({
        detail: status,
        transitions,
        forms,
        definition: def,
      })
    } catch (e) {
      console.error('Primary journey load failed', e)
      setPrimaryJourney(null)
    } finally {
      setPrimaryJourneyLoading(false)
    }
  }

  const loadData = async () => {
    try {
      const defsRes = await processExecApi.definitions()
      let myProfile = null
      try {
        const meRes = await studentApi.me()
        myProfile = meRes.data
      } catch (e) {
        if (user?.role === 'student' && e.response?.status === 404) {
          navigate('/panel/complete-registration', { replace: true })
          return
        }
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

        const primaryId = myProfile.extra_data?.primary_instance_id
        if (primaryId) {
          await loadPrimaryJourney(primaryId)
        } else {
          setPrimaryJourney(null)
        }
      } else {
        setPrimaryJourney(null)
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
      showToast(`فرایند ${labelProcess(processCode)} آغاز شد`)
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
      const dashRes = await processExecApi.dashboard(instanceId)
      const status = dashRes.data?.status
      const transitions = dashRes.data?.transitions || []
      const forms = dashRes.data?.forms || []
      setInstanceDetail(status)
      setAvailableTransitions(transitions)
      setInstanceForms(forms)
      const pcode = status?.process_code
      if (pcode) {
        try {
          const defRes = await processExecApi.getDefinition(pcode)
          setProcessDefinition(defRes.data)
        } catch {
          setProcessDefinition(null)
        }
      } else {
        setProcessDefinition(null)
      }
    } catch (err) {
      console.error('View error:', err)
    }
  }

  const triggerTransition = async (transition) => {
    if (!selectedInstance) return
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    const lockedProc = isStudentStepFormLocked(instanceDetail?.context_data, instanceDetail?.current_state)
    if (!lockedProc && stepFormsBlockTransition(instanceForms, stepFormValues)) {
      showToast('ابتدا همهٔ موارد الزام فرم این مرحله را تکمیل کنید.', 'error')
      return
    }
    try {
      let payload = mergeFormPayload(decisionNotes, stepFormValues)
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
      if (toState) payload.to_state = toState
      const res = await processExecApi.trigger(selectedInstance, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
      })
      if (res.data.success) {
        showToast(`انتقال انجام شد: ${labelState(res.data.to_state)}`)
        viewInstance(selectedInstance)
        loadData()
      } else {
        showToast(res.data.error || 'خطا در انتقال', 'error')
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا', 'error')
    }
  }

  const triggerPrimaryTransition = async (transition) => {
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    const pid = studentProfile?.extra_data?.primary_instance_id || primaryJourney?.detail?.instance_id
    if (!pid) {
      showToast('مسیر اصلی یافت نشد', 'error')
      return
    }
    const lockedP = isStudentStepFormLocked(primaryJourney?.detail?.context_data, primaryJourney?.detail?.current_state)
    if (!lockedP && stepFormsBlockTransition(primaryJourney?.forms, stepFormValues)) {
      showToast('ابتدا همهٔ موارد الزام فرم این مرحله را تکمیل کنید.', 'error')
      return
    }
    try {
      let payload = mergeFormPayload(decisionNotes, stepFormValues)
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
      if (toState) payload.to_state = toState
      const res = await processExecApi.trigger(pid, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
      })
      if (res.data.success) {
        showToast(`انتقال انجام شد: ${labelState(res.data.to_state)}`)
        setSelectedInstance(pid)
        await Promise.all([loadPrimaryJourney(pid), viewInstance(pid)])
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
    { id: 'gamification', label: 'پیشرفت و مدال‌ها', icon: '🏆' },
    { id: 'sessions', label: 'جلسات آنلاین', icon: '🎥' },
    { id: 'assignments', label: 'تکالیف', icon: '📚' },
    { id: 'requests', label: 'درخواست‌های دیگر', icon: '📝' },
    { id: 'profile', label: 'پروفایل', icon: '👤' },
  ]

  const roadmapStates = processDefinition ? buildRoadmapStates(processDefinition) : []
  const roadmapProgress = instanceDetail && roadmapStates.length
    ? Math.min(100, Math.round((roadmapStates.findIndex(s => s.code === instanceDetail.current_state) + 1) / roadmapStates.length * 100))
    : 0
  const nextHint = availableTransitions[0]?.description || availableTransitions[0]?.trigger_event
  const stepFormLockedProcess = isStudentStepFormLocked(instanceDetail?.context_data, instanceDetail?.current_state)
  const stepFormLockedPrimary = isStudentStepFormLocked(primaryJourney?.detail?.context_data, primaryJourney?.detail?.current_state)
  const processTransitionBlocked = instanceDetail && stepFormsBlockTransition(instanceForms, stepFormValues, {
    lockedSubmitted: stepFormLockedProcess,
  })

  const primaryGuidance =
    studentProfile && primaryJourney?.detail && primaryJourney?.definition
      ? buildStudentGuidance({
          definition: primaryJourney.definition,
          detail: primaryJourney.detail,
          transitions: primaryJourney.transitions,
          forms: primaryJourney.forms,
          stepFormLocked: stepFormLockedPrimary,
        })
      : null

  const instanceGuidance =
    instanceDetail && processDefinition
      ? buildStudentGuidance({
          definition: processDefinition,
          detail: instanceDetail,
          transitions: availableTransitions,
          forms: instanceForms,
          stepFormLocked: stepFormLockedProcess,
        })
      : null

  const accessCtx = { studentProfile, activeProcesses }
  const registrationBlocking = studentProfile && hasActiveRegistrationProcess(activeProcesses)
  const quickActionItems = [
    { code: 'session_payment', icon: '💳', label: 'پرداخت جلسات' },
    { code: 'educational_leave', icon: '🏖️', label: 'درخواست مرخصی' },
    { code: 'extra_session', icon: '➕', label: 'جلسه اضافی' },
    { code: 'student_session_cancellation', icon: '🚫', label: 'کنسل جلسه درمان' },
    { code: 'student_supervision_cancellation', icon: '🚫', label: 'کنسل جلسه سوپرویژن' },
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
              ? `${user?.full_name_fa || user?.username} | کد دانشجویی: ${formatStudentCodeDisplay(studentProfile.student_code)} | دوره: ${studentProfile.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'}`
              : 'پروفایل دانشجو یافت نشد — لطفاً با مدیریت تماس بگیرید'}
          </p>
        </div>
      </div>

      {/* درخواست اداری / تیکت — همیشه قابل مشاهده در پنل دانشجو */}
      <div
        className="card"
        style={{
          marginBottom: '1.25rem',
          padding: '1rem 1.25rem',
          borderRadius: '12px',
          border: '1px solid rgba(59, 130, 246, 0.35)',
          background: 'linear-gradient(135deg, rgba(239, 246, 255, 0.95) 0%, rgba(255, 255, 255, 0.98) 100%)',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <div>
            <strong style={{ fontSize: '1.05rem' }}>درخواست به واحد اداری</strong>
            <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.95rem', maxWidth: '42rem' }}>
              برای مواردی مثل باز کردن پروفایل برای ویرایش مرحلهٔ ثبت‌شده، اصلاح داده یا پیگیری فرایند، می‌توانید تیکت ثبت کنید و مسئول مربوط را انتخاب کنید.
            </p>
          </div>
          <Link to="/panel/tickets" className="btn btn-primary" style={{ whiteSpace: 'nowrap' }}>
            تیکت‌ها و درخواست‌ها
          </Link>
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
          {studentProfile && (
            <StudentQuestCard
              loading={primaryJourneyLoading}
              detail={primaryJourney?.detail}
              definition={primaryJourney?.definition}
              transitions={primaryJourney?.transitions}
              forms={primaryJourney?.forms}
              stepFormLocked={stepFormLockedPrimary}
              stepFormValues={stepFormValues}
              onStepFieldChange={(name, v) => setStepFormValues(prev => ({ ...prev, [name]: v }))}
              onFormRegisterSubmit={async ({ ok, missing }) => {
                if (!ok) {
                  showToast(`موارد ناقص: ${missing.join('، ')}`, 'error')
                  return
                }
                const pid = studentProfile?.extra_data?.primary_instance_id || primaryJourney?.detail?.instance_id
                if (!pid) {
                  showToast('شناسه فرایند یافت نشد', 'error')
                  return
                }
                try {
                  await processExecApi.registerStudentStepForms(pid, { form_values: stepFormValues })
                  await loadPrimaryJourney(pid)
                  showToast(
                    'اطلاعات این مرحله ثبت شد. اگر دکمهٔ مرحلهٔ بعد را می‌بینید همان را بزنید؛ در غیر این صورت منتظر اقدام اداری بمانید.',
                    'success',
                  )
                } catch (e) {
                  const d = e.response?.data?.detail
                  if (d && typeof d === 'object' && Array.isArray(d.missing)) {
                    showToast(`موارد ناقص: ${d.missing.join('، ')}`, 'error')
                  } else {
                    showToast(typeof d === 'string' ? d : (e.message || 'خطا در ثبت'), 'error')
                  }
                }
              }}
              decisionNotes={decisionNotes}
              onDecisionNotesChange={setDecisionNotes}
              onTrigger={triggerPrimaryTransition}
              onOpenProcesses={() => setActiveTab('processes')}
              extraData={studentProfile.extra_data}
            />
          )}

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

          <PanelRoleActionQueue />

          {studentProfile && (
            <div className="card gam-dashboard-card" style={{ marginTop: '1.5rem' }}>
              <div className="card-header">
                <h3 className="card-title">پیشرفت مسیر آموزشی</h3>
                <span className="badge gam-dashboard-xp-badge">XP</span>
              </div>
              <GamificationPanel
                extraData={studentProfile.extra_data}
                compact
                onOpenDetails={() => setActiveTab('gamification')}
              />
            </div>
          )}

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
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                    اگر تازه ثبت‌نام کرده‌اید، معمولاً مسیر ثبت‌نام از بالای همین صفحه (کارت مسیر) دیده می‌شود؛ در غیر این صورت با پذیرش تماس بگیرید.
                  </p>
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
                          {labelProcess(p.process_code)}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.25rem' }}>
                          وضعیت: {labelState(p.current_state)}
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
                            {labelProcess(p.process_code)}
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
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', lineHeight: 1.6 }}>
                فقط اگر در این مرحله از مسیر تحصیلی‌تان مجاز باشید، دکمه فعال است؛ بقیه را از «درخواست‌های دیگر» ببینید (با توضیح قفل بودن).
              </p>
              <div className="quick-actions-grid">
                {quickActionItems.map(item => {
                  const { ok, reasonFa } = canStartProcess(item.code, accessCtx)
                  return (
                    <button
                      key={item.code}
                      type="button"
                      className="quick-action-btn"
                      disabled={!ok}
                      title={!ok ? reasonFa : item.label}
                      onClick={() => ok && startProcess(item.code)}
                      style={!ok ? { opacity: 0.45, cursor: 'not-allowed' } : undefined}
                    >
                      <span className="quick-action-icon">{item.icon}</span>
                      <span>{item.label}</span>
                    </button>
                  )
                })}
                <button type="button" className="quick-action-btn" onClick={() => setActiveTab('requests')}>
                  <span className="quick-action-icon">📝</span>
                  <span>درخواست‌های دیگر</span>
                </button>
                <button type="button" className="quick-action-btn" onClick={() => setActiveTab('profile')}>
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
                        <div style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</div>
                        <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>وضعیت: {labelState(p.current_state)}</div>
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
                      <span>{labelProcess(p.process_code)}</span>
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
                  {labelProcess(instanceDetail.process_code)}
                </h3>
                <button onClick={() => { setSelectedInstance(null); setInstanceDetail(null); setProcessDefinition(null) }}
                  className="btn btn-outline btn-sm">بستن</button>
              </div>

              {instanceGuidance && (
                <div style={{ padding: '0 0 1rem' }}>
                  <StudentProcessGuidancePanel guidance={instanceGuidance} variant="light" />
                </div>
              )}

              {processDefinition && roadmapStates.length > 0 && (
                <div style={{ marginBottom: '1.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.75rem' }}>مسیر این فرایند</h4>
                  <div style={{ marginBottom: '0.5rem', fontSize: '0.75rem', color: '#6b7280' }}>
                    پیشرفت تقریبی مسیر: {roadmapProgress}%
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                    {roadmapStates.map((st, i) => {
                      const curIdx = roadmapStates.findIndex(s => s.code === instanceDetail.current_state)
                      const isCurrent = st.code === instanceDetail.current_state
                      const past = curIdx >= 0 && i < curIdx
                      return (
                        <div key={st.code} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <div style={{
                            padding: '0.35rem 0.6rem', borderRadius: '8px', fontSize: '0.78rem', fontWeight: isCurrent ? 700 : 500,
                            background: isCurrent ? 'var(--primary-light)' : past ? '#ecfdf5' : '#f3f4f6',
                            border: isCurrent ? '2px solid var(--primary)' : '1px solid #e5e7eb',
                          }}>
                            {i + 1}. {st.name_fa || st.code}
                          </div>
                          {i < roadmapStates.length - 1 && <span style={{ color: '#9ca3af' }}>→</span>}
                        </div>
                      )
                    })}
                  </div>
                  {nextHint && (
                    <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: '#fffbeb', borderRadius: '8px', borderRight: '4px solid #f59e0b', fontSize: '0.85rem' }}>
                      <strong style={{ color: '#b45309' }}>راهنمای قدم بعد:</strong>{' '}
                      {nextHint}
                    </div>
                  )}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت فعلی</label>
                  <div style={{ fontWeight: 700, color: 'var(--primary)', fontSize: '0.95rem' }}>{labelState(instanceDetail.current_state)}</div>
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

              <InstanceContextSummary
                contextData={instanceDetail.context_data}
                history={instanceDetail.history}
                forms={instanceForms}
                title="پرونده و سابقه (قبل از اقدام)"
              />

              {filterFormsForStudent(instanceForms || []).length > 0 && stepFormLockedProcess && (
                <div className="psf-locked-banner" role="status" style={{
                  marginBottom: '1.25rem', padding: '1rem 1.25rem', borderRadius: '10px',
                  background: 'linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%)',
                  borderRight: '4px solid #16a34a', fontSize: '0.9rem', lineHeight: 1.7,
                }}>
                  اطلاعات این مرحله قبلاً ثبت شده است. برای ویرایش، مسئول مربوط (اداری) باید از پنل کارمندان، امکان ویرایش را برای شما باز کند؛ سپس همین صفحه را تازه کنید.
                </div>
              )}
              {!stepFormLockedProcess && (
                <ProcessStepForms
                  forms={instanceForms}
                  values={stepFormValues}
                  onFieldChange={(name, v) => setStepFormValues(prev => ({ ...prev, [name]: v }))}
                  disabled={false}
                  hasAvailableTransitions={(availableTransitions?.length || 0) > 0}
                  onRegisterSubmit={async ({ ok, missing }) => {
                    if (!ok) {
                      showToast(`موارد ناقص: ${missing.join('، ')}`, 'error')
                      return
                    }
                    if (!selectedInstance) {
                      showToast('فرایند انتخاب نشده است', 'error')
                      return
                    }
                    try {
                      await processExecApi.registerStudentStepForms(selectedInstance, { form_values: stepFormValues })
                      await viewInstance(selectedInstance)
                      showToast(
                        'اطلاعات این مرحله ثبت شد. اگر دکمهٔ مرحلهٔ بعد را می‌بینید همان را بزنید؛ در غیر این صورت منتظر اقدام اداری بمانید.',
                        'success',
                      )
                    } catch (e) {
                      const d = e.response?.data?.detail
                      if (d && typeof d === 'object' && Array.isArray(d.missing)) {
                        showToast(`موارد ناقص: ${d.missing.join('، ')}`, 'error')
                      } else {
                        showToast(typeof d === 'string' ? d : (e.message || 'خطا در ثبت'), 'error')
                      }
                    }
                  }}
                />
              )}

              {/* Available Actions */}
              {availableTransitions.length > 0 && (
                <div style={{
                  padding: '1.25rem', background: 'linear-gradient(135deg, var(--primary-light) 0%, #f0f4ff 100%)',
                  borderRadius: '10px', marginBottom: '1.5rem', borderRight: '4px solid var(--primary)',
                }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--primary)' }}>
                    اقدامات ممکن
                  </h4>
                  {processTransitionBlocked && (
                    <p style={{ fontSize: '0.82rem', color: '#b45309', marginBottom: '0.75rem', lineHeight: 1.6 }}>
                      تا تکمیل فرم مرحلهٔ فعلی، رفتن به مرحلهٔ بعد ممکن نیست.
                    </p>
                  )}
                  <DecisionNotesBlock
                    value={decisionNotes}
                    onChange={setDecisionNotes}
                    title="توضیح همراه اقدام (اختیاری)"
                    hint="با زدن دکمه، این متن به‌عنوان یادداشت همراه انتقال ثبت می‌شود (با مقادیر فرم ادغام می‌شود)."
                  />
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {availableTransitions.map((t, idx) => (
                      <button
                        key={`${t.trigger_event}-${idx}`}
                        type="button"
                        onClick={() => triggerTransition(t)}
                        className="btn btn-primary"
                        style={{ fontSize: '0.85rem', opacity: processTransitionBlocked ? 0.5 : 1 }}
                        disabled={processTransitionBlocked}
                        title={processTransitionBlocked ? 'فرم این مرحله را کامل کنید' : (t.description || t.trigger_event)}
                      >
                        {(t.description || t.description_fa || t.trigger_event)}
                        <span style={{ fontSize: '0.7rem', marginRight: '0.5rem', opacity: 0.7 }}>
                          → {labelState(t.to_state)}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

            </div>
          )}
        </div>
      )}

      {/* Online sessions */}
      {activeTab === 'sessions' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">جلسات آنلاین درمان</h3>
          </div>
          {!studentProfile ? (
            <div className="empty-state" style={{ padding: '2rem' }}>پروفایل دانشجو یافت نشد.</div>
          ) : therapySessions.length === 0 ? (
            <p style={{ padding: '1rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
              هنوز جلسه‌ای در تقویم شما ثبت نشده است. پس از پرداخت موفق و فعال‌سازی لینک توسط درمانگر، لینک ورود (اسکای‌روم / الوکام و …) در این بخش نمایش داده می‌شود.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {therapySessions.map(s => (
                <div
                  key={s.id}
                  style={{
                    padding: '1rem', borderRadius: '8px', border: '1px solid var(--border)',
                    display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '0.75rem', alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>تاریخ جلسه: {s.session_date}</div>
                    <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>وضعیت پرداخت: {s.payment_status} | وضعیت جلسه: {s.status}</div>
                  </div>
                  {s.meeting_url ? (
                    <a href={s.meeting_url} target="_blank" rel="noopener noreferrer" className="btn btn-primary btn-sm">
                      ورود به جلسه
                    </a>
                  ) : (
                    <span className="badge badge-warning" style={{ fontSize: '0.75rem' }}>در انتظار لینک از درمانگر</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Assignments */}
      {activeTab === 'assignments' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">تکالیف</h3>
          </div>
          {!studentProfile ? (
            <div className="empty-state" style={{ padding: '2rem' }}>پروفایل دانشجو یافت نشد.</div>
          ) : assignments.length === 0 ? (
            <p style={{ padding: '1rem', color: 'var(--text-secondary)' }}>تکلیفی تعیین نشده است.</p>
          ) : (
            <AssignmentList assignments={assignments} showToast={showToast} />
          )}
        </div>
      )}

      {/* Request Tab — فقط وقتی مجاز است واقعاً شروع می‌شود؛ بقیه با توضیح قفل */}
      {activeTab === 'requests' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">درخواست‌های تکمیلی</h3>
            <input
              type="text"
              placeholder="جستجو..."
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
            <>
              <div className="requests-intro">
                <p>
                  <strong>قدم اصلی شما</strong> همیشه از <button type="button" className="link-like" onClick={() => setActiveTab('dashboard')}>داشبورد</button>
                  {' '}و کارت «مسیر فعلی» است. اینجا فقط وقتی باید بروید که به فرایند دیگری (مثلاً مرخصی یا سوپرویژن) نیاز دارید و در همان مرحله مجازید.
                </p>
                {registrationBlocking && (
                  <div className="requests-banner" role="status">
                    فرایند ثبت‌نام دوره هنوز باز است؛ تا تکمیل آن، شروع فرایندهای دیگر از اینجا غیرفعال است. مسیر را از داشبورد جلو ببرید.
                  </div>
                )}
              </div>
              <div className="requests-grid">
                {availableProcesses
                  .filter(p => {
                    if (!processFilter) return true
                    const label = p.name_fa || labelProcess(p.code)
                    return label.includes(processFilter) || p.code.includes(processFilter)
                  })
                  .map(p => {
                    const hasActive = activeProcesses.some(a => a.process_code === p.code)
                    const { ok, reasonFa } = canStartProcess(p.code, accessCtx)
                    const canClick = !hasActive && ok
                    return (
                      <div
                        key={p.code || p.id}
                        className={`requests-card ${hasActive ? 'requests-card--active' : ''} ${!canClick && !hasActive ? 'requests-card--locked' : ''}`}
                      >
                        <div className="requests-card-title">
                          {p.name_fa || labelProcess(p.code)}
                        </div>
                        <div className="requests-card-desc">
                          {p.description || `کد: ${p.code}`}
                        </div>
                        {hasActive ? (
                          <span className="badge badge-warning">فرایند فعال دارید — از «فرایندها» ادامه دهید</span>
                        ) : canClick ? (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() => startProcess(p.code)}
                          >
                            آغاز فرایند
                          </button>
                        ) : (
                          <div className="requests-locked">
                            <span className="badge" style={{ background: '#f1f5f9', color: '#64748b' }}>قفل در این مرحله</span>
                            <p className="requests-lock-reason">{reasonFa}</p>
                          </div>
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
            </>
          )}
        </div>
      )}

      {/* Gamification Tab */}
      {activeTab === 'gamification' && (
        <div ref={gamificationTabPanelRef} className="card gam-tab-card" id="student-gamification-panel">
          <div className="card-header">
            <h3 className="card-title">پیشرفت، رتبه و مدال‌ها</h3>
          </div>
          {studentProfile ? (
            <GamificationPanel extraData={studentProfile.extra_data} />
          ) : (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <p>برای مشاهدهٔ پیشرفت، ابتدا پروفایل دانشجویی باید فعال باشد.</p>
            </div>
          )}
        </div>
      )}

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {primaryGuidance && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">فرایند فعلی و تکلیف شما</h3>
              </div>
              <StudentProcessGuidancePanel guidance={primaryGuidance} variant="light" />
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0 1.25rem 1.25rem', lineHeight: 1.65 }}>
                جزئیات کامل فرم‌ها و دکمه‌ها را در تب <button type="button" className="link-like" onClick={() => setActiveTab('dashboard')}>داشبورد</button>
                {' '}در کارت «مسیر فعلی» یا در تب <button type="button" className="link-like" onClick={() => setActiveTab('processes')}>فرایندها</button> می‌بینید.
              </p>
            </div>
          )}
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
                <ProfileField label="کد دانشجویی" value={formatStudentCodeDisplay(studentProfile.student_code)} />
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
        </div>
      )}
    </div>
  )
}

function AssignmentList({ assignments, showToast }) {
  const [texts, setTexts] = useState({})
  const submit = async (id) => {
    try {
      await assignmentApi.submit(id, { body_text: texts[id] || '' })
      showToast('تکلیف ارسال شد')
    } catch (e) {
      showToast(e.response?.data?.detail || 'خطا', 'error')
    }
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {assignments.map(a => (
        <div key={a.id} style={{ padding: '1rem', border: '1px solid var(--border)', borderRadius: '8px' }}>
          <div style={{ fontWeight: 600 }}>{a.title_fa}</div>
          {a.description && <p style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>{a.description}</p>}
          {a.due_at && (
            <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
              مهلت: {new Date(a.due_at).toLocaleDateString('fa-IR')}
            </div>
          )}
          <textarea
            value={texts[a.id] || ''}
            onChange={e => setTexts({ ...texts, [a.id]: e.target.value })}
            placeholder="پاسخ یا توضیح تکلیف..."
            style={{
              width: '100%', marginTop: '0.75rem', minHeight: '80px', padding: '0.5rem',
              borderRadius: '6px', border: '1px solid #d1d5db', fontFamily: 'inherit',
            }}
          />
          <button type="button" className="btn btn-primary btn-sm" style={{ marginTop: '0.5rem' }} onClick={() => submit(a.id)}>
            ارسال تکلیف
          </button>
        </div>
      ))}
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
