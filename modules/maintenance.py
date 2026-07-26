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


async def enable_maintenance() -> tuple[bool, str]:
    """
    1. Tulis halaman maintenance HTML
    2. Enable nginx maintenance config
    3. Stop PM2 apps
    4. Catat ke DB
    """
    errors = []

    # 1. Tulis HTML
    _write_maintenance_page()

    # 2. Nginx — symlink maintenance config ke sites-enabled
    maint_enabled = "/etc/nginx/sites-enabled/maintenance"
    normal_enabled = "/etc/nginx/sites-enabled/default"

    # disable normal site
    if os.path.islink(normal_enabled):
        ok, out = _run(["sudo", "rm", normal_enabled])
        if not ok:
            errors.append(f"rm default site: {out}")

    # enable maintenance site kalau ada
    if os.path.isfile(NGINX_MAINTENANCE_CONF):
        if not os.path.islink(maint_enabled):
            ok, out = _run(["sudo", "ln", "-s", NGINX_MAINTENANCE_CONF, maint_enabled])
            if not ok:
                errors.append(f"ln maintenance: {out}")
    else:
        # fallback — return 503 via nginx inline config
        _write_nginx_503()

    ok, out = _nginx_reload()
    if not ok:
        errors.append(f"nginx reload: {out}")

    # 3. Stop PM2
    if PM2_PROCESSES:
        for name in PM2_PROCESSES:
            _run(["pm2", "stop", name])
    else:
        _run(["pm2", "stop", "all"])

    # 4. DB
    await set_maintenance(True)

    if errors:
        return False, "Partial error:\n" + "\n".join(errors)
    return True, "Maintenance diaktifkan."


async def disable_maintenance() -> tuple[bool, str]:
    """
    1. Disable nginx maintenance config
    2. Re-enable normal config
    3. Start PM2 apps
    4. Catat ke DB
    """
    errors = []

    maint_enabled = "/etc/nginx/sites-enabled/maintenance"
    normal_enabled = "/etc/nginx/sites-enabled/default"

    # remove maintenance symlink
    if os.path.islink(maint_enabled):
        ok, out = _run(["sudo", "rm", maint_enabled])
        if not ok:
            errors.append(f"rm maintenance: {out}")

    # re-enable normal site
    if not os.path.islink(normal_enabled) and os.path.isfile(NGINX_NORMAL_CONF):
        ok, out = _run(["sudo", "ln", "-s", NGINX_NORMAL_CONF, normal_enabled])
        if not ok:
            errors.append(f"ln normal site: {out}")

    ok, out = _nginx_reload()
    if not ok:
        errors.append(f"nginx reload: {out}")

    # start PM2
    if PM2_PROCESSES:
        for name in PM2_PROCESSES:
            _run(["pm2", "start", name])
    else:
        _run(["pm2", "resurrect"])

    await set_maintenance(False)

    if errors:
        return False, "Partial error:\n" + "\n".join(errors)
    return True, "Maintenance selesai. Sistem kembali normal."


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
    if data["active"]:
        started = data.get("started_at", "?")
        return (
            "🚧 <b>Maintenance Mode</b>\n"
            "─" * 33 + "\n"
            "Status : 🔴 <b>MAINTENANCE AKTIF</b>\n"
            f"Sejak  : <code>{started}</code>\n\n"
            "• Nginx → halaman maintenance\n"
            "• PM2 apps → stopped\n"
            "• Alert → dimatikan"
        )
    return (
        "🚧 <b>Maintenance Mode</b>\n"
        "─" * 33 + "\n"
        "Status : 🟢 <b>NORMAL</b>\n\n"
        "Aktifkan untuk:\n"
        "• Redirect nginx ke halaman maintenance\n"
        "• Stop semua PM2 apps\n"
        "• Matikan semua alert"
    )
