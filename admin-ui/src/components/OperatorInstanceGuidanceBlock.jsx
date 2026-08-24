import React from 'react'
import StudentProcessGuidancePanel from './StudentProcessGuidancePanel'
import { useOperatorProcessGuidance } from '../hooks/useOperatorProcessGuidance'

export default function OperatorInstanceGuidanceBlock({
  instanceDetail,
  portalRole,
  user,
  availableTransitions = [],
  stepFormLocked = false,
}) {
  const { guidance, loading } = useOperatorProcessGuidance({
    instanceDetail,
    portalRole: portalRole || user?.role,
    user,
    availableTransitions,
    stepFormLocked,
  })

  if (loading && !guidance) {
    return (
      <div
        className="spg spg--light"
        data-testid="operator-guidance-block"
        style={{ marginBottom: '1.25rem', opacity: 0.7, fontSize: '0.85rem' }}
      >
        در حال بارگذاری راهنمای مرحله…
      </div>
    )
  }

  if (!guidance) return null

  return (
    <div data-testid="operator-guidance-block" style={{ marginBottom: '1.25rem', minWidth: 0, maxWidth: '100%' }}>
      <StudentProcessGuidancePanel guidance={guidance} variant="light" />
    </div>
  )
}
