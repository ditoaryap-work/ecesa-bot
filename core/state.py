from __future__ import annotations
"""
In-memory shared state untuk hal yang tidak perlu persist ke disk.
Hal yang perlu persist (mute, maintenance) ada di db.py.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BotState:
    # pending input dari user (misal: lagi nunggu konfirmasi reboot)
    pending_action: dict[int, str] = field(default_factory=dict)

    # last known network bytes untuk hitung delta traffic
    last_net_bytes: dict[str, int] = field(default_factory=dict)

    # last disk usage untuk deteksi spike
    last_disk_gb: float = 0.0

    # waktu bot start
    started_at: datetime = field(default_factory=datetime.now)


# singleton — di-import langsung
state = BotState()
