#!/bin/bash
# ─────────────────────────────────────────────────────────
# Ecesa VPS Monitor Bot — Install Script
# Jalankan sebagai root: sudo bash install.sh
# ─────────────────────────────────────────────────────────
set -e

INSTALL_DIR="/opt/ecesa-bot"
BOT_USER="vpsbot"
SERVICE_NAME="ecesa-bot"
PYTHON="python3"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Root check ────────────────────────────────────────────
[ "$EUID" -ne 0 ] && error "Jalankan sebagai root: sudo bash install.sh"

echo ""
echo "═══════════════════════════════════════"
echo "  🖥️  Ecesa VPS Monitor Bot — Installer"
echo "═══════════════════════════════════════"
echo ""

# ── Dependency check ──────────────────────────────────────
info "Cek dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl git

# ── Create user ───────────────────────────────────────────
if ! id "$BOT_USER" &>/dev/null; then
    info "Membuat user $BOT_USER..."
    useradd --system --no-create-home --shell /bin/false "$BOT_USER"
fi

# ── Copy files ────────────────────────────────────────────
info "Install ke $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp -r . "$INSTALL_DIR/"
mkdir -p "$INSTALL_DIR/state"

# ── Python venv ───────────────────────────────────────────
info "Setup Python virtual environment..."
$PYTHON -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
info "Dependencies installed."

# ── Config ────────────────────────────────────────────────
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    warn "File .env dibuat dari contoh."
    echo ""
    read -rp "  Masukkan BOT_TOKEN dari @BotFather: " BOT_TOKEN
    read -rp "  Masukkan CHAT_ID Telegram lu: " CHAT_ID
    sed -i "s|your_bot_token_here|$BOT_TOKEN|g" "$INSTALL_DIR/.env"
    sed -i "s|your_telegram_chat_id_here|$CHAT_ID|g" "$INSTALL_DIR/.env"
    info "Token & Chat ID disimpan."
fi

chmod 600 "$INSTALL_DIR/.env"

# ── Permissions ───────────────────────────────────────────
chown -R "$BOT_USER:$BOT_USER" "$INSTALL_DIR"

# ── Sudo rules ────────────────────────────────────────────
info "Setup sudo rules untuk $BOT_USER..."
cat > "/etc/sudoers.d/$BOT_USER" << 'EOF'
# Ecesa bot — minimal sudo untuk operasi yang dibutuhkan
vpsbot ALL=(ALL) NOPASSWD: /bin/systemctl restart nginx
vpsbot ALL=(ALL) NOPASSWD: /bin/systemctl restart postgresql
vpsbot ALL=(ALL) NOPASSWD: /bin/systemctl restart redis
vpsbot ALL=(ALL) NOPASSWD: /bin/systemctl restart pgbouncer
vpsbot ALL=(ALL) NOPASSWD: /bin/systemctl reload nginx
vpsbot ALL=(ALL) NOPASSWD: /bin/systemctl is-active *
vpsbot ALL=(ALL) NOPASSWD: /usr/sbin/ufw deny from * to any
vpsbot ALL=(ALL) NOPASSWD: /bin/rm /etc/nginx/sites-enabled/*
vpsbot ALL=(ALL) NOPASSWD: /bin/ln -s /etc/nginx/sites-available/* /etc/nginx/sites-enabled/*
vpsbot ALL=(ALL) NOPASSWD: /bin/cp /tmp/nginx_maintenance_fallback.conf /etc/nginx/sites-available/maintenance
vpsbot ALL=(ALL) NOPASSWD: /bin/shutdown -r *
vpsbot ALL=(ALL) NOPASSWD: /usr/bin/apt update -y
vpsbot ALL=(ALL) NOPASSWD: /usr/bin/apt upgrade -y *
EOF
chmod 440 "/etc/sudoers.d/$BOT_USER"
info "Sudo rules disimpan."

# ── Systemd service ───────────────────────────────────────
info "Install systemd service..."
cp "$INSTALL_DIR/ecesa-bot.service" "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"
info "Service $SERVICE_NAME berjalan."

# ── Cron jobs ─────────────────────────────────────────────
info "Setup cron jobs..."
CRON_FILE="/etc/cron.d/ecesa-bot"
cat > "$CRON_FILE" << EOF
# Ecesa Bot — scheduled tasks
# Healthcheck tiap 5 menit
*/5 * * * * $BOT_USER $INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/watchdog/healthcheck.py >> /var/log/ecesa-bot-health.log 2>&1

# Daily report jam 08:00 WIB (UTC+7 = 01:00 UTC)
0 1 * * * $BOT_USER $INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/watchdog/daily_summary.py >> /var/log/ecesa-bot-daily.log 2>&1
EOF
chmod 644 "$CRON_FILE"
info "Cron jobs terpasang."

# ── PAM hook ──────────────────────────────────────────────
info "Setup PAM hook untuk SSH login notif..."
chmod +x "$INSTALL_DIR/watchdog/ssh_notify_pam.sh"
PAM_LINE="session optional pam_exec.so $INSTALL_DIR/watchdog/ssh_notify_pam.sh"
if ! grep -q "ssh_notify_pam.sh" /etc/pam.d/sshd; then
    echo "$PAM_LINE" >> /etc/pam.d/sshd
    info "PAM hook ditambahkan ke /etc/pam.d/sshd"
else
    warn "PAM hook sudah ada, skip."
fi

# ── Done ──────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════"
echo -e "  ${GREEN}✅  Instalasi selesai!${NC}"
echo "═══════════════════════════════════════"
echo ""
echo "  Bot status : $(systemctl is-active $SERVICE_NAME)"
echo "  Bot logs   : journalctl -u $SERVICE_NAME -f"
echo "  Config     : $INSTALL_DIR/.env"
echo ""
echo "  Buka Telegram dan ketik /menu ke bot lu."
echo ""
