import React, { useEffect, useState, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import { dynamicFormsApi } from '../services/api'
import PopupToast from '../components/PopupToast'

const EMPTY_SCHEMA = `{
  "fields": [
    { "name": "note", "type": "textarea", "label_fa": "توضیح کوتاه", "required": true }
  ]
}`

export default function DynamicFormsAdmin() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [toast, setToast] = useState(null)
  const [templates, setTemplates] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [schemaText, setSchemaText] = useState(EMPTY_SCHEMA)
  const [busy, setBusy] = useState(false)
  const [assignments, setAssignments] = useState([])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const canManage = user?.role === 'admin' || user?.role === 'staff'

  const loadList = useCallback(async () => {
    const res = await dynamicFormsApi.listTemplates()
    setTemplates(res.data?.templates || [])
  }, [])

  const loadDetail = async (id) => {
    const res = await dynamicFormsApi.getTemplate(id)
    setDetail(res.data)
    const vers = res.data?.versions || []
    const latest = vers[0]
    if (latest?.schema_json) {
      setSchemaText(JSON.stringify(latest.schema_json, null, 2))
    } else {
      setSchemaText(EMPTY_SCHEMA)
    }
  }

  const loadAssignments = async () => {
    const res = await dynamicFormsApi.listAssignments({})
    setAssignments(res.data?.assignments || [])
  }

  useEffect(() => {
    if (!canManage) return
    loadList().catch(() => showToast('بارگذاری ناموفق', 'error'))
  }, [canManage, loadList])

  useEffect(() => {
    if (!selectedId || !canManage) return
    loadDetail(selectedId).catch(() => showToast('جزئیات قالب ناموفق', 'error'))
    loadAssignments().catch(() => {})
  }, [selectedId, canManage])

  if (!canManage) {
    return (
      <div className="card" style={{ padding: '2rem' }}>
        <p>فقط مدیر یا کارمند دفتر به این بخش دسترسی دارند.</p>
        <button type="button" className="btn btn-outline" onClick={() => navigate('/panel')}>
          بازگشت
        </button>
      </div>
    )
  }

  const handleCreate = async () => {
    const code = window.prompt('کد یکتای قالب (انگلیسی، بدون فاصله):', 'feedback_demo')
    if (!code?.trim()) return
    const nameFa = window.prompt('نام فارسی:', 'فرم بازخورد نمونه') || code
    setBusy(true)
    try {
      await dynamicFormsApi.createTemplate({
        code: code.trim(),
        name_fa: nameFa.trim(),
        audience: 'student',
      })
      showToast('قالب ایجاد شد.')
      await loadList()
    } catch (e) {
      showToast(e.response?.data?.detail || e.message || 'خطا', 'error')
    } finally {
      setBusy(false)
    }
  }

  const handlePublish = async () => {
    if (!selectedId) return
    let schema
    try {
      schema = JSON.parse(schemaText)
    } catch {
      showToast('JSON نامعتبر است.', 'error')
      return
    }
    setBusy(true)
    try {
      await dynamicFormsApi.publishVersion(selectedId, { form_schema_json: schema, publish: true })
      showToast('نسخه منتشر شد.')
      await loadDetail(selectedId)
      await loadList()
    } catch (e) {
      showToast(e.response?.data?.detail || e.message || 'خطا', 'error')
    } finally {
      setBusy(false)
    }
  }

  const handleCreateAssignment = async () => {
    if (!selectedId) {
      showToast('ابتدا قالب را انتخاب کنید.', 'error')
      return
    }
    const pc = window.prompt('کد فرایند (مثلاً introductory_course_registration):', '')?.trim()
    const st = window.prompt('کد وضعیت (state_code):', '')?.trim()
    if (!pc || !st) return
    setBusy(true)
    try {
      await dynamicFormsApi.createAssignment({
        template_id: selectedId,
        assignment_type: 'process',
        process_code: pc,
        state_code: st,
        context_key: `df_${pc}_${st}`.slice(0, 80),
        sort_order: 0,
        active: true,
      })
      showToast('اتصال فرایند ثبت شد.')
      await loadAssignments()
    } catch (e) {
      showToast(e.response?.data?.detail || e.message || 'خطا', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PopupToast toast={toast} />
      <div className="page-header">
        <div>
          <h1 className="page-title">فرم‌های داینامیک</h1>
          <p className="page-subtitle">
            تعریف قالب، انتشار نسخه (schema JSON)، و اتصال به فرایند/وضعیت. دانشجو در همان state فرم را در پنل می‌بیند.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '1.5rem', alignItems: 'start' }}>
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">قالب‌ها</h3>
            <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={handleCreate}>
              + قالب
            </button>
          </div>
          <ul style={{ listStyle: 'none', padding: '0 1rem 1rem', margin: 0 }}>
            {templates.map((t) => (
              <li key={t.id} style={{ marginBottom: '0.35rem' }}>
                <button
                  type="button"
                  className={`btn btn-ghost btn-sm ${selectedId === t.id ? 'active' : ''}`}
                  style={{ width: '100%', textAlign: 'right' }}
                  onClick={() => setSelectedId(t.id)}
                >
                  {t.name_fa}
                  <span className="muted" style={{ fontSize: '0.75rem', display: 'block' }}>
                    {t.code}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title">ویرایش schema (آخرین نسخه)</h3>
            {selectedId && (
              <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={handlePublish}>
                انتشار نسخه
              </button>
            )}
          </div>
          {detail && (
            <p style={{ padding: '0 1rem', marginTop: 0, fontSize: '0.9rem' }} className="muted">
              {detail.name_fa} — نسخه‌ها: {(detail.versions || []).length}
            </p>
          )}
          <div style={{ padding: '0 1rem 1rem' }}>
            <textarea
              className="form-input"
              rows={18}
              value={schemaText}
              onChange={(e) => setSchemaText(e.target.value)}
              style={{ fontFamily: 'monospace', fontSize: '0.82rem', direction: 'ltr', textAlign: 'left' }}
            />
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: '1.5rem' }}>
        <div className="card-header">
          <h3 className="card-title">اتصال به فرایند (assignment)</h3>
          <button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={handleCreateAssignment}>
            + اتصال برای قالب انتخاب‌شده
          </button>
        </div>
        <div style={{ padding: '0 1rem 1rem', overflowX: 'auto' }}>
          <table className="data-table" style={{ width: '100%', fontSize: '0.88rem' }}>
            <thead>
              <tr>
                <th>فرایند</th>
                <th>وضعیت</th>
                <th>قالب</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((a) => (
                <tr key={a.id}>
                  <td>{a.process_code || '—'}</td>
                  <td>{a.state_code || '—'}</td>
                  <td style={{ fontSize: '0.8rem' }}>{a.template_id?.slice(0, 8)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
