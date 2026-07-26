from __future__ import annotations
"""
Daily summary — dijalankan via cron tiap hari jam 08:00 WIB.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil
from aiogram import Bot
from datetime import datetime

from core.config import BOT_TOKEN, TLS_DOMAINS, TLS_WARN_DAYS
from core.db import init_db, get_ssh_logs
from core.messaging import send
from modules.services import get_services
from modules.system import check_pending_updates
from modules.status import _tls_days
from modules.fail2ban import get_fail2ban_status


async def main() -> None:
    await init_db()
    bot = Bot(token=BOT_TOKEN)

    try:
        now = datetime.now()
        day_str = now.strftime("%A, %d %b %Y")

        # Metrics
        cpu = psutil.cpu_percent(interval=2)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        load = psutil.getloadavg()
        uptime_sec = int(__import__("time").time() - psutil.boot_time())
        d, r = divmod(uptime_sec, 86400)
        h = r // 3600

        # Services
        services = get_services()
        all_ok = all(s["ok"] for s in services)
        svc_down = [s["name"] for s in services if not s["ok"]]

        # SSH logs hari ini
        logs = await get_ssh_logs(50)
        today = now.strftime("%Y-%m-%d")
        logs_today = [l for l in logs if l.get("logged_at", "").startswith(today)]
        unknown_logins = [l for l in logs_today if not l.get("trusted")]

        # Fail2ban
        f2b = get_fail2ban_status()
        total_banned = sum(len(v) for v in f2b.get("banned", {}).values())

        # TLS
        tls_lines = []
        for domain in TLS_DOMAINS:
            days = _tls_days(domain)
            if days is None:
                tls_lines.append(f"❓ {domain}: tidak bisa cek")
            elif days <= TLS_WARN_DAYS:
                tls_lines.append(f"⚠️ {domain}: {days} hari lagi!")
            else:
                tls_lines.append(f"✅ {domain}: {days} hari lagi")

        # Pending updates
        pending = check_pending_updates()

        # Build message
        svc_status = "✅ Semua normal" if all_ok else f"⚠️ Down: {', '.join(svc_down)}"
        login_status = f"{len(logs_today)} login" + (f" ⚠️ {len(unknown_logins)} unknown" if unknown_logins else " (semua trusted)")

        tls_str = "\n".join(f"   {l}" for l in tls_lines) if tls_lines else "   (tidak dikonfigurasi)"

        msg = (
            f"📊 <b>Daily Report — {day_str}</b>\n"
            f"{'─' * 33}\n"
            f"⏱ Uptime    : <code>{d}h {h}j</code>\n"
            f"🧠 RAM       : <code>{round(mem.used/1e9,1)}G/{round(mem.total/1e9,1)}G ({mem.percent}%)</code>\n"
            f"💾 Disk /    : <code>{round(disk.used/1e9,1)}G/{round(disk.total/1e9,1)}G ({disk.percent}%)</code>\n"
            f"🌡 CPU       : <code>{cpu}%</code>\n"
            f"📈 Load      : <code>{load[0]:.2f} / {load[1]:.2f} / {load[2]:.2f}</code>\n"
            f"{'─' * 33}\n"
            f"⚙️ Services  : {svc_status}\n"
            f"🛡 Fail2ban  : <code>{total_banned} IP banned</code>\n"
            f"👥 SSH login : <code>{login_status}</code>\n"
            f"📦 Updates   : <code>{pending} paket pending</code>\n"
            f"{'─' * 33}\n"
            f"🔒 TLS:\n{tls_str}\n"
            f"{'─' * 33}\n"
        )

        # Summary footer
        issues = []
        if not all_ok:
            issues.append(f"service down: {', '.join(svc_down)}")
        if mem.percent >= 85:
            issues.append(f"RAM tinggi {mem.percent}%")
        if disk.percent >= 85:
            issues.append(f"Disk kritis {disk.percent}%")
        if unknown_logins:
            issues.append(f"{len(unknown_logins)} SSH login tidak dikenal")
        if pending > 10:
            issues.append(f"{pending} update pending")

        if issues:
            msg += f"⚠️ Perlu perhatian:\n" + "\n".join(f"• {i}" for i in issues)
        else:
            msg += "💡 Semua sistem normal ✅"

        await send(bot, msg)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
