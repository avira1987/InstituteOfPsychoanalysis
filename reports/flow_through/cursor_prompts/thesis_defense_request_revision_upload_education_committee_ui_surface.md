# Flow-Through Gap: thesis_defense_request / revision_upload

## Context
- **Process:** `thesis_defense_request`
- **State:** `revision_upload`
- **Role:** `education_committee` → portal: `education_committee`
- **Trigger:** `second_defense_scheduled` → `second_defense_held`
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
Build or fix UI so user with role `education_committee` can:
1. Open the correct portal/deep link for this state
2. See and fill the step form
3. Submit the form
4. Click transition `second_defense_scheduled` and reach `second_defense_held`

## Acceptance criteria
- Add `data-testid`: `uf-field-{name}`, `operator-transition-second_defense_scheduled` or `quest-transition-second_defense_held`
- API: `POST .../operator-step-forms/register` (or student variant) returns 200
- API: `POST .../trigger` with `second_defense_scheduled` succeeds
- Playwright flow-through test for this step passes
