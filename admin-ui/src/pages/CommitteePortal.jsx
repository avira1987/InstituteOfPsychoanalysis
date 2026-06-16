import React, { useState, useEffect, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { usePortalInstanceDeepLink } from '../hooks/usePortalInstanceDeepLink'
import { processExecApi, studentApi, panelApi } from '../services/api'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import { notesPayload } from '../utils/decisionPayload'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import { isDocumentReviewState } from '../utils/documentReviewStates'
import {
  isComprehensiveEvalTrigger,
  validateInterviewEvaluationForm,
  mergeInterviewEvaluationPayload,
} from '../utils/interviewEvaluationPayload'
import {
  canSubmitInterviewResult,
  filterInterviewResultTransitions,
} from '../utils/interviewResultAccess'
import InstanceContextSummary from '../components/InstanceContextSummary'
import DecisionNotesBlock from '../components/DecisionNotesBlock'
import PopupToast from '../components/PopupToast'
import ProcessRollbackSection from '../components/ProcessRollbackSection'
import OperatorPortalReminderBanner from '../components/OperatorPortalReminderBanner'
import OperatorFollowupSection from '../components/OperatorFollowupSection'
import ResolvedProcessHistoryBanner from '../components/ResolvedProcessHistoryBanner'
import OperatorStepFormsSection from '../components/OperatorStepFormsSection'
import OperatorInstanceGuidanceBlock from '../components/OperatorInstanceGuidanceBlock'
import {
  COMMITTEE_DEEP_LINK_TABS,
  COMMITTEE_DEFAULT_CONFIG,
  getCommitteeKindConfig,
  getCommitteeKindPath,
  getCommitteeRoleConfig,
} from '../utils/portalCommitteeKinds'

export default function CommitteePortal() {
  const { kind: kindParam } = useParams()
  const kind = kindParam || 'progress'
  const kindMeta = getCommitteeKindConfig(kind)
  const portalPath = getCommitteeKindPath(kind)
  const { user } = useAuth()
  const config = getCommitteeRoleConfig(user?.role) || COMMITTEE_DEFAULT_CONFIG
  const [activeTab, setActiveTab] = useState('reviews')
  const [allStudents, setAllStudents] = useState([])
  const [pendingReviews, setPendingReviews] = useState([])
  const [allActiveInstances, setAllActiveInstances] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [rollbackBusy, setRollbackBusy] = useState(false)
  /** فیلدهای جلسه مرخصی آموزشی — همراه تریگر committee_set_meeting به API فرستاده می‌شود */
  const [leaveMeeting, setLeaveMeeting] = useState({
    committee_meeting_at: '',
    committee_meeting_mode: 'in_person',
    committee_meeting_link: '',
    committee_meeting_location_fa: '',
  })
  const [operatorFollowupItems, setOperatorFollowupItems] = useState([])
  const [operatorReadinessAlerts, setOperatorReadinessAlerts] = useState([])
  /** فرم ارزیابی مصاحبهٔ ورود به دوره جامع (محرمانه) — همراه تریگر نتیجه ارسال می‌شود */
  const [interviewEval, setInterviewEval] = useState({
    evaluation_notes: '',
    rejection_reason: '',
    suggestion_text: '',
  })

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    try {
      const [studentsRes, followupRes] = await Promise.all([
        studentApi.list().catch(() => ({ data: [] })),
        panelApi.myOperatorFollowup().catch(() => ({ data: {} })),
      ])
      const students = studentsRes.data || []
      setAllStudents(students)
      setOperatorFollowupItems(followupRes.data?.items || [])
      setOperatorReadinessAlerts(followupRes.data?.readiness_alerts || [])

      const pending = []
      const allActive = []
      for (const s of students) {
        try {
          const instRes = await processExecApi.studentInstances(s.id)
          const instances = instRes.data?.instances || []
          for (const inst of instances) {
            if (!inst.is_completed && !inst.is_cancelled) {
              // مراحل بررسی/تکمیل مدارک مخصوص پنل کارمند است و در پنل‌های کمیته نمایش داده نمی‌شود.
              if (isDocumentReviewState(inst.current_state)) continue
              const enriched = { ...inst, student_code: s.student_code, student_id: s.id }
              allActive.push(enriched)
              if (isWaitingForReview(inst.current_state, inst.process_code)) {
                pending.push(enriched)
              }
            }
          }
        } catch { /* skip */ }
      }
      setPendingReviews(pending)
      setAllActiveInstances(allActive)
    } catch (err) {
      console.error('Load error:', err)
    } finally {
      setLoading(false)
    }
  }

  const isWaitingForReview = (state, processCode) => {
    if (!state) return false
    const keywordMatch = config.reviewKeywords.some((kw) => {
      if (!state.includes(kw)) return false
      if (kw === 'interview_completed' && processCode !== 'comprehensive_course_registration') {
        return false
      }
      return true
    })
    if (!keywordMatch) return false
    const kindRoles = kindMeta?.portalRoles || []
    if (user?.role === 'admin' || kindRoles.includes(user?.role)) return true
    return false
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
      const ctx = statusRes.data?.context_data || {}
      const iso = ctx.committee_meeting_at
      let localDt = ''
      if (typeof iso === 'string' && iso.length >= 10) {
        try {
          const d = new Date(iso)
          if (!Number.isNaN(d.getTime())) {
            const pad = n => String(n).padStart(2, '0')
            localDt = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
          }
        } catch { /* ignore */ }
      }
      setLeaveMeeting({
        committee_meeting_at: localDt,
        committee_meeting_mode: ctx.committee_meeting_mode === 'online' ? 'online' : 'in_person',
        committee_meeting_link: ctx.committee_meeting_link || '',
        committee_meeting_location_fa: ctx.committee_meeting_location_fa || '',
      })
      setInterviewEval({
        evaluation_notes: ctx.interview_evaluation_notes || '',
        rejection_reason: ctx.interview_rejection_reason || '',
        suggestion_text: ctx.interview_suggestion_text || '',
      })
    } catch (err) {
      console.error('View error:', err)
    }
  }

  usePortalInstanceDeepLink({
    loading,
    setActiveTab,
    viewInstance,
    allowedTabs: COMMITTEE_DEEP_LINK_TABS,
  })

  const handleProcessRollback = async (reason) => {
    if (!selectedInstance) return
    setRollbackBusy(true)
    try {
      const res = await processExecApi.rollback(selectedInstance, { reason: reason || undefined })
      if (res.data?.success) {
        showToast(`فرایند به «${labelState(res.data.to_state)}» برگردانده شد`)
        await viewInstance(selectedInstance)
        loadData()
      } else {
        showToast(res.data?.error || 'بازگشت انجام نشد', 'error')
      }
    } catch (e) {
      const d = e.response?.data?.detail
      showToast(typeof d === 'string' ? d : (e.message || 'خطا در بازگشت'), 'error')
    } finally {
      setRollbackBusy(false)
    }
  }

  const triggerTransition = async (transition) => {
    if (!selectedInstance) return
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    try {
      let payload = notesPayload(decisionNotes)
      if (
        instanceDetail?.process_code === 'educational_leave'
        && triggerEvent === 'committee_set_meeting'
      ) {
        if (!leaveMeeting.committee_meeting_at || !String(leaveMeeting.committee_meeting_at).trim()) {
          showToast('تاریخ و ساعت جلسه را مشخص کنید.', 'error')
          return
        }
        const mode = leaveMeeting.committee_meeting_mode
        if (mode === 'online' && !(leaveMeeting.committee_meeting_link || '').trim()) {
          showToast('برای جلسه آنلاین، لینک جلسه الزامی است.', 'error')
          return
        }
        if (mode === 'in_person' && !(leaveMeeting.committee_meeting_location_fa || '').trim()) {
          showToast('برای جلسه حضوری، آدرس یا محل الزامی است.', 'error')
          return
        }
        let iso = ''
        try {
          const d = new Date(leaveMeeting.committee_meeting_at)
          if (Number.isNaN(d.getTime())) {
            showToast('تاریخ و ساعت جلسه معتبر نیست.', 'error')
            return
          }
          iso = d.toISOString()
        } catch {
          showToast('تاریخ و ساعت جلسه معتبر نیست.', 'error')
          return
        }
        payload = {
          ...payload,
          committee_meeting_at: iso,
          committee_meeting_mode: mode,
          committee_meeting_link: (leaveMeeting.committee_meeting_link || '').trim(),
          committee_meeting_location_fa: (leaveMeeting.committee_meeting_location_fa || '').trim(),
        }
      }
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
      if (
        instanceDetail?.process_code === 'comprehensive_course_registration'
        && isComprehensiveEvalTrigger(triggerEvent)
      ) {
        const evalError = validateInterviewEvaluationForm(interviewEval, triggerEvent)
        if (evalError) {
          showToast(evalError, 'error')
          return
        }
        payload = mergeInterviewEvaluationPayload(payload, interviewEval, triggerEvent)
      }
      if (toState) payload.to_state = toState
      const res = await processExecApi.trigger(selectedInstance, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
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

  const tabs = useMemo(() => {
    const base = [
      { id: 'reviews', label: `کارهای من (${pendingReviews.length})`, icon: '📥' },
      { id: 'dashboard', label: 'داشبورد', icon: '📊' },
    ]
    if (kindMeta?.showAllTab || user?.role === 'admin') {
      base.push({ id: 'all', label: 'همه فرایندها', icon: '🔄' })
    }
    base.push({ id: 'students', label: 'دانشجویان', icon: '👨‍🎓' })
    return base
  }, [pendingReviews.length, kindMeta, user?.role])

  const instanceContext = instanceDetail?.context_data || {}
  const transitionsForActions = filterInterviewResultTransitions(
    availableTransitions,
    user,
    instanceContext,
  )
  const canSubmitInterview = canSubmitInterviewResult(user, instanceContext)

  return (
    <div>
      <PopupToast toast={toast} />

      <ResolvedProcessHistoryBanner
        instanceDetail={instanceDetail}
        availableTransitions={availableTransitions}
      />

      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.5rem', background: 'var(--primary-light)',
          }}>
            {config.icon}
          </div>
          <div>
            <h1 className="page-title">{config.title}</h1>
            <p className="page-subtitle">
              {user?.full_name_fa || user?.username} | {config.subtitle}
            </p>
          </div>
        </div>
      </div>

      <OperatorPortalReminderBanner
        portalPath={portalPath}
        pendingTab="reviews"
        actionLabel="رفتن به بررسی‌ها"
      />

      <OperatorFollowupSection
        items={operatorFollowupItems}
        readinessAlerts={operatorReadinessAlerts}
        inboxTitle="پرونده‌های باز مرتبط با نقش شما"
      />

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
              onClick={() => setActiveTab('reviews')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('reviews') } }}
              title="مشاهده درخواست‌های منتظر بررسی"
            >
              <div className="stat-icon warning">📥</div>
              <div>
                <div className="stat-value">{pendingReviews.length}</div>
                <div className="stat-label">منتظر بررسی</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('all')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('all') } }}
              title="مشاهده همه فرایندها"
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
              onClick={() => setActiveTab('students')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('students') } }}
              title="مشاهده لیست دانشجویان"
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
              onClick={() => setActiveTab('all')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('all') } }}
              title="مشاهده فرایندهای بررسی‌شده"
            >
              <div className="stat-icon success">✅</div>
              <div>
                <div className="stat-value">{allActiveInstances.length - pendingReviews.length}</div>
                <div className="stat-label">بررسی‌شده</div>
              </div>
            </div>
          </div>

          <div className="dashboard-grid">
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">درخواست‌های منتظر بررسی</h3>
                {pendingReviews.length > 0 && (
                  <button className="btn btn-outline btn-sm" onClick={() => setActiveTab('reviews')}>
                    بررسی
                  </button>
                )}
              </div>
              {pendingReviews.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>✅</div>
                  <p>درخواست منتظری وجود ندارد</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {pendingReviews.slice(0, 6).map(p => (
                    <button
                      key={p.instance_id}
                      onClick={() => { viewInstance(p.instance_id); setActiveTab('reviews') }}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                        textAlign: 'right', border: '1px solid #fde68a', background: '#fffbeb',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 500 }}>
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

            <div className="card">
              <div className="card-header">
                <h3 className="card-title">آمار دانشجویان</h3>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--primary)' }}>
                    {allStudents.filter(s => s.course_type === 'comprehensive').length}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#6b7280' }}>دوره جامع</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--info)' }}>
                    {allStudents.filter(s => s.course_type === 'introductory').length}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#6b7280' }}>دوره آشنایی</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--success)' }}>
                    {allStudents.filter(s => s.therapy_started).length}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#6b7280' }}>درمان فعال</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--warning)' }}>
                    {allStudents.filter(s => s.is_intern).length}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#6b7280' }}>کارآموز</div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Reviews Tab */}
      {activeTab === 'reviews' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">بررسی‌ها ({pendingReviews.length})</h3>
            </div>
            {pendingReviews.length === 0 ? (
              <div className="empty-state" style={{ padding: '3rem' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>✅</div>
                <p>همه موارد بررسی شده‌اند</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {pendingReviews.map(p => (
                  <button
                    key={p.instance_id}
                    onClick={() => viewInstance(p.instance_id)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                      textAlign: 'right',
                      border: selectedInstance === p.instance_id ? `2px solid ${config.accentColor}` : '1px solid var(--border)',
                      background: selectedInstance === p.instance_id ? 'var(--primary-light)' : '#fff',
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

          {instanceDetail && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">
                  {labelProcess(instanceDetail.process_code)}
                </h3>
                <button onClick={() => { setSelectedInstance(null); setInstanceDetail(null) }}
                  className="btn btn-outline btn-sm">بستن</button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت</label>
                  <div style={{ fontWeight: 700, color: config.accentColor }}>{labelState(instanceDetail.current_state)}</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>تاریخ شروع</label>
                  <div>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت کلی</label>
                  {instanceDetail.is_completed
                    ? <span className="badge badge-success">تکمیل</span>
                    : <span className="badge badge-warning">در جریان</span>
                  }
                </div>
              </div>

              <OperatorInstanceGuidanceBlock
                instanceDetail={instanceDetail}
                portalRole={user?.role}
                availableTransitions={availableTransitions}
              />

              <InstanceContextSummary
                contextData={instanceDetail.context_data}
                history={instanceDetail.history}
                title="پرونده و سابقه (قبل از تصمیم)"
              />

              <OperatorStepFormsSection
                instanceId={selectedInstance}
                processCode={instanceDetail.process_code}
                currentState={instanceDetail.current_state}
                contextData={instanceDetail.context_data}
                isCompleted={instanceDetail.is_completed}
                isCancelled={instanceDetail.is_cancelled}
                role={user?.role}
                showToast={showToast}
                onUpdated={() => viewInstance(selectedInstance)}
              />

              {instanceDetail.process_code === 'educational_leave'
                && instanceDetail.current_state === 'committee_review'
                && availableTransitions.some(t => t.trigger_event === 'committee_set_meeting') && (
                <div style={{
                  padding: '1rem 1.25rem', marginBottom: '1.25rem', borderRadius: '10px',
                  background: '#f0f9ff', borderRight: '4px solid #0284c7',
                }}>
                  <h4 style={{ fontSize: '0.92rem', fontWeight: 700, marginBottom: '0.75rem', color: '#0369a1' }}>
                    تعیین جلسه کمیته پیشرفت (زمان و لینک برای دانشجو)
                  </h4>
                  <p style={{ fontSize: '0.82rem', color: '#475569', marginBottom: '0.75rem', lineHeight: 1.65 }}>
                    پیش از زدن دکمهٔ ثبت جلسه، همهٔ موارد زیر را پر کنید؛ پس از انتقال، در پورتال دانشجو و پیامک نمایش داده می‌شود.
                  </p>
                  <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem' }}>
                    تاریخ و ساعت جلسه (محلی مرورگر)
                    <input
                      type="datetime-local"
                      className="psf-input"
                      style={{ width: '100%', marginTop: '0.35rem' }}
                      value={leaveMeeting.committee_meeting_at}
                      onChange={e => setLeaveMeeting(prev => ({ ...prev, committee_meeting_at: e.target.value }))}
                    />
                  </label>
                  <div style={{ marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.35rem' }}>نحوهٔ برگزاری</span>
                    <label style={{ marginLeft: '1rem' }}>
                      <input
                        type="radio"
                        name="leave-meeting-mode"
                        checked={leaveMeeting.committee_meeting_mode === 'in_person'}
                        onChange={() => setLeaveMeeting(prev => ({ ...prev, committee_meeting_mode: 'in_person' }))}
                      />
                      {' '}حضوری
                    </label>
                    <label>
                      <input
                        type="radio"
                        name="leave-meeting-mode"
                        checked={leaveMeeting.committee_meeting_mode === 'online'}
                        onChange={() => setLeaveMeeting(prev => ({ ...prev, committee_meeting_mode: 'online' }))}
                      />
                      {' '}آنلاین
                    </label>
                  </div>
                  {leaveMeeting.committee_meeting_mode === 'online' ? (
                    <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem' }}>
                      لینک جلسه
                      <input
                        type="url"
                        className="psf-input"
                        dir="ltr"
                        style={{ width: '100%', marginTop: '0.35rem' }}
                        placeholder="https://..."
                        value={leaveMeeting.committee_meeting_link}
                        onChange={e => setLeaveMeeting(prev => ({ ...prev, committee_meeting_link: e.target.value }))}
                      />
                    </label>
                  ) : (
                    <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem' }}>
                      آدرس یا محل حضوری
                      <textarea
                        className="psf-input psf-textarea"
                        rows={2}
                        style={{ width: '100%', marginTop: '0.35rem' }}
                        value={leaveMeeting.committee_meeting_location_fa}
                        onChange={e => setLeaveMeeting(prev => ({ ...prev, committee_meeting_location_fa: e.target.value }))}
                      />
                    </label>
                  )}
                </div>
              )}

              {instanceDetail.process_code === 'comprehensive_course_registration'
                && instanceDetail.current_state === 'interview_completed'
                && canSubmitInterview
                && transitionsForActions.some(t => isComprehensiveEvalTrigger(t.trigger_event)) && (
                <div style={{
                  padding: '1rem 1.25rem', marginBottom: '1.25rem', borderRadius: '10px',
                  background: '#fef2f2', borderRight: '4px solid #dc2626',
                }}>
                  <h4 style={{ fontSize: '0.92rem', fontWeight: 700, marginBottom: '0.5rem', color: '#b91c1c' }}>
                    فرم ارزیابی مصاحبهٔ ورود به دوره جامع (محرمانه)
                  </h4>
                  <p style={{ fontSize: '0.8rem', color: '#7f1d1d', marginBottom: '0.75rem', lineHeight: 1.65 }}>
                    این فرم را پیش از ثبت نتیجه پر کنید. توضیحات ارزیابی و دلیل رد محرمانه است و فقط در پورتال پذیرش
                    ذخیره می‌شود و هرگز به دانشجو نمایش داده نمی‌شود. سپس روی دکمهٔ نتیجهٔ موردنظر (پذیرش / رد قطعی /
                    رد با پیشنهاد) کلیک کنید.
                  </p>
                  <label style={{ display: 'block', marginBottom: '0.6rem', fontSize: '0.85rem' }}>
                    توضیحات ارزیابی (الزامی)
                    <textarea
                      className="psf-input psf-textarea"
                      rows={3}
                      style={{ width: '100%', marginTop: '0.35rem' }}
                      value={interviewEval.evaluation_notes}
                      onChange={e => setInterviewEval(prev => ({ ...prev, evaluation_notes: e.target.value }))}
                    />
                  </label>
                  <label style={{ display: 'block', marginBottom: '0.6rem', fontSize: '0.85rem' }}>
                    دلیل رد (محرمانه — الزامی در صورت رد)
                    <textarea
                      className="psf-input psf-textarea"
                      rows={2}
                      style={{ width: '100%', marginTop: '0.35rem' }}
                      placeholder="فقط در صورت رد قطعی یا رد با پیشنهاد لازم است"
                      value={interviewEval.rejection_reason}
                      onChange={e => setInterviewEval(prev => ({ ...prev, rejection_reason: e.target.value }))}
                    />
                  </label>
                  <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.85rem' }}>
                    متن پیشنهاد (الزامی برای «رد همراه با پیشنهاد»)
                    <textarea
                      className="psf-input psf-textarea"
                      rows={2}
                      style={{ width: '100%', marginTop: '0.35rem' }}
                      value={interviewEval.suggestion_text}
                      onChange={e => setInterviewEval(prev => ({ ...prev, suggestion_text: e.target.value }))}
                    />
                  </label>
                </div>
              )}

              <ProcessRollbackSection
                user={user}
                instanceDetail={instanceDetail}
                onRollback={handleProcessRollback}
                busy={rollbackBusy}
              />

              {transitionsForActions.length > 0 && (
                <div style={{
                  padding: '1.25rem', background: 'var(--success-light)',
                  borderRadius: '10px', marginBottom: '1.5rem', borderRight: '4px solid var(--success)',
                }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--success)' }}>
                    تصمیم کمیته
                  </h4>
                  <DecisionNotesBlock
                    value={decisionNotes}
                    onChange={setDecisionNotes}
                    title="توضیح یا مستندات تصمیم (اختیاری)"
                    hint="متن همراه همان دکمه‌ای که می‌زنید در پرونده ثبت می‌شود."
                  />
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {transitionsForActions.map((t, idx) => {
                      const isApproval = t.trigger_event?.includes('approved') || t.trigger_event?.includes('confirm') || t.trigger_event?.includes('accept') || t.trigger_event?.includes('eligible')
                      const isReject = t.trigger_event?.includes('reject') || t.trigger_event?.includes('decline') || t.trigger_event?.includes('ineligible') || t.trigger_event?.includes('terminate')
                      return (
                        <button
                          key={idx}
                          onClick={() => triggerTransition(t)}
                          style={{
                            padding: '0.6rem 1.2rem', borderRadius: '8px', border: 'none',
                            cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
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
          )}
        </div>
      )}

      {/* All Processes Tab */}
      {activeTab === 'all' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">همه فرایندهای فعال ({allActiveInstances.length})</h3>
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
                      <td style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</td>
                      <td>{formatStudentCodeDisplay(p.student_code)}</td>
                      <td>
                        <span className={`badge ${isWaitingForReview(p.current_state, p.process_code) ? 'badge-warning' : 'badge-info'}`}>
                          {labelState(p.current_state)}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.82rem', color: '#6b7280' }}>
                        {p.started_at ? new Date(p.started_at).toLocaleDateString('fa-IR') : '-'}
                      </td>
                      <td>
                        <button className="btn btn-outline btn-sm" onClick={() => { viewInstance(p.instance_id); setActiveTab('reviews') }}>
                          بررسی
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Students Tab */}
      {activeTab === 'students' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">دانشجویان ({allStudents.length})</h3>
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
                {allStudents.map(s => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 600 }}>{formatStudentCodeDisplay(s.student_code)}</td>
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
