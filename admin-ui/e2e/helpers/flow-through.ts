import type { APIRequestContext, Page } from '@playwright/test'
import { expect } from '@playwright/test'
import { loginWithPasswordChallenge } from './auth'
import { getE2eBaseUrl } from './env'
import { answerFromMathQuestion } from './challenge'

export type FlowMatrixRow = {
  step_id: string
  process_code: string
  state_code: string
  required_role: string
  portal_role: string
  trigger: string
  to_state: string
  form_codes?: string[]
  field_specs?: Array<{
    name: string
    type?: string
    label_fa?: string
    required?: boolean
    options?: unknown[]
    columns?: unknown[]
  }>
  deep_link_template?: string
  ui_layer?: string
  portal_page?: string
  action_type?: string
}

export type SeedResponse = {
  instance_id: string
  student_id: string
  student_code: string
  process_code: string
  target_state: string
  current_state: string
  mode: string
}

const baseURL = getE2eBaseUrl()

export function portalLoginUsername(portalRole: string): string {
  if (portalRole === 'admin') return 'admin'
  if (portalRole === 'student' || portalRole === 'applicant') return ''
  return `${portalRole}1`
}

export function portalPassword(portalRole: string): string {
  return portalRole === 'admin' ? 'admin123' : 'demo123'
}

export async function seedFlowStep(
  request: APIRequestContext,
  adminToken: string,
  processCode: string,
  targetState: string,
  opts?: { studentCode?: string; instituteStudent?: boolean },
): Promise<SeedResponse> {
  const r = await request.post(`${baseURL}/api/admin/flow-through/seed`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: {
      process_code: processCode,
      target_state: targetState,
      student_code: opts?.studentCode,
      institute_student: opts?.instituteStudent ?? processCode.includes('semester_preparation'),
    },
  })
  if (!r.ok()) {
    throw new Error(`[flow-through] seed failed ${r.status()}: ${await r.text()}`)
  }
  return r.json() as Promise<SeedResponse>
}

export async function loginAsRole(
  request: APIRequestContext,
  page: Page,
  portalRole: string,
  studentUsername?: string,
): Promise<string> {
  const username = studentUsername || portalLoginUsername(portalRole)
  const password = portalPassword(portalRole)
  if (!username) {
    throw new Error('student login requires studentUsername from seed')
  }
  const token = await loginWithPasswordChallenge(request, baseURL, username, password)
  await page.goto('/login?staff=1', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  const card = page.locator('.login-card')
  await card.waitFor({ state: 'visible' })
  const ans = answerFromMathQuestion((await card.textContent()) || '')
  await page.getByTestId('login-challenge-answer').fill(ans)
  await page.getByTestId('login-submit').click()
  await page.waitForURL(/\/panel/, { timeout: 45_000 })
  return token
}

export function resolveDeepLink(row: FlowMatrixRow, seed: SeedResponse): string {
  const tpl =
    row.deep_link_template ||
    `/panel/semester-prep/workbench?process_code=${row.process_code}&state_code=${row.state_code}`
  return tpl
    .replace('{instance_id}', seed.instance_id)
    .replace('{student_id}', seed.student_id)
}

export async function fillUnifiedField(
  page: Page,
  spec: NonNullable<FlowMatrixRow['field_specs']>[number],
) {
  const name = spec.name
  const t = (spec.type || 'text').toLowerCase()
  const field = page.getByTestId(`uf-field-${name}`)
  const input = page.getByTestId(`uf-input-${name}`)

  if (t === 'table') {
    const table = page.getByTestId(`uf-table-${name}`)
    await expect(table).toBeVisible({ timeout: 15_000 })
    return
  }
  if (t === 'date_range_list' || t === 'shamsi_date' || t === 'date') {
    const y = page.locator(`[data-testid$="-y"]`).first()
    if (await y.count()) {
      await y.selectOption({ index: 1 })
    }
    return
  }
  if (t === 'checkbox') {
    if (await field.locator('input[type="checkbox"]').count()) {
      await field.locator('input[type="checkbox"]').first().check()
    }
    return
  }
  if (t === 'select' || t === 'radio') {
    if (await input.count()) {
      await input.selectOption({ index: 1 })
    }
    return
  }
  if (await input.count()) {
    await input.fill(t === 'number' ? '1000000' : 'تست flow-through')
    return
  }
  if (await field.count()) {
    await field.locator('input, textarea, select').first().fill('تست')
  }
}

export async function fillFormFromSpecs(page: Page, specs: FlowMatrixRow['field_specs']) {
  for (const spec of specs || []) {
    if (!spec?.name) continue
    await fillUnifiedField(page, spec)
  }
}

export async function submitOperatorForm(page: Page) {
  const btn = page.getByTestId('operator-step-forms-save')
  await expect(btn).toBeVisible({ timeout: 20_000 })
  await btn.click()
}

export async function clickOperatorTransition(page: Page, trigger: string) {
  const btn = page.getByTestId(`operator-transition-${trigger}`)
  await expect(btn).toBeVisible({ timeout: 20_000 })
  await btn.click()
}

export async function assertInstanceState(
  request: APIRequestContext,
  token: string,
  instanceId: string,
  expectedState: string,
) {
  const r = await request.get(`${baseURL}/api/process/${instanceId}/status`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(r.ok()).toBeTruthy()
  const body = (await r.json()) as { current_state: string }
  expect(body.current_state).toBe(expectedState)
}
