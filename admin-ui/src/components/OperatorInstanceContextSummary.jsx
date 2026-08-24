import React from 'react'
import InstanceContextSummary from './InstanceContextSummary'
import { useOperatorContextFormLabels } from '../hooks/useOperatorContextFormLabels'
import { useOperatorProcessGuidance } from '../hooks/useOperatorProcessGuidance'

/**
 * خلاصهٔ پرونده برای اپراتورها — فرم‌ها، راهنما و فیلتر غیر-admin یکجا.
 */
export default function OperatorInstanceContextSummary({
  user,
  instanceDetail,
  availableTransitions = [],
  studentCode,
  studentNameFa,
  forms: formsProp,
  extraLabelForms: extraLabelFormsProp,
  title = 'پرونده و سابقه (قبل از تصمیم)',
  /** برای پنل مصاحبه‌گر: فقط فیلدهای کاربری مصاحبه */
  contextAudience = null,
  showHistory = true,
  ...rest
}) {
  const portalRole = user?.role
  const showTechnicalContext = portalRole === 'admin' && contextAudience !== 'interviewer'
  const { forms: loadedForms, extraLabelForms: loadedExtra } = useOperatorContextFormLabels(instanceDetail)
  const forms = formsProp ?? loadedForms
  const extraLabelForms = extraLabelFormsProp ?? loadedExtra
  const { guidance } = useOperatorProcessGuidance({
    instanceDetail,
    portalRole,
    user,
    availableTransitions,
  })

  if (!instanceDetail) return null

  return (
    <InstanceContextSummary
      contextData={instanceDetail.context_data}
      history={instanceDetail.history}
      forms={forms}
      extraLabelForms={extraLabelForms}
      portalRole={portalRole}
      instanceDetail={instanceDetail}
      guidance={guidance}
      studentCode={studentCode}
      studentNameFa={studentNameFa}
      showTechnicalContext={showTechnicalContext}
      showOperatorCaseFacts
      contextAudience={contextAudience}
      showHistory={showHistory}
      title={title}
      {...rest}
    />
  )
}
