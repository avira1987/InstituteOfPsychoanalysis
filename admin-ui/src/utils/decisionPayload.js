/**
 * Payload ارسالی همراه trigger: یادداشت متنی به‌صورت فیلد `notes` در context_data ذخیره می‌شود.
 * @param {string} decisionNotes
 * @returns {Record<string, string>}
 */
export function notesPayload(decisionNotes) {
  const t = typeof decisionNotes === 'string' ? decisionNotes.trim() : ''
  return t ? { notes: t } : {}
}
