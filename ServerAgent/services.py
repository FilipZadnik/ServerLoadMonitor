import subprocess
from typing import Dict, List


def _run_systemctl(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl"] + args,
        capture_output=True,
        text=True,
        check=False,
    )


def _enabled_map() -> Dict[str, bool]:
    result = _run_systemctl(["list-unit-files", "--type=service", "--no-legend", "--no-pager"])
    if result.returncode != 0:
        print(f"[services] Failed to list unit files: {result.stderr.strip()}")
        return {}

    enabled_by_name = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        unit_name = parts[0]
        unit_state = parts[1]
        if unit_name.endswith(".service"):
            enabled_by_name[unit_name] = unit_state == "enabled"
    return enabled_by_name


def collect_services() -> List[Dict]:
    enabled_by_name = _enabled_map()

    result = _run_systemctl(
        ["list-units", "--type=service", "--all", "--no-legend", "--no-pager", "--plain"]
    )
    if result.returncode != 0:
        print(f"[services] Failed to list services: {result.stderr.strip()}")
        return []

    services = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 3:
            continue
        name = parts[0]
        active_state = parts[2]
        if not name.endswith(".service"):
            continue

        services.append(
            {
                "name": name,
                "status": "running" if active_state == "active" else "stopped",
                "enabled": enabled_by_name.get(name, False),
            }
        )

    services.sort(key=lambda item: item["name"])
    return services
