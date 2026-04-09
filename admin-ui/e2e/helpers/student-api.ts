import type { APIRequestContext, Page } from '@playwright/test'

export type StudentMe = {
  id: string
  user_id: string
  student_code: string
  therapy_started: boolean
  current_term: number
  term_count: number
  course_type: string
  extra_data?: Record<string, unknown> | null
}

export async function getTokenFromPage(page: Page): Promise<string | null> {
  return page.evaluate(() => localStorage.getItem('token'))
}

export async function fetchStudentMe(
  request: APIRequestContext,
  baseURL: string,
  token: string,
): Promise<StudentMe> {
  const r = await request.get(`${baseURL}/api/students/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!r.ok()) {
    throw new Error(`[E2E] GET students/me ${r.status()}: ${await r.text()}`)
  }
  return r.json() as Promise<StudentMe>
}

/** دانشجو نباید بتواند پروفایل را بدون نقش اداری ویرایش کند — اجرای واقعی سیاست بک‌اند */
export async function tryPatchStudentAsStudent(
  request: APIRequestContext,
  baseURL: string,
  studentToken: string,
  studentId: string,
  body: Record<string, unknown>,
): Promise<number> {
  const r = await request.patch(`${baseURL}/api/students/${studentId}`, {
    headers: { Authorization: `Bearer ${studentToken}` },
    data: body,
  })
  return r.status()
}

export async function patchStudentAsAdmin(
  request: APIRequestContext,
  baseURL: string,
  adminToken: string,
  studentId: string,
  body: Record<string, unknown>,
): Promise<StudentMe> {
  const r = await request.patch(`${baseURL}/api/students/${studentId}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: body,
  })
  if (!r.ok()) {
    throw new Error(`[E2E] PATCH students (admin) ${r.status()}: ${await r.text()}`)
  }
  return r.json() as Promise<StudentMe>
}

/**
 * Soft-delete E2E user: requires admin (not staff) — matches DELETE /api/admin/users/{id}.
 * Safe to call when cleanup is best-effort (logs non-2xx, does not throw).
 */
export async function deactivateUserAsAdmin(
  request: APIRequestContext,
  baseURL: string,
  adminToken: string,
  userId: string,
): Promise<{ ok: boolean; status: number }> {
  const r = await request.delete(`${baseURL}/api/admin/users/${userId}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  })
  const ok = r.ok()
  if (!ok) {
    console.warn(`[E2E] cleanup DELETE admin/users/${userId} → ${r.status()}: ${await r.text()}`)
  }
  return { ok, status: r.status() }
}
