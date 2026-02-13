import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { processApi, ruleApi } from '../services/api'

export default function ProcessEditor() {
  const { processId } = useParams()
  const navigate = useNavigate()
  const [process, setProcess] = useState(null)
  const [states, setStates] = useState([])
  const [transitions, setTransitions] = useState([])
  const [allRules, setAllRules] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('visual')
  const [toast, setToast] = useState(null)

  // State form
  const [showAddState, setShowAddState] = useState(false)
  const [editingState, setEditingState] = useState(null)
  const [stateForm, setStateForm] = useState({ code: '', name_fa: '', state_type: 'intermediate', assigned_role: '', sla_hours: '' })

  // Transition form
  const [showAddTransition, setShowAddTransition] = useState(false)
  const [editingTransition, setEditingTransition] = useState(null)
  const [transForm, setTransForm] = useState({
    from_state_code: '', to_state_code: '', trigger_event: '', required_role: '',
    priority: 0, description_fa: '', condition_rules: [], actions: '[]',
  })

  // Process edit
  const [editingProcess, setEditingProcess] = useState(false)
  const [processForm, setProcessForm] = useState({})

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    loadData()
  }, [processId])

  const loadData = async () => {
    try {
      const [procRes, statesRes, transRes, rulesRes] = await Promise.all([
        processApi.get(processId),
        processApi.getStates(processId),
        processApi.getTransitions(processId),
        ruleApi.list({ is_active: true }),
      ])
      setProcess(procRes.data)
      setStates(statesRes.data)
      setTransitions(transRes.data)
      setAllRules(rulesRes.data)
      setProcessForm({
        name_fa: procRes.data.name_fa,
        name_en: procRes.data.name_en || '',
        description: procRes.data.description || '',
        initial_state_code: procRes.data.initial_state_code,
      })
    } catch (err) {
      console.error('Failed to load process:', err)
    } finally {
      setLoading(false)
    }
  }

  // ─── Process Edit ─────────────────────────────────
  const handleUpdateProcess = async (e) => {
    e.preventDefault()
    try {
      await processApi.update(processId, processForm)
      showToast('فرایند با موفقیت ویرایش شد')
      setEditingProcess(false)
      loadData()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  // ─── State CRUD ───────────────────────────────────
  const resetStateForm = () => {
    setStateForm({ code: '', name_fa: '', state_type: 'intermediate', assigned_role: '', sla_hours: '' })
    setEditingState(null)
    setShowAddState(false)
  }

  const handleAddState = async (e) => {
    e.preventDefault()
    const data = { ...stateForm, sla_hours: stateForm.sla_hours ? parseInt(stateForm.sla_hours) : null }
    try {
      if (editingState) {
        await processApi.updateState(editingState, data)
        showToast('وضعیت ویرایش شد')
      } else {
        await processApi.createState(processId, data)
        showToast('وضعیت جدید اضافه شد')
      }
      resetStateForm()
      loadData()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const startEditState = (s) => {
    setStateForm({
      code: s.code,
      name_fa: s.name_fa,
      state_type: s.state_type,
      assigned_role: s.assigned_role || '',
      sla_hours: s.sla_hours || '',
    })
    setEditingState(s.id)
    setShowAddState(true)
  }

  const handleDeleteState = async (stateId) => {
    if (!confirm('آیا مطمئن هستید؟ وضعیت حذف خواهد شد.')) return
    try {
      await processApi.deleteState(stateId)
      showToast('وضعیت حذف شد')
      loadData()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  // ─── Transition CRUD ──────────────────────────────
  const resetTransForm = () => {
    setTransForm({
      from_state_code: '', to_state_code: '', trigger_event: '', required_role: '',
      priority: 0, description_fa: '', condition_rules: [], actions: '[]',
    })
    setEditingTransition(null)
    setShowAddTransition(false)
  }

  const handleAddTransition = async (e) => {
    e.preventDefault()
    let actions = []
    try {
      actions = JSON.parse(transForm.actions || '[]')
    } catch {
      showToast('فرمت JSON عملیات‌ها نامعتبر است', 'error')
      return
    }
    const data = {
      ...transForm,
      priority: parseInt(transForm.priority) || 0,
      condition_rules: transForm.condition_rules.length > 0 ? transForm.condition_rules : null,
      actions: actions.length > 0 ? actions : null,
    }
    try {
      if (editingTransition) {
        await processApi.updateTransition(editingTransition, data)
        showToast('انتقال ویرایش شد')
      } else {
        await processApi.createTransition(processId, data)
        showToast('انتقال جدید اضافه شد')
      }
      resetTransForm()
      loadData()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const startEditTransition = (t) => {
    setTransForm({
      from_state_code: t.from_state_code,
      to_state_code: t.to_state_code,
      trigger_event: t.trigger_event,
      required_role: t.required_role || '',
      priority: t.priority || 0,
      description_fa: t.description_fa || '',
      condition_rules: t.condition_rules || [],
      actions: JSON.stringify(t.actions || [], null, 2),
    })
    setEditingTransition(t.id)
    setShowAddTransition(true)
  }

  const handleDeleteTransition = async (transId) => {
    if (!confirm('آیا مطمئن هستید؟ انتقال حذف خواهد شد.')) return
    try {
      await processApi.deleteTransition(transId)
      showToast('انتقال حذف شد')
      loadData()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const toggleConditionRule = (ruleCode) => {
    setTransForm((prev) => {
      const rules = prev.condition_rules.includes(ruleCode)
        ? prev.condition_rules.filter((r) => r !== ruleCode)
        : [...prev.condition_rules, ruleCode]
      return { ...prev, condition_rules: rules }
    })
  }

  const getStateTypeClass = (type) => {
    switch (type) {
      case 'initial': return 'initial'
      case 'terminal': return 'terminal'
      default: return 'intermediate'
    }
  }

  const roles = ['student', 'therapist', 'supervisor', 'admin', 'staff', 'progress_committee', 'system']

  if (loading) return <div className="empty-state">در حال بارگذاری...</div>
  if (!process) return <div className="empty-state">فرایند یافت نشد</div>

  return (
    <div>
      {/* Toast */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>{toast.msg}</div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">{process.name_fa}</h1>
          <p className="page-subtitle">کد: {process.code} | نسخه: v{process.version} | وضعیت شروع: {process.initial_state_code}</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-outline" onClick={() => setEditingProcess(!editingProcess)}>
            {editingProcess ? 'لغو' : 'ویرایش فرایند'}
          </button>
          <button className="btn btn-outline" onClick={() => navigate('/processes')}>
            بازگشت به لیست
          </button>
        </div>
      </div>

      {/* Edit Process Form */}
      {editingProcess && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 className="card-title" style={{ marginBottom: '1rem' }}>ویرایش اطلاعات فرایند</h3>
          <form onSubmit={handleUpdateProcess} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">نام فارسی</label>
              <input className="form-input" value={processForm.name_fa} onChange={(e) => setProcessForm({ ...processForm, name_fa: e.target.value })} required />
            </div>
            <div className="form-group">
              <label className="form-label">نام انگلیسی</label>
              <input className="form-input" value={processForm.name_en} onChange={(e) => setProcessForm({ ...processForm, name_en: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label">وضعیت شروع</label>
              <select className="form-input" value={processForm.initial_state_code} onChange={(e) => setProcessForm({ ...processForm, initial_state_code: e.target.value })}>
                <option value="">انتخاب...</option>
                {states.map((s) => <option key={s.code} value={s.code}>{s.name_fa} ({s.code})</option>)}
              </select>
            </div>
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label className="form-label">توضیحات</label>
              <textarea className="form-input" rows="2" value={processForm.description} onChange={(e) => setProcessForm({ ...processForm, description: e.target.value })} />
            </div>
            <div><button className="btn btn-primary" type="submit">ذخیره تغییرات</button></div>
          </form>
        </div>
      )}

      {/* Tab Switcher */}
      <div className="tab-bar">
        {[
          { key: 'visual', label: 'نمای بصری' },
          { key: 'states', label: `وضعیت‌ها (${states.length})` },
          { key: 'transitions', label: `انتقال‌ها (${transitions.length})` },
        ].map((tab) => (
          <button
            key={tab.key}
            className={`tab-item ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Visual Tab */}
      {activeTab === 'visual' && (
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: '1rem' }}>نمودار وضعیت فرایند</h3>
          <div className="process-canvas">
            {states.length === 0 ? (
              <div className="empty-state">
                <p>وضعیتی تعریف نشده. از تب «وضعیت‌ها» اقدام کنید.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', justifyContent: 'center' }}>
                {states.map((s) => (
                  <div key={s.id} className={`state-node ${getStateTypeClass(s.state_type)}`}>
                    <div>
                      <div className="state-label">{s.name_fa}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                        {s.code} | {s.state_type}
                      </div>
                      {s.assigned_role && (
                        <div style={{ fontSize: '0.7rem', marginTop: '0.25rem' }}>
                          <span className="badge badge-info">{s.assigned_role}</span>
                        </div>
                      )}
                      {s.sla_hours && (
                        <div style={{ fontSize: '0.65rem', color: 'var(--warning)', marginTop: '0.15rem' }}>
                          SLA: {s.sla_hours} ساعت
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {transitions.length > 0 && (
              <div style={{ marginTop: '2rem', borderTop: '1px dashed var(--border)', paddingTop: '1rem' }}>
                <h4 style={{ marginBottom: '0.75rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>انتقال‌ها:</h4>
                {transitions.map((t) => (
                  <div key={t.id} className="transition-item">
                    <span className="badge badge-info">{t.from_state_code}</span>
                    <span className="transition-arrow">→</span>
                    <span style={{ fontWeight: 500, color: 'var(--primary)' }}>{t.trigger_event}</span>
                    <span className="transition-arrow">→</span>
                    <span className="badge badge-success">{t.to_state_code}</span>
                    {t.required_role && <span className="badge badge-warning">{t.required_role}</span>}
                    {t.condition_rules && t.condition_rules.length > 0 && (
                      <span className="badge badge-danger" title={t.condition_rules.join(', ')}>
                        {t.condition_rules.length} قانون
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* States Tab */}
      {activeTab === 'states' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">وضعیت‌ها ({states.length})</h3>
            <button className="btn btn-primary btn-sm" onClick={() => { resetStateForm(); setShowAddState(!showAddState) }}>
              {showAddState && !editingState ? 'لغو' : '+ وضعیت جدید'}
            </button>
          </div>

          {showAddState && (
            <form onSubmit={handleAddState} className="inline-form" style={{ marginBottom: '1.5rem' }}>
              <h4 style={{ gridColumn: '1 / -1', marginBottom: '0.5rem' }}>
                {editingState ? 'ویرایش وضعیت' : 'افزودن وضعیت جدید'}
              </h4>
              <div className="form-group">
                <label className="form-label">کد</label>
                <input className="form-input" value={stateForm.code} onChange={(e) => setStateForm({ ...stateForm, code: e.target.value })} required disabled={!!editingState} />
              </div>
              <div className="form-group">
                <label className="form-label">نام فارسی</label>
                <input className="form-input" value={stateForm.name_fa} onChange={(e) => setStateForm({ ...stateForm, name_fa: e.target.value })} required />
              </div>
              <div className="form-group">
                <label className="form-label">نوع</label>
                <select className="form-input" value={stateForm.state_type} onChange={(e) => setStateForm({ ...stateForm, state_type: e.target.value })}>
                  <option value="initial">شروع (initial)</option>
                  <option value="intermediate">میانی (intermediate)</option>
                  <option value="terminal">پایانی (terminal)</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">نقش مسئول</label>
                <select className="form-input" value={stateForm.assigned_role} onChange={(e) => setStateForm({ ...stateForm, assigned_role: e.target.value })}>
                  <option value="">بدون نقش</option>
                  {roles.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">SLA (ساعت)</label>
                <input className="form-input" type="number" value={stateForm.sla_hours} onChange={(e) => setStateForm({ ...stateForm, sla_hours: e.target.value })} placeholder="اختیاری" />
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
                <button className="btn btn-primary" type="submit">{editingState ? 'ذخیره' : 'افزودن'}</button>
                {editingState && <button className="btn btn-outline" type="button" onClick={resetStateForm}>لغو</button>}
              </div>
            </form>
          )}

          <div className="table-container">
            <table>
              <thead>
                <tr><th>کد</th><th>نام</th><th>نوع</th><th>نقش</th><th>SLA</th><th>عملیات</th></tr>
              </thead>
              <tbody>
                {states.length === 0 ? (
                  <tr><td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>وضعیتی تعریف نشده</td></tr>
                ) : (
                  states.map((s) => (
                    <tr key={s.id}>
                      <td><code>{s.code}</code></td>
                      <td>{s.name_fa}</td>
                      <td><span className={`badge badge-${s.state_type === 'initial' ? 'success' : s.state_type === 'terminal' ? 'danger' : 'info'}`}>{s.state_type}</span></td>
                      <td>{s.assigned_role || '-'}</td>
                      <td>{s.sla_hours ? `${s.sla_hours} ساعت` : '-'}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button className="btn btn-outline btn-sm" onClick={() => startEditState(s)}>ویرایش</button>
                          <button className="btn btn-danger btn-sm" onClick={() => handleDeleteState(s.id)}>حذف</button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Transitions Tab */}
      {activeTab === 'transitions' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">انتقال‌ها ({transitions.length})</h3>
            <button className="btn btn-primary btn-sm" onClick={() => { resetTransForm(); setShowAddTransition(!showAddTransition) }}>
              {showAddTransition && !editingTransition ? 'لغو' : '+ انتقال جدید'}
            </button>
          </div>

          {showAddTransition && (
            <form onSubmit={handleAddTransition} className="inline-form" style={{ marginBottom: '1.5rem' }}>
              <h4 style={{ gridColumn: '1 / -1', marginBottom: '0.5rem' }}>
                {editingTransition ? 'ویرایش انتقال' : 'افزودن انتقال جدید'}
              </h4>
              <div className="form-group">
                <label className="form-label">از وضعیت</label>
                <select className="form-input" value={transForm.from_state_code} onChange={(e) => setTransForm({ ...transForm, from_state_code: e.target.value })} required>
                  <option value="">انتخاب...</option>
                  {states.map((s) => <option key={s.code} value={s.code}>{s.name_fa} ({s.code})</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">به وضعیت</label>
                <select className="form-input" value={transForm.to_state_code} onChange={(e) => setTransForm({ ...transForm, to_state_code: e.target.value })} required>
                  <option value="">انتخاب...</option>
                  {states.map((s) => <option key={s.code} value={s.code}>{s.name_fa} ({s.code})</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">رویداد محرک</label>
                <input className="form-input" value={transForm.trigger_event} onChange={(e) => setTransForm({ ...transForm, trigger_event: e.target.value })} required placeholder="مثلاً student_submitted" style={{ direction: 'ltr' }} />
              </div>
              <div className="form-group">
                <label className="form-label">نقش مورد نیاز</label>
                <select className="form-input" value={transForm.required_role} onChange={(e) => setTransForm({ ...transForm, required_role: e.target.value })}>
                  <option value="">بدون محدودیت</option>
                  {roles.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">اولویت</label>
                <input className="form-input" type="number" value={transForm.priority} onChange={(e) => setTransForm({ ...transForm, priority: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">توضیح فارسی</label>
                <input className="form-input" value={transForm.description_fa} onChange={(e) => setTransForm({ ...transForm, description_fa: e.target.value })} placeholder="اختیاری" />
              </div>

              {/* Condition Rules Picker */}
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">شرایط (قوانین)</label>
                <div className="rules-picker">
                  {allRules.length === 0 ? (
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>قانونی تعریف نشده</span>
                  ) : (
                    allRules.map((r) => (
                      <label key={r.code} className={`rule-chip ${transForm.condition_rules.includes(r.code) ? 'selected' : ''}`}>
                        <input
                          type="checkbox"
                          checked={transForm.condition_rules.includes(r.code)}
                          onChange={() => toggleConditionRule(r.code)}
                          style={{ display: 'none' }}
                        />
                        <span>{r.name_fa}</span>
                        <code>{r.code}</code>
                      </label>
                    ))
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">عملیات پس از انتقال (JSON)</label>
                <textarea
                  className="form-input"
                  rows="3"
                  value={transForm.actions}
                  onChange={(e) => setTransForm({ ...transForm, actions: e.target.value })}
                  style={{ fontFamily: 'monospace', direction: 'ltr', textAlign: 'left' }}
                  placeholder='[{"type": "notification", "notification_type": "sms", "template": "...", "recipients": ["student"]}]'
                />
              </div>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn btn-primary" type="submit">{editingTransition ? 'ذخیره' : 'افزودن'}</button>
                {editingTransition && <button className="btn btn-outline" type="button" onClick={resetTransForm}>لغو</button>}
              </div>
            </form>
          )}

          <div className="table-container">
            <table>
              <thead>
                <tr><th>از</th><th></th><th>به</th><th>رویداد</th><th>نقش</th><th>شرایط</th><th>عملیات</th><th>اولویت</th><th>اقدامات</th></tr>
              </thead>
              <tbody>
                {transitions.length === 0 ? (
                  <tr><td colSpan="9" style={{ textAlign: 'center', padding: '2rem' }}>انتقالی تعریف نشده</td></tr>
                ) : (
                  transitions.map((t) => (
                    <tr key={t.id}>
                      <td><span className="badge badge-info">{t.from_state_code}</span></td>
                      <td style={{ textAlign: 'center', fontWeight: 'bold', color: 'var(--primary)' }}>→</td>
                      <td><span className="badge badge-success">{t.to_state_code}</span></td>
                      <td><strong>{t.trigger_event}</strong></td>
                      <td>{t.required_role || '-'}</td>
                      <td>
                        {t.condition_rules && t.condition_rules.length > 0 ? (
                          <span className="badge badge-warning" title={t.condition_rules.join(', ')}>
                            {t.condition_rules.length} قانون
                          </span>
                        ) : '-'}
                      </td>
                      <td>
                        {t.actions && t.actions.length > 0 ? (
                          <span className="badge badge-primary" title={JSON.stringify(t.actions)}>
                            {t.actions.length} عملیات
                          </span>
                        ) : '-'}
                      </td>
                      <td>{t.priority}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button className="btn btn-outline btn-sm" onClick={() => startEditTransition(t)}>ویرایش</button>
                          <button className="btn btn-danger btn-sm" onClick={() => handleDeleteTransition(t.id)}>حذف</button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
