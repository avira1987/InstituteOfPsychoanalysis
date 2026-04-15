# ─── فرانت (Vite) — بدون نیاز به npm روی میزبان؛ خروجی در مرحلهٔ نهایی کپی می‌شود ───
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV NPM_CONFIG_FUND=false
COPY admin-ui/package.json admin-ui/package-lock.json ./
# با NODE_ENV=production، npm devDependencies (vite و …) را نصب نمی‌کند → vite: not found
RUN NODE_ENV=development npm ci --no-audit
COPY admin-ui/ ./
# بدون ENV NODE_ENV=production قبل از بیلد — npm ممکن است devDeps را از PATH حذف کند و vite پیدا نشود
RUN npm exec vite build

FROM python:3.12-slim

# بدون gcc/libpq-dev: همهٔ بسته‌ها از wheelhouse با ویل از پیش ساخته نصب می‌شوند (کمتر دانلود از debian، بیلد پایدارتر در شبکه ضعیف).
# اگر روزی pip به سورس نیاز داشت، موقتاً gcc و libpq-dev را برگردانید.
WORKDIR /app

# wheelهای از پیش ساخته‌شده (روی ماشین لینوکس با pip wheel) — pip داخل بیلد به اینترنت نیاز ندارد
COPY docker/wheelhouse /tmp/wheelhouse
COPY requirements-docker.txt .
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheelhouse -r requirements-docker.txt \
    && rm -rf /tmp/wheelhouse

COPY . .
COPY --from=frontend-build /frontend/dist ./admin-ui/dist

EXPOSE 3000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000", "--log-level", "warning"]
