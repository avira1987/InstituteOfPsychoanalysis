import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { processExecApi, studentApi } from '../services/api'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import { notesPayload } from '../utils/decisionPayload'
import InstanceContextSummary from '../components/InstanceContextSummary'
import DecisionNotesBlock from '../components/DecisionNotesBlock'
import PanelRoleActionQueue from '../components/PanelRoleActionQueue'

const roleConfig = {
  progress_committee: {
    title: 'پنل کمیته پیشرفت',
    subtitle: 'بررسی مرخصی‌ها، تغییرات درمان و پیشرفت دانشجویان',
    icon: '📈',
    accentColor: 'var(--success)',
    reviewKeywords: ['committee_review', 'progress_committee', 'leave_review', 'progress_review', 'awaiting_committee'],
  },
  education_committee: {
    title: 'پنل کمیته آموزش',
    subtitle: 'بررسی نهایی و صدور حکم ادامه یا توقف',
    icon: '🎓',
    accentColor: 'var(--primary)',
    reviewKeywords: ['education_committee', 'education_review', 'final_verdict', 'continuation_review'],
  },
  supervision_committee: {
    title: 'پنل کمیته نظارت',
    subtitle: 'بررسی موارد انضباطی و ارائه توصیه‌ها',
    icon: '🔍',
    accentColor: 'var(--warning)',
    reviewKeywords: ['supervision_committee', 'supervision_review', 'disciplinary_review'],
  },
  specialized_commission: {
    title: 'پنل کمیسیون تخصصی',
    subtitle: 'بررسی قطع زودرس درمان و تصمیم‌گیری صلاحیت',
    icon: '⚖️',
    accentColor: 'var(--danger)',
    reviewKeywords: ['specialized_commission', 'commission_review', 'eligibility_review', 'early_termination'],
  },
  therapy_committee_chair: {
    title: 'پنل مسئول کمیته درمان آموزشی',
    subtitle: 'واگذاری پیگیری و مشاهده موارد عدم حضور',
    icon: '🏥',
    accentColor: 'var(--info)',
    reviewKeywords: ['therapy_committee', 'chair_review', 'delegation', 'no_show'],
  },
  therapy_committee_executor: {
    title: 'پنل مجری کمیته درمان آموزشی',
    subtitle: 'پیگیری دانشجویان و ثبت گزارش',
    icon: '📝',
    accentColor: 'var(--primary)',
    reviewKeywords: ['executor_review', 'followup', 'executor_report', 'definitive_stop'],
  },
  deputy_education: {
    title: 'پنل معاون مدیر آموزش',
    subtitle: 'مشاهده هشدارهای SLA و درخواست‌های مرخصی',
    icon: '📊',
    accentColor: 'var(--warning)',
    reviewKeywords: ['deputy_review', 'sla_alert', 'escalation', 'deputy_education'],
  },
  monitoring_committee_officer: {
    title: 'پنل مسئول کمیته نظارت',
    subtitle: 'مشاهده هشدارهای تخلف و مدیریت ارجاع بیماران',
    icon: '🛡️',
    accentColor: 'var(--danger)',
    reviewKeywords: ['monitoring', 'violation', 'referral', 'monitoring_committee'],
  },
}

const defaultConfig = {
  title: 'پنل کمیته',
  subtitle: 'بررسی درخواست‌ها و تصمیم‌گیری',
  icon: '📋',
  accentColor: 'var(--primary)',
  reviewKeywords: ['review', 'committee', 'pending', 'awaiting'],
}

export default function CommitteePortal() {
  const { user } = useAuth()
  const config = roleConfig[user?.role] || defaultConfig
  const [activeTab, setActiveTab] = useState('dashboard')
  const [allStudents, setAllStudents] = useState([])
  const [pendingReviews, setPendingReviews] = useState([])
  const [allActiveInstances, setAllActiveInstances] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')
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
      const allActive = []
      for (const s of students) {
        try {
          const instRes = await processExecApi.studentInstances(s.id)
          const instances = instRes.data?.instances || []
          for (const inst of instances) {
            if (!inst.is_completed && !inst.is_cancelled) {
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
    return config.reviewKeywords.some(kw => state.includes(kw))
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

  const tabs = [
    { id: 'dashboard', label: 'داشبورد', icon: '📊' },
    { id: 'reviews', label: `بررسی‌ها (${pendingReviews.length})`, icon: '📥' },
    { id: 'all', label: 'همه فرایندها', icon: '🔄' },
    { id: 'students', label: 'دانشجویان', icon: '👨‍🎓' },
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

          <PanelRoleActionQueue />

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

              <InstanceContextSummary
                contextData={instanceDetail.context_data}
                history={instanceDetail.history}
                title="پرونده و سابقه (قبل از تصمیم)"
              />

              {availableTransitions.length > 0 && (
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
                    {availableTransitions.map((t, idx) => {
                      const isApproval = t.trigger_event?.includes('approved') || t.trigger_event?.includes('confirm') || t.trigger_event?.includes('accept') || t.trigger_event?.includes('eligible')
                      const isReject = t.trigger_event?.includes('reject') || t.trigger_event?.includes('decline') || t.trigger_event?.includes('ineligible') || t.trigger_event?.includes('terminate')
                      return (
                        <button
                          key={idx}
                          onClick={() => triggerTransition(t.trigger_event)}
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
