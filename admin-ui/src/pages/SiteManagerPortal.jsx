import React, { useState, useEffect, useMemo } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { usePortalInstanceDeepLink } from '../hooks/usePortalInstanceDeepLink'
import { useProcessCodeUrlFilter } from '../hooks/useProcessCodeUrlFilter'
import { processExecApi, studentApi, panelApi } from '../services/api'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import { notesPayload } from '../utils/decisionPayload'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import { useToast } from '../contexts/ToastContext'
import DocumentsReviewPanel from '../components/DocumentsReviewPanel'
import OperatorPortalReminderBanner from '../components/OperatorPortalReminderBanner'
import OperatorFollowupSection from '../components/OperatorFollowupSection'
import ResolvedProcessHistoryBanner from '../components/ResolvedProcessHistoryBanner'
import OperatorProcessInstancePanel from '../components/OperatorProcessInstancePanel'
import AttendanceTrackingPanel from '../components/AttendanceTrackingPanel'
import Supervision50hCompletionPanel from '../components/Supervision50hCompletionPanel'
import UnannouncedAbsenceReactionPanel from '../components/UnannouncedAbsenceReactionPanel'
import UnannouncedSupervisionAbsenceReactionPanel from '../components/UnannouncedSupervisionAbsenceReactionPanel'

const SITE_MANAGER_DEEP_LINK_TABS = [
  'dashboard',
  'alerts',
  'pending',
  'documentsReview',
  'overview',
]

const siteManagerReviewStates = [
  'site_manager_review', 'site_manager_followup', 'pending_site_manager',
  'attendance_check', 'followup_required', 'site_review',
]

export default function SiteManagerPortal() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('pending')
  const [allStudents, setAllStudents] = useState([])
  const [pendingActions, setPendingActions] = useState([])
  const [attendanceAlerts, setAttendanceAlerts] = useState([])
  const [allActiveInstances, setAllActiveInstances] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [operatorFollowupItems, setOperatorFollowupItems] = useState([])
  const [operatorReadinessAlerts, setOperatorReadinessAlerts] = useState([])
  const { showToast } = useToast()

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

  usePortalInstanceDeepLink({
    loading,
    setActiveTab,
    viewInstance,
    allowedTabs: SITE_MANAGER_DEEP_LINK_TABS,
  })

  const { processCodeFilter, filteredItems: pendingActionsFiltered } = useProcessCodeUrlFilter({
    loading,
    items: pendingActions,
    getProcessCode: (p) => p.process_code,
    getInstanceId: (p) => p.instance_id || p.id,
    viewInstance,
    setActiveTab,
    tabWhenFiltered: 'pending',
  })

  const displayPendingActions = processCodeFilter ? pendingActionsFiltered : pendingActions

  const triggerTransition = async (transition) => {
    if (!selectedInstance) return
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    try {
      let payload = notesPayload(decisionNotes)
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
      if (toState) payload.to_state = toState
      const res = await processExecApi.trigger(selectedInstance, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
      })
      if (res.data.success) {
        showToast(`عملیات انجام شد: ${labelState(res.data.to_state)}`)
        viewInstance(selectedInstance)
        loadData()
      } else {
        showToast(res.data.error || 'خطا', 'error')
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا', 'error')
    }
  }

  /** قبل از return بارگذاری — وگرنه React #310 (تعداد متفاوت هوک). */
  const documentReviewQueue = useMemo(
    () =>
      allActiveInstances.filter(
        i =>
          i.process_code === 'introductory_course_registration' &&
          ['documents_review', 'documents_incomplete'].includes(i.current_state),
      ),
    [allActiveInstances],
  )

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '4rem' }}>
        <div className="loading-spinner" />
      </div>
    )
  }

  const tabs = [
    { id: 'pending', label: `کارهای من (${displayPendingActions.length})`, icon: '📥' },
    { id: 'dashboard', label: 'داشبورد', icon: '📊' },
    { id: 'alerts', label: `هشدارها (${attendanceAlerts.length})`, icon: '🔔' },
    { id: 'documentsReview', label: `بررسی مدارک (${documentReviewQueue.length})`, icon: '📎' },
    { id: 'overview', label: 'نمای کلی', icon: '👁️' },
  ]

  return (
    <div>

      <ResolvedProcessHistoryBanner
        instanceDetail={instanceDetail}
        availableTransitions={availableTransitions}
      />

      <div className="page-header">
        <div>
          <h1 className="page-title">پنل مسئول سایت</h1>
          <p className="page-subtitle">
            {user?.full_name_fa || user?.username} | نظارت بر حضور و غیاب و پیگیری‌ها
          </p>
        </div>
      </div>

      <OperatorPortalReminderBanner portalPath="/panel/portal/site-manager" pendingTab="pending" />

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
                <div className="stat-value">{displayPendingActions.length}</div>
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
                          {labelProcess(a.process_code)}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                          دانشجو: {formatStudentCodeDisplay(a.student_code)} | {labelState(a.current_state)}
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
              {displayPendingActions.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>📭</div>
                  <p>پیگیری منتظری وجود ندارد</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {displayPendingActions.slice(0, 5).map(p => (
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
                          دانشجو: {formatStudentCodeDisplay(p.student_code)}
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
                      <div style={{ fontWeight: 500 }}>{labelProcess(a.process_code)}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                        دانشجو: {formatStudentCodeDisplay(a.student_code)} | {labelState(a.current_state)}
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
            decisionNotes={decisionNotes}
            setDecisionNotes={setDecisionNotes}
            triggerTransition={triggerTransition}
            user={user}
            showToast={showToast}
            onRefreshInstance={() => viewInstance(selectedInstance)}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
          />}
        </div>
      )}

      {/* Pending Tab */}
      {activeTab === 'pending' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">پیگیری‌ها ({displayPendingActions.length})</h3>
            </div>
            {pendingActions.length === 0 ? (
              <div className="empty-state" style={{ padding: '3rem' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>✅</div>
                <p>پیگیری منتظری وجود ندارد</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {displayPendingActions.map(p => (
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
          {instanceDetail && <ActionPanel
            instanceDetail={instanceDetail}
            availableTransitions={availableTransitions}
            decisionNotes={decisionNotes}
            setDecisionNotes={setDecisionNotes}
            triggerTransition={triggerTransition}
            user={user}
            showToast={showToast}
            onRefreshInstance={() => viewInstance(selectedInstance)}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
          />}
        </div>
      )}

      {activeTab === 'documentsReview' && (
        <DocumentsReviewPanel
          queue={documentReviewQueue}
          onRefresh={loadData}
          showToast={showToast}
        />
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
                      <td style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</td>
                      <td>{formatStudentCodeDisplay(p.student_code)}</td>
                      <td>
                        <span className={`badge ${isWaitingForSiteManager(p.current_state) ? 'badge-warning' : 'badge-info'}`}>
                          {labelState(p.current_state)}
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
                decisionNotes={decisionNotes}
                setDecisionNotes={setDecisionNotes}
                triggerTransition={triggerTransition}
                user={user}
                showToast={showToast}
                onRefreshInstance={() => viewInstance(selectedInstance)}
                onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ActionPanel({ instanceDetail, availableTransitions, decisionNotes, setDecisionNotes, triggerTransition, user, showToast, onRefreshInstance, onClose }) {
  const isAttendanceFollowup =
    instanceDetail?.process_code === 'attendance_tracking'
    && instanceDetail?.current_state === 'site_manager_pending'
  const isSupervision50hFollowup =
    instanceDetail?.process_code === 'supervision_50h_completion'
    && instanceDetail?.current_state === 'site_manager_pending'

  return (
    <>
      <AttendanceTrackingPanel
        detail={instanceDetail}
        active={instanceDetail?.process_code === 'attendance_tracking'}
      />
      <Supervision50hCompletionPanel
        detail={instanceDetail}
        active={instanceDetail?.process_code === 'supervision_50h_completion'}
      />
      <UnannouncedAbsenceReactionPanel
        detail={instanceDetail}
        active={instanceDetail?.process_code === 'unannounced_absence_reaction'}
      />
      <UnannouncedSupervisionAbsenceReactionPanel
        detail={instanceDetail}
        active={instanceDetail?.process_code === 'unannounced_supervision_absence_reaction'}
      />
      <OperatorProcessInstancePanel
        user={user}
        instanceDetail={instanceDetail}
        availableTransitions={availableTransitions}
        onClose={onClose}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        onTriggerTransition={triggerTransition}
        decisionNotes={decisionNotes}
        setDecisionNotes={setDecisionNotes}
        showCourseSelection={false}
        contextSummaryTitle="پرونده و سابقه (قبل از اقدام)"
        renderExtraBeforeActions={
          isAttendanceFollowup || isSupervision50hFollowup
            ? () => (
              <>
                {isAttendanceFollowup && (
                  <div
                    data-testid="site-manager-attendance-followup-banner"
                    style={{
                      marginBottom: '1rem',
                      padding: '0.85rem 1rem',
                      borderRadius: '10px',
                      background: '#fef2f2',
                      borderRight: '4px solid var(--danger)',
                      fontSize: '0.88rem',
                      lineHeight: 1.7,
                    }}
                  >
                    <strong>پیگیری عدم ثبت حضور و غیاب (فرایند ۶)</strong>
                    <p style={{ margin: '0.35rem 0 0' }}>
                      درمانگر برای این جلسه حضور/غیاب ثبت نکرده است. پس از تماس یا پیگیری، دکمهٔ
                      «مسئول سایت پیگیری کرد» را بزنید تا پرونده به مرحلهٔ ثبت درمانگر برگردد.
                      در صورت تأخیر بیش از ۲ روز، پرونده به معاون آموزش اسکیت می‌شود.
                    </p>
                  </div>
                )}
                {isSupervision50hFollowup && (
                  <div
                    data-testid="site-manager-supervision-50h-followup-banner"
                    style={{
                      marginBottom: '1rem',
                      padding: '0.85rem 1rem',
                      borderRadius: '10px',
                      background: '#fef2f2',
                      borderRight: '4px solid var(--danger)',
                      fontSize: '0.88rem',
                      lineHeight: 1.7,
                    }}
                  >
                    <strong>پیگیری عدم ثبت سوپرویژن (فرایند ۲۰)</strong>
                    <p style={{ margin: '0.35rem 0 0' }}>
                      سوپروایزر برای این جلسه حضور/غیاب ثبت نکرده است. پس از تماس، دکمهٔ
                      «مسئول سایت پیگیری کرد» را بزنید تا پرونده به مرحلهٔ ثبت سوپروایزر برگردد.
                      در صورت تأخیر بیش از ۲ روز، پرونده به معاون آموزش اسکیت می‌شود.
                    </p>
                  </div>
                )}
              </>
            )
            : undefined
        }
      actionsBoxStyle={{
        padding: '1.25rem',
        background: 'var(--warning-light)',
        borderRadius: '10px',
        marginBottom: '1.5rem',
        borderRight: '4px solid var(--warning)',
      }}
      />
    </>
  )
}
