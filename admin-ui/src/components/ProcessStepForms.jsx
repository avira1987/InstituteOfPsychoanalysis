import React from 'react'
import { filterFormsForStudent, validateStepForms } from '../utils/processFormsStudent'

function FieldRow({ field, values, onFieldChange, disabled }) {
  const t = field.type || 'text'
  const name = field.name
  const id = `pf-${name}`
  const value = values[name]
  const onChange = v => onFieldChange(name, v)

  if (t === 'textarea') {
    return (
      <label className="psf-field" htmlFor={id}>
        <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
        <textarea
          id={id}
          className="psf-input psf-textarea"
          value={value ?? ''}
          onChange={e => onChange(e.target.value)}
          disabled={disabled}
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
          disabled={disabled}
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
                  disabled={disabled}
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
          disabled={disabled}
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
          disabled={disabled}
        />
        <span>{field.label_fa || name}{field.required ? ' *' : ''}</span>
      </label>
    )
  }

  if (t === 'file_upload') {
    return (
      <div className="psf-field">
        <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
        <input
          type="file"
          accept={field.accept || '*/*'}
          className="psf-file"
          onChange={e => {
            const file = e.target.files?.[0]
            if (!file) {
              onChange(null)
              return
            }
            onChange({ file_name: file.name, size: file.size, mime: file.type })
          }}
          disabled={disabled}
        />
        {value?.file_name && (
          <span className="psf-file-name">{value.file_name}</span>
        )}
      </div>
    )
  }

  if (t === 'sms_verification') {
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
    return (
      <div className="psf-field psf-advanced">
        <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
        <p className="psf-hint">
          اگر لیست زنده در دسترس نیست، مقدار را دستی وارد کنید یا پس از هماهنگی با پذیرش، گزینهٔ تأیید را بزنید.
        </p>
        <input
          type="text"
          className="psf-input"
          placeholder="مقدار یا شناسهٔ انتخاب"
          dir="ltr"
          value={value ?? ''}
          onChange={e => onChange(e.target.value)}
          disabled={disabled}
          data-testid={`pf-checkbox-list-${name}`}
        />
        <label className="psf-field psf-check">
          <input
            type="checkbox"
            data-testid={`pf-checkbox-list-ack-${name}`}
            checked={!!values[ackKey]}
            onChange={e => onFieldChange(ackKey, e.target.checked)}
            disabled={disabled}
          />
          <span>تأیید می‌کنم این بخش را تکمیل کرده‌ام</span>
        </label>
      </div>
    )
  }

  const inputType = t === 'email' ? 'email' : t === 'tel' ? 'tel' : 'text'
  return (
    <label className="psf-field" htmlFor={id}>
      <span className="psf-label">{field.label_fa || name}{field.required ? ' *' : ''}</span>
      <input
        id={id}
        type={inputType}
        className="psf-input"
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        dir={inputType === 'text' ? 'rtl' : 'ltr'}
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
}) {
  const list = filterFormsForStudent(forms || [])
  if (list.length === 0) return null

  const { ok, missing } = validateStepForms(forms, values)

  const handleRegisterClick = () => {
    const result = validateStepForms(forms, values)
    if (onRegisterSubmit) {
      onRegisterSubmit(result)
    }
  }

  const leadText = hasAvailableTransitions
    ? 'فیلدها را تکمیل کنید، «ثبت اطلاعات این مرحله» را بزنید؛ سپس در صورت وجود، «مرحلهٔ بعد» را انتخاب کنید.'
    : 'فیلدها را تکمیل و ثبت کنید. ادامهٔ مسیر در این مرحله توسط اداری/سیستم انجام می‌شود؛ بعداً صفحه را تازه کنید.'

  const submitHint = !ok
    ? 'موارد الزام را پر کنید و دوباره ثبت کنید.'
    : hasAvailableTransitions
      ? 'پس از ثبت، در صورت وجود دکمهٔ «مرحلهٔ بعد» یا «اقدام»، همان را بزنید.'
      : 'ثبت انجام شد؛ اقدام بعدی از سمت اداری است.'

  return (
    <div className="process-step-forms">
      <h4 className="psf-title">این مرحله</h4>
      <p className="psf-lead">
        {leadText}
      </p>
      {list.map(form => (
        <div key={form.code || form.name_fa} className="psf-card">
          <div className="psf-card-head">
            <span className="psf-card-title">{form.name_fa || form.code}</span>
          </div>
          {form.note_fa && <p className="psf-note">{form.note_fa}</p>}
          <div className="psf-fields">
            {(form.fields || []).map(field => (
              <FieldRow
                key={field.name}
                field={field}
                values={values}
                disabled={disabled}
                onFieldChange={onFieldChange}
              />
            ))}
          </div>
        </div>
      ))}
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
