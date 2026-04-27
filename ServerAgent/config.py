import json
import os
from typing import Any, Dict, Optional, Tuple


BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_INTERVAL_SECONDS = 5
DEFAULT_PROCESS_SNAPSHOT_INTERVAL_SECONDS = 30
DEFAULT_SERVICE_SNAPSHOT_INTERVAL_SECONDS = 60

HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))
HTTP_RETRIES = int(os.getenv("HTTP_RETRIES", "3"))
RETRY_DELAY_SECONDS = float(os.getenv("RETRY_DELAY_SECONDS", "2"))

CONFIG_PATH = os.getenv("AGENT_CONFIG_PATH", "agent_config.json")

_SERVER_ID: Optional[Any] = os.getenv("SERVER_ID")
_AGENT_TOKEN: Optional[str] = os.getenv("AGENT_TOKEN")
_PAIRING_CODE: Optional[str] = None

INTERVAL_KEY = "INTERVAL_SECONDS"
PROCESS_SNAPSHOT_INTERVAL_KEY = "PROCESS_SNAPSHOT_INTERVAL_SECONDS"
SERVICE_SNAPSHOT_INTERVAL_KEY = "SERVICE_SNAPSHOT_INTERVAL_SECONDS"


def _normalize_interval(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(1, parsed)


_INTERVAL_SECONDS = _normalize_interval(os.getenv(INTERVAL_KEY), DEFAULT_INTERVAL_SECONDS)
_PROCESS_SNAPSHOT_INTERVAL_SECONDS = _normalize_interval(
    os.getenv(PROCESS_SNAPSHOT_INTERVAL_KEY),
    DEFAULT_PROCESS_SNAPSHOT_INTERVAL_SECONDS,
)
_SERVICE_SNAPSHOT_INTERVAL_SECONDS = _normalize_interval(
    os.getenv(SERVICE_SNAPSHOT_INTERVAL_KEY),
    DEFAULT_SERVICE_SNAPSHOT_INTERVAL_SECONDS,
)


def _load_from_disk() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
            payload = json.load(config_file)
            if isinstance(payload, dict):
                return payload
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[config] Failed to read {CONFIG_PATH}: {exc}")
    return {}


def _save_to_disk(payload: Dict[str, Any]) -> bool:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
            json.dump(payload, config_file, indent=2)
            config_file.write("\n")
        return True
    except OSError as exc:
        print(f"[config] Failed to write {CONFIG_PATH}: {exc}")
        return False


def load_local_config() -> None:
    global _SERVER_ID, _AGENT_TOKEN, _PAIRING_CODE
    global _INTERVAL_SECONDS, _PROCESS_SNAPSHOT_INTERVAL_SECONDS, _SERVICE_SNAPSHOT_INTERVAL_SECONDS

    payload = _load_from_disk()
    if not _SERVER_ID:
        _SERVER_ID = payload.get("SERVER_ID")
    if not _AGENT_TOKEN:
        _AGENT_TOKEN = payload.get("AGENT_TOKEN")
    _PAIRING_CODE = payload.get("PAIRING_CODE")
    _INTERVAL_SECONDS = _normalize_interval(payload.get(INTERVAL_KEY), _INTERVAL_SECONDS)
    _PROCESS_SNAPSHOT_INTERVAL_SECONDS = _normalize_interval(
        payload.get(PROCESS_SNAPSHOT_INTERVAL_KEY),
        _PROCESS_SNAPSHOT_INTERVAL_SECONDS,
    )
    _SERVICE_SNAPSHOT_INTERVAL_SECONDS = _normalize_interval(
        payload.get(SERVICE_SNAPSHOT_INTERVAL_KEY),
        _SERVICE_SNAPSHOT_INTERVAL_SECONDS,
    )


def get_server_id() -> Optional[Any]:
    return _SERVER_ID


def get_agent_token() -> Optional[str]:
    return _AGENT_TOKEN


def get_pairing_code() -> Optional[str]:
    return _PAIRING_CODE


def has_credentials() -> bool:
    return bool(_SERVER_ID and _AGENT_TOKEN)


def get_interval_seconds() -> int:
    return _INTERVAL_SECONDS


def get_process_snapshot_interval_seconds() -> int:
    return _PROCESS_SNAPSHOT_INTERVAL_SECONDS


def get_service_snapshot_interval_seconds() -> int:
    return _SERVICE_SNAPSHOT_INTERVAL_SECONDS


def get_collection_intervals() -> Tuple[int, int, int]:
    return (
        _INTERVAL_SECONDS,
        _PROCESS_SNAPSHOT_INTERVAL_SECONDS,
        _SERVICE_SNAPSHOT_INTERVAL_SECONDS,
    )


def set_collection_intervals(
    *,
    interval_seconds: Optional[int] = None,
    process_snapshot_interval_seconds: Optional[int] = None,
    service_snapshot_interval_seconds: Optional[int] = None,
) -> Tuple[bool, bool]:
    global _INTERVAL_SECONDS, _PROCESS_SNAPSHOT_INTERVAL_SECONDS, _SERVICE_SNAPSHOT_INTERVAL_SECONDS

    new_interval = _normalize_interval(interval_seconds, _INTERVAL_SECONDS)
    new_process_interval = _normalize_interval(
        process_snapshot_interval_seconds,
        _PROCESS_SNAPSHOT_INTERVAL_SECONDS,
    )
    new_service_interval = _normalize_interval(
        service_snapshot_interval_seconds,
        _SERVICE_SNAPSHOT_INTERVAL_SECONDS,
    )

    changed = (
        new_interval != _INTERVAL_SECONDS
        or new_process_interval != _PROCESS_SNAPSHOT_INTERVAL_SECONDS
        or new_service_interval != _SERVICE_SNAPSHOT_INTERVAL_SECONDS
    )

    _INTERVAL_SECONDS = new_interval
    _PROCESS_SNAPSHOT_INTERVAL_SECONDS = new_process_interval
    _SERVICE_SNAPSHOT_INTERVAL_SECONDS = new_service_interval

    if not changed:
        return False, True

    payload = _load_from_disk()
    payload[INTERVAL_KEY] = _INTERVAL_SECONDS
    payload[PROCESS_SNAPSHOT_INTERVAL_KEY] = _PROCESS_SNAPSHOT_INTERVAL_SECONDS
    payload[SERVICE_SNAPSHOT_INTERVAL_KEY] = _SERVICE_SNAPSHOT_INTERVAL_SECONDS
    saved = _save_to_disk(payload)
    return True, saved


def set_registration_data(server_id: Any, agent_token: str, pairing_code: Optional[str]) -> bool:
    global _SERVER_ID, _AGENT_TOKEN, _PAIRING_CODE

    _SERVER_ID = server_id
    _AGENT_TOKEN = agent_token
    _PAIRING_CODE = pairing_code

    payload = _load_from_disk()
    payload["SERVER_ID"] = server_id
    payload["AGENT_TOKEN"] = agent_token
    if pairing_code:
        payload["PAIRING_CODE"] = pairing_code
    else:
        payload.pop("PAIRING_CODE", None)

    return _save_to_disk(payload)


def build_headers(agent_token: Optional[str] = None) -> dict:
    token = agent_token or _AGENT_TOKEN
    if not token:
        raise ValueError("AGENT_TOKEN is not configured.")
    return {
        "Authorization": f"Agent {token}",
        "Content-Type": "application/json",
    }


load_local_config()
