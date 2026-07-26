from __future__ import annotations
"""
SSH login notifier — dipanggil via PAM hook saat ada SSH login.
Usage: python3 ssh_notify.py <username> <ip>

Setup di /etc/pam.d/sshd:
    session optional pam_exec.so /opt/ecesa-bot/watchdog/ssh_notify_pam.sh
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from datetime import datetime

from core.config import BOT_TOKEN, TRUSTED_IPS
from core.db import init_db, add_ssh_log
from core.keyboards import kb_ssh_alert
from core.messaging import send


async def main(user: str, ip: str) -> None:
    await init_db()
    bot = Bot(token=BOT_TOKEN)

    trusted = ip in TRUSTED_IPS
    await add_ssh_log(user, ip, trusted)

    ts = datetime.now().strftime("%H:%M:%S WIB")
    trust_icon = "✅" if trusted else "⚠️"
    trust_label = "TRUSTED" if trusted else "UNKNOWN ⚠️"

    msg = (
        f"🔐 <b>SSH LOGIN</b>\n"
        f"{'─' * 33}\n"
        f"User   : <code>{user}</code>\n"
        f"IP     : <code>{ip}</code> — {trust_label}\n"
        f"Waktu  : <code>{ts}</code>"
    )

    keyboard = None if trusted else kb_ssh_alert(ip)
    await send(bot, msg, keyboard)
    await bot.session.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: ssh_notify.py <user> <ip>")
        sys.exit(1)
    user = sys.argv[1]
    ip = sys.argv[2]
    asyncio.run(main(user, ip))
