#!/bin/bash
# PAM hook — dipanggil oleh /etc/pam.d/sshd saat login
# Hanya jalankan saat login (PAM_TYPE=open_session)
if [ "$PAM_TYPE" = "open_session" ]; then
    IP="${PAM_RHOST:-unknown}"
    USER="${PAM_USER:-unknown}"
    /usr/bin/python3 /opt/ecesa-bot/watchdog/ssh_notify.py "$USER" "$IP" &
fi
