import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { processExecApi } from '../services/api'
import UnifiedFormRenderer from './UnifiedFormRenderer'
import { validateSemesterPrepCalendarDates } from '../utils/semesterPrepCalendarValidation'

/**
 * لایهٔ عمومی متادیتا-محور برای «مشاهده + ویرایش/به‌روزرسانی دادهٔ ثبت‌شدهٔ فرایند».
 *
 * این کامپوننت برای همهٔ فرایندها بدون کد اختصاصی کار می‌کند: داده و مجوزها را از
 * `GET /process/{id}/data` می‌گیرد، فیلدهای مرئی برای نقش را نمایش می‌دهد و فقط
 * فیلدهایی را که نقش جاری در `editable_by` آن‌هاست قابل ویرایش می‌کند.
 */
export default function ProcessDataManager({
  instanceId,
  role,
  showToast,
  onUpdated,
  title = 'دادهٔ ثبت‌شدهٔ پرونده',
  /** فقط فرم‌های این state (مثلاً workbench آماده‌سازی ترم) */
  stateCode = null,
}) {
  const [data, setData] = useState(null)
  const [values, setValues] = useState({})
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [reason, setReason] = useState('')
  const [editing, setEditing] = useState(false)
  const [fieldErrors, setFieldErrors] = useState({})

  const load = useCallback(() => {
    if (!instanceId) return
    let active = true
    setLoading(true)
    processExecApi
      .getProcessData(instanceId)
      .then((res) => {
        if (!active) return
        setData(res.data)
        setValues(res.data?.values || {})
      })
      .catch(() => active && setData(null))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [instanceId])

  useEffect(() => {
    const cleanup = load()
    return cleanup
  }, [load])

  const editableSet = useMemo(
    () => new Set(data?.editable_field_names || []),
    [data],
  )

  const forms = useMemo(() => {
    const all = data?.forms || []
    if (!stateCode) return all
    return all.filter((f) => f.used_in_state === stateCode)
  }, [data?.forms, stateCode])
  const canEdit = useMemo(
    () => forms.some((f) => (f.fields || []).some((field) => field.__editable)),
    [forms],
  )

  const save = async () => {
    if (stateCode === 'calendar_entry' && data?.process_code === 'fall_semester_preparation') {
      const calendarErrors = validateSemesterPrepCalendarDates(values)
      if (calendarErrors.length) {
        const nextErrors = {}
        for (const item of calendarErrors) {
          if (item.field && !nextErrors[item.field]) nextErrors[item.field] = item.message
        }
        setFieldErrors(nextErrors)
        showToast?.(calendarErrors[0].message, 'error')
        return
      }
    }
    setFieldErrors({})
    setBusy(true)
    try {
      const fieldValues = {}
      editableSet.forEach((name) => {
        if (values[name] !== undefined) fieldValues[name] = values[name]
      })
      const res = await processExecApi.updateProcessData(instanceId, {
        field_values: fieldValues,
        reason: reason.trim() || undefined,
      })
      showToast?.('تغییرات ذخیره شد.')
      setEditing(false)
      setReason('')
      onUpdated?.(res.data?.context_data)
      load()
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در ذخیرهٔ تغییرات', 'error')
    } finally {
      setBusy(false)
    }
  }

  const cancel = () => {
    setValues(data?.values || {})
    setReason('')
    setEditing(false)
  }

  if (!instanceId) return null
  if (loading) {
    return (
      <div style={{ marginBottom: '1.25rem', padding: '1rem', background: '#f8fafc', borderRadius: '10px' }}>
        <p className="muted" style={{ margin: 0 }}>در حال بارگذاری دادهٔ پرونده…</p>
      </div>
    )
  }
  if (!data || forms.length === 0) return null

  return (
    <div
      data-testid="process-data-manager"
      style={{
        marginBottom: '1.25rem',
        padding: '1rem 1.25rem',
        background: '#f8fafc',
        borderRadius: '10px',
        borderRight: '4px solid #64748b',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: 0, color: '#334155' }}>{title}</h4>
        {canEdit && !editing && (
          <button
            type="button"
            className="btn btn-outline btn-sm"
            data-testid="process-data-edit-toggle"
            onClick={() => setEditing(true)}
          >
            ویرایش داده‌ها
          </button>
        )}
      </div>

      {!canEdit && (
        <p className="muted" style={{ fontSize: '0.8rem', marginTop: 0 }}>
          شما فقط اجازهٔ مشاهدهٔ این داده‌ها را دارید.
        </p>
      )}

      {forms.map((form) => (
        <div key={form.code || form.name_fa || form.title_fa} style={{ marginBottom: '1rem' }}>
          {(form.name_fa || form.title_fa) && (
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              {form.name_fa || form.title_fa}
            </div>
          )}
          <UnifiedFormRenderer
            schemaJson={{ fields: form.fields || [] }}
            values={values}
            onChange={(next) => {
              setValues(next)
              setFieldErrors({})
            }}
            role={role}
            disabled={!editing}
            editableFieldNames={editing ? editableSet : new Set()}
            fieldErrors={fieldErrors}
            showToast={showToast}
          />
        </div>
      ))}

      {editing && (
        <div style={{ marginTop: '0.75rem' }}>
          <label className="psf-field" style={{ display: 'block', marginBottom: '0.5rem' }}>
            <span className="psf-label">دلیل تغییر (اختیاری)</span>
            <textarea
              className="psf-input form-input"
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="برای ثبت در سابقهٔ ممیزی"
            />
          </label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              data-testid="process-data-save"
              disabled={busy}
              onClick={save}
            >
              {busy ? 'در حال ذخیره…' : 'ذخیرهٔ تغییرات'}
            </button>
            <button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={cancel}>
              انصراف
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
