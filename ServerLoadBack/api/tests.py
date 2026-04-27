from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .alerts import evaluate_server_alerts
from .models import (
    AgentCommand,
    AndroidDeviceToken,
    Metric,
    ProcessSnapshot,
    Server,
    ServerAlertState,
    ServiceSnapshot,
    UserSettings,
)

User = get_user_model()


class AuthApiTests(APITestCase):
    def test_register_creates_user_and_returns_jwt_tokens(self):
        payload = {
            "username": "alice",
            "password": "supersafe123",
            "email": "alice@example.com",
        }

        response = self.client.post("/api/auth/register/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("settings", response.data)
        self.assertEqual(response.data["settings"]["data_refresh_interval_seconds"], 5)
        self.assertEqual(response.data["user"]["username"], "alice")
        self.assertTrue(User.objects.filter(username="alice").exists())
        self.assertTrue(UserSettings.objects.filter(user__username="alice").exists())

    def test_login_returns_jwt_tokens(self):
        User.objects.create_user(username="bob", password="secretpass123")

        response = self.client.post(
            "/api/auth/login/",
            {"username": "bob", "password": "secretpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("settings", response.data)
        self.assertEqual(response.data["settings"]["data_refresh_interval_seconds"], 5)
        self.assertEqual(response.data["user"]["username"], "bob")


class PairingFlowTests(APITestCase):
    def _jwt_header_for_user(self, user: User) -> str:
        refresh = RefreshToken.for_user(user)
        return f"Bearer {str(refresh.access_token)}"

    def test_pair_endpoint_requires_jwt_authentication(self):
        server = Server.objects.create(
            hostname="srv-1",
            ip_address="10.0.0.1",
            pairing_code="123-456",
            agent_token=str(uuid4()),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
        )

        response = self.client.post(
            "/api/servers/pair/",
            {"pairing_code": server.pairing_code, "name": "Prod"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pair_assigns_server_to_authenticated_user(self):
        user = User.objects.create_user(username="carol", password="secretpass123")
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        server = Server.objects.create(
            hostname="srv-2",
            ip_address="10.0.0.2",
            pairing_code="234-567",
            agent_token=str(uuid4()),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
        )

        response = self.client.post(
            "/api/servers/pair/",
            {
                "pairing_code": server.pairing_code,
                "name": "Web Server",
                "interval_seconds": 7,
                "process_snapshot_interval_seconds": 45,
                "service_snapshot_interval_seconds": 120,
                "metric_retention_days": 20,
                "notify_on_offline": False,
                "notify_on_high_cpu": True,
                "notify_on_high_ram": False,
                "cpu_alert_threshold_percent": 91,
                "ram_alert_threshold_percent": 93,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        server.refresh_from_db()
        self.assertEqual(server.user_id, user.id)
        self.assertTrue(server.is_paired)
        self.assertIsNone(server.pairing_code)
        self.assertIsNone(server.pairing_expires_at)
        self.assertEqual(server.interval_seconds, 7)
        self.assertEqual(server.process_snapshot_interval_seconds, 45)
        self.assertEqual(server.service_snapshot_interval_seconds, 120)
        self.assertEqual(server.metric_retention_days, 20)
        self.assertFalse(server.notify_on_offline)
        self.assertTrue(server.notify_on_high_cpu)
        self.assertFalse(server.notify_on_high_ram)
        self.assertEqual(server.cpu_alert_threshold_percent, 91)
        self.assertEqual(server.ram_alert_threshold_percent, 93)

    def test_servers_list_returns_only_authenticated_users_paired_servers(self):
        user = User.objects.create_user(username="dave", password="secretpass123")
        other_user = User.objects.create_user(username="erin", password="secretpass123")
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        own_paired = Server.objects.create(
            user=user,
            name="Own paired",
            hostname="srv-own",
            ip_address="10.0.0.3",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
        )
        Server.objects.create(
            user=user,
            name="Own unpaired",
            hostname="srv-own-unpaired",
            ip_address="10.0.0.4",
            pairing_code="345-678",
            agent_token=str(uuid4()),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
        )
        Server.objects.create(
            user=other_user,
            name="Other paired",
            hostname="srv-other",
            ip_address="10.0.0.5",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
        )

        response = self.client.get("/api/servers/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], own_paired.id)

    def test_servers_list_requires_jwt_authentication(self):
        response = self.client.get("/api/servers/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_servers_list_is_sorted_by_sort_order(self):
        user = User.objects.create_user(username="sort-user", password="secretpass123")
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        first = Server.objects.create(
            user=user,
            name="First",
            hostname="srv-first",
            ip_address="10.0.3.1",
            agent_token=str(uuid4()),
            is_paired=True,
            sort_order=2,
        )
        second = Server.objects.create(
            user=user,
            name="Second",
            hostname="srv-second",
            ip_address="10.0.3.2",
            agent_token=str(uuid4()),
            is_paired=True,
            sort_order=0,
        )
        third = Server.objects.create(
            user=user,
            name="Third",
            hostname="srv-third",
            ip_address="10.0.3.3",
            agent_token=str(uuid4()),
            is_paired=True,
            sort_order=1,
        )

        response = self.client.get("/api/servers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [second.id, third.id, first.id])

    def test_reorder_endpoint_updates_server_order(self):
        user = User.objects.create_user(username="reorder-user", password="secretpass123")
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        first = Server.objects.create(
            user=user,
            name="First",
            hostname="srv-order-first",
            ip_address="10.0.4.1",
            agent_token=str(uuid4()),
            is_paired=True,
            sort_order=0,
        )
        second = Server.objects.create(
            user=user,
            name="Second",
            hostname="srv-order-second",
            ip_address="10.0.4.2",
            agent_token=str(uuid4()),
            is_paired=True,
            sort_order=1,
        )
        third = Server.objects.create(
            user=user,
            name="Third",
            hostname="srv-order-third",
            ip_address="10.0.4.3",
            agent_token=str(uuid4()),
            is_paired=True,
            sort_order=2,
        )

        response = self.client.patch(
            "/api/servers/reorder/",
            {"server_ids": [third.id, first.id, second.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [third.id, first.id, second.id])

        first.refresh_from_db()
        second.refresh_from_db()
        third.refresh_from_db()
        self.assertEqual(first.sort_order, 1)
        self.assertEqual(second.sort_order, 2)
        self.assertEqual(third.sort_order, 0)


class AgentRegisterApiTests(APITestCase):
    def test_agent_register_stores_system_information(self):
        payload = {
            "hostname": "srv-register",
            "ip_address": "10.1.1.10",
            "os_name": "Ubuntu 22.04 LTS",
            "kernel_version": "5.15.0-101-generic",
            "cpu_model": "Intel Xeon E5-2670",
            "cpu_cores": 8,
            "total_ram_bytes": 16777216000,
            "total_disk_bytes": 549755813888,
        }

        response = self.client.post("/api/agent/register/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        server = Server.objects.get(id=response.data["server_id"])
        self.assertEqual(server.hostname, payload["hostname"])
        self.assertEqual(server.ip_address, payload["ip_address"])
        self.assertEqual(server.os_name, payload["os_name"])
        self.assertEqual(server.kernel_version, payload["kernel_version"])
        self.assertEqual(server.cpu_model, payload["cpu_model"])
        self.assertEqual(server.cpu_cores, payload["cpu_cores"])
        self.assertEqual(server.total_ram_bytes, payload["total_ram_bytes"])
        self.assertEqual(server.total_disk_bytes, payload["total_disk_bytes"])


class ServerSettingsApiTests(APITestCase):
    def _jwt_header_for_user(self, user: User) -> str:
        refresh = RefreshToken.for_user(user)
        return f"Bearer {str(refresh.access_token)}"

    def test_settings_get_returns_current_intervals(self):
        user = User.objects.create_user(username="jack", password="secretpass123")
        server = Server.objects.create(
            user=user,
            name="settings-host",
            hostname="srv-settings",
            ip_address="10.0.0.30",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
            interval_seconds=9,
            process_snapshot_interval_seconds=40,
            service_snapshot_interval_seconds=80,
            metric_retention_days=14,
            notify_on_offline=False,
            notify_on_high_cpu=True,
            notify_on_high_ram=False,
            cpu_alert_threshold_percent=77,
            ram_alert_threshold_percent=88,
        )
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        response = self.client.get(f"/api/servers/{server.id}/settings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["interval_seconds"], 9)
        self.assertEqual(response.data["process_snapshot_interval_seconds"], 40)
        self.assertEqual(response.data["service_snapshot_interval_seconds"], 80)
        self.assertEqual(response.data["metric_retention_days"], 14)
        self.assertFalse(response.data["notify_on_offline"])
        self.assertTrue(response.data["notify_on_high_cpu"])
        self.assertFalse(response.data["notify_on_high_ram"])
        self.assertEqual(response.data["cpu_alert_threshold_percent"], 77)
        self.assertEqual(response.data["ram_alert_threshold_percent"], 88)

    def test_settings_patch_updates_intervals(self):
        user = User.objects.create_user(username="kate", password="secretpass123")
        server = Server.objects.create(
            user=user,
            name="settings-host-2",
            hostname="srv-settings-2",
            ip_address="10.0.0.31",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
        )
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        response = self.client.patch(
            f"/api/servers/{server.id}/settings/",
            {
                "interval_seconds": 4,
                "service_snapshot_interval_seconds": 90,
                "metric_retention_days": 10,
                "notify_on_high_ram": False,
                "cpu_alert_threshold_percent": 92,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        server.refresh_from_db()
        self.assertEqual(server.interval_seconds, 4)
        self.assertEqual(server.process_snapshot_interval_seconds, 30)
        self.assertEqual(server.service_snapshot_interval_seconds, 90)
        self.assertEqual(server.metric_retention_days, 10)
        self.assertFalse(server.notify_on_high_ram)
        self.assertEqual(server.cpu_alert_threshold_percent, 92)

    def test_settings_patch_rejects_invalid_interval(self):
        user = User.objects.create_user(username="lisa", password="secretpass123")
        server = Server.objects.create(
            user=user,
            name="settings-host-3",
            hostname="srv-settings-3",
            ip_address="10.0.0.32",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
        )
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        response = self.client.patch(
            f"/api/servers/{server.id}/settings/",
            {"interval_seconds": 0},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserSettingsApiTests(APITestCase):
    def _jwt_header_for_user(self, user: User) -> str:
        refresh = RefreshToken.for_user(user)
        return f"Bearer {str(refresh.access_token)}"

    def test_user_settings_get_returns_default(self):
        user = User.objects.create_user(username="mike", password="secretpass123")
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        response = self.client.get("/api/users/settings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data_refresh_interval_seconds"], 5)
        self.assertTrue(UserSettings.objects.filter(user=user).exists())

    def test_user_settings_patch_updates_value(self):
        user = User.objects.create_user(username="nina", password="secretpass123")
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        response = self.client.patch(
            "/api/users/settings/",
            {"data_refresh_interval_seconds": 30},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data_refresh_interval_seconds"], 30)
        self.assertEqual(UserSettings.objects.get(user=user).data_refresh_interval_seconds, 30)

    def test_user_settings_requires_authentication(self):
        response = self.client.get("/api/users/settings/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AndroidPushTokenApiTests(APITestCase):
    def _jwt_header_for_user(self, user: User) -> str:
        refresh = RefreshToken.for_user(user)
        return f"Bearer {str(refresh.access_token)}"

    def test_register_push_token_creates_or_updates_token(self):
        user = User.objects.create_user(username="push-user", password="secretpass123")
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        response = self.client.post(
            "/api/users/push-token/",
            {"token": "fcm-token-1", "device_name": "Pixel 9"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = AndroidDeviceToken.objects.get(token="fcm-token-1")
        self.assertEqual(token.user_id, user.id)
        self.assertTrue(token.is_active)
        self.assertEqual(token.device_name, "Pixel 9")

    def test_delete_push_token_marks_token_inactive(self):
        user = User.objects.create_user(username="push-user-delete", password="secretpass123")
        token = AndroidDeviceToken.objects.create(user=user, token="fcm-token-2", device_name="Pixel", is_active=True)
        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))

        response = self.client.delete(
            "/api/users/push-token/",
            {"token": token.token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        token.refresh_from_db()
        self.assertFalse(token.is_active)


class MonitoringReadApiTests(APITestCase):
    def _jwt_header_for_user(self, user: User) -> str:
        refresh = RefreshToken.for_user(user)
        return f"Bearer {str(refresh.access_token)}"

    def test_servers_list_returns_latest_metric_for_each_server(self):
        user = User.objects.create_user(username="frank", password="secretpass123")
        server = Server.objects.create(
            user=user,
            name="Main host",
            hostname="srv-main",
            ip_address="10.0.0.10",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
        )
        Metric.objects.create(
            server=server,
            cpu_usage=10,
            ram_usage=20,
            disk_usage=30,
            network_upload_bytes=100,
            network_download_bytes=200,
            collected_at=timezone.now() - timedelta(minutes=1),
        )
        Metric.objects.create(
            server=server,
            cpu_usage=11,
            ram_usage=21,
            disk_usage=31,
            network_upload_bytes=101,
            network_download_bytes=201,
            collected_at=timezone.now(),
        )

        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))
        response = self.client.get("/api/servers/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["latest_metric"]["cpu_usage"], 11)
        self.assertEqual(response.data[0]["latest_metric"]["ram_usage"], 21)

    def test_servers_list_exposes_online_status_based_on_three_times_interval(self):
        user = User.objects.create_user(username="frank-online", password="secretpass123")
        online_server = Server.objects.create(
            user=user,
            name="Online host",
            hostname="srv-online",
            ip_address="10.0.1.10",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
            interval_seconds=10,
            last_seen=timezone.now() - timedelta(seconds=29),
        )
        offline_server = Server.objects.create(
            user=user,
            name="Offline host",
            hostname="srv-offline",
            ip_address="10.0.1.11",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
            interval_seconds=10,
            last_seen=timezone.now() - timedelta(seconds=31),
        )

        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))
        response = self.client.get("/api/servers/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        server_by_id = {item["id"]: item for item in response.data}

        self.assertTrue(server_by_id[online_server.id]["is_online"])
        self.assertFalse(server_by_id[offline_server.id]["is_online"])
        self.assertEqual(server_by_id[online_server.id]["offline_timeout_seconds"], 30)
        self.assertEqual(server_by_id[offline_server.id]["offline_timeout_seconds"], 30)

    def test_overview_returns_current_metric_processes_and_services(self):
        user = User.objects.create_user(username="gina", password="secretpass123")
        server = Server.objects.create(
            user=user,
            name="Overview host",
            hostname="srv-overview",
            ip_address="10.0.0.11",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
        )
        Metric.objects.create(
            server=server,
            cpu_usage=55.5,
            ram_usage=66.6,
            disk_usage=77.7,
            network_upload_bytes=123,
            network_download_bytes=456,
            collected_at=timezone.now(),
        )
        ProcessSnapshot.objects.create(
            server=server,
            pid=111,
            name="python",
            cpu_usage=12.3,
            ram_usage=4.5,
            collected_at=timezone.now(),
        )
        ServiceSnapshot.objects.create(
            server=server,
            name="nginx",
            status="active",
            enabled=True,
            collected_at=timezone.now(),
        )

        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))
        response = self.client.get(f"/api/servers/{server.id}/overview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["server"]["id"], server.id)
        self.assertEqual(response.data["latest_metric"]["cpu_usage"], 55.5)
        self.assertEqual(len(response.data["processes"]), 1)
        self.assertEqual(response.data["processes"][0]["name"], "python")
        self.assertEqual(len(response.data["services"]), 1)
        self.assertEqual(response.data["services"][0]["name"], "nginx")

    def test_overview_rejects_access_to_another_users_server(self):
        user = User.objects.create_user(username="henry", password="secretpass123")
        other_user = User.objects.create_user(username="irene", password="secretpass123")
        foreign_server = Server.objects.create(
            user=other_user,
            name="foreign",
            hostname="srv-foreign",
            ip_address="10.0.0.12",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
        )

        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))
        response = self.client.get(f"/api/servers/{foreign_server.id}/overview/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_server_command_status_returns_command_for_owner(self):
        user = User.objects.create_user(username="owner-cmd", password="secretpass123")
        server = Server.objects.create(
            user=user,
            name="owner-server",
            hostname="srv-owner-cmd",
            ip_address="10.0.0.40",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
        )
        command = AgentCommand.objects.create(
            server=server,
            action="stop",
            service="nginx",
            status="success",
            success=True,
            return_code=0,
            stdout="ok",
        )

        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(user))
        response = self.client.get(f"/api/servers/{server.id}/commands/{command.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], command.id)
        self.assertEqual(response.data["status"], "success")
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["return_code"], 0)

    def test_server_command_status_rejects_foreign_user(self):
        owner = User.objects.create_user(username="owner-2", password="secretpass123")
        other = User.objects.create_user(username="other-2", password="secretpass123")
        server = Server.objects.create(
            user=owner,
            name="foreign-server",
            hostname="srv-foreign-cmd",
            ip_address="10.0.0.41",
            pairing_code=None,
            agent_token=str(uuid4()),
            is_paired=True,
            pairing_expires_at=None,
        )
        command = AgentCommand.objects.create(
            server=server,
            action="start",
            service="docker",
            status="pending",
        )

        self.client.credentials(HTTP_AUTHORIZATION=self._jwt_header_for_user(other))
        response = self.client.get(f"/api/servers/{server.id}/commands/{command.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AgentIngestBehaviorTests(APITestCase):
    def _agent_header_for_server(self, server: Server) -> str:
        return f"Agent {server.agent_token}"

    def test_agent_can_fetch_current_interval_settings(self):
        server = Server.objects.create(
            hostname="srv-settings-agent",
            ip_address="10.0.0.24",
            pairing_code="123-987",
            agent_token=str(uuid4()),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
            interval_seconds=6,
            process_snapshot_interval_seconds=22,
            service_snapshot_interval_seconds=33,
        )
        self.client.credentials(HTTP_AUTHORIZATION=self._agent_header_for_server(server))

        response = self.client.get(f"/api/agent/{server.id}/settings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["interval_seconds"], 6)
        self.assertEqual(response.data["process_snapshot_interval_seconds"], 22)
        self.assertEqual(response.data["service_snapshot_interval_seconds"], 33)

    def test_process_ingest_replaces_previous_snapshot(self):
        server = Server.objects.create(
            hostname="srv-process",
            ip_address="10.0.0.20",
            pairing_code="456-789",
            agent_token=str(uuid4()),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
        )
        self.client.credentials(HTTP_AUTHORIZATION=self._agent_header_for_server(server))

        first_payload = {
            "server_id": server.id,
            "collected_at": timezone.now().isoformat(),
            "processes": [
                {"pid": 1, "name": "proc-a", "cpu_usage": 10.0, "ram_usage": 1.0},
                {"pid": 2, "name": "proc-b", "cpu_usage": 20.0, "ram_usage": 2.0},
            ],
        }
        second_payload = {
            "server_id": server.id,
            "collected_at": timezone.now().isoformat(),
            "processes": [
                {"pid": 3, "name": "proc-c", "cpu_usage": 30.0, "ram_usage": 3.0},
            ],
        }

        self.assertEqual(self.client.post("/processes/", first_payload, format="json").status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.post("/processes/", second_payload, format="json").status_code, status.HTTP_201_CREATED)

        server.refresh_from_db()
        snapshots = ProcessSnapshot.objects.filter(server=server).order_by("pid")
        self.assertEqual(snapshots.count(), 1)
        self.assertEqual(snapshots.first().pid, 3)

    def test_services_ingest_replaces_previous_snapshot(self):
        server = Server.objects.create(
            hostname="srv-service",
            ip_address="10.0.0.21",
            pairing_code="567-890",
            agent_token=str(uuid4()),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
        )
        self.client.credentials(HTTP_AUTHORIZATION=self._agent_header_for_server(server))

        first_payload = {
            "server_id": server.id,
            "collected_at": timezone.now().isoformat(),
            "services": [
                {"name": "nginx", "status": "active", "enabled": True},
                {"name": "ssh", "status": "active", "enabled": True},
            ],
        }
        second_payload = {
            "server_id": server.id,
            "collected_at": timezone.now().isoformat(),
            "services": [
                {"name": "docker", "status": "inactive", "enabled": False},
            ],
        }

        self.assertEqual(self.client.post("/services/", first_payload, format="json").status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.post("/services/", second_payload, format="json").status_code, status.HTTP_201_CREATED)

        server.refresh_from_db()
        snapshots = ServiceSnapshot.objects.filter(server=server).order_by("name")
        self.assertEqual(snapshots.count(), 1)
        self.assertEqual(snapshots.first().name, "docker")

    def test_command_result_accepts_service_suffix_mismatch(self):
        server = Server.objects.create(
            hostname="srv-cmd",
            ip_address="10.0.0.23",
            pairing_code="789-012",
            agent_token=str(uuid4()),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
        )
        command = AgentCommand.objects.create(
            server=server,
            action="stop",
            service="nginx",
            status="pending",
        )
        self.client.credentials(HTTP_AUTHORIZATION=self._agent_header_for_server(server))

        payload = {
            "success": True,
            "action": "stop",
            "service": "nginx.service",
            "return_code": 0,
            "stdout": "",
            "stderr": "",
        }
        response = self.client.post(
            f"/api/agent/{server.id}/commands/{command.id}/result/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        command.refresh_from_db()
        self.assertEqual(command.status, "success")
        self.assertTrue(command.success)

    def test_command_result_updates_service_snapshot_immediately(self):
        server = Server.objects.create(
            hostname="srv-cmd-state",
            ip_address="10.0.0.26",
            pairing_code="890-123",
            agent_token=str(uuid4()),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
        )
        snapshot = ServiceSnapshot.objects.create(
            server=server,
            name="nginx.service",
            status="inactive",
            enabled=False,
            collected_at=timezone.now() - timedelta(minutes=10),
        )
        command = AgentCommand.objects.create(
            server=server,
            action="start",
            service="nginx",
            status="pending",
        )
        self.client.credentials(HTTP_AUTHORIZATION=self._agent_header_for_server(server))

        payload = {
            "success": True,
            "action": "start",
            "service": "nginx.service",
            "return_code": 0,
            "stdout": "",
            "stderr": "",
        }
        response = self.client.post(
            f"/api/agent/{server.id}/commands/{command.id}/result/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        command.refresh_from_db()
        snapshot.refresh_from_db()
        self.assertEqual(command.status, "success")
        self.assertEqual(snapshot.status, "running")
        self.assertFalse(snapshot.enabled)

    @override_settings(MAX_METRICS_PER_SERVER=3)
    def test_metrics_ingest_keeps_only_recent_entries(self):
        server = Server.objects.create(
            hostname="srv-metric",
            ip_address="10.0.0.22",
            pairing_code="678-901",
            agent_token=str(uuid4()),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
        )
        self.client.credentials(HTTP_AUTHORIZATION=self._agent_header_for_server(server))

        for index in range(5):
            payload = {
                "server_id": server.id,
                "cpu_usage": 10 + index,
                "ram_usage": 20 + index,
                "disk_usage": 30 + index,
                "uptime_seconds": 1000 + index,
                "network_upload_bytes": 100 + index,
                "network_download_bytes": 200 + index,
                "collected_at": (timezone.now() + timedelta(seconds=index)).isoformat(),
            }
            response = self.client.post("/metrics/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        metrics = Metric.objects.filter(server=server).order_by("-collected_at", "-id")
        self.assertEqual(metrics.count(), 3)
        self.assertEqual(metrics.first().cpu_usage, 14)
        self.assertEqual(metrics.first().uptime_seconds, 1004)

    def test_metrics_ingest_applies_server_retention_days(self):
        server = Server.objects.create(
            hostname="srv-retention",
            ip_address="10.0.0.25",
            pairing_code="321-654",
            agent_token=str(uuid4()),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
            metric_retention_days=1,
        )
        self.client.credentials(HTTP_AUTHORIZATION=self._agent_header_for_server(server))

        Metric.objects.create(
            server=server,
            cpu_usage=1,
            ram_usage=1,
            disk_usage=1,
            uptime_seconds=1,
            network_upload_bytes=1,
            network_download_bytes=1,
            collected_at=timezone.now() - timedelta(days=3),
        )

        payload = {
            "server_id": server.id,
            "cpu_usage": 22,
            "ram_usage": 33,
            "disk_usage": 44,
            "uptime_seconds": 123,
            "network_upload_bytes": 111,
            "network_download_bytes": 222,
            "collected_at": timezone.now().isoformat(),
        }
        response = self.client.post("/metrics/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        metrics = Metric.objects.filter(server=server).order_by("-collected_at", "-id")
        self.assertEqual(metrics.count(), 1)
        self.assertEqual(metrics.first().cpu_usage, 22)


class AlertEvaluationTests(APITestCase):
    def test_evaluate_alerts_activates_and_resolves_states(self):
        user = User.objects.create_user(username="alert-user", password="secretpass123")
        server = Server.objects.create(
            user=user,
            name="Alert host",
            hostname="srv-alert",
            ip_address="10.2.0.10",
            agent_token=str(uuid4()),
            is_paired=True,
            interval_seconds=5,
            notify_on_offline=True,
            notify_on_high_cpu=True,
            notify_on_high_ram=True,
            cpu_alert_threshold_percent=80,
            ram_alert_threshold_percent=80,
            last_seen=timezone.now(),
        )
        Metric.objects.create(
            server=server,
            cpu_usage=95.0,
            ram_usage=91.0,
            disk_usage=10.0,
            network_upload_bytes=1,
            network_download_bytes=1,
            collected_at=timezone.now(),
        )

        evaluate_server_alerts(server, send_notifications=False)
        cpu_state = ServerAlertState.objects.get(server=server, alert_type=ServerAlertState.TYPE_CPU_HIGH)
        ram_state = ServerAlertState.objects.get(server=server, alert_type=ServerAlertState.TYPE_RAM_HIGH)
        offline_state = ServerAlertState.objects.get(server=server, alert_type=ServerAlertState.TYPE_OFFLINE)

        self.assertTrue(cpu_state.is_active)
        self.assertTrue(ram_state.is_active)
        self.assertFalse(offline_state.is_active)

        server.last_seen = timezone.now() - timedelta(seconds=30)
        server.save(update_fields=["last_seen"])
        Metric.objects.create(
            server=server,
            cpu_usage=12.0,
            ram_usage=22.0,
            disk_usage=11.0,
            network_upload_bytes=1,
            network_download_bytes=1,
            collected_at=timezone.now() + timedelta(seconds=1),
        )
        evaluate_server_alerts(server, send_notifications=False)

        cpu_state.refresh_from_db()
        ram_state.refresh_from_db()
        offline_state.refresh_from_db()
        self.assertFalse(cpu_state.is_active)
        self.assertFalse(ram_state.is_active)
        self.assertTrue(offline_state.is_active)
