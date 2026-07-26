"""
Disk usage — per mount point + delta spike detection.
"""
import psutil
from core.config import DISK_THRESHOLD


def get_disk() -> list[dict]:
    partitions = psutil.disk_partitions(all=False)
    results = []
    for p in partitions:
        try:
            usage = psutil.disk_usage(p.mountpoint)
            results.append({
                "mount":     p.mountpoint,
                "device":    p.device,
                "fstype":    p.fstype,
                "total_gb":  round(usage.total / 1e9, 1),
                "used_gb":   round(usage.used / 1e9, 1),
                "free_gb":   round(usage.free / 1e9, 1),
                "pct":       usage.percent,
                "critical":  usage.percent >= DISK_THRESHOLD,
            })
        except PermissionError:
            continue
    return results


def format_disk(partitions: list[dict]) -> str:
    lines = ["💾 <b>Disk Usage</b>", "─" * 33]
    for p in partitions:
        icon = "🔴" if p["critical"] else "🟡" if p["pct"] > 70 else "🟢"
        bar_filled = int(p["pct"] / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        lines.append(
            f"{icon} <code>{p['mount']}</code> ({p['fstype']})\n"
            f"   [{bar}] {p['pct']}%\n"
            f"   {p['used_gb']}G / {p['total_gb']}G  (free: {p['free_gb']}G)"
        )
    return "\n".join(lines)
