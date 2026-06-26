import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { usePortalInstanceDeepLink } from '../hooks/usePortalInstanceDeepLink'
import { processExecApi, studentApi, panelApi } from '../services/api'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import { notesPayload } from '../utils/decisionPayload'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import { isDocumentReviewState } from '../utils/documentReviewStates'
import InstanceContextSummary from '../components/InstanceContextSummary'
import DecisionNotesBlock from '../components/DecisionNotesBlock'
import PopupToast from '../components/PopupToast'
import OperatorPortalReminderBanner from '../components/OperatorPortalReminderBanner'
import OperatorFollowupSection from '../components/OperatorFollowupSection'
import ResolvedProcessHistoryBanner from '../components/ResolvedProcessHistoryBanner'
import OperatorInstanceGuidanceBlock from '../components/OperatorInstanceGuidanceBlock'
import OperatorStepFormsSection from '../components/OperatorStepFormsSection'
import Supervision50hCompletionPanel from '../components/Supervision50hCompletionPanel'
import StudentSupervisionSessionIncreasePanel from '../components/StudentSupervisionSessionIncreasePanel'
import ShamsiDatePicker from '../components/ShamsiDatePicker'
import {
  isoDateToShamsiParts,
  shamsiDateToIsoDate,
  defaultShamsiDate,
} from '../utils/shamsiDateTime'

const SUPERVISOR_DEEP_LINK_TABS = ['dashboard', 'reviews', 'students', 'processes']

const supervisorReviewStates = [
  'supervisor_review', 'supervisor_decision', 'awaiting_supervisor',
  'pending_supervisor', 'supervisor_approval', 'therapist_review',
]

export default function SupervisorPortal() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('reviews')
  const [allStudents, setAllStudents] = useState([])
  const [pendingReviews, setPendingReviews] = useState([])
  const [allActiveInstances, setAllActiveInstances] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')
  /** پیشنهاد جایگزین برای supervision_session_increase */
  const [supervisionIncreaseAltDate, setSupervisionIncreaseAltDate] = useState('')
  const [supervisionIncreaseAltTime, setSupervisionIncreaseAltTime] = useState('')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [studentSearch, setStudentSearch] = useState('')
  const [operatorFollowupItems, setOperatorFollowupItems] = useState([])
  const [operatorReadinessAlerts, setOperatorReadinessAlerts] = useState([])

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
              // مراحل بررسی/تکمیل مدارک مخصوص پنل کارمند است و در پنل سوپروایزر نمایش داده نمی‌شود.
              if (isDocumentReviewState(inst.current_state)) continue
              const enriched = { ...inst, student_code: s.student_code, student_id: s.id }
              allActive.push(enriched)
              if (isWaitingForReview(inst.current_state)) {
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

  const isWaitingForReview = (state) => {
    if (!state) return false
    return supervisorReviewStates.some(rs => state.includes(rs)) ||
           state.includes('supervisor') || state.includes('review')
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

  usePortalInstanceDeepLink({
    loading,
    setActiveTab,
    viewInstance,
    allowedTabs: SUPERVISOR_DEEP_LINK_TABS,
  })

  const triggerTransition = async (transition) => {
    if (!selectedInstance) return
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    try {
      let payload = notesPayload(decisionNotes)
      const st = instanceDetail?.current_state
      const pcode = instanceDetail?.process_code
      if (
        pcode === 'supervision_session_increase'
        && st === 'supervisor_review'
        && triggerEvent === 'supervisor_proposed_alternative'
      ) {
        const ad = supervisionIncreaseAltDate.trim()
        const at = supervisionIncreaseAltTime.trim()
        if (!ad || !at) {
          showToast('برای پیشنهاد جایگزین، تاریخ و ساعت را انتخاب کنید.', 'error')
          return
        }
        payload = { ...payload, supervisor_alternative_date: ad, supervisor_alternative_time_hhmm: at }
      }
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
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

  const filteredStudents = allStudents.filter(s => {
    if (!studentSearch) return true
    return s.student_code?.includes(studentSearch)
  })

  const tabs = [
    { id: 'reviews', label: `کارهای من (${pendingReviews.length})`, icon: '📥' },
    { id: 'dashboard', label: 'داشبورد', icon: '📊' },
    { id: 'students', label: 'دانشجویان', icon: '👨‍🎓' },
    { id: 'processes', label: 'فرایندها', icon: '🔄' },
  ]

  return (
    <div>
      <PopupToast toast={toast} />

      <ResolvedProcessHistoryBanner
        instanceDetail={instanceDetail}
        availableTransitions={availableTransitions}
      />

      <div className="page-header">
        <div>
          <h1 className="page-title">پنل سوپروایزر</h1>
          <p className="page-subtitle">
            {user?.full_name_fa || user?.username} | نظارت بر درمانگران و دانشجویان
          </p>
        </div>
      </div>

      <OperatorPortalReminderBanner
        portalPath="/panel/portal/supervisor"
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
              onClick={() => setActiveTab('students')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('students') } }}
              title="مشاهده دانشجویان با درمان فعال"
            >
              <div className="stat-icon success">✅</div>
              <div>
                <div className="stat-value">{allStudents.filter(s => s.therapy_started).length}</div>
                <div className="stat-label">درمان فعال</div>
              </div>
            </div>
          </div>

          <div className="dashboard-grid">
            {/* Pending Reviews */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">درخواست‌های منتظر تصمیم</h3>
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
                  {pendingReviews.slice(0, 5).map(p => (
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

            {/* Students Summary */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">خلاصه دانشجویان</h3>
                <button className="btn btn-outline btn-sm" onClick={() => setActiveTab('students')}>
                  همه
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
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
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', maxHeight: '250px', overflowY: 'auto' }}>
                {allStudents.slice(0, 8).map(s => (
                  <div key={s.id} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '0.5rem 0.75rem', background: 'var(--bg)', borderRadius: '6px', fontSize: '0.85rem',
                  }}>
                    <span style={{ fontWeight: 500 }}>{formatStudentCodeDisplay(s.student_code)}</span>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <span className={`badge ${s.therapy_started ? 'badge-success' : 'badge-warning'}`}
                        style={{ fontSize: '0.65rem' }}>
                        {s.therapy_started ? 'درمان فعال' : 'بدون درمان'}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>{s.weekly_sessions} جلسه</span>
                    </div>
                  </div>
                ))}
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
                <p>درخواست منتظری وجود ندارد</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {pendingReviews.map(p => (
                  <button
                    key={p.instance_id}
                    onClick={() => viewInstance(p.instance_id)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer', textAlign: 'right',
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

          {instanceDetail && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">
                  {labelProcess(instanceDetail.process_code)}
                </h3>
                <button onClick={() => { setSelectedInstance(null); setInstanceDetail(null) }}
                  className="btn btn-outline btn-sm">بستن</button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت</label>
                  <div style={{ fontWeight: 700, color: 'var(--warning)' }}>{labelState(instanceDetail.current_state)}</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>تاریخ</label>
                  <div>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
                </div>
              </div>

              <OperatorInstanceGuidanceBlock
                instanceDetail={instanceDetail}
                portalRole={user?.role}
                availableTransitions={availableTransitions}
              />

              <Supervision50hCompletionPanel
                detail={instanceDetail}
                active={instanceDetail?.process_code === 'supervision_50h_completion'}
              />

              <StudentSupervisionSessionIncreasePanel
                detail={instanceDetail}
                active={instanceDetail?.process_code === 'supervision_session_increase'}
                portalRole="supervisor"
              />

              {instanceDetail?.process_code === 'supervision_50h_completion'
                && instanceDetail?.current_state === 'supervisor_recording' && (
                <div
                  data-testid="supervisor-50h-attendance-actions"
                  style={{
                    marginBottom: '1.25rem',
                    padding: '1rem 1.15rem',
                    borderRadius: '10px',
                    background: '#f0fdfa',
                    borderRight: '4px solid #0d9488',
                  }}
                >
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                    ثبت حضور/غیاب جلسه سوپرویژن (فرایند ۲۰)
                  </h4>
                  <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '0 0 0.65rem', lineHeight: 1.6 }}>
                    تاریخ جلسه:
                    {' '}
                    {instanceDetail.context_data?.supervision_session_date
                      || instanceDetail.context_data?.session_date
                      || '—'}
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {availableTransitions
                      .filter((t) => t.trigger_event === 'student_present')
                      .map((t) => (
                        <button
                          key={t.trigger_event}
                          type="button"
                          className="btn btn-success btn-sm"
                          disabled={
                            instanceDetail.context_data?.supervision_session_paid === false
                            || instanceDetail.context_data?.session_paid === false
                          }
                          onClick={() => triggerTransition(t)}
                        >
                          ✓ حاضر (+۱ ساعت)
                        </button>
                      ))}
                    {availableTransitions
                      .filter((t) => t.trigger_event === 'student_absent')
                      .map((t) => (
                        <button
                          key={t.trigger_event}
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={() => triggerTransition(t)}
                        >
                          غایب
                        </button>
                      ))}
                  </div>
                </div>
              )}

              <OperatorStepFormsSection
                instanceId={instanceDetail.instance_id}
                processCode={instanceDetail.process_code}
                currentState={instanceDetail.current_state}
                contextData={instanceDetail.context_data}
                isCompleted={instanceDetail.is_completed}
                isCancelled={instanceDetail.is_cancelled}
                role={user?.role}
                showToast={showToast}
                onUpdated={() => viewInstance(selectedInstance)}
              />

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
                  {instanceDetail.process_code === 'supervision_session_increase'
                    && instanceDetail.current_state === 'supervisor_review' && (
                    <div style={{ marginBottom: '0.75rem', fontSize: '0.88rem' }}>
                      <span style={{ display: 'block', marginBottom: '0.35rem', fontWeight: 600 }}>
                        پیشنهاد زمان جایگزین (فقط هنگام زدن دکمهٔ «پیشنهاد جایگزین»)
                      </span>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end' }}>
                        <div style={{ minWidth: '16rem' }}>
                          <ShamsiDatePicker
                            label="تاریخ جایگزین"
                            value={(supervisionIncreaseAltDate && isoDateToShamsiParts(supervisionIncreaseAltDate)) || defaultShamsiDate()}
                            onChange={(p) => setSupervisionIncreaseAltDate(shamsiDateToIsoDate(p.jy, p.jm, p.jd))}
                          />
                        </div>
                        <label style={{ fontSize: '0.8rem' }}>
                          <span style={{ display: 'block', marginBottom: '0.2rem', fontWeight: 600 }}>ساعت</span>
                          <input
                            className="form-input"
                            type="time"
                            dir="ltr"
                            style={{ textAlign: 'left', maxWidth: '8rem' }}
                            value={supervisionIncreaseAltTime}
                            onChange={e => setSupervisionIncreaseAltTime(e.target.value)}
                          />
                        </label>
                      </div>
                      <span style={{ display: 'block', marginTop: '0.35rem', fontSize: '0.78rem', color: '#64748b' }}>
                        در صورت تایید یا رد بدون پیشنهاد جایگزین، این فیلدها را خالی بگذارید.
                      </span>
                    </div>
                  )}
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

      {/* Students Tab */}
      {activeTab === 'students' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">دانشجویان ({allStudents.length})</h3>
            <input
              type="text"
              placeholder="جستجو..."
              value={studentSearch}
              onChange={e => setStudentSearch(e.target.value)}
              className="form-input"
              style={{ width: '200px' }}
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
                  <th>درمان</th>
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

      {/* Processes Tab */}
      {activeTab === 'processes' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">فرایندهای فعال ({allActiveInstances.length})</h3>
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
                        <span className={`badge ${isWaitingForReview(p.current_state) ? 'badge-warning' : 'badge-info'}`}>
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
    </div>
  )
}
