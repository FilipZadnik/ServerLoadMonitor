import subprocess
import time
from typing import Dict, List, Optional, Tuple

import requests

import config

ALLOWED_ACTIONS = {"start", "stop", "enable", "disable"}


def _build_url(path: str) -> str:
    return f"{config.BACKEND_URL.rstrip('/')}/{path.lstrip('/')}"


def _request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    json: Optional[dict] = None,
    retries: int = config.HTTP_RETRIES,
) -> Optional[requests.Response]:
    for attempt in range(1, retries + 1):
        try:
            response = session.request(method, url, json=json, timeout=config.HTTP_TIMEOUT_SECONDS)
            if 400 <= response.status_code < 500 and response.status_code != 429:
                detail = (response.text or "").strip()
                if len(detail) > 300:
                    detail = detail[:300] + "..."
                print(
                    f"[commands] Client error {method} {url}: HTTP {response.status_code}"
                    + (f" | {detail}" if detail else "")
                )
                return None
            if 500 <= response.status_code < 600:
                raise requests.HTTPError(
                    f"Server error: HTTP {response.status_code}",
                    response=response,
                )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            print(f"[commands] HTTP error ({attempt}/{retries}) {method} {url}: {exc}")
            if attempt < retries:
                time.sleep(config.RETRY_DELAY_SECONDS * attempt)
    return None


def fetch_commands(session: requests.Session) -> List[Dict]:
    server_id = config.get_server_id()
    if server_id is None:
        print("[commands] SERVER_ID is not configured.")
        return []

    url = _build_url(f"/api/agent/{server_id}/commands/")
    response = _request_with_retry(session, "GET", url)
    if response is None:
        return []

    try:
        payload = response.json()
    except ValueError:
        print("[commands] Invalid JSON while fetching commands.")
        return []

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return payload["results"]
        if isinstance(payload.get("commands"), list):
            return payload["commands"]
    return []


def _parse_command(command: Dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    action = command.get("action")
    service = command.get("service")

    if not action or not service:
        raw_command = str(command.get("command", "")).strip()
        if raw_command:
            parts = raw_command.split()
            if len(parts) == 3 and parts[0] == "systemctl":
                action = parts[1]
                service = parts[2]

    if not action or not service:
        return None, None, "Command must include action/service or command."
    if action not in ALLOWED_ACTIONS:
        return None, None, f"Action '{action}' is not allowed."

    if not service.endswith(".service"):
        service = f"{service}.service"

    return action, service, None


def execute_command(command: Dict) -> Dict:
    action, service, error = _parse_command(command)
    if error:
        return {"success": False, "error": error}

    cmd = ["systemctl", action, service]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "action": action,
            "service": service,
            "error": "Command timed out.",
        }
    except Exception as exc:
        return {
            "success": False,
            "action": action,
            "service": service,
            "error": str(exc),
        }

    return {
        "success": completed.returncode == 0,
        "action": action,
        "service": service,
        "return_code": completed.returncode,
        "stdout": (completed.stdout or "").strip()[-1000:],
        "stderr": (completed.stderr or "").strip()[-1000:],
    }


def send_command_result(session: requests.Session, command_id: int, result_data: Dict) -> bool:
    server_id = config.get_server_id()
    if server_id is None:
        print("[commands] SERVER_ID is not configured.")
        return False

    url = _build_url(f"/api/agent/{server_id}/commands/{command_id}/result/")
    response = _request_with_retry(session, "POST", url, json=result_data)
    return response is not None
