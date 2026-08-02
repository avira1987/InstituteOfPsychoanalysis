import { test, expect } from '@playwright/test'
import { readFileSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import { loginWithPasswordChallenge } from './helpers/auth'
import { getE2eBaseUrl, hasAdminCredentials } from './helpers/env'
import {
  type FlowMatrixRow,
  clickOperatorTransition,
  fillFormFromSpecs,
  loginAsRole,
  resolveDeepLink,
  seedFlowStep,
  submitOperatorForm,
  assertInstanceState,
} from './helpers/flow-through'

const __dirname = dirname(fileURLToPath(import.meta.url))
const matrixPath = resolve(__dirname, '../../reports/flow_through/matrix_enriched.json')

function loadMatrixRows(): FlowMatrixRow[] {
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

const rows = loadMatrixRows()
const baseURL = getE2eBaseUrl()

test.describe('Flow-Through matrix (UI)', () => {
  test.beforeAll(() => {
    if (!rows.length) {
      test.skip(true, `No matrix rows (run build_matrix + resolve_ui_surface): ${matrixPath}`)
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
        studentCode: `FLOW-PW-${row.process_code.slice(0, 8)}-${row.state_code.slice(0, 8)}`,
        instituteStudent: row.process_code.includes('semester_preparation'),
      })

      expect(seed.current_state).toBe(row.state_code)

      const actorToken = await loginAsRole(request, page, row.portal_role)
      const href = resolveDeepLink(row, seed)
      await page.goto(href, { waitUntil: 'domcontentloaded' })

      await expect(page.getByTestId('operator-step-forms-section').or(page.getByTestId('quest-step-form-submit'))).toBeVisible({
        timeout: 30_000,
      })

      if ((row.field_specs || []).length > 0) {
        await fillFormFromSpecs(page, row.field_specs)
        if (row.ui_layer?.includes('operator') || row.ui_layer === 'operator_semester_prep') {
          await submitOperatorForm(page)
        } else {
          const studentSubmit = page.getByTestId('quest-step-form-submit')
          if (await studentSubmit.isVisible()) {
            await studentSubmit.click()
          }
        }
      }

      if (row.ui_layer?.includes('operator') || row.ui_layer === 'operator_semester_prep') {
        await clickOperatorTransition(page, row.trigger)
      } else {
        const tbtn = page.getByTestId(`quest-transition-${row.to_state}`).or(
          page.getByTestId(`quest-transition-${row.trigger}`),
        )
        if (await tbtn.count()) {
          await tbtn.first().click()
        }
      }

      await assertInstanceState(request, actorToken, seed.instance_id, row.to_state)
    })
  }
})
