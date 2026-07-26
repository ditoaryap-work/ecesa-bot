"""
Semua inline keyboard builder ada di sini.
Konsisten: tiap screen punya keyboard-nya sendiri.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """Builder helper — rows berisi list of (text, callback_data)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=c) for t, c in row]
            for row in rows
        ]
    )


def nav_row(current: str) -> list[tuple[str, str]]:
    """Baris navigasi bawah — selalu ada di tiap screen."""
    row = [("🏠 Menu", "nav:menu")]
    if current != "menu":
        row.append(("🔄 Refresh", f"nav:{current}"))
    return row


# ─── Main Menu ────────────────────────────────────────────────────────────────

def kb_menu() -> InlineKeyboardMarkup:
    return _kb([
        [("📊 Status", "nav:status"), ("⚙️ Services", "nav:services")],
        [("📋 Logs", "nav:logs"), ("💾 Disk", "nav:disk")],
        [("🛡 Fail2ban", "nav:fail2ban"), ("👥 SSH Logins", "nav:sshlog")],
        [("🚧 Maintenance", "nav:maintenance"), ("🔧 System", "nav:system")],
        [("🔇 Mute Alerts", "nav:mute"), ("❌ Tutup", "close")],
    ])


# ─── Status ──────────────────────────────────────────────────────────────────

def kb_status() -> InlineKeyboardMarkup:
    return _kb([nav_row("status")])


# ─── Services ────────────────────────────────────────────────────────────────

def kb_services(services: list[str]) -> InlineKeyboardMarkup:
    restart_rows = []
    row = []
    for i, svc in enumerate(services):
        row.append((f"🔄 {svc}", f"svc_ask:{svc}"))
        if len(row) == 2:
            restart_rows.append(row)
            row = []
    if row:
        restart_rows.append(row)
    return _kb(restart_rows + [nav_row("services")])


def kb_service_confirm(svc: str) -> InlineKeyboardMarkup:
    return _kb([
        [("✅ Ya, restart", f"svc_do:{svc}"), ("❌ Batal", "nav:services")],
    ])


# ─── Logs ─────────────────────────────────────────────────────────────────────

def kb_logs() -> InlineKeyboardMarkup:
    return _kb([
        [("🌐 Nginx Error", "log:nginx_error"), ("🌐 Nginx Access", "log:nginx_access")],
        [("🐘 PostgreSQL", "log:postgresql"), ("📦 PM2", "log:pm2")],
        [("🔴 Redis", "log:redis"), ("🔄 pgBouncer", "log:pgbouncer")],
        [("🖥 Syslog", "log:syslog")],
        nav_row("logs"),
    ])


def kb_log_view(log_key: str) -> InlineKeyboardMarkup:
    return _kb([
        [("🔄 Refresh", f"log:{log_key}"), ("⬅️ Back", "nav:logs"), ("🏠 Menu", "nav:menu")],
    ])


# ─── Disk ─────────────────────────────────────────────────────────────────────

def kb_disk() -> InlineKeyboardMarkup:
    return _kb([nav_row("disk")])


# ─── Fail2ban ─────────────────────────────────────────────────────────────────

def kb_fail2ban(banned_ips: list[str]) -> InlineKeyboardMarkup:
    unban_rows = [[("🔓 Unban " + ip, f"f2b_unban:{ip}")] for ip in banned_ips[:10]]
    return _kb(unban_rows + [nav_row("fail2ban")])


# ─── SSH Log ─────────────────────────────────────────────────────────────────

def kb_sshlog() -> InlineKeyboardMarkup:
    return _kb([nav_row("sshlog")])


# ─── Maintenance ─────────────────────────────────────────────────────────────

def kb_maintenance_off() -> InlineKeyboardMarkup:
    return _kb([
        [("🚧 Aktifkan Maintenance", "maint_on")],
        [("🏠 Menu", "nav:menu")],
    ])


def kb_maintenance_on() -> InlineKeyboardMarkup:
    return _kb([
        [("✅ Selesai Maintenance", "maint_off")],
        [("🏠 Menu", "nav:menu")],
    ])


def kb_maintenance_confirm(action: str) -> InlineKeyboardMarkup:
    label = "✅ Ya, aktifkan" if action == "on" else "✅ Ya, selesaikan"
    return _kb([
        [(label, f"maint_confirm:{action}"), ("❌ Batal", "nav:maintenance")],
    ])


# ─── System ──────────────────────────────────────────────────────────────────

def kb_system() -> InlineKeyboardMarkup:
    return _kb([
        [("📦 Update Packages", "sys:update")],
        [("⚡ Optimize (BBR/Swap/Cache)", "sys:optimize")],
        [("🚀 Speedtest", "sys:speedtest")],
        [("🔝 Top Processes", "sys:top")],
        [("💾 Backup Sekarang", "sys:backup")],
        [("🔁 Reboot Server", "sys:reboot_ask")],
        [("🏠 Menu", "nav:menu")],
    ])


def kb_reboot_confirm() -> InlineKeyboardMarkup:
    return _kb([
        [("✅ Konfirmasi Reboot", "sys:reboot_do"), ("❌ Batal", "nav:system")],
    ])


def kb_back_system() -> InlineKeyboardMarkup:
    return _kb([
        [("⬅️ Back", "nav:system"), ("🏠 Menu", "nav:menu")],
    ])


# ─── Mute ─────────────────────────────────────────────────────────────────────

def kb_mute(is_muted: bool) -> InlineKeyboardMarkup:
    rows = [
        [("1 Jam", "mute:3600"), ("6 Jam", "mute:21600"), ("24 Jam", "mute:86400")],
    ]
    if is_muted:
        rows.append([("🔔 Unmute Sekarang", "mute:0")])
    rows.append([("🏠 Menu", "nav:menu")])
    return _kb(rows)


# ─── SSH Alert ───────────────────────────────────────────────────────────────

def kb_ssh_alert(ip: str) -> InlineKeyboardMarkup:
    return _kb([
        [("🚫 Ban IP", f"ssh_ban:{ip}"), ("➕ Whitelist", f"ssh_trust:{ip}")],
        [("🏠 Menu", "nav:menu")],
    ])
