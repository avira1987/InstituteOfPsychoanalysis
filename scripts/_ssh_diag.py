import os
import sys
import paramiko

pw = os.environ.get("REMOTESSH_PASSWORD")
if not pw:
    print("REMOTESSH_PASSWORD", file=sys.stderr)
    sys.exit(1)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("80.191.11.129", 9123, "root", password=pw, timeout=25, allow_agent=False, look_for_keys=False)


def run(cmd: str) -> str:
    _, o, e = c.exec_command(cmd)
    return o.read().decode() + e.read().decode()


cmds = [
    'docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"',
    "docker logs anistito-api --tail 150 2>&1",
    "ss -tlnp | grep 3000 || echo NO_3000",
    "test -f /opt/anistito/docker-compose.prod.yml && echo OPT || true",
    "test -f /root/anistito/docker-compose.prod.yml && echo ROOT || true",
    "find /root /opt /srv -maxdepth 4 -name docker-compose.prod.yml 2>/dev/null",
]
for cmd in cmds:
    print("=" * 70)
    print(cmd)
    print("-" * 70)
    print(run(cmd))

c.close()
