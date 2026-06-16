#!/usr/bin/env python3
"""Sync Melipayamak approved pattern list into project metadata.

Attempts SOAP `GetBaseMessage` and stores normalized output at:
  metadata/melipayamak_patterns.json

برای لیست کامل با عنوان و متن از اکسل پنل از این استفاده کنید:
  python scripts/import_melipayamak_patterns_xlsx.py /path/to/export.xlsx

Required env:
  SMS_USERNAME
  SMS_PASSWORD (or SMS_API_KEY fallback)

Optional env:
  MELIPAYAMAK_BASE_SOAP_URL (default: http://api.payamak-panel.com/post/Send.asmx)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "metadata" / "melipayamak_patterns.json"
SOAP_URL = os.environ.get("MELIPAYAMAK_BASE_SOAP_URL", "").strip()
SOAP_CANDIDATES = [
    "http://api.payamak-panel.com/post/Base.asmx",
    "http://api.payamak-panel.com/post/Send.asmx",
]
METHOD_CANDIDATES = [
    "GetBaseMessage",
    "GetBaseMessages",
]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _extract_xml_string(text: str) -> str:
    """Try to extract XML-ish payload from SOAP return body."""
    t = (text or "").strip()
    if not t:
        return ""
    if t.startswith("<"):
        return t
    try:
        return bytes(t, "utf-8").decode("unicode_escape")
    except Exception:
        return t


def _extract_body_ids(obj: Any) -> list[int]:
    out: list[int] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in {"bodyid", "body_id", "id"} and str(v).strip().isdigit():
                iv = int(str(v).strip())
                if iv > 0:
                    out.append(iv)
            out.extend(_extract_body_ids(v))
    elif isinstance(obj, list):
        for i in obj:
            out.extend(_extract_body_ids(i))
    elif isinstance(obj, str):
        out.extend(int(m) for m in re.findall(r'"?bodyId"?\s*[:=]\s*"?(\\d+)"?', obj, flags=re.I))
    return out


def main() -> int:
    username = (os.environ.get("SMS_USERNAME") or "").strip()
    password = (os.environ.get("SMS_PASSWORD") or os.environ.get("SMS_API_KEY") or "").strip()
    if not username or not password:
        # Reuse project settings loader (reads app.config.ENV_FILE_PATH)
        try:
            from app.config import get_settings  # pylint: disable=import-outside-toplevel

            get_settings.cache_clear()
            s = get_settings()
            username = username or (s.SMS_USERNAME or "").strip()
            password = password or ((s.SMS_PASSWORD or s.SMS_API_KEY or "").strip())
        except Exception:
            pass
    if not username or not password:
        print("Missing SMS_USERNAME or SMS_PASSWORD/SMS_API_KEY in environment.", file=sys.stderr)
        return 2

    endpoints = [SOAP_URL] if SOAP_URL else []
    endpoints.extend([x for x in SOAP_CANDIDATES if x and x not in endpoints])
    resp = None
    selected_method = ""
    selected_url = ""
    last_error = ""
    for ep in endpoints:
        for method in METHOD_CANDIDATES:
            envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <{method} xmlns="http://tempuri.org/">
      <username>{username}</username>
      <password>{password}</password>
    </{method}>
  </soap:Body>
</soap:Envelope>"""
            headers = {
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f"http://tempuri.org/{method}",
            }
            try:
                r = requests.post(ep, data=envelope.encode("utf-8"), headers=headers, timeout=30)
            except Exception as e:
                last_error = str(e)
                continue

            txt = r.text or ""
            if r.status_code == 200:
                resp = r
                selected_method = method
                selected_url = ep
                break
            last_error = f"SOAP status {r.status_code}: {txt[:220]}"
            if "Server did not recognize the value of HTTP Header SOAPAction" in txt:
                continue
        if resp is not None:
            break

    if resp is None:
        print(f"SOAP request failed. Last error: {last_error}", file=sys.stderr)
        return 1

    try:
        root = ET.fromstring(resp.text)
    except Exception as e:
        print(f"SOAP XML parse failed: {e}", file=sys.stderr)
        return 1

    ns = {
        "soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "t": "http://tempuri.org/",
    }
    result_node = root.find(f".//t:{selected_method}Result", ns)
    result_text = (result_node.text if result_node is not None else "") or ""
    payload = _extract_xml_string(result_text)

    body_ids: list[int] = []
    raw_json: Any | None = None

    # Try JSON first
    try:
        raw_json = json.loads(payload)
        body_ids = sorted(set(_extract_body_ids(raw_json)))
    except Exception:
        raw_json = None

    # Fallback: scan raw payload
    if not body_ids:
        body_ids = sorted(set(int(m) for m in re.findall(r"\b(\d{3,})\b", payload)))

    normalized = {
        "source": "melipayamak_GetBaseMessage",
        "soap_url": selected_url,
        "soap_method": selected_method,
        "username": username,
        "count": len(body_ids),
        "patterns": [{"bodyId": bid} for bid in body_ids],
        "raw_payload": raw_json if raw_json is not None else payload,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(body_ids)} pattern(s) to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
