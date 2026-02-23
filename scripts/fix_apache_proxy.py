#!/usr/bin/env python3
"""Patch Apache vhosts to add Anistito ProxyPass. Run on server as root."""
import shutil
from pathlib import Path

BLOCK = """
	# Anistito BPM - Proxy to FastAPI
	ProxyPreserveHost On
	ProxyPass /anistito/api/ http://127.0.0.1:8000/api/
	ProxyPassReverse /anistito/api/ http://127.0.0.1:8000/api/
	ProxyPass /anistito/ http://127.0.0.1:8000/
	ProxyPassReverse /anistito/ http://127.0.0.1:8000/

"""

CONFIGS = [
    Path("/etc/apache2/sites-available/000-default.conf"),
    Path("/etc/apache2/sites-available/default-ssl.conf"),
    Path("/etc/apache2/sites-available/pro.conf"),
]

def patch(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if "ProxyPass /anistito/" in text:
        return False
    backup = path.with_suffix(path.suffix + ".anistito.bak")
    shutil.copy(path, backup)
    print(f"Patched {path} (backup: {backup})")
    new_text = text.replace("</VirtualHost>", BLOCK + "</VirtualHost>", 1)
    path.write_text(new_text, encoding="utf-8")
    return True

def main():
    patched = 0
    for conf in CONFIGS:
        if patch(conf):
            patched += 1
    if patched:
        print("Run: systemctl reload apache2")
    else:
        print("No changes (ProxyPass already present or config not found)")
    return 0

if __name__ == "__main__":
    exit(main())
