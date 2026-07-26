"""
SSH login history dari database.
"""
from core.db import get_ssh_logs
from core.config import TRUSTED_IPS


def format_sshlog(logs: list[dict]) -> str:
    if not logs:
        return "👥 <b>SSH Logins</b>\n\n<i>Belum ada login tercatat.</i>"

    lines = ["👥 <b>SSH Login History</b>", "─" * 33]
    for log in logs:
        trusted = log.get("trusted", 0)
        icon = "✅" if trusted else "⚠️"
        ip = log.get("ip", "?")
        user = log.get("user", "?")
        ts = log.get("logged_at", "?")
        lines.append(f"{icon} <code>{user}@{ip}</code>\n   <i>{ts}</i>")

    return "\n".join(lines)
