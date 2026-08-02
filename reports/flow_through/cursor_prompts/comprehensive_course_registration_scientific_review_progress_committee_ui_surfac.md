# Flow-Through Gap: comprehensive_course_registration / scientific_review

## Context
- **Process:** `comprehensive_course_registration`
- **State:** `scientific_review`
- **Role:** `progress_committee` → portal: `progress_committee`
- **Trigger:** `scientific_approved` → `document_upload`
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
4. Click transition `scientific_approved` and reach `document_upload`

## Acceptance criteria
- Add `data-testid`: `uf-field-{name}`, `operator-transition-scientific_approved` or `quest-transition-document_upload`
- API: `POST .../operator-step-forms/register` (or student variant) returns 200
- API: `POST .../trigger` with `scientific_approved` succeeds
- Playwright flow-through test for this step passes
