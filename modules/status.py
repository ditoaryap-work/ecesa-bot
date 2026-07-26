"""
Status screen — CPU, RAM, disk, network, uptime, TLS.
"""
import asyncio
import subprocess
import time
from datetime import datetime, timezone

import psutil

from core.config import TLS_DOMAINS, TLS_WARN_DAYS


def _uptime() -> str:
    boot = psutil.boot_time()
    delta = int(time.time() - boot)
    d, r = divmod(delta, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    parts = []
    if d: parts.append(f"{d}h")
    if h: parts.append(f"{h}j")
    parts.append(f"{m}m")
    return " ".join(parts)


def _tls_days(domain: str) -> int | None:
    try:
        result = subprocess.run(
            ["openssl", "s_client", "-connect", f"{domain}:443",
             "-servername", domain, "-handshake_timeout", "5"],
            input=b"", capture_output=True, timeout=8
        )
        # parse dari certbot path kalau ada
        cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
        r2 = subprocess.run(
            ["openssl", "x509", "-in", cert_path, "-noout", "-enddate"],
            capture_output=True, text=True, timeout=5
        )
        if r2.returncode == 0:
            date_str = r2.stdout.strip().replace("notAfter=", "")
            exp = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (exp - now).days
    except Exception:
        pass
    return None


def get_status() -> dict:
    cpu = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    load = psutil.getloadavg()
    net = psutil.net_io_counters()
    conns = len(psutil.net_connections())

    tls = {}
    for domain in TLS_DOMAINS:
        days = _tls_days(domain)
        tls[domain] = days

    return {
        "cpu_pct": cpu,
        "cpu_count": cpu_count,
        "ram_used_gb": round(mem.used / 1e9, 1),
        "ram_total_gb": round(mem.total / 1e9, 1),
        "ram_pct": mem.percent,
        "disk_used_gb": round(disk.used / 1e9, 1),
        "disk_total_gb": round(disk.total / 1e9, 1),
        "disk_pct": disk.percent,
        "load": load,
        "net_sent_mb": round(net.bytes_sent / 1e6, 1),
        "net_recv_mb": round(net.bytes_recv / 1e6, 1),
        "connections": conns,
        "uptime": _uptime(),
        "tls": tls,
    }


def format_status(s: dict) -> str:
    now = datetime.now().strftime("%A, %d %b %Y • %H:%M WIB")

    tls_lines = ""
    for domain, days in s["tls"].items():
        if days is None:
            tls_lines += f"\n🔒 TLS <code>{domain}</code>: ❓ tidak bisa cek"
        elif days <= TLS_WARN_DAYS:
            tls_lines += f"\n⚠️ TLS <code>{domain}</code>: {days} hari lagi!"
        else:
            tls_lines += f"\n🔒 TLS <code>{domain}</code>: {days} hari lagi"

    cpu_icon = "🔴" if s["cpu_pct"] > 80 else "🟡" if s["cpu_pct"] > 60 else "🟢"
    ram_icon = "🔴" if s["ram_pct"] > 85 else "🟡" if s["ram_pct"] > 70 else "🟢"
    disk_icon = "🔴" if s["disk_pct"] > 85 else "🟡" if s["disk_pct"] > 70 else "🟢"

    return (
        f"📊 <b>Live Status</b>\n"
        f"<i>{now}</i>\n"
        f"{'─' * 33}\n"
        f"⏱ Uptime   : <code>{s['uptime']}</code>\n"
        f"{cpu_icon} CPU       : <code>{s['cpu_pct']}%</code> ({s['cpu_count']} core)\n"
        f"{ram_icon} RAM       : <code>{s['ram_used_gb']}G/{s['ram_total_gb']}G ({s['ram_pct']}%)</code>\n"
        f"{disk_icon} Disk /    : <code>{s['disk_used_gb']}G/{s['disk_total_gb']}G ({s['disk_pct']}%)</code>\n"
        f"📈 Load     : <code>{s['load'][0]:.2f}, {s['load'][1]:.2f}, {s['load'][2]:.2f}</code>\n"
        f"🌐 Network  : <code>↑{s['net_sent_mb']}MB ↓{s['net_recv_mb']}MB</code>\n"
        f"🔗 Koneksi  : <code>{s['connections']} aktif</code>"
        f"{tls_lines}"
    )
