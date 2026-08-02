# Flow-Through Gap: comprehensive_course_registration / supervision_committee_review

## Context
- **Process:** `comprehensive_course_registration`
- **State:** `supervision_committee_review`
- **Role:** `supervision_committee` → portal: `supervision_committee`
- **Trigger:** `supervision_approved` → `executive_review`
- **Failed at:** `ui_surface` (ui layer)

## Error
```
No UI surface mapped for this step
```

## Expected UI
- **Layer:** `MISSING`
- **Component:** `TBD`

## Form fields (metadata)
(no forms in metadata)

## Task
Build or fix UI so user with role `supervision_committee` can:
1. Open the correct portal/deep link for this state
2. See and fill the step form
3. Submit the form
4. Click transition `supervision_approved` and reach `executive_review`

## Acceptance criteria
- Add `data-testid`: `uf-field-{name}`, `operator-transition-supervision_approved` or `quest-transition-executive_review`
- API: `POST .../operator-step-forms/register` (or student variant) returns 200
- API: `POST .../trigger` with `supervision_approved` succeeds
- Playwright flow-through test for this step passes
