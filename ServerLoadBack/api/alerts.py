from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from django.conf import settings
from django.utils import timezone

from .models import AndroidDeviceToken, Metric, Server, ServerAlertState

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except Exception:  # pragma: no cover - handled gracefully at runtime
    firebase_admin = None
    credentials = None
    messaging = None


_FIREBASE_READY = False


@dataclass
class AlertCheckResult:
    alert_type: str
    became_active: bool
    became_resolved: bool
    active: bool


def _is_firebase_enabled() -> bool:
    return bool(getattr(settings, "FCM_ENABLED", False))


def _ensure_firebase_initialized() -> bool:
    global _FIREBASE_READY

    if not _is_firebase_enabled():
        return False
    if firebase_admin is None or credentials is None or messaging is None:
        logger.warning("FCM_ENABLED=True but firebase_admin is not installed.")
        return False
    if _FIREBASE_READY:
        return True

    cred_path = getattr(settings, "FCM_SERVICE_ACCOUNT_FILE", "")
    if not cred_path:
        logger.warning("FCM is enabled but FCM_SERVICE_ACCOUNT_FILE is not configured.")
        return False

    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _FIREBASE_READY = True
        return True
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to initialize Firebase Admin SDK: %s", exc)
        return False


def _alert_state(server: Server, alert_type: str) -> ServerAlertState:
    state, _ = ServerAlertState.objects.get_or_create(server=server, alert_type=alert_type)
    return state


def _set_state(
    state: ServerAlertState,
    *,
    active_now: bool,
    value: Optional[float] = None,
    now=None,
) -> AlertCheckResult:
    now = now or timezone.now()

    became_active = False
    became_resolved = False

    update_fields = ["last_value", "updated_at"]
    state.last_value = value

    if active_now and not state.is_active:
        state.is_active = True
        state.triggered_at = now
        state.resolved_at = None
        became_active = True
        update_fields.extend(["is_active", "triggered_at", "resolved_at"])
    elif not active_now and state.is_active:
        state.is_active = False
        state.resolved_at = now
        became_resolved = True
        update_fields.extend(["is_active", "resolved_at"])

    if became_active or became_resolved or value is not None:
        state.save(update_fields=sorted(set(update_fields)))

    return AlertCheckResult(
        alert_type=state.alert_type,
        became_active=became_active,
        became_resolved=became_resolved,
        active=state.is_active,
    )


def _tokens_for_user(user) -> list[str]:
    return list(
        AndroidDeviceToken.objects.filter(user=user, is_active=True)
        .order_by("-updated_at")
        .values_list("token", flat=True)
    )


def send_android_push(user, *, title: str, body: str, data: Optional[dict] = None) -> int:
    if not _ensure_firebase_initialized():
        return 0

    tokens = _tokens_for_user(user)
    if not tokens:
        return 0

    payload_data = {k: str(v) for k, v in (data or {}).items()}

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data=payload_data,
        android=messaging.AndroidConfig(priority="high"),
    )

    try:
        result = messaging.send_each_for_multicast(message)
    except Exception as exc:  # pragma: no cover
        logger.exception("FCM send failed: %s", exc)
        return 0

    # Deactivate invalid tokens.
    for index, response in enumerate(result.responses):
        if response.success:
            continue
        token = tokens[index]
        error_str = str(response.exception or "")
        if "registration-token-not-registered" in error_str or "invalid-argument" in error_str:
            AndroidDeviceToken.objects.filter(token=token).update(is_active=False)

    return int(result.success_count)


def _build_trigger_notification(server: Server, alert_type: str, metric: Optional[Metric]) -> tuple[str, str, dict]:
    if alert_type == ServerAlertState.TYPE_OFFLINE:
        title = f"{server.name or server.hostname} is offline"
        body = "Agent heartbeat timed out."
        data = {"type": "offline", "server_id": server.id}
        return title, body, data

    if alert_type == ServerAlertState.TYPE_CPU_HIGH:
        cpu_value = float(metric.cpu_usage) if metric else 0.0
        title = f"High CPU on {server.name or server.hostname}"
        body = f"CPU usage is {cpu_value:.1f}% (threshold {server.cpu_alert_threshold_percent}%)."
        data = {"type": "cpu_high", "server_id": server.id, "cpu": f"{cpu_value:.1f}"}
        return title, body, data

    ram_value = float(metric.ram_usage) if metric else 0.0
    title = f"High RAM on {server.name or server.hostname}"
    body = f"RAM usage is {ram_value:.1f}% (threshold {server.ram_alert_threshold_percent}%)."
    data = {"type": "ram_high", "server_id": server.id, "ram": f"{ram_value:.1f}"}
    return title, body, data


def evaluate_server_alerts(server: Server, *, now=None, send_notifications: bool = True) -> list[AlertCheckResult]:
    now = now or timezone.now()
    metric = server.metrics.order_by("-collected_at", "-id").first()

    checks = [
        (
            ServerAlertState.TYPE_OFFLINE,
            bool(server.notify_on_offline),
            not server.is_online,
            None,
        ),
        (
            ServerAlertState.TYPE_CPU_HIGH,
            bool(server.notify_on_high_cpu),
            bool(metric and metric.cpu_usage > server.cpu_alert_threshold_percent),
            float(metric.cpu_usage) if metric else None,
        ),
        (
            ServerAlertState.TYPE_RAM_HIGH,
            bool(server.notify_on_high_ram),
            bool(metric and metric.ram_usage > server.ram_alert_threshold_percent),
            float(metric.ram_usage) if metric else None,
        ),
    ]

    results: list[AlertCheckResult] = []
    for alert_type, enabled, active_now, value in checks:
        state = _alert_state(server, alert_type)
        result = _set_state(state, active_now=enabled and active_now, value=value, now=now)
        results.append(result)

        if not send_notifications or not enabled or not result.became_active or server.user is None:
            continue

        title, body, data = _build_trigger_notification(server, alert_type, metric)
        sent_count = send_android_push(server.user, title=title, body=body, data=data)
        logger.info(
            "Alert notification sent: server=%s type=%s devices=%s payload=%s",
            server.id,
            alert_type,
            sent_count,
            json.dumps(data),
        )

    return results


def evaluate_all_servers(*, send_notifications: bool = True) -> int:
    count = 0
    for server in Server.objects.filter(is_paired=True, user__isnull=False):
        evaluate_server_alerts(server, send_notifications=send_notifications)
        count += 1
    return count
