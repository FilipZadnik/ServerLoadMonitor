import os
import sys
import threading
import time

from django.conf import settings

from .alerts import evaluate_all_servers

_worker_started = False
_worker_lock = threading.Lock()


def _is_autostart_enabled() -> bool:
    return bool(getattr(settings, "ALERT_WORKER_AUTOSTART", True))


def _should_skip_for_command() -> bool:
    if len(sys.argv) < 2:
        return False

    command = sys.argv[1]
    skip_commands = {
        "migrate",
        "makemigrations",
        "collectstatic",
        "shell",
        "createsuperuser",
        "test",
        "evaluate_alerts",
        "run_alert_worker",
    }
    return command in skip_commands


def _is_runserver_reloader_parent() -> bool:
    # With Django runserver autoreload, parent process should not start worker.
    return len(sys.argv) >= 2 and sys.argv[1] == "runserver" and os.environ.get("RUN_MAIN") != "true"


def _worker_loop() -> None:
    interval = max(1, int(getattr(settings, "ALERT_WORKER_INTERVAL_SECONDS", 15)))
    while True:
        started = time.time()
        try:
            evaluate_all_servers(send_notifications=True)
        except Exception:
            # Keep worker alive even on transient DB/network failures.
            pass

        elapsed = time.time() - started
        sleep_seconds = max(0.0, interval - elapsed)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)


def start_alert_worker_if_enabled() -> None:
    global _worker_started

    if not _is_autostart_enabled():
        return
    if _should_skip_for_command():
        return
    if _is_runserver_reloader_parent():
        return

    with _worker_lock:
        if _worker_started:
            return
        thread = threading.Thread(target=_worker_loop, name="alert-worker", daemon=True)
        thread.start()
        _worker_started = True
