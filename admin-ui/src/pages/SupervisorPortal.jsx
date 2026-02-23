import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { processExecApi, studentApi } from '../services/api'

const processLabels = {
  extra_supervision_session: 'جلسه اضافی سوپرویژن',
  supervision_session_increase: 'افزایش جلسات سوپرویژن',
  supervision_session_reduction: 'کاهش جلسات سوپرویژن',
  supervision_50h_completion: 'تکمیل دوره ۵۰ ساعته',
  supervision_block_transition: 'آغاز سوپرویژن بعدی',
  extra_session: 'جلسه اضافی درمان آموزشی',
  therapy_early_termination: 'قطع زودرس درمان',
  therapist_session_cancellation: 'کنسلی جلسه از سوی درمانگر',
}

export default function SupervisorPortal() {
  const { user } = useAuth()
  const [pendingReviews, setPendingReviews] = useState([])
  const [allStudents, setAllStudents] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [triggerPayload, setTriggerPayload] = useState('{}')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  useEffect(() => {
    loadPending()
  }, [])

  const loadPending = async () => {
    try {
      const studentsRes = await studentApi.list()
      const students = studentsRes.data || []
      setAllStudents(students)

      const pending = []
      for (const s of students) {
        try {
          const instRes = await processExecApi.studentInstances(s.id, { is_completed: false })
          const instances = instRes.data?.instances || []
          for (const inst of instances) {
            if (isWaitingForReview(inst.current_state)) {
              pending.push({
                ...inst,
                student_name: s.student_code,
                student_id: s.id,
              })
            }
          }
        } catch { /* skip */ }
      }
      setPendingReviews(pending)
    } catch (err) {
      console.error('Load error:', err)
    } finally {
      setLoading(false)
    }
  }

  const isWaitingForReview = (state) => {
    const reviewStates = [
      'supervisor_review', 'therapist_review', 'site_manager_review',
      'committee_review', 'awaiting_approval', 'pending_review',
      'payment_required',
    ]
    return reviewStates.some(rs => state?.includes(rs) || state?.includes('review'))
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
        trigger_event: triggerEvent,
        payload,
      })

      if (res.data.success) {
        showToast(`تصمیم ثبت شد: ${res.data.to_state}`)
        viewInstance(selectedInstance)
        loadPending()
      } else {
        showToast(res.data.error || 'خطا', 'error')
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا', 'error')
    }
  }

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
      <div className="loading-spinner" />
    </div>
  }

  return (
    <div>
      {toast && (
        <div style={{
          position: 'fixed', top: '1rem', left: '50%', transform: 'translateX(-50%)',
          padding: '0.75rem 1.5rem', borderRadius: '8px', zIndex: 1000, fontWeight: 500,
          background: toast.type === 'error' ? '#fef2f2' : '#f0fdf4',
          color: toast.type === 'error' ? '#dc2626' : '#16a34a',
          border: `1px solid ${toast.type === 'error' ? '#fca5a5' : '#86efac'}`,
        }}>
          {toast.msg}
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">پورتال سوپروایزر / درمانگر</h1>
          <p className="page-subtitle">
            {user?.full_name_fa || user?.username} | درخواست‌های منتظر بررسی: {pendingReviews.length}
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        {/* Pending Reviews */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">درخواست‌های منتظر تصمیم ({pendingReviews.length})</h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {pendingReviews.map(p => (
              <button
                key={p.instance_id}
                onClick={() => viewInstance(p.instance_id)}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                  textAlign: 'right',
                  border: selectedInstance === p.instance_id ? '2px solid #f59e0b' : '1px solid #e5e7eb',
                  background: selectedInstance === p.instance_id ? '#fffbeb' : '#fff',
                }}
              >
                <div>
                  <div style={{ fontWeight: 500 }}>
                    {processLabels[p.process_code] || p.process_code}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                    دانشجو: {p.student_name} | وضعیت: {p.current_state}
                  </div>
                </div>
                <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>منتظر</span>
              </button>
            ))}
            {pendingReviews.length === 0 && (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#9ca3af' }}>
                <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>✓</div>
                <p>درخواست منتظری وجود ندارد</p>
              </div>
            )}
          </div>
        </div>

        {/* Students Overview */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">دانشجویان ({allStudents.length})</h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', maxHeight: '400px', overflowY: 'auto' }}>
            {allStudents.map(s => (
              <div key={s.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '0.5rem 0.75rem', background: '#f9fafb', borderRadius: '6px',
                fontSize: '0.85rem',
              }}>
                <span>{s.student_code}</span>
                <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                  {s.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'}
                  {' | '}
                  {s.weekly_sessions} جلسه/هفته
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Instance Detail */}
      {instanceDetail && (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <div className="card-header">
            <h2 className="card-title">
              بررسی: {processLabels[instanceDetail.process_code] || instanceDetail.process_code}
            </h2>
            <button onClick={() => { setSelectedInstance(null); setInstanceDetail(null) }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem' }}>
              ✕
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <label style={{ fontSize: '0.75rem', color: '#6b7280' }}>وضعیت فعلی</label>
              <div style={{ fontWeight: 600, color: '#f59e0b' }}>{instanceDetail.current_state}</div>
            </div>
            <div>
              <label style={{ fontSize: '0.75rem', color: '#6b7280' }}>داده‌های درخواست</label>
              <pre style={{
                fontSize: '0.75rem', background: '#f9fafb', padding: '0.5rem',
                borderRadius: '6px', direction: 'ltr', textAlign: 'left', maxHeight: '100px',
                overflow: 'auto',
              }}>
                {JSON.stringify(instanceDetail.context_data || {}, null, 2)}
              </pre>
            </div>
            <div>
              <label style={{ fontSize: '0.75rem', color: '#6b7280' }}>تاریخ شروع</label>
              <div>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
            </div>
          </div>

          {/* Decision Buttons */}
          {availableTransitions.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>تصمیم شما</h3>
              <div style={{ marginBottom: '0.5rem' }}>
                <textarea
                  value={triggerPayload}
                  onChange={e => setTriggerPayload(e.target.value)}
                  placeholder='مثال: {"proposed_time": "شنبه ساعت ۱۰"}'
                  style={{
                    width: '100%', minHeight: '60px', padding: '0.5rem', borderRadius: '6px',
                    border: '1px solid #d1d5db', fontFamily: 'monospace', fontSize: '0.8rem',
                    direction: 'ltr', textAlign: 'left',
                  }}
                />
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {availableTransitions.map((t, idx) => {
                  const isApproval = t.trigger_event?.includes('approved') || t.trigger_event?.includes('confirm')
                  const isReject = t.trigger_event?.includes('reject') || t.trigger_event?.includes('unavailable')
                  return (
                    <button
                      key={idx}
                      onClick={() => triggerTransition(t.trigger_event)}
                      style={{
                        padding: '0.6rem 1.2rem', borderRadius: '8px', border: 'none',
                        cursor: 'pointer', fontWeight: 500, fontSize: '0.85rem',
                        background: isApproval ? '#10b981' : isReject ? '#ef4444' : '#3b82f6',
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

          {/* History */}
          {instanceDetail.history && instanceDetail.history.length > 0 && (
            <div>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>تاریخچه</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                {instanceDetail.history.map((h, idx) => (
                  <div key={idx} style={{
                    display: 'flex', alignItems: 'center', gap: '0.5rem',
                    padding: '0.4rem 0.75rem', background: '#f9fafb', borderRadius: '6px',
                    fontSize: '0.8rem',
                  }}>
                    <span style={{ color: '#9ca3af' }}>{idx + 1}.</span>
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
      )}
    </div>
  )
}
