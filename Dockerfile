FROM python:3.12-slim

# فقط برای apt داخل بیلد (مثلاً socks5h://127.0.0.1:10808 وقتی اینترنت مستقیم نیست).
ARG APT_PROXY
RUN if [ -n "$APT_PROXY" ]; then \
      printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' "$APT_PROXY" "$APT_PROXY" \
        > /etc/apt/apt.conf.d/99anistito-proxy; \
    fi

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/apt/apt.conf.d/99anistito-proxy

# wheelهای از پیش ساخته‌شده (روی ماشین لینوکس با pip wheel) — pip داخل بیلد به اینترنت نیاز ندارد
COPY docker/wheelhouse /tmp/wheelhouse
COPY requirements-docker.txt .
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheelhouse -r requirements-docker.txt \
    && rm -rf /tmp/wheelhouse

COPY . .

EXPOSE 3000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
