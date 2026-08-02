# Flow-Through Gap: comprehensive_course_registration / executive_review

## Context
- **Process:** `comprehensive_course_registration`
- **State:** `executive_review`
- **Role:** `progress_committee` → portal: `progress_committee`
- **Trigger:** `executive_opinion_submitted` → `scientific_review`
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
Build or fix UI so user with role `progress_committee` can:
1. Open the correct portal/deep link for this state
2. See and fill the step form
3. Submit the form
4. Click transition `executive_opinion_submitted` and reach `scientific_review`

## Acceptance criteria
- Add `data-testid`: `uf-field-{name}`, `operator-transition-executive_opinion_submitted` or `quest-transition-scientific_review`
- API: `POST .../operator-step-forms/register` (or student variant) returns 200
- API: `POST .../trigger` with `executive_opinion_submitted` succeeds
- Playwright flow-through test for this step passes
