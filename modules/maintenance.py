from __future__ import annotations
"""
Maintenance mode — toggle nginx ke halaman maintenance + stop/start PM2.
"""
import subprocess
import os
from datetime import datetime

from core.config import NGINX_MAINTENANCE_CONF, NGINX_NORMAL_CONF, PM2_PROCESSES
from core.db import set_maintenance, get_maintenance


MAINTENANCE_HTML = """\
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Maintenance</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f172a; color: #e2e8f0;
            display: flex; align-items: center; justify-content: center;
            min-height: 100vh;
        }
        .card {
            text-align: center; padding: 3rem 4rem;
            background: #1e293b; border-radius: 1rem;
            border: 1px solid #334155;
        }
        h1 { font-size: 2rem; margin-bottom: 1rem; color: #f8fafc; }
        p  { color: #94a3b8; line-height: 1.6; }
        .icon { font-size: 4rem; margin-bottom: 1.5rem; }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">🚧</div>
        <h1>Sedang Maintenance</h1>
        <p>Sistem sedang dalam pemeliharaan.<br>Kami akan segera kembali.</p>
    </div>
</body>
</html>
"""


def _run(cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def _write_maintenance_page() -> None:
    """Tulis halaman maintenance HTML ke /var/www/html/maintenance.html."""
    path = "/var/www/html/maintenance.html"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(MAINTENANCE_HTML)
    except Exception as e:
        print(f"[maintenance] gagal tulis HTML: {e}")


def _nginx_reload() -> tuple[bool, str]:
    return _run(["sudo", "systemctl", "reload", "nginx"])


NGINX_MAINTENANCE_FLAG = "/etc/nginx/ecesa-maintenance.flag"


async def enable_maintenance() -> tuple[bool, str]:
    errors = []

    # 1. Set nginx flag → on
    try:
        flag_content = "set $maintenance_mode on;\n"
        r = subprocess.run(
            ["sudo", "tee", NGINX_MAINTENANCE_FLAG],
            input=flag_content, capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            errors.append(f"flag write: {r.stderr}")
    except Exception as e:
        errors.append(f"flag: {e}")

    # 2. Reload nginx
    ok, out = _nginx_reload()
    if not ok:
        errors.append(f"nginx reload: {out}")

    # 3. Stop PM2
    if PM2_PROCESSES:
        for name in PM2_PROCESSES:
            subprocess.run(["sudo", "-u", "ecesaweb", "pm2", "stop", name],
                         capture_output=True, timeout=30)
    else:
        subprocess.run(["sudo", "-u", "ecesaweb", "pm2", "stop", "all"],
                      capture_output=True, timeout=30)

    # 4. DB
    await set_maintenance(True)

    if errors:
        return False, "Partial error:\n" + "\n".join(errors)
    return True, "Maintenance diaktifkan. ecesa.id → halaman maintenance."


async def disable_maintenance() -> tuple[bool, str]:
    errors = []

    # 1. Set nginx flag → off
    try:
        flag_content = "set $maintenance_mode off;\n"
        r = subprocess.run(
            ["sudo", "tee", NGINX_MAINTENANCE_FLAG],
            input=flag_content, capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            errors.append(f"flag write: {r.stderr}")
    except Exception as e:
        errors.append(f"flag: {e}")

    # 2. Reload nginx
    ok, out = _nginx_reload()
    if not ok:
        errors.append(f"nginx reload: {out}")

    # 3. Start PM2
    if PM2_PROCESSES:
        for name in PM2_PROCESSES:
            subprocess.run(["sudo", "-u", "ecesaweb", "pm2", "start", name],
                         capture_output=True, timeout=30)
    else:
        subprocess.run(["sudo", "-u", "ecesaweb", "pm2", "resurrect"],
                      capture_output=True, timeout=30)

    await set_maintenance(False)

    if errors:
        return False, "Partial error:\n" + "\n".join(errors)
    return True, "Maintenance selesai. ecesa.id kembali normal."


def _write_nginx_503() -> None:
    """Fallback: buat nginx config yang return 503 ke semua request."""
    conf = """
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    return 503;
    error_page 503 /maintenance.html;
    root /var/www/html;
}
"""
    try:
        with open("/tmp/nginx_maintenance_fallback.conf", "w") as f:
            f.write(conf)
        _run(["sudo", "cp", "/tmp/nginx_maintenance_fallback.conf",
              "/etc/nginx/sites-available/maintenance"])
        _run(["sudo", "ln", "-sf",
              "/etc/nginx/sites-available/maintenance",
              "/etc/nginx/sites-enabled/maintenance"])
    except Exception as e:
        print(f"[maintenance] fallback nginx: {e}")


def format_maintenance(data: dict) -> str:
    sep = "─" * 33
    if data["active"]:
        started = data.get("started_at", "?")
        return (
            f"🚧 <b>Maintenance Mode</b>\n"
            f"{sep}\n"
            f"Status : 🔴 <b>MAINTENANCE AKTIF</b>\n"
            f"Sejak  : <code>{started}</code>\n\n"
            f"• Nginx → halaman maintenance\n"
            f"• PM2 apps → stopped\n"
            f"• Alert → dimatikan"
        )
    return (
        f"🚧 <b>Maintenance Mode</b>\n"
        f"{sep}\n"
        f"Status : 🟢 <b>NORMAL</b>\n\n"
        f"Aktifkan untuk:\n"
        f"• Redirect nginx ke halaman maintenance\n"
        f"• Stop semua PM2 apps\n"
        f"• Matikan semua alert"
    )
