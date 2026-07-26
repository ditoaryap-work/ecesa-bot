from __future__ import annotations
"""
Services monitor — systemd + PM2.
"""
import subprocess
import json

from core.config import SYSTEMD_SERVICES, PM2_PROCESSES


def _systemd_status(svc: str) -> str:
    r = subprocess.run(
        ["systemctl", "is-active", svc],
        capture_output=True, text=True
    )
    return r.stdout.strip()


def _pm2_list() -> list[dict]:
    try:
        r = subprocess.run(
            ["pm2", "jlist"], capture_output=True, text=True, timeout=10
        )
        return json.loads(r.stdout or "[]")
    except Exception:
        return []


def get_services() -> list[dict]:
    results = []

    for svc in SYSTEMD_SERVICES:
        status = _systemd_status(svc)
        results.append({
            "name": svc,
            "type": "systemd",
            "status": status,
            "ok": status == "active",
        })

    pm2_procs = _pm2_list()
    if PM2_PROCESSES:
        for name in PM2_PROCESSES:
            proc = next((p for p in pm2_procs if p.get("name") == name), None)
            if proc:
                pm2_status = proc.get("pm2_env", {}).get("status", "unknown")
                results.append({
                    "name": f"pm2/{name}",
                    "type": "pm2",
                    "status": pm2_status,
                    "ok": pm2_status == "online",
                })
            else:
                results.append({
                    "name": f"pm2/{name}",
                    "type": "pm2",
                    "status": "not found",
                    "ok": False,
                })
    elif pm2_procs:
        # Kalau PM2_PROCESSES kosong, tampilkan semua yang ada
        for proc in pm2_procs:
            name = proc.get("name", "?")
            pm2_status = proc.get("pm2_env", {}).get("status", "unknown")
            results.append({
                "name": f"pm2/{name}",
                "type": "pm2",
                "status": pm2_status,
                "ok": pm2_status == "online",
            })

    return results


def format_services(services: list[dict]) -> str:
    lines = []
    for svc in services:
        icon = "✅" if svc["ok"] else "🔴"
        lines.append(f"{icon} <code>{svc['name']:<20}</code> {svc['status']}")

    all_ok = all(s["ok"] for s in services)
    header = "⚙️ <b>Services</b> — " + ("✅ Semua normal" if all_ok else "⚠️ Ada masalah!")
    return header + "\n" + "─" * 33 + "\n" + "\n".join(lines)


def get_all_service_names() -> list[str]:
    """Return daftar nama service untuk keyboard restart buttons."""
    names = list(SYSTEMD_SERVICES)
    pm2_procs = _pm2_list()
    if PM2_PROCESSES:
        names += [f"pm2/{n}" for n in PM2_PROCESSES]
    elif pm2_procs:
        names += [f"pm2/{p.get('name','?')}" for p in pm2_procs]
    return names


def restart_service(name: str) -> tuple[bool, str]:
    """Restart service. Return (success, output)."""
    try:
        if name.startswith("pm2/"):
            pm2_name = name[4:]
            r = subprocess.run(
                ["pm2", "restart", pm2_name],
                capture_output=True, text=True, timeout=30
            )
            return r.returncode == 0, r.stdout + r.stderr
        else:
            r = subprocess.run(
                ["sudo", "systemctl", "restart", name],
                capture_output=True, text=True, timeout=30
            )
            return r.returncode == 0, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout — restart mungkin masih berjalan"
    except Exception as e:
        return False, str(e)
