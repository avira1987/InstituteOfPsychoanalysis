# Flow-Through Testing (موج ۱)

ابزار شش‌مرحله‌ای برای کشف شکاف‌های UI/API در فرایندهای حیاتی — جایگزین تست دستی روی فرم‌ها.

## پیش‌نیاز

- PostgreSQL + `alembic upgrade head`
- `pip install -r requirements.txt`
- `cd admin-ui && npm install`
- کاربران دمو: `python -m app.seed_all_roles` یا seed موجود

## ساخت ماتریس

```bash
python -m scripts.flow_through.build_matrix --wave 1
python -m scripts.flow_through.resolve_ui_surface
```

خروجی:
- `reports/flow_through/matrix.json`
- `reports/flow_through/matrix_enriched.json`

## لایه ۱ — تست API (سریع)

```bash
# همهٔ موج ۱
pytest tests/flow_through -q

# فقط proof آماده‌سازی ترم پاییز
FLOW_THROUGH_PROOF=fall_semester_preparation pytest tests/flow_through -q

# یک فرایند
FLOW_THROUGH_PROCESS=start_therapy pytest tests/flow_through -q
```

## لایه ۲ — تست UI (Playwright)

```bash
# بک‌اند + فرانت در حال اجرا؛ یا webServer در playwright.config
cd admin-ui
set E2E_ADMIN_USERNAME=admin
set E2E_ADMIN_PASSWORD=admin123
set FLOW_THROUGH_PROOF=fall_semester_preparation
npm run test:flow-through
```

Seed از API: `POST /api/admin/flow-through/seed` (نیاز به admin token).

## گزارش شکاف و پرامپت Cursor

```bash
python -m scripts.flow_through.report_gaps
python -m scripts.flow_through.generate_cursor_prompts
```

خروجی:
- `reports/flow_through/gaps.json`
- `reports/flow_through/cursor_prompts/*.md`

## data-testid استاندارد

| عنصر | testid |
|------|--------|
| فیلد اپراتور | `uf-field-{name}`, `uf-input-{name}` |
| جدول | `uf-table-{name}` |
| بازه تاریخ | `uf-range-{name}` |
| ذخیره فرم اپراتور | `operator-step-forms-save` |
| ترنزیشن اپراتور | `operator-transition-{trigger}` |
| فرم دانشجو | `quest-step-form-submit` |
| ترنزیشن دانشجو | `quest-transition-{to_state}` |

## فرایندهای موج ۱

از `app/meta/process_nav_order.py` → `_WAVE1_ORDER` (۱۳ فرایند).

## معیار موفقیت

با اجرای API + UI tests، لیست دقیق `gaps.json` تولید شود؛ هر gap یک فایل `.md` برای ساخت UI در Cursor دارد.
