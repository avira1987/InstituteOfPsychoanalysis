import React, { useState, useEffect } from 'react'
import { ruleApi } from '../services/api'
import PopupToast from '../components/PopupToast'

export default function RuleManager() {
  const [rules, setRules] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [viewExpression, setViewExpression] = useState(null)
  const [toast, setToast] = useState(null)
  const [form, setForm] = useState({
    code: '', name_fa: '', rule_type: 'condition', expression: '{}', error_message_fa: '',
  })

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    loadRules()
  }, [])

  const loadRules = async () => {
    try {
      const res = await ruleApi.list()
      setRules(res.data)
    } catch (err) {
      console.error('Failed to load rules:', err)
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setForm({ code: '', name_fa: '', rule_type: 'condition', expression: '{}', error_message_fa: '' })
    setEditingId(null)
    setShowForm(false)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    let expression
    try {
      expression = JSON.parse(form.expression)
    } catch {
      showToast('فرمت JSON عبارت قانون نامعتبر است', 'error')
      return
    }

    const data = { ...form, expression }

    try {
      if (editingId) {
        await ruleApi.update(editingId, data)
        showToast('قانون با موفقیت ویرایش شد')
      } else {
        await ruleApi.create(data)
        showToast('قانون جدید با موفقیت ایجاد شد')
      }
      resetForm()
      loadRules()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const startEdit = (rule) => {
    setForm({
      code: rule.code,
      name_fa: rule.name_fa,
      rule_type: rule.rule_type,
      expression: JSON.stringify(rule.expression, null, 2),
      error_message_fa: rule.error_message_fa || '',
    })
    setEditingId(rule.id)
    setShowForm(true)
  }

  const handleToggleActive = async (rule) => {
    try {
      if (rule.is_active) {
        await ruleApi.delete(rule.id)
        showToast(`قانون '${rule.code}' غیرفعال شد`)
      } else {
        await ruleApi.update(rule.id, { is_active: true })
        showToast(`قانون '${rule.code}' فعال شد`)
      }
      loadRules()
    } catch (err) {
      showToast('خطا', 'error')
    }
  }

  const filteredRules = rules.filter((r) => {
    if (filter && r.rule_type !== filter) return false
    if (search) {
      const q = search.toLowerCase()
      return r.code.toLowerCase().includes(q) || r.name_fa.includes(search)
    }
    return true
  })

  const ruleTypeLabel = (type) => {
    switch (type) {
      case 'condition': return { label: 'شرط', cls: 'badge-info' }
      case 'validation': return { label: 'اعتبارسنجی', cls: 'badge-warning' }
      case 'computation': return { label: 'محاسبه', cls: 'badge-success' }
      default: return { label: type, cls: 'badge-primary' }
    }
  }

  return (
    <div>
      <PopupToast toast={toast} />

      {/* Expression Modal */}
      {viewExpression && (
        <div className="modal-overlay" onClick={() => setViewExpression(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>عبارت قانون: {viewExpression.code}</h3>
              <button className="modal-close" onClick={() => setViewExpression(null)}>&times;</button>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom: '0.5rem', fontWeight: 600 }}>{viewExpression.name_fa}</p>
              <pre className="code-block">{JSON.stringify(viewExpression.expression, null, 2)}</pre>
              {viewExpression.error_message_fa && (
                <div style={{ marginTop: '1rem' }}>
                  <strong>پیام خطا:</strong> {viewExpression.error_message_fa}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">مدیریت قوانین</h1>
          <p className="page-subtitle">تعریف و ویرایش قوانین پویا (بدون تغییر کد) | مجموع: {rules.length} قانون</p>
        </div>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(!showForm) }}>
          {showForm && !editingId ? 'لغو' : '+ قانون جدید'}
        </button>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 className="card-title" style={{ marginBottom: '1rem' }}>
            {editingId ? 'ویرایش قانون' : 'ایجاد قانون جدید'}
          </h3>
          <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">کد قانون</label>
              <input className="form-input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required disabled={!!editingId} style={{ direction: 'ltr' }} />
            </div>
            <div className="form-group">
              <label className="form-label">نام فارسی</label>
              <input className="form-input" value={form.name_fa} onChange={(e) => setForm({ ...form, name_fa: e.target.value })} required />
            </div>
            <div className="form-group">
              <label className="form-label">نوع</label>
              <select className="form-input" value={form.rule_type} onChange={(e) => setForm({ ...form, rule_type: e.target.value })}>
                <option value="condition">شرط (condition)</option>
                <option value="validation">اعتبارسنجی (validation)</option>
                <option value="computation">محاسبه (computation)</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">پیام خطا (فارسی)</label>
              <input className="form-input" value={form.error_message_fa} onChange={(e) => setForm({ ...form, error_message_fa: e.target.value })} />
            </div>
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label className="form-label">عبارت قانون (JSON)</label>
              <textarea className="form-input" rows="5" value={form.expression}
                onChange={(e) => setForm({ ...form, expression: e.target.value })}
                style={{ fontFamily: 'monospace', direction: 'ltr', textAlign: 'left' }} required />
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn btn-primary" type="submit">{editingId ? 'ذخیره تغییرات' : 'ایجاد'}</button>
              {editingId && <button className="btn btn-outline" type="button" onClick={resetForm}>لغو</button>}
            </div>
          </form>
        </div>
      )}

      {/* Search and Filters */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            className="form-input"
            style={{ flex: 1, minWidth: '200px' }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="جستجو بر اساس کد یا نام..."
          />
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className={`btn ${filter === '' ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setFilter('')}>همه</button>
            <button className={`btn ${filter === 'condition' ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setFilter('condition')}>شرط</button>
            <button className={`btn ${filter === 'validation' ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setFilter('validation')}>اعتبارسنجی</button>
            <button className={`btn ${filter === 'computation' ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setFilter('computation')}>محاسبه</button>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr><th>کد</th><th>نام</th><th>نوع</th><th>عبارت</th><th>وضعیت</th><th>نسخه</th><th>عملیات</th></tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>در حال بارگذاری...</td></tr>
              ) : filteredRules.length === 0 ? (
                <tr><td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>قانونی یافت نشد</td></tr>
              ) : (
                filteredRules.map((r) => {
                  const rt = ruleTypeLabel(r.rule_type)
                  return (
                    <tr key={r.id} style={{ opacity: r.is_active ? 1 : 0.6 }}>
                      <td><code>{r.code}</code></td>
                      <td>{r.name_fa}</td>
                      <td><span className={`badge ${rt.cls}`}>{rt.label}</span></td>
                      <td>
                        <button className="btn btn-outline btn-sm" onClick={() => setViewExpression(r)}>
                          مشاهده عبارت
                        </button>
                      </td>
                      <td>
                        <span className={`badge ${r.is_active ? 'badge-success' : 'badge-danger'}`}>
                          {r.is_active ? 'فعال' : 'غیرفعال'}
                        </span>
                      </td>
                      <td>v{r.version}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button className="btn btn-outline btn-sm" onClick={() => startEdit(r)}>ویرایش</button>
                          <button
                            className={`btn btn-sm ${r.is_active ? 'btn-danger' : 'btn-success'}`}
                            onClick={() => handleToggleActive(r)}
                          >
                            {r.is_active ? 'غیرفعال' : 'فعال'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
