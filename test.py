#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def input_with_default(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else default


def short_token(value: str) -> str:
    if not value:
        return "-"
    if len(value) <= 16:
        return value
    return f"{value[:8]}...{value[-6:]}"


def apply_interval_payload(
    payload: dict[str, Any],
    interval_seconds: int | None = None,
    process_snapshot_interval_seconds: int | None = None,
    service_snapshot_interval_seconds: int | None = None,
) -> None:
    if interval_seconds is not None:
        payload["interval_seconds"] = interval_seconds
    if process_snapshot_interval_seconds is not None:
        payload["process_snapshot_interval_seconds"] = process_snapshot_interval_seconds
    if service_snapshot_interval_seconds is not None:
        payload["service_snapshot_interval_seconds"] = service_snapshot_interval_seconds


def parse_optional_int(value: str) -> int | None:
    raw = (value or "").strip()
    if not raw:
        return None
    return int(raw)


def api_request(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None, token: str | None = None):
    url = f"{base_url.rstrip('/')}{path}"
    body = None
    headers = {"Content-Type": "application/json"}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url=url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read().decode("utf-8")
            data = json.loads(content) if content else {}
            return resp.status, data
    except urllib.error.HTTPError as exc:
        content = exc.read().decode("utf-8")
        try:
            data = json.loads(content) if content else {}
        except json.JSONDecodeError:
            data = {"detail": content}
        return exc.code, data
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot connect to API ({url}). Is Django server running? Error: {exc}") from exc


def print_response(label: str, status_code: int, data: Any) -> None:
    print(f"\n[{label}] status={status_code}")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def do_register(base_url: str, username: str, password: str, email: str = ""):
    return api_request(
        base_url,
        "POST",
        "/api/auth/register/",
        {"username": username, "password": password, "email": email or ""},
    )


def do_login(base_url: str, username: str, password: str):
    return api_request(
        base_url,
        "POST",
        "/api/auth/login/",
        {"username": username, "password": password},
    )


def do_refresh(base_url: str, refresh_token: str):
    return api_request(
        base_url,
        "POST",
        "/api/auth/refresh/",
        {"refresh": refresh_token},
    )


def do_pair(
    base_url: str,
    access_token: str,
    pairing_code: str,
    name: str,
    interval_seconds: int | None = None,
    process_snapshot_interval_seconds: int | None = None,
    service_snapshot_interval_seconds: int | None = None,
):
    payload = {"pairing_code": pairing_code, "name": name}
    apply_interval_payload(
        payload,
        interval_seconds=interval_seconds,
        process_snapshot_interval_seconds=process_snapshot_interval_seconds,
        service_snapshot_interval_seconds=service_snapshot_interval_seconds,
    )
    return api_request(
        base_url,
        "POST",
        "/api/servers/pair/",
        payload,
        token=access_token,
    )


def do_servers(base_url: str, access_token: str):
    return api_request(
        base_url,
        "GET",
        "/api/servers/",
        token=access_token,
    )


def do_server_settings_get(base_url: str, access_token: str, server_id: int):
    return api_request(
        base_url,
        "GET",
        f"/api/servers/{server_id}/settings/",
        token=access_token,
    )


def do_server_settings_patch(
    base_url: str,
    access_token: str,
    server_id: int,
    interval_seconds: int | None = None,
    process_snapshot_interval_seconds: int | None = None,
    service_snapshot_interval_seconds: int | None = None,
):
    payload: dict[str, Any] = {}
    apply_interval_payload(
        payload,
        interval_seconds=interval_seconds,
        process_snapshot_interval_seconds=process_snapshot_interval_seconds,
        service_snapshot_interval_seconds=service_snapshot_interval_seconds,
    )
    return api_request(
        base_url,
        "PATCH",
        f"/api/servers/{server_id}/settings/",
        payload,
        token=access_token,
    )


def cmd_register(args: argparse.Namespace) -> int:
    status_code, data = do_register(args.base_url, args.username, args.password, args.email or "")
    print_response("REGISTER", status_code, data)
    return 0 if status_code in (200, 201) else 1


def cmd_login(args: argparse.Namespace) -> int:
    status_code, data = do_login(args.base_url, args.username, args.password)
    print_response("LOGIN", status_code, data)
    return 0 if status_code == 200 else 1


def cmd_refresh(args: argparse.Namespace) -> int:
    status_code, data = do_refresh(args.base_url, args.refresh_token)
    print_response("REFRESH", status_code, data)
    return 0 if status_code == 200 else 1


def cmd_pair(args: argparse.Namespace) -> int:
    status_code, data = do_pair(
        args.base_url,
        args.access_token,
        args.pairing_code,
        args.name,
        interval_seconds=args.interval_seconds,
        process_snapshot_interval_seconds=args.process_snapshot_interval_seconds,
        service_snapshot_interval_seconds=args.service_snapshot_interval_seconds,
    )
    print_response("PAIR", status_code, data)
    return 0 if status_code == 200 else 1


def cmd_servers(args: argparse.Namespace) -> int:
    status_code, data = do_servers(args.base_url, args.access_token)
    print_response("SERVERS", status_code, data)
    return 0 if status_code == 200 else 1


def cmd_server_settings_get(args: argparse.Namespace) -> int:
    status_code, data = do_server_settings_get(args.base_url, args.access_token, args.server_id)
    print_response("SERVER_SETTINGS_GET", status_code, data)
    return 0 if status_code == 200 else 1


def cmd_server_settings_patch(args: argparse.Namespace) -> int:
    if (
        args.interval_seconds is None
        and args.process_snapshot_interval_seconds is None
        and args.service_snapshot_interval_seconds is None
    ):
        print(
            "SERVER_SETTINGS_PATCH: provide at least one interval argument "
            "(--interval-seconds / --process-snapshot-interval-seconds / --service-snapshot-interval-seconds)."
        )
        return 1

    status_code, data = do_server_settings_patch(
        args.base_url,
        args.access_token,
        args.server_id,
        interval_seconds=args.interval_seconds,
        process_snapshot_interval_seconds=args.process_snapshot_interval_seconds,
        service_snapshot_interval_seconds=args.service_snapshot_interval_seconds,
    )
    print_response("SERVER_SETTINGS_PATCH", status_code, data)
    return 0 if status_code == 200 else 1


def cmd_flow(args: argparse.Namespace) -> int:
    print("Running mobile flow: register -> login -> refresh -> list servers")
    exit_code = 0

    register_code, register_data = do_register(args.base_url, args.username, args.password, args.email or "")
    print_response("REGISTER", register_code, register_data)
    if register_code not in (200, 201):
        print("Register failed. If user already exists, try login command directly.")
        return 1

    login_code, login_data = do_login(args.base_url, args.username, args.password)
    print_response("LOGIN", login_code, login_data)
    if login_code != 200:
        return 1

    access = login_data.get("access")
    refresh = login_data.get("refresh")
    if not access or not refresh:
        print("LOGIN response does not contain access/refresh tokens.")
        return 1

    refresh_code, refresh_data = do_refresh(args.base_url, refresh)
    print_response("REFRESH", refresh_code, refresh_data)
    if refresh_code != 200:
        exit_code = 1

    servers_code, servers_data = do_servers(args.base_url, access)
    print_response("SERVERS", servers_code, servers_data)
    if servers_code != 200:
        exit_code = 1

    if args.pairing_code:
        pair_code, pair_data = do_pair(
            args.base_url,
            access,
            args.pairing_code,
            args.server_name,
            interval_seconds=args.interval_seconds,
            process_snapshot_interval_seconds=args.process_snapshot_interval_seconds,
            service_snapshot_interval_seconds=args.service_snapshot_interval_seconds,
        )
        print_response("PAIR", pair_code, pair_data)
        if pair_code != 200:
            exit_code = 1

    print("\nDone.")
    return exit_code


def run_menu(base_url: str) -> int:
    state: dict[str, str] = {
        "base_url": base_url,
        "username": "",
        "password": "",
        "email": "",
        "access_token": "",
        "refresh_token": "",
    }

    while True:
        print("\n=== API test menu ===")
        print(f"Base URL: {state['base_url']}")
        print(f"Access token:  {short_token(state['access_token'])}")
        print(f"Refresh token: {short_token(state['refresh_token'])}")
        print("1. Register")
        print("2. Login")
        print("3. Refresh token")
        print("4. Pair server")
        print("5. List servers")
        print("6. Run flow")
        print("7. Change base URL")
        print("8. Server settings (GET)")
        print("9. Server settings (PATCH)")
        print("0. Exit")

        choice = input("Choose action number: ").strip()

        try:
            if choice == "1":
                state["username"] = input_with_default("Username", state["username"])
                state["password"] = input_with_default("Password", state["password"])
                state["email"] = input_with_default("Email", state["email"])
                code, data = do_register(state["base_url"], state["username"], state["password"], state["email"])
                print_response("REGISTER", code, data)
                if code in (200, 201):
                    if data.get("access"):
                        state["access_token"] = data["access"]
                    if data.get("refresh"):
                        state["refresh_token"] = data["refresh"]
            elif choice == "2":
                state["username"] = input_with_default("Username", state["username"])
                state["password"] = input_with_default("Password", state["password"])
                code, data = do_login(state["base_url"], state["username"], state["password"])
                print_response("LOGIN", code, data)
                if code == 200:
                    if data.get("access"):
                        state["access_token"] = data["access"]
                    if data.get("refresh"):
                        state["refresh_token"] = data["refresh"]
            elif choice == "3":
                state["refresh_token"] = input_with_default("Refresh token", state["refresh_token"])
                code, data = do_refresh(state["base_url"], state["refresh_token"])
                print_response("REFRESH", code, data)
                if code == 200 and data.get("access"):
                    state["access_token"] = data["access"]
            elif choice == "4":
                state["access_token"] = input_with_default("Access token", state["access_token"])
                pairing_code = input_with_default("Pairing code (123-456)")
                server_name = input_with_default("Server name", "My Server")
                interval_seconds = parse_optional_int(input_with_default("Interval seconds (optional)", ""))
                process_interval = parse_optional_int(
                    input_with_default("Process snapshot interval seconds (optional)", "")
                )
                service_interval = parse_optional_int(
                    input_with_default("Service snapshot interval seconds (optional)", "")
                )
                code, data = do_pair(
                    state["base_url"],
                    state["access_token"],
                    pairing_code,
                    server_name,
                    interval_seconds=interval_seconds,
                    process_snapshot_interval_seconds=process_interval,
                    service_snapshot_interval_seconds=service_interval,
                )
                print_response("PAIR", code, data)
            elif choice == "5":
                state["access_token"] = input_with_default("Access token", state["access_token"])
                code, data = do_servers(state["base_url"], state["access_token"])
                print_response("SERVERS", code, data)
            elif choice == "6":
                state["username"] = input_with_default("Username", state["username"])
                state["password"] = input_with_default("Password", state["password"])
                state["email"] = input_with_default("Email", state["email"])
                pairing_code = input_with_default("Pairing code (optional)")
                server_name = input_with_default("Server name", "My Server")
                interval_seconds = parse_optional_int(input_with_default("Interval seconds (optional)", ""))
                process_interval = parse_optional_int(
                    input_with_default("Process snapshot interval seconds (optional)", "")
                )
                service_interval = parse_optional_int(
                    input_with_default("Service snapshot interval seconds (optional)", "")
                )
                flow_args = argparse.Namespace(
                    base_url=state["base_url"],
                    username=state["username"],
                    password=state["password"],
                    email=state["email"],
                    pairing_code=pairing_code,
                    server_name=server_name,
                    interval_seconds=interval_seconds,
                    process_snapshot_interval_seconds=process_interval,
                    service_snapshot_interval_seconds=service_interval,
                )
                _ = cmd_flow(flow_args)
            elif choice == "7":
                state["base_url"] = input_with_default("New base URL", state["base_url"])
            elif choice == "8":
                state["access_token"] = input_with_default("Access token", state["access_token"])
                server_id = int(input_with_default("Server ID"))
                code, data = do_server_settings_get(state["base_url"], state["access_token"], server_id)
                print_response("SERVER_SETTINGS_GET", code, data)
            elif choice == "9":
                state["access_token"] = input_with_default("Access token", state["access_token"])
                server_id = int(input_with_default("Server ID"))
                interval_seconds = parse_optional_int(input_with_default("Interval seconds (optional)", ""))
                process_interval = parse_optional_int(
                    input_with_default("Process snapshot interval seconds (optional)", "")
                )
                service_interval = parse_optional_int(
                    input_with_default("Service snapshot interval seconds (optional)", "")
                )
                if interval_seconds is None and process_interval is None and service_interval is None:
                    print("No interval value entered. Nothing to update.")
                    continue
                code, data = do_server_settings_patch(
                    state["base_url"],
                    state["access_token"],
                    server_id,
                    interval_seconds=interval_seconds,
                    process_snapshot_interval_seconds=process_interval,
                    service_snapshot_interval_seconds=service_interval,
                )
                print_response("SERVER_SETTINGS_PATCH", code, data)
            elif choice == "0":
                print("Bye.")
                return 0
            else:
                print("Invalid choice. Use number 0-9.")
        except ValueError:
            print("Invalid number format.")
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="API test script for mobile actions (register/login/refresh/pair/list servers/settings).",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")

    subparsers = parser.add_subparsers(dest="command", required=False)

    register = subparsers.add_parser("register", help="Create user account")
    register.add_argument("--username", required=True)
    register.add_argument("--password", required=True)
    register.add_argument("--email", default="")
    register.set_defaults(func=cmd_register)

    login = subparsers.add_parser("login", help="Login user and get JWT tokens")
    login.add_argument("--username", required=True)
    login.add_argument("--password", required=True)
    login.set_defaults(func=cmd_login)

    refresh = subparsers.add_parser("refresh", help="Refresh access token")
    refresh.add_argument("--refresh-token", required=True)
    refresh.set_defaults(func=cmd_refresh)

    pair = subparsers.add_parser("pair", help="Pair server to user account")
    pair.add_argument("--access-token", required=True)
    pair.add_argument("--pairing-code", required=True, help="Format: 123-456")
    pair.add_argument("--name", required=True, help="Server name shown in app")
    pair.add_argument("--interval-seconds", type=int, default=None, help="Optional metric interval")
    pair.add_argument(
        "--process-snapshot-interval-seconds",
        type=int,
        default=None,
        help="Optional process snapshot interval",
    )
    pair.add_argument(
        "--service-snapshot-interval-seconds",
        type=int,
        default=None,
        help="Optional service snapshot interval",
    )
    pair.set_defaults(func=cmd_pair)

    servers = subparsers.add_parser("servers", help="List paired servers for user")
    servers.add_argument("--access-token", required=True)
    servers.set_defaults(func=cmd_servers)

    settings_get = subparsers.add_parser("settings-get", help="Get server interval settings")
    settings_get.add_argument("--access-token", required=True)
    settings_get.add_argument("--server-id", required=True, type=int)
    settings_get.set_defaults(func=cmd_server_settings_get)

    settings_patch = subparsers.add_parser("settings-patch", help="Patch server interval settings")
    settings_patch.add_argument("--access-token", required=True)
    settings_patch.add_argument("--server-id", required=True, type=int)
    settings_patch.add_argument("--interval-seconds", type=int, default=None)
    settings_patch.add_argument("--process-snapshot-interval-seconds", type=int, default=None)
    settings_patch.add_argument("--service-snapshot-interval-seconds", type=int, default=None)
    settings_patch.set_defaults(func=cmd_server_settings_patch)

    flow = subparsers.add_parser("flow", help="Run end-to-end mobile flow")
    flow.add_argument("--username", required=True)
    flow.add_argument("--password", required=True)
    flow.add_argument("--email", default="")
    flow.add_argument("--pairing-code", default="", help="Optional: pair after login")
    flow.add_argument("--server-name", default="My Server", help="Used only with --pairing-code")
    flow.add_argument("--interval-seconds", type=int, default=None, help="Used only with --pairing-code")
    flow.add_argument(
        "--process-snapshot-interval-seconds",
        type=int,
        default=None,
        help="Used only with --pairing-code",
    )
    flow.add_argument(
        "--service-snapshot-interval-seconds",
        type=int,
        default=None,
        help="Used only with --pairing-code",
    )
    flow.set_defaults(func=cmd_flow)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        return run_menu(args.base_url)
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
