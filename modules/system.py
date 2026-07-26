from __future__ import annotations
"""
System tools — top processes, reboot, apt update, optimize, speedtest, backup.
"""
import subprocess
import os
from datetime import datetime

import psutil

from core.config import BACKUP_DIR, BACKUP_DB_NAME


def _run(cmd: list[str], timeout: int = 60) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


# ─── Top Processes ────────────────────────────────────────────────────────────

def get_top(n: int = 10) -> list[dict]:
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
    return procs[:n]


def format_top(procs: list[dict]) -> str:
    lines = ["🔝 <b>Top Processes (CPU)</b>", "─" * 33]
    for p in procs:
        cpu = p.get("cpu_percent", 0) or 0
        mem = p.get("memory_percent", 0) or 0
        icon = "🔴" if cpu > 50 else "🟡" if cpu > 20 else "🟢"
        lines.append(
            f"{icon} <code>{str(p['pid']):<6} {p['name'][:20]:<20}</code> "
            f"CPU:{cpu:5.1f}% MEM:{mem:4.1f}%"
        )
    return "\n".join(lines)


# ─── Update ──────────────────────────────────────────────────────────────────

def apt_update() -> str:
    ok, out = _run(["sudo", "apt", "update", "-y"], timeout=120)
    if not ok:
        return f"❌ apt update gagal:\n<pre>{out[:1000]}</pre>"
    ok2, out2 = _run(["sudo", "apt", "upgrade", "-y", "--no-install-recommends"], timeout=300)
    if ok2:
        return f"✅ System updated.\n<pre>{out2[:1000]}</pre>"
    return f"⚠️ Partial:\n<pre>{out2[:1000]}</pre>"


def check_pending_updates() -> int:
    try:
        r = subprocess.run(
            ["apt", "list", "--upgradable", "--quiet", "2>/dev/null"],
            capture_output=True, text=True, shell=False, timeout=30
        )
        lines = [l for l in r.stdout.splitlines() if "/" in l]
        return len(lines)
    except Exception:
        return 0


# ─── Optimize ────────────────────────────────────────────────────────────────

def optimize() -> str:
    results = []

    # Drop caches via sudo tee
    try:
        r = subprocess.run(
            ["sudo", "tee", "/proc/sys/vm/drop_caches"],
            input="3", capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            results.append("✅ Page cache di-drop")
        else:
            results.append(f"❌ Drop cache: {r.stderr.strip()}")
    except Exception as e:
        results.append(f"❌ Drop cache: {e}")

    # Enable BBR via sudo sysctl
    ok, out = _run(["sysctl", "net.ipv4.tcp_congestion_control"])
    if "bbr" not in out.lower():
        ok2, out2 = _run(["sudo", "sysctl", "-w", "net.ipv4.tcp_congestion_control=bbr"])
        results.append("✅ BBR diaktifkan" if ok2 else f"❌ BBR: {out2}")
    else:
        results.append("ℹ️ BBR sudah aktif")

    # Check swap
    ok, out = _run(["swapon", "--show"])
    lines = [l for l in out.splitlines() if l.strip() and "NAME" not in l]
    if not lines:
        results.append("⚠️ Tidak ada swap aktif")
    else:
        for line in lines:
            results.append(f"ℹ️ Swap: {line.strip()}")

    sep = "─" * 33
    return f"⚡ <b>Optimize</b>\n{sep}\n" + "\n".join(results)


# ─── Speedtest ────────────────────────────────────────────────────────────────

def speedtest() -> str:
    # Coba speedtest-cli dulu, fallback ke curl
    ok, out = _run(["which", "speedtest-cli"])
    if ok:
        ok2, result = _run(["speedtest-cli", "--simple"], timeout=60)
        if ok2:
            return f"🚀 <b>Speedtest</b>\n{'─' * 33}\n<pre>{result}</pre>"

    # fallback: curl ke speedtest server
    ok3, result3 = _run([
        "curl", "-o", "/dev/null", "-w",
        "Speed: %{speed_download} bytes/s\nTime: %{time_total}s",
        "https://speed.cloudflare.com/__down?bytes=10000000",
        "-s", "--max-time", "30"
    ], timeout=35)

    if ok3:
        return f"🚀 <b>Speedtest (Cloudflare)</b>\n{'─' * 33}\n<pre>{result3}</pre>"

    return "❌ Speedtest gagal — install speedtest-cli: <code>pip install speedtest-cli</code>"


# ─── Reboot ──────────────────────────────────────────────────────────────────

def reboot_server() -> tuple[bool, str]:
    ok, out = _run(["sudo", "shutdown", "-r", "+1", "Reboot via Telegram bot"], timeout=10)
    return ok, out


# ─── Backup ──────────────────────────────────────────────────────────────────

def run_backup() -> tuple[bool, str, str | None]:
    """
    Jalankan pg_dump lalu gzip.
    Return: (success, message, file_path|None)
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dump_path = os.path.join(BACKUP_DIR, f"{BACKUP_DB_NAME}_{ts}.sql.gz")

    try:
        # pg_dump via sudo -u postgres | gzip langsung
        pg = subprocess.Popen(
            ["sudo", "-u", "postgres", "pg_dump", "-d", BACKUP_DB_NAME],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        gz = subprocess.Popen(
            ["gzip", "-c"],
            stdin=pg.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if pg.stdout:
            pg.stdout.close()
        gz_out, gz_err = gz.communicate(timeout=300)
        pg.wait(timeout=10)

        if pg.returncode != 0:
            err = pg.stderr.read().decode() if pg.stderr else ""
            return False, f"❌ pg_dump gagal:\n<code>{err[:300]}</code>", None

        with open(dump_path, "wb") as f:
            f.write(gz_out)

        size_mb = round(os.path.getsize(dump_path) / 1e6, 2)
        msg = (
            f"✅ <b>Backup selesai</b>\n"
            f"📁 <code>{dump_path}</code>\n"
            f"💾 Size: <b>{size_mb} MB</b>\n"
            f"🕐 {datetime.now().strftime('%d %b %Y %H:%M WIB')}"
        )
        return True, msg, dump_path

    except subprocess.TimeoutExpired:
        return False, "❌ Backup timeout (>5 menit)", None
    except Exception as e:
        return False, f"❌ Backup error: <code>{e}</code>", None
