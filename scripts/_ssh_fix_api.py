"""Remote: show requirements, rebuild api, verify port 3000."""
import os
import sys
import paramiko

pw = os.environ.get("REMOTESSH_PASSWORD")
if not pw:
    print("REMOTESSH_PASSWORD", file=sys.stderr)
    sys.exit(1)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("80.191.11.129", 9123, "root", password=pw, timeout=30, allow_agent=False, look_for_keys=False)


def run(cmd: str, timeout: int = 600) -> str:
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return o.read().decode() + e.read().decode()


print(run("grep -n jdatetime /opt/anistito/requirements.txt || echo MISSING_JDATETIME"))
print("--- build (may take several minutes) ---")
print(
    run(
        "cd /opt/anistito && docker compose -f docker-compose.prod.yml build --no-cache api "
        "&& docker compose -f docker-compose.prod.yml up -d api",
        timeout=900,
    )
)
print("--- status ---")
print(run("docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | head -6"))
print(run("ss -tlnp | grep 3000 || echo NO_3000"))
print(run("curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/health || echo CURL_FAIL"))

c.close()
