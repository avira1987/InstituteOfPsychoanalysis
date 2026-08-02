import { test, expect } from '@playwright/test'
import { readFileSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import { getE2eBaseUrl, hasAdminCredentials } from '../helpers/env'
import { loginWithPasswordChallenge } from '../helpers/auth'
import {
  type FlowMatrixRow,
  clickOperatorTransition,
  fillFormFromSpecs,
  loginAsRole,
  resolveDeepLink,
  seedFlowStep,
  submitOperatorForm,
  assertInstanceState,
} from '../helpers/flow-through'

const __dirname = dirname(fileURLToPath(import.meta.url))
const matrixPath = resolve(__dirname, '../../../reports/flow_through/onboarding/matrix_enriched.json')

function loadOnboardingRows(): FlowMatrixRow[] {
  if (!existsSync(matrixPath)) {
    return []
  }
  const data = JSON.parse(readFileSync(matrixPath, 'utf8')) as { rows?: FlowMatrixRow[] }
  let rows = data.rows || []
  const proof = process.env.FLOW_THROUGH_PROOF
  if (proof) {
    rows = rows.filter((r) => r.process_code === proof)
  }
  const processFilter = process.env.FLOW_THROUGH_PROCESS
  if (processFilter) {
    rows = rows.filter((r) => r.process_code === processFilter)
  }
  return rows.filter((r) => r.ui_layer !== 'MISSING')
}

const rows = loadOnboardingRows()
const baseURL = getE2eBaseUrl()

test.describe('Onboarding flow-through (UI)', () => {
  test.beforeAll(() => {
    if (!rows.length) {
      test.skip(true, `No onboarding matrix rows: ${matrixPath}`)
    }
    if (!hasAdminCredentials()) {
      test.skip(true, 'Set E2E_ADMIN_USERNAME and E2E_ADMIN_PASSWORD for seed API')
    }
  })

  for (const row of rows) {
    test(`${row.step_id}`, async ({ page, request }) => {
      const adminUser = process.env.E2E_ADMIN_USERNAME || 'admin'
      const adminPass = process.env.E2E_ADMIN_PASSWORD || 'admin123'
      const adminToken = await loginWithPasswordChallenge(request, baseURL, adminUser, adminPass)

      const seed = await seedFlowStep(request, adminToken, row.process_code, row.state_code, {
        studentCode: `FLOW-ONB-PW-${row.process_code.slice(0, 8)}`,
        instituteStudent: row.process_code.includes('semester_preparation'),
      })

      expect(seed.current_state).toBe(row.state_code)

      const actorToken = await loginAsRole(request, page, row.portal_role)
      const href = resolveDeepLink(row, seed)
      await page.goto(href, { waitUntil: 'domcontentloaded' })

      const formSection = page
        .getByTestId('operator-step-forms-section')
        .or(page.getByTestId('quest-step-form-submit'))
        .or(page.getByTestId('interview-slot-picker'))
      await expect(formSection.first()).toBeVisible({ timeout: 30_000 })

      if (row.action_type === 'interview_book') {
        const slotBtn = page.getByTestId('interview-slot-book').first()
        if (await slotBtn.isVisible()) {
          await slotBtn.click()
        }
      } else if ((row.field_specs || []).length > 0) {
        await fillFormFromSpecs(page, row.field_specs)
        if (row.ui_layer?.includes('operator') || row.ui_layer === 'operator_semester_prep') {
          await submitOperatorForm(page)
        } else {
          const studentSubmit = page.getByTestId('quest-step-form-submit')
          if (await studentSubmit.isVisible()) {
            await studentSubmit.click()
          }
        }
        await clickOperatorTransition(page, row.trigger)
      } else {
        await clickOperatorTransition(page, row.trigger)
      }

      await assertInstanceState(request, actorToken, seed.instance_id, row.to_state)
    })
  }
})
