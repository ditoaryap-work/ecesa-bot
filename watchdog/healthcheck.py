from __future__ import annotations
"""
Healthcheck — dijalankan via cron tiap 5 menit.
State-based: hanya kirim alert saat status BERUBAH (ok→fail atau fail→ok).
Reminder tiap REALERT_INTERVAL_HOURS selama masih fail.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil
from aiogram import Bot
from datetime import datetime, timedelta

from core.config import (
    BOT_TOKEN, CPU_THRESHOLD, RAM_THRESHOLD,
    DISK_THRESHOLD, DISK_DELTA_ALERT_GB,
    SYSTEMD_SERVICES, PM2_PROCESSES, REALERT_INTERVAL_HOURS
)
from core.db import init_db, get_alert_state, set_alert_state, is_muted, get_disk_snapshot, set_disk_snapshot
from core.messaging import alert
from modules.services import get_services


async def check_cpu(bot: Bot) -> None:
    cpu = psutil.cpu_percent(interval=2)
    key = "cpu"
    prev = await get_alert_state(key)

    if cpu >= CPU_THRESHOLD:
        if prev["status"] != "fail":
            await set_alert_state(key, "fail")
            # Top process
            procs = sorted(
                psutil.process_iter(["pid", "name", "cpu_percent"]),
                key=lambda p: p.info.get("cpu_percent") or 0, reverse=True
            )
            top = procs[0].info if procs else {}
            await alert(bot,
                f"🔴 <b>CPU SPIKE</b>\n"
                f"{'─'*33}\n"
                f"CPU    : <code>{cpu}%</code> (threshold: {CPU_THRESHOLD}%)\n"
                f"Proses : <code>{top.get('name','?')} (pid {top.get('pid','?')})</code> — {top.get('cpu_percent',0):.1f}%\n"
                f"Waktu  : <code>{datetime.now().strftime('%H:%M:%S WIB')}</code>"
            )
        else:
            # Reminder tiap N jam
            fired = datetime.fromisoformat(prev["fired_at"]) if prev.get("fired_at") else None
            if fired and datetime.now() - fired >= timedelta(hours=REALERT_INTERVAL_HOURS):
                await set_alert_state(key, "fail")
                await alert(bot,
                    f"⏰ <b>CPU masih tinggi</b> (reminder)\n"
                    f"CPU: <code>{cpu}%</code>"
                )
    elif prev["status"] == "fail":
        await set_alert_state(key, "ok")
        await alert(bot,
            f"✅ <b>CPU kembali normal</b>\n"
            f"CPU: <code>{cpu}%</code>"
        )


async def check_ram(bot: Bot) -> None:
    mem = psutil.virtual_memory()
    key = "ram"
    prev = await get_alert_state(key)

    if mem.percent >= RAM_THRESHOLD:
        if prev["status"] != "fail":
            await set_alert_state(key, "fail")
            await alert(bot,
                f"🔴 <b>RAM TINGGI</b>\n"
                f"{'─'*33}\n"
                f"RAM    : <code>{mem.percent}%</code> "
                f"({round(mem.used/1e9,1)}G / {round(mem.total/1e9,1)}G)\n"
                f"Waktu  : <code>{datetime.now().strftime('%H:%M:%S WIB')}</code>"
            )
    elif prev["status"] == "fail":
        await set_alert_state(key, "ok")
        await alert(bot, f"✅ <b>RAM kembali normal</b>\nRAM: <code>{mem.percent}%</code>")


async def check_disk(bot: Bot) -> None:
    disk = psutil.disk_usage("/")
    used_gb = round(disk.used / 1e9, 1)
    key = "disk"
    prev = await get_alert_state(key)

    # Alert threshold
    if disk.percent >= DISK_THRESHOLD:
        if prev["status"] != "fail":
            await set_alert_state(key, "fail")
            await alert(bot,
                f"💾 <b>DISK KRITIS</b>\n"
                f"{'─'*33}\n"
                f"Disk / : <code>{disk.percent}%</code> "
                f"({used_gb}G / {round(disk.total/1e9,1)}G)\n"
                f"Free   : <code>{round(disk.free/1e9,1)}G</code>\n"
                f"Waktu  : <code>{datetime.now().strftime('%H:%M:%S WIB')}</code>"
            )
    elif prev["status"] == "fail":
        await set_alert_state(key, "ok")
        await alert(bot, f"✅ <b>Disk kembali normal</b>\nDisk: <code>{disk.percent}%</code>")

    # Delta spike detection
    last_gb = await get_disk_snapshot()
    await set_disk_snapshot(used_gb)
    if last_gb is not None:
        delta = used_gb - last_gb
        if delta >= DISK_DELTA_ALERT_GB:
            await alert(bot,
                f"⚠️ <b>DISK SPIKE</b>\n"
                f"{'─'*33}\n"
                f"Disk naik <b>+{delta:.1f}G</b> dalam 5 menit\n"
                f"Sekarang: <code>{used_gb}G / {round(disk.total/1e9,1)}G</code>"
            )


async def check_services(bot: Bot) -> None:
    services = get_services()
    for svc in services:
        key = f"svc:{svc['name']}"
        prev = await get_alert_state(key)

        if not svc["ok"]:
            if prev["status"] != "fail":
                await set_alert_state(key, "fail")
                await alert(bot,
                    f"🚨 <b>SERVICE DOWN</b>\n"
                    f"{'─'*33}\n"
                    f"Service : <code>{svc['name']}</code>\n"
                    f"Status  : <code>{svc['status']}</code>\n"
                    f"Waktu   : <code>{datetime.now().strftime('%H:%M:%S WIB')}</code>"
                )
            else:
                fired = datetime.fromisoformat(prev["fired_at"]) if prev.get("fired_at") else None
                if fired and datetime.now() - fired >= timedelta(hours=REALERT_INTERVAL_HOURS):
                    await set_alert_state(key, "fail")
                    await alert(bot,
                        f"⏰ <b>{svc['name']} masih down</b> (reminder)\n"
                        f"Status: <code>{svc['status']}</code>"
                    )
        elif prev["status"] == "fail":
            await set_alert_state(key, "ok")
            await alert(bot,
                f"✅ <b>SERVICE RECOVERED</b>\n"
                f"{'─'*33}\n"
                f"Service : <code>{svc['name']}</code>\n"
                f"Status  : <code>active (running)</code>"
            )


async def check_ports(bot: Bot) -> None:
    """Deteksi port baru yang terbuka (dibanding snapshot sebelumnya)."""
    import subprocess, json
    key = "ports_snapshot"
    prev_state = await get_alert_state(key)

    try:
        r = subprocess.run(
            ["ss", "-tlnp"], capture_output=True, text=True, timeout=5
        )
        # Extract port numbers
        import re
        current_ports = set(re.findall(r":(\d{2,5})\s", r.stdout))

        prev_ports_str = prev_state.get("fired_at") or ""
        if prev_ports_str.startswith("ports:"):
            prev_ports = set(prev_ports_str[6:].split(","))
        else:
            prev_ports = current_ports

        new_ports = current_ports - prev_ports
        if new_ports:
            await alert(bot,
                f"🔍 <b>PORT BARU TERBUKA</b>\n"
                f"{'─'*33}\n"
                f"Port baru: <code>{', '.join(sorted(new_ports))}</code>\n"
                f"⚠️ Verifikasi apakah ini normal!"
            )

        # Simpan snapshot baru di fired_at field (hack ringan)
        async with __import__("aiosqlite").connect(__import__("core.config", fromlist=["DB_PATH"]).DB_PATH) as db:
            await db.execute("""
                INSERT INTO alert_state (key, status, fired_at, count)
                VALUES (?, 'ok', ?, 0)
                ON CONFLICT(key) DO UPDATE SET fired_at = ?
            """, (key, "ports:" + ",".join(sorted(current_ports)),
                       "ports:" + ",".join(sorted(current_ports))))
            await db.commit()
    except Exception as e:
        print(f"[check_ports] error: {e}")


async def main() -> None:
    await init_db()
    bot = Bot(token=BOT_TOKEN)

    muted, _ = await is_muted()

    try:
        await check_services(bot)
        await check_cpu(bot)
        await check_ram(bot)
        await check_disk(bot)
        await check_ports(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
