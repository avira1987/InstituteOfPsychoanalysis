import type { APIRequestContext } from '@playwright/test'

export type ProcessInstanceRow = {
  instance_id: string
  process_code: string
  current_state: string
  is_completed: boolean
  is_cancelled: boolean
}

export async function fetchStudentProcessInstances(
  request: APIRequestContext,
  baseURL: string,
  token: string,
  studentId: string,
): Promise<ProcessInstanceRow[]> {
  const r = await request.get(`${baseURL}/api/process/instances/student/${studentId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!r.ok()) {
    throw new Error(`[E2E] GET process instances ${r.status()}: ${await r.text()}`)
  }
  const body = (await r.json()) as { instances?: ProcessInstanceRow[] }
  return body.instances ?? []
}

export async function cancelProcessInstanceAsAdmin(
  request: APIRequestContext,
  baseURL: string,
  adminToken: string,
  instanceId: string,
): Promise<{ ok: boolean }> {
  const r = await request.post(`${baseURL}/api/admin/process-instances/${instanceId}/cancel`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  })
  if (!r.ok()) {
    throw new Error(`[E2E] POST cancel instance ${r.status()}: ${await r.text()}`)
  }
  return r.json() as Promise<{ ok: boolean }>
}
