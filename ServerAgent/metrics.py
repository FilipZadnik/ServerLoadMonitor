import os
from typing import Dict

import psutil
import time


IGNORED_FS_TYPES = {
    "autofs",
    "binfmt_misc",
    "cgroup",
    "cgroup2",
    "configfs",
    "debugfs",
    "devpts",
    "devtmpfs",
    "efivarfs",
    "fusectl",
    "hugetlbfs",
    "mqueue",
    "overlay",
    "proc",
    "pstore",
    "securityfs",
    "selinuxfs",
    "squashfs",
    "sysfs",
    "tmpfs",
    "tracefs",
}


def _should_include_partition(partition: psutil._common.sdiskpart) -> bool:
    mountpoint = (partition.mountpoint or "").strip()
    if not mountpoint:
        return False

    fstype = (partition.fstype or "").strip().lower()
    if fstype in IGNORED_FS_TYPES:
        return False

    device = (partition.device or "").strip().lower()
    if device.startswith("/dev/loop") or device.startswith("loop"):
        return False

    return True


def collect_disk_usage_summary() -> Dict[str, float]:
    total_bytes = 0
    used_bytes = 0
    seen_mountpoints = set()
    seen_filesystems = set()

    for partition in psutil.disk_partitions(all=False):
        if not _should_include_partition(partition):
            continue

        mountpoint = partition.mountpoint
        if mountpoint in seen_mountpoints:
            continue
        seen_mountpoints.add(mountpoint)

        try:
            fs_id = os.stat(mountpoint).st_dev
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if fs_id in seen_filesystems:
            continue
        seen_filesystems.add(fs_id)

        try:
            usage = psutil.disk_usage(mountpoint)
        except (FileNotFoundError, PermissionError, OSError):
            continue

        if usage.total <= 0:
            continue

        total_bytes += int(usage.total)
        used_bytes += int(usage.used)

    if total_bytes <= 0:
        # Fallback keeps compatibility on minimal/odd environments.
        usage = psutil.disk_usage("/")
        total_bytes = int(usage.total)
        used_bytes = int(usage.used)

    usage_percent = (used_bytes / total_bytes * 100.0) if total_bytes > 0 else 0.0
    return {
        "total_bytes": total_bytes,
        "used_bytes": used_bytes,
        "total_mb": round(total_bytes / (1024.0 * 1024.0), 2),
        "used_mb": round(used_bytes / (1024.0 * 1024.0), 2),
        "usage_percent": round(usage_percent, 2),
    }


class MetricsCollector:
    def __init__(self) -> None:
        self._previous_net = psutil.net_io_counters()

    def collect(self) -> Dict[str, float]:
        cpu_usage = psutil.cpu_percent(interval=0.2)
        ram_usage = psutil.virtual_memory().percent
        disk_summary = collect_disk_usage_summary()
        disk_usage = disk_summary["usage_percent"]

        current_net = psutil.net_io_counters()
        upload_delta = max(0, current_net.bytes_sent - self._previous_net.bytes_sent)
        download_delta = max(0, current_net.bytes_recv - self._previous_net.bytes_recv)
        self._previous_net = current_net

        return {
            "cpu_usage": round(cpu_usage, 2),
            "ram_usage": round(ram_usage, 2),
            "disk_usage": round(disk_usage, 2),
            "uptime_seconds": max(0, int(time.time() - psutil.boot_time())),
            "network_upload_bytes": upload_delta,
            "network_download_bytes": download_delta,
        }
