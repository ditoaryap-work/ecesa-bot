from __future__ import annotations
"""
Main bot — entry point, handler semua command & callback.
"""
import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from core.config import BOT_TOKEN, CHAT_ID
from core.db import init_db
from core.middlewares import AuthMiddleware, ThrottleMiddleware, AutoDeleteMiddleware
from core.messaging import send, edit, delete
from core.keyboards import (
    kb_menu, kb_status, kb_services, kb_service_confirm,
    kb_logs, kb_log_view, kb_disk, kb_fail2ban, kb_sshlog,
    kb_maintenance_off, kb_maintenance_on, kb_maintenance_confirm,
    kb_system, kb_reboot_confirm, kb_back_system, kb_mute, kb_ssh_alert,
)
from core.state import state

from modules.status import get_status, format_status
from modules.services import get_services, format_services, get_all_service_names, restart_service
from modules.logs import get_log, format_log
from modules.disk import get_disk, format_disk
from modules.fail2ban import get_fail2ban_status, format_fail2ban, unban_ip
from modules.sshlog import format_sshlog
from modules.maintenance import enable_maintenance, disable_maintenance, format_maintenance
from modules.mute import mute_for, format_mute
from modules.system import get_top, format_top, apt_update, optimize, speedtest, run_backup, reboot_server

from core.db import get_ssh_logs, get_maintenance, is_muted, set_mute

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ─── Register middlewares ─────────────────────────────────────────────────────

dp.message.middleware(AuthMiddleware())
dp.callback_query.middleware(AuthMiddleware())
dp.callback_query.middleware(ThrottleMiddleware())
dp.message.middleware(AutoDeleteMiddleware())


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _header() -> str:
    now = datetime.now().strftime("%d %b %Y • %H:%M WIB")
    return f"🖥 <b>Ecesa VPS Monitor</b>\n<i>{now}</i>\n{'─' * 33}\n"


async def show_menu(chat_id: int, message_id: int | None = None) -> None:
    muted, _ = await is_muted()
    maint = await get_maintenance()

    status_line = ""
    if maint["active"]:
        status_line = "\n🔴 <b>MAINTENANCE MODE AKTIF</b>"
    elif muted:
        status_line = "\n🔇 Alert sedang dimute"

    text = _header() + "Pilih menu:" + status_line

    if message_id:
        await edit(bot, message_id, text, kb_menu())
    else:
        await send(bot, text, kb_menu())


# ─── Commands ─────────────────────────────────────────────────────────────────

@dp.message(Command("start"))
@dp.message(Command("menu"))
async def cmd_start(msg: Message) -> None:
    await show_menu(msg.chat.id)


@dp.message(Command("status"))
async def cmd_status(msg: Message) -> None:
    s = await asyncio.get_event_loop().run_in_executor(None, get_status)
    await send(bot, format_status(s), kb_status())


@dp.message(Command("help"))
async def cmd_help(msg: Message) -> None:
    text = (
        "🤖 <b>Ecesa Bot — Commands</b>\n"
        "─" * 33 + "\n"
        "/start atau /menu — buka menu utama\n"
        "/status — live status server\n"
        "/help — tampilkan ini\n\n"
        "Semua fitur tersedia via menu interaktif."
    )
    await send(bot, text)


# ─── Callback handler utama ──────────────────────────────────────────────────

@dp.callback_query()
async def handle_callback(cb: CallbackQuery) -> None:
    data = cb.data or ""
    msg_id = cb.message.message_id if cb.message else None

    await cb.answer()  # hilangkan loading spinner

    # ── Navigation ────────────────────────────────────────────────────────────
    if data == "nav:menu":
        await show_menu(CHAT_ID, msg_id)

    elif data == "close":
        if msg_id:
            await delete(bot, msg_id)

    elif data == "nav:status":
        s = await asyncio.get_event_loop().run_in_executor(None, get_status)
        await edit(bot, msg_id, format_status(s), kb_status())

    elif data == "nav:services":
        services = await asyncio.get_event_loop().run_in_executor(None, get_services)
        names = await asyncio.get_event_loop().run_in_executor(None, get_all_service_names)
        await edit(bot, msg_id, format_services(services), kb_services(names))

    elif data == "nav:logs":
        await edit(bot, msg_id,
            "📋 <b>Logs</b>\n─" * 1 + "─" * 32 + "\nPilih sumber log:",
            kb_logs())

    elif data == "nav:disk":
        partitions = await asyncio.get_event_loop().run_in_executor(None, get_disk)
        await edit(bot, msg_id, format_disk(partitions), kb_disk())

    elif data == "nav:fail2ban":
        f2b = await asyncio.get_event_loop().run_in_executor(None, get_fail2ban_status)
        all_banned = []
        for ips in f2b.get("banned", {}).values():
            all_banned.extend(ips)
        await edit(bot, msg_id, format_fail2ban(f2b), kb_fail2ban(all_banned))

    elif data == "nav:sshlog":
        logs = await get_ssh_logs(20)
        await edit(bot, msg_id, format_sshlog(logs), kb_sshlog())

    elif data == "nav:maintenance":
        maint = await get_maintenance()
        kb = kb_maintenance_on() if maint["active"] else kb_maintenance_off()
        await edit(bot, msg_id, format_maintenance(maint), kb)

    elif data == "nav:system":
        await edit(bot, msg_id,
            "🔧 <b>System Tools</b>\n─" * 1 + "─" * 32 + "\nPilih tool:",
            kb_system())

    elif data == "nav:mute":
        muted, _ = await is_muted()
        text = await format_mute()
        await edit(bot, msg_id, text, kb_mute(muted))

    # ── Services restart ─────────────────────────────────────────────────────
    elif data.startswith("svc_ask:"):
        svc = data[8:]
        await edit(bot, msg_id,
            f"⚠️ <b>Konfirmasi Restart</b>\n─" * 1 + "─" * 32 + "\n"
            f"Restart <code>{svc}</code> sekarang?\n"
            f"Service akan down beberapa detik.",
            kb_service_confirm(svc))

    elif data.startswith("svc_do:"):
        svc = data[7:]
        await edit(bot, msg_id, f"⏳ Merestart <code>{svc}</code>...", None)
        ok, out = await asyncio.get_event_loop().run_in_executor(None, restart_service, svc)
        icon = "✅" if ok else "❌"
        result = f"{icon} <b>Restart {svc}</b>\n<pre>{out[:500] or 'selesai'}</pre>"
        await edit(bot, msg_id, result, kb_back_system())

    # ── Logs ─────────────────────────────────────────────────────────────────
    elif data.startswith("log:"):
        key = data[4:]
        await edit(bot, msg_id, "⏳ Mengambil log...", None)
        content = await asyncio.get_event_loop().run_in_executor(None, get_log, key)
        await edit(bot, msg_id, format_log(key, content), kb_log_view(key))

    # ── Fail2ban unban ────────────────────────────────────────────────────────
    elif data.startswith("f2b_unban:"):
        ip = data[10:]
        ok, out = await asyncio.get_event_loop().run_in_executor(None, unban_ip, ip)
        await cb.answer(f"{'✅' if ok else '❌'} {out}", show_alert=True)
        # Refresh fail2ban screen
        f2b = await asyncio.get_event_loop().run_in_executor(None, get_fail2ban_status)
        all_banned = []
        for ips in f2b.get("banned", {}).values():
            all_banned.extend(ips)
        await edit(bot, msg_id, format_fail2ban(f2b), kb_fail2ban(all_banned))

    # ── SSH alert actions ─────────────────────────────────────────────────────
    elif data.startswith("ssh_ban:"):
        ip = data[8:]
        import subprocess
        r = subprocess.run(["sudo", "ufw", "deny", "from", ip, "to", "any"],
                          capture_output=True, text=True)
        ok = r.returncode == 0
        await cb.answer(f"{'✅ Banned' if ok else '❌ Gagal'}: {ip}", show_alert=True)
        if msg_id and ok:
            await edit(bot, msg_id,
                f"🚫 <b>IP Di-ban</b>\n<code>{ip}</code> diblokir via UFW.", None)

    elif data.startswith("ssh_trust:"):
        ip = data[10:]
        from core.config import TRUSTED_IPS
        if ip not in TRUSTED_IPS:
            TRUSTED_IPS.append(ip)
        await cb.answer(f"✅ {ip} ditambah ke whitelist (session ini)", show_alert=True)

    # ── Maintenance ──────────────────────────────────────────────────────────
    elif data == "maint_on":
        await edit(bot, msg_id,
            "🚧 <b>Aktifkan Maintenance?</b>\n─" * 1 + "─" * 32 + "\n"
            "• Nginx → halaman maintenance\n"
            "• PM2 apps → stopped\n"
            "• Semua alert → dimatikan",
            kb_maintenance_confirm("on"))

    elif data == "maint_off":
        await edit(bot, msg_id,
            "✅ <b>Selesaikan Maintenance?</b>\n─" * 1 + "─" * 32 + "\n"
            "• Nginx → kembali normal\n"
            "• PM2 apps → distart ulang\n"
            "• Alert → diaktifkan kembali",
            kb_maintenance_confirm("off"))

    elif data == "maint_confirm:on":
        await edit(bot, msg_id, "⏳ Mengaktifkan maintenance...", None)
        # Auto-mute alerts saat maintenance
        await set_mute(None)  # clear dulu
        from datetime import timedelta
        await set_mute((datetime.now() + timedelta(hours=24)).isoformat())
        ok, msg_text = await enable_maintenance()
        icon = "✅" if ok else "⚠️"
        maint = await get_maintenance()
        result = f"{icon} {msg_text}\n\n" + format_maintenance(maint)
        await edit(bot, msg_id, result, kb_maintenance_on())

    elif data == "maint_confirm:off":
        await edit(bot, msg_id, "⏳ Menyelesaikan maintenance...", None)
        ok, msg_text = await disable_maintenance()
        await set_mute(None)  # unmute
        icon = "✅" if ok else "⚠️"
        maint = await get_maintenance()
        result = f"{icon} {msg_text}\n\n" + format_maintenance(maint)
        await edit(bot, msg_id, result, kb_maintenance_off())

    # ── Mute ─────────────────────────────────────────────────────────────────
    elif data.startswith("mute:"):
        seconds = int(data[5:])
        result = await mute_for(seconds)
        await cb.answer(result[:190])
        muted, _ = await is_muted()
        text = await format_mute()
        await edit(bot, msg_id, text, kb_mute(muted))

    # ── System tools ─────────────────────────────────────────────────────────
    elif data == "sys:top":
        procs = await asyncio.get_event_loop().run_in_executor(None, get_top)
        await edit(bot, msg_id, format_top(procs), kb_back_system())

    elif data == "sys:optimize":
        await edit(bot, msg_id, "⏳ Menjalankan optimasi...", None)
        result = await asyncio.get_event_loop().run_in_executor(None, optimize)
        await edit(bot, msg_id, result, kb_back_system())

    elif data == "sys:speedtest":
        await edit(bot, msg_id, "⏳ Menjalankan speedtest...", None)
        result = await asyncio.get_event_loop().run_in_executor(None, speedtest)
        await edit(bot, msg_id, result, kb_back_system())

    elif data == "sys:update":
        await edit(bot, msg_id, "⏳ Menjalankan apt update...", None)
        result = await asyncio.get_event_loop().run_in_executor(None, apt_update)
        await edit(bot, msg_id, result, kb_back_system())

    elif data == "sys:backup":
        await edit(bot, msg_id, "⏳ Menjalankan backup...", None)
        result = await asyncio.get_event_loop().run_in_executor(None, run_backup)
        await edit(bot, msg_id, result, kb_back_system())

    elif data == "sys:reboot_ask":
        await edit(bot, msg_id,
            "⚠️ <b>REBOOT SERVER?</b>\n─" * 1 + "─" * 32 + "\n"
            "Server akan restart.\n"
            "Estimasi downtime: ~30-60 detik.",
            kb_reboot_confirm())

    elif data == "sys:reboot_do":
        await edit(bot, msg_id,
            "🔁 <b>Reboot dijadwalkan dalam 1 menit</b>\n"
            "Bot akan offline sejenak, lalu kembali otomatis.", None)
        await asyncio.get_event_loop().run_in_executor(None, reboot_server)


# ─── Startup ──────────────────────────────────────────────────────────────────

async def on_startup() -> None:
    await init_db()
    log.info("DB initialized")
    await send(bot,
        f"🟢 <b>Ecesa Bot Online</b>\n"
        f"<i>{datetime.now().strftime('%d %b %Y %H:%M WIB')}</i>\n\n"
        f"Ketik /menu untuk membuka panel."
    )
    log.info("Bot started, notification sent")


async def on_shutdown() -> None:
    await send(bot, "🔴 <b>Ecesa Bot Offline</b>")
    log.info("Bot shutting down")


async def main() -> None:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
