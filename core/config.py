from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
CHAT_ID: int = int(os.getenv("CHAT_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN tidak diset di .env")
if not CHAT_ID:
    raise RuntimeError("CHAT_ID tidak diset di .env")

# ─── Thresholds ──────────────────────────────────────────────────────────────
CPU_THRESHOLD: int = int(os.getenv("CPU_THRESHOLD", "80"))
RAM_THRESHOLD: int = int(os.getenv("RAM_THRESHOLD", "85"))
DISK_THRESHOLD: int = int(os.getenv("DISK_THRESHOLD", "85"))
DISK_DELTA_ALERT_GB: int = int(os.getenv("DISK_DELTA_ALERT_GB", "5"))

# ─── Services ────────────────────────────────────────────────────────────────
SYSTEMD_SERVICES: list[str] = os.getenv("SYSTEMD_SERVICES", "nginx postgresql redis pgbouncer").split()
PM2_PROCESSES: list[str] = [p for p in os.getenv("PM2_PROCESSES", "").split() if p]

# ─── TLS ─────────────────────────────────────────────────────────────────────
TLS_DOMAINS: list[str] = [d for d in os.getenv("TLS_DOMAINS", "").split() if d]
TLS_WARN_DAYS: int = int(os.getenv("TLS_WARN_DAYS", "14"))

# ─── Maintenance ─────────────────────────────────────────────────────────────
NGINX_MAINTENANCE_CONF: str = os.getenv("NGINX_MAINTENANCE_CONF", "/etc/nginx/sites-available/maintenance")
NGINX_NORMAL_CONF: str = os.getenv("NGINX_NORMAL_CONF", "/etc/nginx/sites-available/ecesa")

# ─── Backup ──────────────────────────────────────────────────────────────────
BACKUP_DIR: str = os.getenv("BACKUP_DIR", "/var/backups/ecesa")
BACKUP_DB_NAME: str = os.getenv("BACKUP_DB_NAME", "ecesa_prod")

# ─── Scheduling ──────────────────────────────────────────────────────────────
DAILY_REPORT_HOUR: int = int(os.getenv("DAILY_REPORT_HOUR", "8"))
REALERT_INTERVAL_HOURS: int = int(os.getenv("REALERT_INTERVAL_HOURS", "6"))

# ─── SSH Trusted IPs ─────────────────────────────────────────────────────────
TRUSTED_IPS: list[str] = [ip for ip in os.getenv("TRUSTED_IPS", "").split() if ip]

# ─── Internal paths ──────────────────────────────────────────────────────────
BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR: str = os.path.join(BASE_DIR, "state")
DB_PATH: str = os.path.join(STATE_DIR, "ecesa_bot.db")

os.makedirs(STATE_DIR, exist_ok=True)
