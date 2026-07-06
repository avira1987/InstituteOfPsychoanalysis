/** رویداد سراسری برای به‌روزرسانی زنگوله و صفحهٔ اعلان‌ها پس از انجام کار یا بستن دستی. */
export const PANEL_NOTIFICATIONS_CHANGED_EVENT = 'panel-notifications-changed'

export function dispatchPanelNotificationsChanged() {
  try {
    window.dispatchEvent(new CustomEvent(PANEL_NOTIFICATIONS_CHANGED_EVENT))
  } catch {
    /* ignore */
  }
}
