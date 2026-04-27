import time
from typing import Dict, List

import psutil


def _combined_score(process: Dict) -> float:
    # CPU and RAM are both percentages, so simple sum gives balanced ranking.
    return float(process.get("cpu_usage", 0.0)) + float(process.get("ram_usage", 0.0))


def collect_top_processes(limit: int = 10, sample_duration: float = 0.2) -> List[Dict]:
    processes = []

    # Prime CPU counters first, then sample once more after a short delay.
    for proc in psutil.process_iter(attrs=["pid"]):
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(sample_duration)

    for proc in psutil.process_iter(attrs=["pid", "name", "memory_percent"]):
        try:
            processes.append(
                {
                    "pid": proc.info["pid"],
                    "name": proc.info["name"] or "unknown",
                    "cpu_usage": round(proc.cpu_percent(interval=None), 2),
                    "ram_usage": round(proc.info["memory_percent"] or 0.0, 2),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if limit <= 0:
        return []

    # Build candidates from both dimensions so RAM-heavy idle CPU processes are not dropped.
    by_cpu = sorted(processes, key=lambda item: item["cpu_usage"], reverse=True)[:limit]
    by_ram = sorted(processes, key=lambda item: item["ram_usage"], reverse=True)[:limit]

    merged = {}
    for item in by_cpu + by_ram:
        merged[item["pid"]] = item

    if len(merged) < limit:
        for item in sorted(processes, key=_combined_score, reverse=True):
            merged[item["pid"]] = item
            if len(merged) >= limit:
                break

    ranked = sorted(
        merged.values(),
        key=lambda item: (_combined_score(item), item["cpu_usage"], item["ram_usage"]),
        reverse=True,
    )
    return ranked[:limit]
