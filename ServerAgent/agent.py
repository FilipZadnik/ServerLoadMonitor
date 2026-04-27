import json
import os
import platform
import socket
import time
from datetime import datetime, timezone
from typing import Dict, Optional

import qrcode_terminal
import psutil
import requests

import config
from commands import execute_command, fetch_commands, send_command_result
from metrics import MetricsCollector, collect_disk_usage_summary
from processes import collect_top_processes
from services import collect_services


def log(message: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_url(path: str) -> str:
    return f"{config.BACKEND_URL.rstrip('/')}/{path.lstrip('/')}"


def get_local_ip_address() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()


def _read_os_name() -> str:
    os_release_path = "/etc/os-release"
    if os.path.exists(os_release_path):
        try:
            with open(os_release_path, "r", encoding="utf-8") as file:
                for line in file:
                    if not line.startswith("PRETTY_NAME="):
                        continue
                    return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass

    return platform.platform()


def _read_cpu_model() -> str:
    cpuinfo_path = "/proc/cpuinfo"
    if os.path.exists(cpuinfo_path):
        try:
            with open(cpuinfo_path, "r", encoding="utf-8") as file:
                for line in file:
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    if key.strip().lower() == "model name":
                        return value.strip()
        except OSError:
            pass

    return platform.processor() or "Unknown CPU"


def collect_system_info() -> Dict[str, object]:
    virtual_memory = psutil.virtual_memory()
    disk_summary = collect_disk_usage_summary()
    core_count = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 1

    return {
        "hostname": socket.gethostname(),
        "ip_address": get_local_ip_address(),
        "os_name": _read_os_name(),
        "kernel_version": platform.release(),
        "cpu_model": _read_cpu_model(),
        "cpu_cores": int(core_count),
        "total_ram_bytes": int(virtual_memory.total),
        "total_disk_bytes": int(disk_summary["total_bytes"]),
    }


def update_session_headers(session: requests.Session) -> bool:
    try:
        session.headers.update(config.build_headers())
        return True
    except ValueError:
        return False


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    json: Optional[Dict] = None,
    retries: int = config.HTTP_RETRIES,
    use_auth: bool = True,
) -> Optional[requests.Response]:
    if use_auth and "Authorization" not in session.headers and not update_session_headers(session):
        log("Missing AGENT_TOKEN, request skipped.")
        return None

    for attempt in range(1, retries + 1):
        try:
            response = session.request(method, url, json=json, timeout=config.HTTP_TIMEOUT_SECONDS)
            if 500 <= response.status_code < 600:
                raise requests.HTTPError(
                    f"Server error: HTTP {response.status_code}",
                    response=response,
                )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            log(f"HTTP error ({attempt}/{retries}) {method} {url}: {exc}")
            if attempt < retries:
                time.sleep(config.RETRY_DELAY_SECONDS * attempt)
    return None


def print_pairing_qr(pairing_code: str) -> None:
    pairing_data = json.dumps({"pairing_code": pairing_code}, separators=(",", ":"))
    print("Pair this server with the mobile app.")
    print(f"Pairing code: {pairing_code}")
    print(f"QR payload: {pairing_data}")
    qrcode_terminal.draw(pairing_data)


def register_agent(session: requests.Session) -> bool:
    payload = collect_system_info()
    response = request_with_retry(
        session,
        "POST",
        build_url("/api/agent/register/"),
        json=payload,
        use_auth=False,
    )
    if response is None:
        log("Registration failed: backend unavailable. Will retry later.")
        return False

    try:
        data = response.json()
    except ValueError:
        log("Registration failed: backend returned invalid JSON.")
        return False

    server_id = data.get("server_id")
    agent_token = data.get("agent_token")
    pairing_code = data.get("pairing_code")
    if not server_id or not agent_token or not pairing_code:
        log("Registration failed: missing server_id/agent_token/pairing_code in response.")
        return False

    if not config.set_registration_data(server_id, str(agent_token), str(pairing_code)):
        log("Registration succeeded, but saving local config failed.")
        return False

    if not update_session_headers(session):
        log("Registration succeeded, but auth header could not be configured.")
        return False

    log(f"Registered agent successfully. Server ID: {server_id}")
    print_pairing_qr(str(pairing_code))
    return True


def send_metrics(session: requests.Session, collector: MetricsCollector) -> None:
    server_id = config.get_server_id()
    if server_id is None:
        log("Metrics skipped: SERVER_ID is missing.")
        return

    payload = {
        "server_id": server_id,
        "collected_at": utc_now_iso(),
        **collector.collect(),
    }
    response = request_with_retry(session, "POST", build_url("/metrics/"), json=payload)
    if response is not None:
        log("Metrics sent.")


def send_processes(session: requests.Session) -> None:
    server_id = config.get_server_id()
    if server_id is None:
        log("Processes skipped: SERVER_ID is missing.")
        return

    payload = {
        "server_id": server_id,
        "collected_at": utc_now_iso(),
        "processes": collect_top_processes(limit=10),
    }
    response = request_with_retry(session, "POST", build_url("/processes/"), json=payload)
    if response is not None:
        log(f"Processes sent ({len(payload['processes'])} items).")


def send_services(session: requests.Session) -> None:
    server_id = config.get_server_id()
    if server_id is None:
        log("Services skipped: SERVER_ID is missing.")
        return

    payload = {
        "server_id": server_id,
        "collected_at": utc_now_iso(),
        "services": collect_services(),
    }
    response = request_with_retry(session, "POST", build_url("/services/"), json=payload)
    if response is not None:
        log(f"Services sent ({len(payload['services'])} items).")


def handle_commands(session: requests.Session) -> None:
    server_id = config.get_server_id()
    if server_id is None:
        log("Command handling skipped: SERVER_ID is missing.")
        return

    commands = fetch_commands(session)
    if not commands:
        return

    log(f"Received {len(commands)} command(s).")

    for command in commands:
        command_id = command.get("id")
        if command_id is None:
            log("Skipping command without id.")
            continue

        result = execute_command(command)
        result["handled_at"] = utc_now_iso()
        result["server_id"] = server_id

        sent = send_command_result(session, command_id, result)
        if sent:
            log(f"Result sent for command #{command_id}.")
        else:
            log(f"Failed to send result for command #{command_id}.")


def sync_remote_interval_settings(session: requests.Session) -> bool:
    server_id = config.get_server_id()
    if server_id is None:
        return False

    response = request_with_retry(
        session,
        "GET",
        build_url(f"/api/agent/{server_id}/settings/"),
    )
    if response is None:
        return False

    try:
        data = response.json()
    except ValueError:
        log("Settings sync skipped: backend returned invalid JSON.")
        return False

    if not isinstance(data, dict):
        log("Settings sync skipped: unexpected payload type.")
        return False

    changed, saved = config.set_collection_intervals(
        interval_seconds=data.get("interval_seconds"),
        process_snapshot_interval_seconds=data.get("process_snapshot_interval_seconds"),
        service_snapshot_interval_seconds=data.get("service_snapshot_interval_seconds"),
    )
    if changed:
        interval_seconds, process_interval, service_interval = config.get_collection_intervals()
        save_message = "saved to local config." if saved else "applied, but local config save failed."
        log(
            "Interval settings updated from backend: "
            f"interval={interval_seconds}s, processes={process_interval}s, services={service_interval}s ({save_message})"
        )
    return changed


def main() -> None:
    session = requests.Session()
    collector = MetricsCollector()
    _, process_interval, service_interval = config.get_collection_intervals()
    next_processes_at = 0.0
    next_services_at = 0.0

    log("Agent started.")
    log(f"Backend: {config.BACKEND_URL}")
    log(f"Interval: {config.get_interval_seconds()}s")
    log(f"Process snapshot interval: {process_interval}s")
    log(f"Service snapshot interval: {service_interval}s")

    if config.has_credentials():
        if not update_session_headers(session):
            log("Stored credentials found, but AGENT_TOKEN is invalid.")
            return
        log(f"Loaded local credentials. Server ID: {config.get_server_id()}")
    else:
        log("No local credentials found. Running first-time registration.")
        while not config.has_credentials():
            if register_agent(session):
                break
            time.sleep(config.get_interval_seconds())

    while True:
        loop_start = time.time()
        try:
            intervals_changed = sync_remote_interval_settings(session)
            _, current_process_interval, current_service_interval = config.get_collection_intervals()
            if intervals_changed:
                if current_process_interval != process_interval:
                    process_interval = current_process_interval
                    next_processes_at = loop_start
                if current_service_interval != service_interval:
                    service_interval = current_service_interval
                    next_services_at = loop_start

            send_metrics(session, collector)
            now = time.time()
            if now >= next_processes_at:
                send_processes(session)
                next_processes_at = now + process_interval
            if now >= next_services_at:
                send_services(session)
                next_services_at = now + service_interval
            handle_commands(session)
        except Exception as exc:
            log(f"Unexpected loop error: {exc}")

        elapsed = time.time() - loop_start
        sleep_time = max(0, config.get_interval_seconds() - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Agent stopped by user.")
