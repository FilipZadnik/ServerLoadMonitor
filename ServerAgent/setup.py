#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="First-time setup for Server Monitoring Agent (register + pairing QR + systemd service)."
    )
    parser.add_argument(
        "--service-name",
        default="server-monitoring-agent",
        help="systemd service name (without .service). Default: server-monitoring-agent",
    )
    parser.add_argument(
        "--service-user",
        default="root",
        help="Linux user running the service. Default: root (sudo privileges).",
    )
    parser.add_argument(
        "--python-bin",
        default=sys.executable,
        help="Python binary path for systemd ExecStart.",
    )
    parser.add_argument(
        "--config-path",
        default=None,
        help="Custom AGENT_CONFIG_PATH for the service.",
    )
    parser.add_argument(
        "--skip-service",
        action="store_true",
        help="Only register and show pairing QR. Do not create systemd service.",
    )
    parser.add_argument(
        "--force-register",
        action="store_true",
        help="Force new registration even when local credentials already exist.",
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Enable service for boot, but do not start it immediately.",
    )
    parser.add_argument(
        "--pairing-timeout",
        type=int,
        default=0,
        help="Seconds to wait for pairing before giving up (0 = wait forever).",
    )
    parser.add_argument(
        "--pairing-poll-interval",
        type=int,
        default=3,
        help="How often to check pairing status in seconds. Default: 3",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip automatic installation of requirements.txt.",
    )
    return parser.parse_args()


def run_command(command: List[str], *, input_text: str = "") -> None:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "Unknown error"
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{stderr}")


def install_requirements(args: argparse.Namespace) -> None:
    if args.skip_install:
        print("Skipping requirements installation (--skip-install).")
        return

    project_dir = Path(__file__).resolve().parent
    requirements_path = project_dir / "requirements.txt"
    if not requirements_path.exists():
        print("requirements.txt not found, skipping dependency installation.")
        return

    command = [
        args.python_bin,
        "-m",
        "pip",
        "install",
        "-r",
        str(requirements_path),
        "--break-system-packages",
    ]
    print("Installing Python dependencies from requirements.txt ...")
    run_command(command)


def build_service_unit(
    service_name: str,
    service_user: str,
    working_dir: Path,
    python_bin: str,
    backend_url: str,
    config_path: str,
) -> str:
    env_lines = [
        'Environment="PYTHONUNBUFFERED=1"',
        f'Environment="BACKEND_URL={backend_url}"',
    ]
    if config_path:
        env_lines.append(f'Environment="AGENT_CONFIG_PATH={config_path}"')

    env_block = "\n".join(env_lines)
    return f"""[Unit]
Description=Server Monitoring Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={service_user}
WorkingDirectory={working_dir}
ExecStart={python_bin} {working_dir / 'agent.py'}
Restart=always
RestartSec=5
{env_block}

[Install]
WantedBy=multi-user.target
"""


def install_systemd_service(args: argparse.Namespace, backend_url: str) -> None:
    service_name = args.service_name.strip()
    if not service_name:
        raise RuntimeError("Service name cannot be empty.")

    working_dir = Path(__file__).resolve().parent
    service_path = f"/etc/systemd/system/{service_name}.service"

    service_user = (args.service_user or "root").strip() or "root"
    config_path = args.config_path or str(working_dir / "agent_config.json")

    unit_content = build_service_unit(
        service_name=service_name,
        service_user=service_user,
        working_dir=working_dir,
        python_bin=args.python_bin,
        backend_url=backend_url,
        config_path=config_path,
    )

    use_sudo = os.geteuid() != 0
    maybe_sudo = ["sudo"] if use_sudo else []

    print(f"Installing systemd service: {service_path}")
    run_command([*maybe_sudo, "tee", service_path], input_text=unit_content)
    run_command([*maybe_sudo, "systemctl", "daemon-reload"])
    run_command([*maybe_sudo, "systemctl", "enable", f"{service_name}.service"])

    if not args.no_start:
        run_command([*maybe_sudo, "systemctl", "restart", f"{service_name}.service"])
        print(f"Service enabled and started: {service_name}.service")
    else:
        print(f"Service enabled (not started now): {service_name}.service")


def wait_until_paired(session, config_module, build_url_fn, *, timeout_seconds: int, poll_interval_seconds: int) -> bool:
    server_id = config_module.get_server_id()
    if server_id is None:
        print("Cannot wait for pairing: SERVER_ID missing.")
        return False

    poll_interval_seconds = max(1, int(poll_interval_seconds))
    timeout_seconds = max(0, int(timeout_seconds))
    deadline = time.time() + timeout_seconds if timeout_seconds > 0 else None

    print("Waiting for successful pairing in mobile app...")
    while True:
        if deadline is not None and time.time() > deadline:
            return False

        try:
            response = session.get(
                build_url_fn(f"/api/agent/{server_id}/settings/"),
                timeout=config_module.HTTP_TIMEOUT_SECONDS,
            )
            if response.ok:
                payload = response.json()
                if isinstance(payload, dict) and payload.get("is_paired") is True:
                    return True
        except Exception:
            pass

        time.sleep(poll_interval_seconds)


def main() -> int:
    args = parse_args()

    if args.config_path:
        os.environ["AGENT_CONFIG_PATH"] = args.config_path

    try:
        install_requirements(args)
    except Exception as exc:
        print(f"Requirements installation failed: {exc}")
        return 1

    import requests

    import config
    from agent import build_url, print_pairing_qr, register_agent

    backend_url = config.BACKEND_URL

    session = requests.Session()

    should_register = args.force_register or not config.has_credentials()
    if should_register:
        print("Registering agent on backend...")
        if not register_agent(session):
            print("Registration failed. Fix backend/network and run setup again.")
            return 1
    else:
        print("Existing credentials found in local config.")
        try:
            session.headers.update(config.build_headers())
        except Exception:
            print("Stored credentials are invalid or incomplete.")
            return 1
        pairing_code = config.get_pairing_code()
        if pairing_code:
            print("Showing stored pairing code and QR again:")
            print_pairing_qr(str(pairing_code))
        else:
            print("Pairing code is not available in local config (server may already be paired).")

    if args.skip_service:
        print("Setup completed (service creation skipped).")
        return 0

    is_paired = wait_until_paired(
        session,
        config,
        build_url,
        timeout_seconds=args.pairing_timeout,
        poll_interval_seconds=args.pairing_poll_interval,
    )
    if not is_paired:
        print("Pairing was not confirmed in time. Service was not created.")
        return 1
    print("Pairing confirmed. Proceeding with service setup...")

    try:
        install_systemd_service(args, backend_url)
    except Exception as exc:
        print(f"Service setup failed: {exc}")
        return 1

    print("Setup completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
