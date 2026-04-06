#!/bin/sh
# روشن کردن پروکسی محلی (Xray) برای apt/docker روی هاست — بعد از نصب، vpn-host-off.sh را بزنید.
# نیاز: /opt/xray/xray و /opt/xray/config.json
set -eu
XRAY_BIN="/opt/xray/xray"
XRAY_CFG="/opt/xray/config.json"
if [ ! -x "$XRAY_BIN" ] || [ ! -f "$XRAY_CFG" ]; then
  echo "Missing $XRAY_BIN or $XRAY_CFG" >&2
  exit 1
fi

cat > /etc/systemd/system/xray.service << 'UNIT'
[Unit]
Description=Xray (outbound proxy for package installs)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/opt/xray/xray run -c /opt/xray/config.json
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/http-proxy.conf << 'PROXY'
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:10809"
Environment="HTTPS_PROXY=http://127.0.0.1:10809"
Environment="NO_PROXY=localhost,127.0.0.1"
PROXY

systemctl daemon-reload
systemctl enable --now xray
sleep 2
systemctl restart docker
echo "xray + docker proxy ON. Use: proxychains4 apt-get ... for apt"
