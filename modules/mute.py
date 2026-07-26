"""
Mute alerts — timed suppression.
"""
from datetime import datetime, timedelta
from core.db import set_mute, is_muted


DURATIONS = {
    3600:  "1 Jam",
    21600: "6 Jam",
    86400: "24 Jam",
}


async def mute_for(seconds: int) -> str:
    if seconds == 0:
        await set_mute(None)
        return "🔔 Alert dinyalakan kembali."

    until = datetime.now() + timedelta(seconds=seconds)
    await set_mute(until.isoformat())
    label = DURATIONS.get(seconds, f"{seconds}s")
    return f"🔇 Alert dimute selama <b>{label}</b>.\nAktif kembali: <code>{until.strftime('%H:%M WIB')}</code>"


async def format_mute() -> str:
    muted, until_str = await is_muted()
    lines = ["🔇 <b>Mute Alerts</b>", "─" * 33]
    if muted and until_str:
        until = datetime.fromisoformat(until_str)
        lines.append(f"Status : 🔇 <b>MUTED</b>")
        lines.append(f"Sampai : <code>{until.strftime('%d %b %Y %H:%M WIB')}</code>")
        lines.append("\nTekan <b>Unmute</b> untuk mengaktifkan alert lebih awal.")
    else:
        lines.append("Status : 🔔 <b>AKTIF</b>")
        lines.append("\nPilih durasi untuk mematikan alert sementara:")
    return "\n".join(lines)
