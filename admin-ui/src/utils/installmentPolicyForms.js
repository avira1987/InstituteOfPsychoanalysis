/** هم‌تراز app.services.installment_settings_service.apply_installment_policy_to_forms */

function optionValue(opt) {
  if (opt && typeof opt === 'object') return opt.value
  return opt
}

export function isInstallmentEnabled(policy) {
  if (!policy || typeof policy !== 'object' || !('installment_enabled' in policy)) return true
  return policy.installment_enabled !== false
}

export function applyInstallmentPolicyToForms(forms, policy, contextData) {
  const already = (contextData || {}).payment_method === 'installment'
  const enabled = isInstallmentEnabled(policy) || already
  if (enabled) return Array.isArray(forms) ? forms : []
  return (forms || []).map((form) => {
    if (!form || typeof form !== 'object') return form
    const fields = (form.fields || []).filter((field) => field?.name !== 'installment_count').map((field) => {
      if (field?.name !== 'payment_method' || !Array.isArray(field.options)) return field
      return {
        ...field,
        options: field.options.filter((opt) => optionValue(opt) !== 'installment'),
      }
    })
    return { ...form, fields }
  })
}
