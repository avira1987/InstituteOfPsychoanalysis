# راهنمای عملیات — انستیتو (Production)

## تماس و اولویت‌بندی حوادث

| سطح | مثال | اقدام |
|-----|------|--------|
| P0 | پرداخت موفق در درگاه ولی فرایند دانشجو پیش نرفته | تطبیق مالی فوراً |
| P1 | پیامک ارسال نشده | بررسی outbox و ملی‌پیامک |
| P2 | اسلات مصاحبه گیر کرده | بررسی Alocom و مهلت پرداخت |

## تطبیق پرداخت (Payment reconciliation)

1. در `audit_logs` رویدادهای `payment_transition_failed` را جستجو کنید.
2. جدول `payment_gateway_receipts` را با `payment_pending` و `financial_records` مقایسه کنید.
3. اگر رسید وجود دارد ولی `payment_pending` هنوز هست: از پنل ادمین ترنزیشن دستی یا `POST /api/process/{id}/rollback` (فقط admin/staff/deputy_education).
4. **هرگز** رکورد مالی تکراری بدون بررسی رسید درگاه ایجاد نکنید.

## بازگردانی دستی فرایند (Rollback)

- `POST /api/process/{instance_id}/rollback` — فقط نقش‌های admin، deputy_education، staff.
- Rollback **فقط وضعیت** را برمی‌گرداند؛ سوابق مالی، جلسات درمان و یکپارچه‌سازی‌های خارجی را خنثی نمی‌کند.

## پیامک و notification outbox

- جدول `notification_outbox`: وضعیت `pending` / `failed` / `sent`.
- Worker هر ۶۰ ثانیه retry می‌کند ( backoff نمایی تا ۳۰ دقیقه).
- در production: `SMS_PROVIDER=mellipayamak` و `SMS_SIMULATION_UI=false`.

## اقدام‌های ناموفق فرایند

- جدول `failed_actions`: اکشن‌های پس از ترنزیشن که خطا داده‌اند.
- اپراتور می‌تواند علت را ببیند و دستی اقدام کند (ارسال مجدد SMS، تکمیل Alocom، …).

## پشتیبان‌گیری و بازیابی

ر. [`docs/BACKUP_RESTORE_RUNBOOK_FA.md`](BACKUP_RESTORE_RUNBOOK_FA.md)

## ظرفیت (VPS ۲GB)

- یک worker uvicorn؛ حدود ۲۰–۴۰ کاربر همزمان سبک.
- حلقه‌های پس‌زمینه: SLA، تقویم، outbox — در همان پروسه.
- برای بار بالاتر: چند worker + leader election (فاز بعدی).
