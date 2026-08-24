import React from 'react'

export function FieldErrorMsg({ message }) {
  if (!message) return null
  return <p className="psf-field-error-msg" role="alert">{message}</p>
}

export function RequiredMark() {
  return <span className="psf-required-mark" aria-hidden="true"> *</span>
}

export function fieldShellClass(error, base = 'psf-field') {
  return error ? `${base} psf-field--error` : base
}

export function FieldChrome({
  htmlFor,
  label,
  required = false,
  hint,
  error,
  children,
  as = 'label',
  className,
  testId,
}) {
  const Tag = as === 'div' ? 'div' : 'label'
  const extra = Tag === 'label' && htmlFor ? { htmlFor } : {}
  return (
    <Tag className={className || fieldShellClass(error)} data-testid={testId} {...extra}>
      {label ? (
        <span className="psf-label form-label">
          {label}
          {required ? <RequiredMark /> : null}
        </span>
      ) : null}
      {hint ? <p className="psf-hint">{hint}</p> : null}
      {children}
      <FieldErrorMsg message={error} />
    </Tag>
  )
}
