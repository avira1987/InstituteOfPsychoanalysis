import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { processExecApi, studentApi } from '../services/api'

const processLabels = {
  educational_leave: 'مرخصی آموزشی',
  start_therapy: 'آغاز درمان آموزشی',
  extra_session: 'جلسه اضافی درمان آموزشی',
  session_payment: 'پرداخت جلسات',
  therapy_changes: 'تغییرات درمان آموزشی',
  therapy_session_increase: 'افزایش جلسات هفتگی درمان',
  therapy_session_reduction: 'کاهش جلسات هفتگی درمان',
  therapy_interruption: 'وقفه در درمان آموزشی',
  student_session_cancellation: 'کنسل کردن جلسات درمان',
  supervision_block_transition: 'آغاز سوپرویژن بعدی',
  supervision_50h_completion: 'تکمیل دوره ۵۰ ساعته سوپرویژن',
  supervision_session_increase: 'افزایش جلسات هفتگی سوپرویژن',
  extra_supervision_session: 'جلسه اضافی سوپرویژن',
  supervision_session_reduction: 'کاهش جلسات هفتگی سوپرویژن',
}

const stateColors = {
  initial: '#3b82f6',
  intermediate: '#f59e0b',
  terminal: '#10b981',
}

export default function StudentPortal() {
  const { user } = useAuth()
  const [studentProfile, setStudentProfile] = useState(null)
  const [activeProcesses, setActiveProcesses] = useState([])
  const [completedProcesses, setCompletedProcesses] = useState([])
  const [availableProcesses, setAvailableProcesses] = useState([])
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
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [defsRes, studentsRes] = await Promise.all([
        processExecApi.definitions(),
        studentApi.list(),
      ])

      const myProfile = studentsRes.data?.find(
        s => s.user_id === user?.id
      )
      setStudentProfile(myProfile)

      if (myProfile) {
        const instancesRes = await processExecApi.studentInstances(myProfile.id)
        const instances = instancesRes.data?.instances || []
        setActiveProcesses(instances.filter(i => !i.is_completed && !i.is_cancelled))
        setCompletedProcesses(instances.filter(i => i.is_completed))
      }

      setAvailableProcesses(defsRes.data?.processes || [])
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
      showToast(`فرایند ${processLabels[processCode] || processCode} آغاز شد`)
      loadData()
      viewInstance(res.data.instance_id)
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا در آغاز فرایند', 'error')
    }
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
        showToast(`انتقال انجام شد: ${res.data.to_state}`)
        viewInstance(selectedInstance)
        loadData()
      } else {
        showToast(res.data.error || 'خطا در انتقال', 'error')
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
          <h1 className="page-title">پورتال دانشجو</h1>
          <p className="page-subtitle">
            {studentProfile
              ? `${user?.full_name_fa || user?.username} | کد: ${studentProfile.student_code} | دوره: ${studentProfile.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'}`
              : 'پروفایل دانشجو یافت نشد'}
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        {/* Available Processes */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">فرایندهای قابل اجرا</h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {availableProcesses.map(p => (
              <button
                key={p.code || p.id}
                onClick={() => startProcess(p.code)}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '0.75rem 1rem', border: '1px solid #e5e7eb', borderRadius: '8px',
                  background: '#fff', cursor: 'pointer', textAlign: 'right',
                }}
              >
                <span style={{ fontWeight: 500 }}>
                  {processLabels[p.code] || p.name_fa || p.code}
                </span>
                <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>آغاز</span>
              </button>
            ))}
            {availableProcesses.length === 0 && (
              <p style={{ color: '#9ca3af', padding: '1rem' }}>فرایندی تعریف نشده است</p>
            )}
          </div>
        </div>

        {/* Active Processes */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">فرایندهای فعال ({activeProcesses.length})</h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {activeProcesses.map(p => (
              <button
                key={p.instance_id}
                onClick={() => viewInstance(p.instance_id)}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                  textAlign: 'right',
                  border: selectedInstance === p.instance_id ? '2px solid #3b82f6' : '1px solid #e5e7eb',
                  background: selectedInstance === p.instance_id ? '#eff6ff' : '#fff',
                }}
              >
                <div>
                  <div style={{ fontWeight: 500 }}>
                    {processLabels[p.process_code] || p.process_code}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                    وضعیت: {p.current_state}
                  </div>
                </div>
                <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>فعال</span>
              </button>
            ))}
            {activeProcesses.length === 0 && (
              <p style={{ color: '#9ca3af', padding: '1rem' }}>فرایند فعالی ندارید</p>
            )}
          </div>

          {completedProcesses.length > 0 && (
            <>
              <div className="card-header" style={{ marginTop: '1rem' }}>
                <h2 className="card-title">تکمیل‌شده ({completedProcesses.length})</h2>
              </div>
              {completedProcesses.slice(0, 5).map(p => (
                <div key={p.instance_id} style={{
                  padding: '0.5rem 1rem', border: '1px solid #d1fae5', borderRadius: '8px',
                  background: '#f0fdf4', marginBottom: '0.25rem', fontSize: '0.85rem',
                }}>
                  {processLabels[p.process_code] || p.process_code}
                  <span className="badge badge-success" style={{ marginRight: '0.5rem', fontSize: '0.65rem' }}>تکمیل</span>
                </div>
              ))}
            </>
          )}
        </div>
      </div>

      {/* Instance Detail */}
      {instanceDetail && (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <div className="card-header">
            <h2 className="card-title">
              جزئیات: {processLabels[instanceDetail.process_code] || instanceDetail.process_code}
            </h2>
            <button onClick={() => { setSelectedInstance(null); setInstanceDetail(null) }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem' }}>
              ✕
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <label style={{ fontSize: '0.75rem', color: '#6b7280' }}>وضعیت فعلی</label>
              <div style={{ fontWeight: 600, color: '#3b82f6' }}>{instanceDetail.current_state}</div>
            </div>
            <div>
              <label style={{ fontSize: '0.75rem', color: '#6b7280' }}>تاریخ شروع</label>
              <div>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
            </div>
            <div>
              <label style={{ fontSize: '0.75rem', color: '#6b7280' }}>وضعیت</label>
              <div>
                {instanceDetail.is_completed
                  ? <span className="badge badge-success">تکمیل‌شده</span>
                  : <span className="badge badge-warning">در جریان</span>
                }
              </div>
            </div>
          </div>

          {/* Available Actions */}
          {availableTransitions.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>اقدامات ممکن</h3>
              <div style={{ marginBottom: '0.5rem' }}>
                <textarea
                  value={triggerPayload}
                  onChange={e => setTriggerPayload(e.target.value)}
                  placeholder='{"key": "value"}'
                  style={{
                    width: '100%', minHeight: '60px', padding: '0.5rem', borderRadius: '6px',
                    border: '1px solid #d1d5db', fontFamily: 'monospace', fontSize: '0.8rem',
                    direction: 'ltr', textAlign: 'left',
                  }}
                />
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {availableTransitions.map((t, idx) => (
                  <button
                    key={idx}
                    onClick={() => triggerTransition(t.trigger_event)}
                    className="btn btn-primary"
                    style={{ fontSize: '0.85rem' }}
                  >
                    {t.description || t.trigger_event}
                    <span style={{ fontSize: '0.7rem', marginRight: '0.5rem', opacity: 0.7 }}>
                      → {t.to_state}
                    </span>
                  </button>
                ))}
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
