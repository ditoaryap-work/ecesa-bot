"""
Log viewer — nginx, postgresql, redis, pgbouncer, pm2, syslog.
"""
import subprocess


LOG_SOURCES = {
    "nginx_error":  ("tail", ["-n", "30", "/var/log/nginx/error.log"]),
    "nginx_access": ("tail", ["-n", "30", "/var/log/nginx/access.log"]),
    "postgresql":   ("journalctl", ["-u", "postgresql", "-n", "30", "--no-pager"]),
    "redis":        ("journalctl", ["-u", "redis", "-n", "30", "--no-pager"]),
    "pgbouncer":    ("journalctl", ["-u", "pgbouncer", "-n", "30", "--no-pager"]),
    "pm2":          ("pm2", ["logs", "--nostream", "--lines", "30"]),
    "syslog":       ("journalctl", ["-n", "30", "--no-pager"]),
}


def get_log(key: str) -> str:
    if key not in LOG_SOURCES:
        return "❌ Log source tidak dikenal."

    cmd_type, args = LOG_SOURCES[key]

    try:
        if cmd_type == "tail":
            r = subprocess.run(["tail"] + args, capture_output=True, text=True, timeout=10)
        elif cmd_type == "journalctl":
            r = subprocess.run(["journalctl"] + args, capture_output=True, text=True, timeout=10)
        elif cmd_type == "pm2":
            r = subprocess.run(["pm2"] + args, capture_output=True, text=True, timeout=15)
        else:
            return "❌ Tipe log tidak dikenal."

        output = r.stdout.strip() or r.stderr.strip() or "(tidak ada output)"
        # Telegram max 4096 char — potong dari belakang
        if len(output) > 3500:
            output = "...(dipotong)\n" + output[-3400:]
        return output
    except subprocess.TimeoutExpired:
        return "⏱ Timeout saat membaca log."
    except FileNotFoundError as e:
        return f"❌ Command tidak ditemukan: {e}"
    except Exception as e:
        return f"❌ Error: {e}"


def format_log(key: str, content: str) -> str:
    labels = {
        "nginx_error": "🌐 Nginx Error Log",
        "nginx_access": "🌐 Nginx Access Log",
        "postgresql": "🐘 PostgreSQL Log",
        "redis": "🔴 Redis Log",
        "pgbouncer": "🔄 pgBouncer Log",
        "pm2": "📦 PM2 Log",
        "syslog": "🖥 Syslog",
    }
    label = labels.get(key, key)
    return f"📋 <b>{label}</b>\n{'─' * 33}\n<pre>{content}</pre>"
