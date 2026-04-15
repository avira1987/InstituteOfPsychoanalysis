import React, { useState } from 'react'
import { filterFormsForStudent, validateStepForms } from '../utils/processFormsStudent'
import { processExecApi } from '../services/api'
import { resolveUploadPublicUrl, parseStepFileUploadValue } from '../utils/uploadPublicUrl'
import {
  resolveCheckboxListOptions,
  normalizeSelectedCoursesValue,
} from '../utils/resolveCourseFieldOptions'

function FieldRow({ field, values, onFieldChange, disabled, instanceId, onUploadError, contextData, lockedInPartialMode }) {
  const t = field.type || 'text'
  const name = field.name
  const id = `pf-${name}`
  const value = values[name]
  const onChange = v => onFieldChange(name, v)
  const locked = !!lockedInPartialMode

  if (t === 'textarea') {
    return (
      <label className="psf-field" htmlFor={id}>
        <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
        <textarea
          id={id}
          className="psf-input psf-textarea"
          value={value ?? ''}
          onChange={e => onChange(e.target.value)}
          disabled={disabled || locked}
          rows={3}
        />
      </label>
    )
  }

  if (t === 'select' && Array.isArray(field.options)) {
    return (
      <label className="psf-field" htmlFor={id}>
        <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
        <select
          id={id}
          className="psf-input"
          value={value ?? ''}
          onChange={e => onChange(e.target.value)}
          disabled={disabled || locked}
        >
          <option value="">— انتخاب کنید —</option>
          {field.options.map(opt => {
            const v = typeof opt === 'object' ? opt.value : opt
            const lab = typeof opt === 'object' ? (opt.label_fa || opt.value) : opt
            return (
              <option key={String(v)} value={v}>{lab}</option>
            )
          })}
        </select>
      </label>
    )
  }

  if (t === 'radio' && Array.isArray(field.options)) {
    return (
      <fieldset className="psf-field psf-fieldset">
        <legend className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</legend>
        <div className="psf-radio-group">
          {field.options.map(opt => {
            const v = typeof opt === 'object' ? opt.value : opt
            const lab = typeof opt === 'object' ? (opt.label_fa || String(v)) : opt
            return (
              <label key={String(v)} className="psf-radio">
                <input
                  type="radio"
                  name={name}
                  checked={value === v}
                  onChange={() => onChange(v)}
                  disabled={disabled || locked}
                />
                <span>{lab}</span>
              </label>
            )
          })}
        </div>
      </fieldset>
    )
  }

  if (t === 'number') {
    return (
      <label className="psf-field" htmlFor={id}>
        <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
        <input
          id={id}
          type="number"
          className="psf-input"
          min={field.min}
          max={field.max}
          value={value ?? ''}
          onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          disabled={disabled || locked}
        />
      </label>
    )
  }

  if (t === 'checkbox') {
    return (
      <label className="psf-field psf-check">
        <input
          type="checkbox"
          checked={!!value}
          onChange={e => onChange(e.target.checked)}
          disabled={disabled || locked}
        />
        <span>{field.label_fa || name}{field.required ? ' *' : ''}</span>
      </label>
    )
  }

  if (t === 'file_upload') {
    const parsed = parseStepFileUploadValue(value)
    const src = parsed.url ? resolveUploadPublicUrl(parsed.url) : ''
    const showImage = parsed.url && parsed.mime.startsWith('image/')
    const showPdf = parsed.url && parsed.mime === 'application/pdf'

    if (locked) {
      return (
        <div className="psf-field">
          <span className="psf-label">{field.label_fa || name}</span>
          <p className="psf-hint" style={{ color: '#15803d', marginTop: 0 }}>
            این مدرک قبلاً توسط پذیرش تأیید شده است؛ نیازی به بارگذاری مجدد ندارید. در صورت اعلام نقص جدید، همین بخش برای بارگذاری باز می‌شود.
          </p>
          {parsed.isLocalPlaceholder && (
            <p className="psf-hint psf-hint--warn">فقط نام فایل محلی ثبت شده بود.</p>
          )}
          {!parsed.url && !parsed.isLocalPlaceholder && <p className="muted" style={{ fontSize: '0.85rem' }}>—</p>}
          {showImage && (
            <div style={{ marginTop: '0.5rem' }}>
              <a href={src} target="_blank" rel="noopener noreferrer">
                <img
                  src={src}
                  alt=""
                  style={{ maxWidth: '100%', maxHeight: '160px', borderRadius: '8px', border: '1px solid #e5e7eb' }}
                />
              </a>
            </div>
          )}
          {showPdf && (
            <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline" style={{ marginTop: '0.5rem' }}>
              باز کردن PDF
            </a>
          )}
          {parsed.url && !showImage && !showPdf && (
            <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline" style={{ marginTop: '0.5rem' }}>
              باز کردن فایل
            </a>
          )}
          {parsed.fileName && (
            <span className="psf-file-name" style={{ display: 'block', marginTop: '0.35rem' }}>{parsed.fileName}</span>
          )}
        </div>
      )
    }

    return (
      <div className="psf-field">
        <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
        <input
          type="file"
          accept={field.accept || '*/*'}
          className="psf-file"
          onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) {
              onChange(null)
              return
            }
            if (!instanceId) {
              onChange({ file_name: file.name, size: file.size, mime: file.type })
              return
            }
            const fd = new FormData()
            fd.append('file', file)
            fd.append('field_name', name)
            try {
              const res = await processExecApi.uploadStudentStepFile(instanceId, fd)
              onUploadError?.(null)
              onChange(res.data)
            } catch (err) {
              const d = err.response?.data?.detail
              onUploadError?.(typeof d === 'string' ? d : 'خطا در آپلود فایل')
            }
          }}
          disabled={disabled}
        />
        {showImage && (
          <div style={{ marginTop: '0.5rem' }}>
            <img
              src={src}
              alt=""
              style={{ maxWidth: '100%', maxHeight: '140px', borderRadius: '8px', border: '1px solid #e5e7eb' }}
            />
          </div>
        )}
        {value?.file_name && (
          <span className="psf-file-name">{value.file_name}</span>
        )}
      </div>
    )
  }

  if (t === 'date_picker') {
    return (
      <label className="psf-field" htmlFor={id}>
        <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
        {field.description_fa && <p className="psf-hint">{field.description_fa}</p>}
        <input
          id={id}
          type="date"
          className="psf-input"
          value={value ?? ''}
          onChange={e => onChange(e.target.value)}
          disabled={disabled || locked}
          dir="ltr"
        />
      </label>
    )
  }

  if (t === 'sms_verification') {
    if (locked) {
      const ok = value != null && String(value).trim() !== ''
      return (
        <div className="psf-field">
          <span className="psf-label">{field.label_fa || name}</span>
          <p style={{ margin: '0.35rem 0 0', fontSize: '0.9rem', color: ok ? '#15803d' : '#64748b' }}>
            {ok ? 'تعهدنامه با کد پیامکی ثبت شده است؛ برای این مرحله نیازی به ورود مجدد کد نیست.' : '—'}
          </p>
        </div>
      )
    }
    return (
      <label className="psf-field" htmlFor={id}>
        <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
        {field.description_fa && <p className="psf-hint">{field.description_fa}</p>}
        <input
          id={id}
          type="text"
          className="psf-input"
          dir="ltr"
          placeholder="کد تأیید"
          value={value ?? ''}
          onChange={e => onChange(e.target.value)}
          disabled={disabled}
        />
      </label>
    )
  }

  if (t === 'radio_list' || t === 'checkbox_list') {
    const ackKey = `${name}_ack`
    const resolved = t === 'checkbox_list' ? resolveCheckboxListOptions(field, contextData) : { useFallback: true }
    if (t === 'checkbox_list' && resolved.options && resolved.options.length > 0 && !resolved.useFallback) {
      const selected = normalizeSelectedCoursesValue(value)
      const maxSel = resolved.maxSelect
      const toggle = (code) => {
        let next = normalizeSelectedCoursesValue(value)
        if (next.includes(code)) {
          next = next.filter(x => x !== code)
        } else if (maxSel === 1) {
          next = [code]
        } else if (maxSel == null || next.length < maxSel) {
          next = [...next, code]
        }
        onChange(next)
      }
      return (
        <div className="psf-field psf-advanced">
          <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
          {field.note_fa && <p className="psf-hint">{field.note_fa}</p>}
          {resolved.hint && <p className="psf-hint psf-hint--warn">{resolved.hint}</p>}
          {maxSel != null && (
            <p className="psf-hint">
              حداکثر {maxSel} درس قابل انتخاب است؛ در حال حاضر {selected.length} مورد انتخاب شده است.
            </p>
          )}
          <div className="psf-checkbox-grid" role="group" aria-label={field.label_fa || name}>
            {resolved.options.map(opt => {
              const v = opt.value
              const checked = selected.includes(v)
              const atMax = maxSel != null && !checked && selected.length >= maxSel
              return (
                <label key={v} className={`psf-check-row ${atMax ? 'psf-check-row--disabled' : ''}`}>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={disabled || locked || atMax}
                    onChange={() => toggle(v)}
                    data-testid={`pf-course-opt-${v}`}
                  />
                  <span>{opt.label_fa || v}</span>
                </label>
              )
            })}
          </div>
        </div>
      )
    }
    return (
      <div className="psf-field psf-advanced">
        <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
        <p className="psf-hint">
          اگر لیست زنده در دسترس نیست، مقدار را دستی وارد کنید یا پس از هماهنگی با پذیرش، گزینهٔ تأیید را بزنید.
        </p>
        {resolved.hint && <p className="psf-hint psf-hint--warn">{resolved.hint}</p>}
        <input
          type="text"
          className="psf-input"
          placeholder="مقدار یا شناسهٔ انتخاب"
          dir="ltr"
          value={typeof value === 'string' || value == null ? (value ?? '') : JSON.stringify(value)}
          onChange={e => onChange(e.target.value)}
          disabled={disabled || locked}
          data-testid={`pf-checkbox-list-${name}`}
        />
        <label className="psf-field psf-check">
          <input
            type="checkbox"
            data-testid={`pf-checkbox-list-ack-${name}`}
            checked={!!values[ackKey]}
            onChange={e => onFieldChange(ackKey, e.target.checked)}
            disabled={disabled || locked}
          />
          <span>تأیید می‌کنم این بخش را تکمیل کرده‌ام</span>
        </label>
      </div>
    )
  }

  const inputType = t === 'email' ? 'email' : t === 'tel' ? 'tel' : 'text'
  const textDir = field.dir === 'ltr' ? 'ltr' : inputType === 'text' ? 'rtl' : 'ltr'
  return (
    <label className="psf-field" htmlFor={id}>
      <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
      {field.description_fa && <p className="psf-hint">{field.description_fa}</p>}
      <input
        id={id}
        type={inputType}
        className="psf-input"
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        disabled={disabled || locked}
        dir={textDir}
      />
    </label>
  )
}

/**
 * فرم‌های مرحلهٔ فعلی فرایند (فقط نقش دانشجو)
 */
export default function ProcessStepForms({
  forms,
  values,
  onFieldChange,
  disabled,
  onRegisterSubmit,
  /** آیا API حداقل یک انتقال برای نقش دانشجو برگردانده (دکمهٔ مرحله بعد وجود دارد) */
  hasAvailableTransitions = true,
  /** شناسه نمونه برای آپلود واقعی فایل به سرور */
  instanceId = null,
  /** اگر پر باشد، فقط همین فیلدها (نقص مدارک) نمایش و اعتبارسنجی می‌شوند */
  resubmitFieldNames = null,
  /** پرونده نمونه — برای لیست دروس مجاز از روی interview_result و غیره */
  contextData = null,
}) {
  const [uploadErr, setUploadErr] = useState(null)
  const list = filterFormsForStudent(forms || [])
  if (list.length === 0) return null

  const validateOpts = {
    resubmitFieldNames: Array.isArray(resubmitFieldNames) && resubmitFieldNames.length
      ? resubmitFieldNames
      : undefined,
    contextData: contextData || undefined,
  }
  const { ok, missing } = validateStepForms(forms, values, validateOpts)

  const handleRegisterClick = () => {
    const result = validateStepForms(forms, values, validateOpts)
    if (onRegisterSubmit) {
      onRegisterSubmit(result)
    }
  }

  const partialMode = Array.isArray(resubmitFieldNames) && resubmitFieldNames.length > 0
  const resubmitSet = partialMode ? new Set(resubmitFieldNames) : null
  const lockedInPartial = (fieldName) => partialMode && resubmitSet && !resubmitSet.has(fieldName)

  const leadText = partialMode
    ? 'مدارک تأییدشده در زیر برای مرور شما مانده‌اند؛ فقط مواردی که پذیرش برای اصلاح اعلام کرده دوباره بارگذاری کنید؛ سپس «ثبت اطلاعات این مرحله» را بزنید.'
    : hasAvailableTransitions
      ? 'فیلدها را تکمیل کنید، «ثبت اطلاعات این مرحله» را بزنید؛ سپس در صورت وجود، دکمهٔ «ادامه و ثبت مرحله» را بزنید تا به مرحلهٔ بعد بروید (پرداخت یا پیامک در صورت نیاز توسط سامانه انجام می‌شود).'
      : 'فیلدها را تکمیل و ثبت کنید. ادامهٔ مسیر در این مرحله توسط اداری/سیستم انجام می‌شود؛ بعداً صفحه را تازه کنید.'

  const submitHint = !ok
    ? 'موارد الزام را پر کنید و دوباره ثبت کنید.'
    : hasAvailableTransitions
      ? 'پس از ثبت، در صورت وجود دکمهٔ «ادامه و ثبت مرحله»، همان را بزنید.'
      : 'ثبت انجام شد؛ اقدام بعدی از سمت اداری است.'

  return (
    <div className="process-step-forms">
      <h4 className="psf-title">این مرحله</h4>
      <p className="psf-lead">
        {leadText}
      </p>
      {uploadErr && (
        <div className="psf-warning" role="alert">
          {uploadErr}
        </div>
      )}
      {list.map(form => {
        const fields = form.fields || []
        if (partialMode && fields.length && !fields.some((f) => resubmitFieldNames.includes(f.name))) {
          return (
            <div key={form.code || form.name_fa} className="psf-card">
              <p className="psf-note">موردی برای اصلاح در این فرم نیست؛ با پذیرش هماهنگ کنید.</p>
            </div>
          )
        }
        return (
          <div key={form.code || form.name_fa} className="psf-card">
            <div className="psf-card-head">
              <span className="psf-card-title">{form.name_fa || form.code}</span>
            </div>
            {form.note_fa && <p className="psf-note">{form.note_fa}</p>}
            <div className="psf-fields">
              {fields.map(field => (
                <FieldRow
                  key={field.name}
                  field={field}
                  values={values}
                  disabled={disabled}
                  onFieldChange={onFieldChange}
                  instanceId={instanceId}
                  onUploadError={msg => setUploadErr(msg || null)}
                  contextData={contextData}
                  lockedInPartialMode={lockedInPartial(field.name)}
                />
              ))}
            </div>
          </div>
        )
      })}
      {!ok && (
        <div className="psf-warning" role="status">
          <strong>ناقص:</strong>
          {' '}
          {missing.join('، ')}
        </div>
      )}

      <div className="psf-submit-row">
        <button
          type="button"
          data-testid="quest-step-form-submit"
          className="btn btn-primary psf-submit-btn"
          disabled={disabled}
          onClick={handleRegisterClick}
        >
          ثبت اطلاعات این مرحله
        </button>
        <span className="psf-submit-hint">{submitHint}</span>
      </div>
    </div>
  )
}
