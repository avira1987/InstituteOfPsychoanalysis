#!/bin/sh
# خاموش کردن Xray و حذف پروکسی Docker بعد از نصب وابستگیها
set -eu
systemctl stop xray 2>/dev/null || true
systemctl disable xray 2>/dev/null || true
rm -f /etc/systemd/system/xray.service
rm -f /etc/systemd/system/docker.service.d/http-proxy.conf
systemctl daemon-reload
systemctl restart docker
echo "xray OFF, docker proxy removed."
