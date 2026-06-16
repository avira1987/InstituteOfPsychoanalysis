#!/usr/bin/env sh
# بیلد admin-ui داخل کانتینر؛ خروجی در ./admin-ui/dist
set -e
cd "$(dirname "$0")/.."
# -T: no TTY so npm output streams on Windows/CI (avoids looking "stuck")
docker compose --profile admin-ui-build run -T --rm admin-ui-build
