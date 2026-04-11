#!/usr/bin/env sh
# بیلد admin-ui داخل کانتینر؛ خروجی در ./admin-ui/dist
set -e
cd "$(dirname "$0")/.."
docker compose --profile admin-ui-build run --rm admin-ui-build
