import React, { useEffect, useState, useCallback } from 'react'
import { dynamicFormsApi } from '../services/api'
import UnifiedFormRenderer from './UnifiedFormRenderer'
import { validateUnifiedAnswers } from '../utils/unifiedFormValidation'
import PopupToast from './PopupToast'

/**
 * فرم‌های داینامیک متصل به نمونه فرایند (همان state) — از API open-for-instance.
 */
export default function StudentDynamicFormsSection({ instanceId, onSubmitted }) {
  const [toast, setToast] = useState(null)
  const [loading, setLoading] = useState(true)
  const [assignments, setAssignments] = useState([])
  const [valuesByAssignment, setValuesByAssignment] = useState({})
  const [busy, setBusy] = useState({})

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const load = useCallback(async () => {
    if (!instanceId) {
      setAssignments([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const res = await dynamicFormsApi.openForInstance(instanceId)
      setAssignments(res.data?.assignments || [])
      setValuesByAssignment({})
    } catch {
      setAssignments([])
      showToast('بارگذاری فرم‌های تکمیلی ناموفق بود.', 'error')
    } finally {
      setLoading(false)
    }
  }, [instanceId])

  useEffect(() => {
    void load()
  }, [load])

  const uploadFileFor = useCallback(
    async (aid, versionId, fieldName, file) => {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('field_name', fieldName)
      fd.append('template_version_id', versionId)
      fd.append('assignment_id', aid)
      fd.append('instance_id', instanceId)
      const res = await dynamicFormsApi.uploadResponseFile(fd)
      return res.data
    },
    [instanceId],
  )

  const submitOne = async (a) => {
    const aid = a.assignment_id
    const answers = valuesByAssignment[aid] || {}
    const { ok, missing } = validateUnifiedAnswers(a.schema_json, answers, { role: 'student' })
    if (!ok) {
      showToast(`موارد ناقص: ${missing.join('، ')}`, 'error')
      return
    }
    setBusy((prev) => ({ ...prev, [aid]: true }))
    try {
      await dynamicFormsApi.createResponse({
        template_version_id: a.version_id,
        assignment_id: aid,
        instance_id: instanceId,
        answers_json: answers,
        submit: true,
      })
      showToast('فرم با موفقیت ثبت شد.')
      await load()
      onSubmitted?.()
    } catch (e) {
      const d = e.response?.data?.detail
      if (d?.error === 'validation_failed' && Array.isArray(d.missing)) {
        showToast(`موارد ناقص: ${d.missing.join('، ')}`, 'error')
      } else {
        showToast(typeof d === 'string' ? d : e.message || 'خطا', 'error')
      }
    } finally {
      setBusy((prev) => ({ ...prev, [aid]: false }))
    }
  }

  if (!instanceId || loading) return null
  if (assignments.length === 0) return null

  return (
    <div className="card" style={{ marginBottom: '1.25rem' }} data-testid="student-dynamic-forms-section">
      <PopupToast toast={toast} />
      <div className="card-header">
        <h3 className="card-title">فرم‌های تکمیلی این مرحله</h3>
        <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.9rem' }}>
          پرسش‌های اضافه تعریف‌شده برای همین وضعیت فرایند؛ پس از ثبت، در پروندهٔ فرایند ذخیره می‌شود.
        </p>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {assignments.map((a) => (
          <div
            key={a.assignment_id}
            style={{
              border: '1px solid var(--border)',
              borderRadius: '10px',
              padding: '1rem',
              background: 'var(--bg)',
            }}
          >
            <h4 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>{a.template_name_fa || a.template_code}</h4>
            <UnifiedFormRenderer
              schemaJson={a.schema_json}
              role="student"
              values={valuesByAssignment[a.assignment_id] || {}}
              onChange={(next) =>
                setValuesByAssignment((prev) => ({ ...prev, [a.assignment_id]: next }))
              }
              onUploadFile={(fieldName, file) =>
                uploadFileFor(a.assignment_id, a.version_id, fieldName, file)
              }
              disabled={!!busy[a.assignment_id]}
              showToast={showToast}
            />
            <button
              type="button"
              className="btn btn-primary"
              style={{ marginTop: '0.75rem' }}
              disabled={!!busy[a.assignment_id]}
              onClick={() => submitOne(a)}
            >
              {busy[a.assignment_id] ? 'در حال ثبت…' : 'ثبت و ارسال'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
