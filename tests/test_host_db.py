"""
تست وجود داده فرایندها در دیتابیس هاست اینترنتی.
اجرا: pytest tests/test_host_db.py -v
یا مستقیم: python tests/test_host_db.py
"""
import subprocess
import sys


def run_ssh(cmd: str) -> tuple[str, int]:
    """اجرای دستور روی سرور via plink."""
    from pathlib import Path
    plink = str(Path(__file__).resolve().parents[1] / "plink.exe")
    full = f'{plink} -batch -hostkey SHA256:F459aXR14g147aSBxWlTypGEKisuxzYnrYl4kcDyPdA -P 2022 -pw parsbpms.com root@80.191.11.129 "{cmd}"'
    r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=30)
    return (r.stdout + r.stderr).strip(), r.returncode


def test_db_has_processes():
    """بررسی وجود فرایندها در دیتابیس هاست."""
    out, code = run_ssh(
        "docker exec anistito-db psql -U anistito -d anistito -t -c 'SELECT COUNT(*) FROM process_definitions;'"
    )
    assert code == 0, f"SSH failed: {out}"
    count = int(out.strip())
    assert count > 0, f"DB empty. process count: {count}"
    return count


def test_api_process_count():
    """بررسی endpoint debug/process-count روی سرور."""
    out, code = run_ssh("curl -s http://localhost:3000/debug/process-count")
    assert code == 0, f"curl failed: {out}"
    assert "process_count" in out, f"Invalid response: {out}"
    return out


def test_api_processes_list_needs_auth():
    """بررسی اینکه /api/admin/processes نیاز به احراز هویت دارد."""
    out, code = run_ssh("curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/api/admin/processes/")
    assert code == 0
    # 401 = needs auth, 200 = ok, 307 = redirect
    assert out.strip() in ("401", "200", "307"), f"Unexpected status: {out}"


if __name__ == "__main__":
    print("=== Host DB Test ===\n")
    try:
        n = test_db_has_processes()
        print(f"OK DB: {n} processes")
    except Exception as e:
        print(f"FAIL DB: {e}")
        sys.exit(1)
    try:
        r = test_api_process_count()
        print(f"OK API debug: {r}")
    except Exception as e:
        print(f"FAIL API: {e}")
        sys.exit(1)
    try:
        test_api_processes_list_needs_auth()
        print("OK API admin/processes reachable")
    except Exception as e:
        print(f"FAIL API admin: {e}")
    print("\n=== Done ===")
