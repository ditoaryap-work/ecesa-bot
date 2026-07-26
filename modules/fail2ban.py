from __future__ import annotations
"""
Fail2ban integration — lihat banned IPs dan unban.
"""
import subprocess
import re


def _run(cmd: list[str], timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception as e:
        return str(e)


def is_fail2ban_available() -> bool:
    r = subprocess.run(["which", "fail2ban-client"], capture_output=True)
    return r.returncode == 0


def get_banned_ips(jail: str = "sshd") -> list[str]:
    out = _run(["fail2ban-client", "status", jail])
    match = re.search(r"Banned IP list:\s*(.*)", out)
    if match:
        ips = match.group(1).strip().split()
        return [ip for ip in ips if ip]
    return []


def get_fail2ban_status() -> dict:
    try:
        if not is_fail2ban_available():
            return {"available": False, "jails": [], "banned": {}}

        # list jails
        out = _run(["fail2ban-client", "status"])
        jails_match = re.search(r"Jail list:\s*(.*)", out)
        jails = []
        if jails_match:
            jails = [j.strip() for j in jails_match.group(1).split(",") if j.strip()]

        banned: dict[str, list[str]] = {}
        for jail in jails:
            banned[jail] = get_banned_ips(jail)

        return {"available": True, "jails": jails, "banned": banned}
    except Exception as e:
        return {"available": False, "jails": [], "banned": {}, "error": str(e)}


def unban_ip(ip: str, jail: str = "sshd") -> tuple[bool, str]:
    if not re.match(r"^[\d\.a-fA-F:]+$", ip):
        return False, "IP tidak valid"
    try:
        r = subprocess.run(
            ["fail2ban-client", "set", jail, "unbanip", ip],
            capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0, r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return False, str(e)


def format_fail2ban(data: dict) -> str:
    is_available = data.get("available", False)
    if not is_available:
        err = data.get("error", "")
        msg = f"\n<i>{err}</i>" if err else ""
        return f"🛡 <b>Fail2ban</b>\n\n❌ fail2ban tidak tersedia.{msg}"

    lines = ["🛡 <b>Fail2ban</b>", "─" * 33]
    total_banned = 0
    banned = data.get("banned", {})

    for jail, ips in banned.items():
        total_banned += len(ips)
        lines.append(f"<b>{jail}</b>: {len(ips)} IP banned")
        for ip in ips[:5]:
            lines.append(f"  • <code>{ip}</code>")
        if len(ips) > 5:
            lines.append(f"  ... +{len(ips) - 5} lagi")

    if total_banned == 0:
        lines.append("✅ Tidak ada IP yang di-ban saat ini.")

    return "\n".join(lines)
