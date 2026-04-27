import random
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import F, Max
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import AgentTokenAuthentication
from .models import AgentCommand, AndroidDeviceToken, Metric, ProcessSnapshot, Server, ServiceSnapshot, UserSettings
from .permissions import IsAgentAuthenticated
from .serializers import (
    AgentCommandSerializer,
    AgentRegisterSerializer,
    AndroidPushTokenSerializer,
    CommandResultSerializer,
    CreateServerCommandSerializer,
    IntervalSettingsSerializer,
    MetricSerializer,
    MetricSnapshotSerializer,
    PairServerSerializer,
    ProcessBatchSerializer,
    ProcessSnapshotSerializer,
    ReorderServersSerializer,
    ServerCommandStatusSerializer,
    ServerSettingsSerializer,
    ServerSerializer,
    ServiceBatchSerializer,
    ServiceSnapshotSerializer,
    UserSettingsSerializer,
    UserLoginSerializer,
    UserRegisterSerializer,
)

INTERVAL_FIELDS = (
    "interval_seconds",
    "process_snapshot_interval_seconds",
    "service_snapshot_interval_seconds",
    "metric_retention_days",
    "notify_on_offline",
    "notify_on_high_cpu",
    "notify_on_high_ram",
    "cpu_alert_threshold_percent",
    "ram_alert_threshold_percent",
)


def _generate_pairing_code() -> str:
    return f"{random.randint(0, 999):03d}-{random.randint(0, 999):03d}"


def _create_unique_pairing_code() -> str:
    for _ in range(30):
        code = _generate_pairing_code()
        if not Server.objects.filter(pairing_code=code).exists():
            return code
    raise RuntimeError("Unable to generate unique pairing code.")


def _create_agent_token() -> str:
    return secrets.token_urlsafe(48)


def _build_user_tokens(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def _get_or_create_user_settings(user) -> UserSettings:
    settings_obj, _ = UserSettings.objects.get_or_create(user=user)
    return settings_obj


def _get_user_server_or_404(user, server_id: int) -> Server:
    return get_object_or_404(Server, id=server_id, user=user, is_paired=True)


def _max_metrics_per_server() -> int:
    return int(getattr(settings, "MAX_METRICS_PER_SERVER", 720))


def _trim_metric_history(server: Server) -> None:
    retention_days = int(getattr(server, "metric_retention_days", 0) or 0)
    if retention_days > 0:
        delete_before = timezone.now() - timedelta(days=retention_days)
        Metric.objects.filter(server=server, collected_at__lt=delete_before).delete()

    max_metrics = _max_metrics_per_server()
    if max_metrics <= 0:
        return

    stale_ids = list(
        Metric.objects.filter(server=server)
        .order_by("-collected_at", "-id")
        .values_list("id", flat=True)[max_metrics:]
    )
    if stale_ids:
        Metric.objects.filter(id__in=stale_ids).delete()


def _normalize_service_name(service: str) -> str:
    value = (service or "").strip()
    if value.endswith(".service"):
        return value[: -len(".service")]
    return value


def _apply_interval_settings(server: Server, values: dict) -> list[str]:
    changed_fields = []
    for field_name in INTERVAL_FIELDS:
        if field_name not in values:
            continue
        new_value = values[field_name]
        if getattr(server, field_name) == new_value:
            continue
        setattr(server, field_name, new_value)
        changed_fields.append(field_name)
    return changed_fields


def _apply_service_snapshot_from_command(
    *,
    server: Server,
    service_name: str,
    action: str,
    collected_at,
) -> None:
    normalized_target = _normalize_service_name(service_name)
    snapshots = list(ServiceSnapshot.objects.filter(server=server))

    snapshot = None
    for item in snapshots:
        if _normalize_service_name(item.name) == normalized_target:
            snapshot = item
            break

    if snapshot is None:
        status_value = "stopped"
        enabled_value = False
        if action == "start":
            status_value = "running"
        elif action == "enable":
            enabled_value = True

        ServiceSnapshot.objects.create(
            server=server,
            name=service_name,
            status=status_value,
            enabled=enabled_value,
            collected_at=collected_at,
        )
        return

    changed_fields = []
    if action == "start" and snapshot.status != "running":
        snapshot.status = "running"
        changed_fields.append("status")
    elif action == "stop" and snapshot.status != "stopped":
        snapshot.status = "stopped"
        changed_fields.append("status")

    if action == "enable" and not snapshot.enabled:
        snapshot.enabled = True
        changed_fields.append("enabled")
    elif action == "disable" and snapshot.enabled:
        snapshot.enabled = False
        changed_fields.append("enabled")

    if snapshot.collected_at != collected_at:
        snapshot.collected_at = collected_at
        changed_fields.append("collected_at")

    if changed_fields:
        snapshot.save(update_fields=changed_fields)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user_settings = UserSettings.objects.create(
            user=user,
            data_refresh_interval_seconds=UserSettings.DEFAULT_DATA_REFRESH_INTERVAL_SECONDS,
        )
        tokens = _build_user_tokens(user)

        return Response(
            {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
                "settings": UserSettingsSerializer(user_settings).data,
                **tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request=request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        user_settings = _get_or_create_user_settings(user)
        tokens = _build_user_tokens(user)
        return Response(
            {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
                "settings": UserSettingsSerializer(user_settings).data,
                **tokens,
            },
            status=status.HTTP_200_OK,
        )


class AgentRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AgentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        server = Server.objects.create(
            hostname=serializer.validated_data["hostname"],
            ip_address=serializer.validated_data["ip_address"],
            os_name=serializer.validated_data.get("os_name", ""),
            kernel_version=serializer.validated_data.get("kernel_version", ""),
            cpu_model=serializer.validated_data.get("cpu_model", ""),
            cpu_cores=serializer.validated_data.get("cpu_cores"),
            total_ram_bytes=serializer.validated_data.get("total_ram_bytes"),
            total_disk_bytes=serializer.validated_data.get("total_disk_bytes"),
            pairing_code=_create_unique_pairing_code(),
            agent_token=_create_agent_token(),
            is_paired=False,
            pairing_expires_at=timezone.now() + timedelta(minutes=15),
        )

        return Response(
            {
                "server_id": server.id,
                "pairing_code": server.pairing_code,
                "agent_token": server.agent_token,
            },
            status=status.HTTP_201_CREATED,
        )


class PairServerView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PairServerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pairing_code = serializer.validated_data["pairing_code"]
        server = Server.objects.filter(pairing_code=pairing_code, is_paired=False).first()
        if server is None:
            return Response({"detail": "Invalid pairing code."}, status=status.HTTP_400_BAD_REQUEST)

        if not server.pairing_expires_at or server.pairing_expires_at < timezone.now():
            return Response({"detail": "Pairing code expired."}, status=status.HTTP_400_BAD_REQUEST)

        server.user = request.user
        server.name = serializer.validated_data["name"]
        server.is_paired = True
        server.pairing_code = None
        server.pairing_expires_at = None
        max_sort_order = (
            Server.objects.filter(user=request.user, is_paired=True)
            .aggregate(max_sort_order=Max("sort_order"))
            .get("max_sort_order")
        )
        server.sort_order = (max_sort_order + 1) if max_sort_order is not None else 0
        changed_interval_fields = _apply_interval_settings(server, serializer.validated_data)

        update_fields = [
            "user",
            "name",
            "is_paired",
            "pairing_code",
            "pairing_expires_at",
            "sort_order",
            "updated_at",
        ]
        update_fields.extend(changed_interval_fields)
        server.save(update_fields=update_fields)

        return Response(ServerSerializer(server).data, status=status.HTTP_200_OK)


class UserServersView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        servers = Server.objects.filter(user=request.user, is_paired=True).order_by("sort_order", "-updated_at")
        return Response(ServerSerializer(servers, many=True).data, status=status.HTTP_200_OK)


class ReorderServersView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = ReorderServersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        server_ids = serializer.validated_data["server_ids"]
        servers = list(
            Server.objects.filter(user=request.user, is_paired=True, id__in=server_ids).only("id")
        )
        if len(servers) != len(server_ids):
            return Response(
                {"detail": "Some servers were not found for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        server_ids_set = set(server_ids)
        all_user_server_ids = set(
            Server.objects.filter(user=request.user, is_paired=True).values_list("id", flat=True)
        )
        if server_ids_set != all_user_server_ids:
            return Response(
                {"detail": "You must send all paired user server IDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for sort_order, server_id in enumerate(server_ids):
                Server.objects.filter(user=request.user, id=server_id).update(sort_order=sort_order)

        ordered_servers = Server.objects.filter(user=request.user, is_paired=True).order_by("sort_order", "-updated_at")
        return Response(ServerSerializer(ordered_servers, many=True).data, status=status.HTTP_200_OK)


class ServerOverviewView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, server_id: int):
        server = _get_user_server_or_404(request.user, server_id)
        
        # 1. Získání parametru 'minutes' z URL (default 15)
        try:
            minutes = int(request.query_params.get('minutes', '15').replace('m', ''))
        except ValueError:
            minutes = 15

        # 2. Načtení historie metrik pro grafy
        time_threshold = timezone.now() - timedelta(minutes=minutes)
        metrics_history = server.metrics.filter(collected_at__gte=time_threshold).order_by('collected_at')

        latest_metric = server.metrics.order_by("-collected_at", "-id").first()
        processes = (
            server.processes.annotate(total_usage=F("cpu_usage") + F("ram_usage"))
            .order_by("-total_usage", "-cpu_usage", "-ram_usage", "name")
        )
        services = server.services.order_by("name")

        return Response(
            {
                "server": ServerSerializer(server).data,
                "latest_metric": MetricSnapshotSerializer(latest_metric).data if latest_metric else None,
                # 3. Přidání metrik do odpovědi
                "metrics": MetricSnapshotSerializer(metrics_history, many=True).data,
                "processes": ProcessSnapshotSerializer(processes, many=True).data,
                "services": ServiceSnapshotSerializer(services, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

class ServerProcessesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, server_id: int):
        server = _get_user_server_or_404(request.user, server_id)
        processes = (
            server.processes.annotate(total_usage=F("cpu_usage") + F("ram_usage"))
            .order_by("-total_usage", "-cpu_usage", "-ram_usage", "name")
        )
        return Response(ProcessSnapshotSerializer(processes, many=True).data, status=status.HTTP_200_OK)


class ServerServicesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, server_id: int):
        server = _get_user_server_or_404(request.user, server_id)
        services = server.services.order_by("name")
        return Response(ServiceSnapshotSerializer(services, many=True).data, status=status.HTTP_200_OK)


class ServerSettingsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, server_id: int):
        server = _get_user_server_or_404(request.user, server_id)
        return Response(ServerSettingsSerializer(server).data, status=status.HTTP_200_OK)

    def patch(self, request, server_id: int):
        server = _get_user_server_or_404(request.user, server_id)
        serializer = IntervalSettingsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        changed_identity_fields = []
        if "name" in request.data:
            new_name = str(request.data.get("name", "")).strip()
            if new_name and server.name != new_name:
                server.name = new_name
                changed_identity_fields.append("name")

        changed_interval_fields = _apply_interval_settings(server, serializer.validated_data)
        changed_fields = [*changed_identity_fields, *changed_interval_fields]
        if changed_fields:
            server.save(update_fields=[*changed_fields, "updated_at"])

        return Response(ServerSettingsSerializer(server).data, status=status.HTTP_200_OK)

    def delete(self, request, server_id: int):
        server = _get_user_server_or_404(request.user, server_id)
        server.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ServerCommandsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, server_id: int):
        server = _get_user_server_or_404(request.user, server_id)
        serializer = CreateServerCommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service_value = serializer.validated_data["service"].strip()
        if not service_value:
            return Response({"detail": "Service name is required."}, status=status.HTTP_400_BAD_REQUEST)

        command = AgentCommand.objects.create(
            server=server,
            action=serializer.validated_data["action"],
            service=service_value,
            status="pending",
        )
        return Response(
            {
                "id": command.id,
                "action": command.action,
                "service": command.service,
                "status": command.status,
                "created_at": command.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class ServerCommandStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, server_id: int, command_id: int):
        server = _get_user_server_or_404(request.user, server_id)
        command = get_object_or_404(AgentCommand, id=command_id, server=server)
        return Response(ServerCommandStatusSerializer(command).data, status=status.HTTP_200_OK)


class UserSettingsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_settings = _get_or_create_user_settings(request.user)
        return Response(UserSettingsSerializer(user_settings).data, status=status.HTTP_200_OK)

    def patch(self, request):
        user_settings = _get_or_create_user_settings(request.user)
        serializer = UserSettingsSerializer(user_settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class AndroidPushTokenView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AndroidPushTokenSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        device = serializer.save()
        return Response(
            {
                "token": device.token,
                "device_name": device.device_name,
                "is_active": device.is_active,
                "last_seen": device.last_seen,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        serializer = AndroidPushTokenSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"].strip()
        AndroidDeviceToken.objects.filter(user=request.user, token=token).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentBaseView(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [IsAgentAuthenticated]

    def _server(self, request) -> Server:
        return request.auth

    def _validate_server_id(self, request, payload_server_id: int) -> Server:
        server = self._server(request)
        if server.id != payload_server_id:
            raise PermissionDenied("server_id does not match token.")
        return server

    def _validate_path_server_id(self, request, server_id: int) -> Server:
        server = self._server(request)
        if server.id != server_id:
            raise PermissionDenied("URL server_id does not match token.")
        return server


class MetricsIngestView(AgentBaseView):
    def post(self, request):
        serializer = MetricSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        server = self._validate_server_id(request, data["server_id"])

        Metric.objects.create(
            server=server,
            cpu_usage=data["cpu_usage"],
            ram_usage=data["ram_usage"],
            disk_usage=data["disk_usage"],
            uptime_seconds=data.get("uptime_seconds", 0),
            network_upload_bytes=data["network_upload_bytes"],
            network_download_bytes=data["network_download_bytes"],
            collected_at=data.get("collected_at", timezone.now()),
        )
        _trim_metric_history(server)
        return Response({"detail": "Metrics saved."}, status=status.HTTP_201_CREATED)


class ProcessesIngestView(AgentBaseView):
    def post(self, request):
        serializer = ProcessBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        server = self._validate_server_id(request, data["server_id"])
        collected_at = data.get("collected_at", timezone.now())

        items = [
            ProcessSnapshot(
                server=server,
                pid=proc["pid"],
                name=proc["name"],
                cpu_usage=proc["cpu_usage"],
                ram_usage=proc["ram_usage"],
                collected_at=collected_at,
            )
            for proc in data["processes"]
        ]
        with transaction.atomic():
            ProcessSnapshot.objects.filter(server=server).delete()
            if items:
                ProcessSnapshot.objects.bulk_create(items)

        return Response({"detail": "Processes saved."}, status=status.HTTP_201_CREATED)


class ServicesIngestView(AgentBaseView):
    def post(self, request):
        serializer = ServiceBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        server = self._validate_server_id(request, data["server_id"])
        collected_at = data.get("collected_at", timezone.now())

        items = [
            ServiceSnapshot(
                server=server,
                name=svc["name"],
                status=svc["status"],
                enabled=svc["enabled"],
                collected_at=collected_at,
            )
            for svc in data["services"]
        ]
        with transaction.atomic():
            ServiceSnapshot.objects.filter(server=server).delete()
            if items:
                ServiceSnapshot.objects.bulk_create(items)

        return Response({"detail": "Services saved."}, status=status.HTTP_201_CREATED)


class AgentCommandsView(AgentBaseView):
    def get(self, request, server_id: int):
        server = self._validate_path_server_id(request, server_id)
        commands = AgentCommand.objects.filter(server=server, status="pending").order_by("created_at")
        return Response(AgentCommandSerializer(commands, many=True).data, status=status.HTTP_200_OK)


class AgentServerSettingsView(AgentBaseView):
    def get(self, request, server_id: int):
        server = self._validate_path_server_id(request, server_id)
        return Response(ServerSettingsSerializer(server).data, status=status.HTTP_200_OK)


class CommandResultView(AgentBaseView):
    def post(self, request, server_id: int, command_id: int):
        server = self._validate_path_server_id(request, server_id)
        command = get_object_or_404(AgentCommand, id=command_id, server=server)

        serializer = CommandResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        action_matches = data["action"] == command.action
        service_matches = _normalize_service_name(data["service"]) == _normalize_service_name(command.service)
        if not action_matches or not service_matches:
            return Response(
                {"detail": "Command action/service does not match stored command."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        executed_at = data.get("handled_at", timezone.now())
        with transaction.atomic():
            command.success = data["success"]
            command.status = "success" if data["success"] else "failed"
            command.return_code = data.get("return_code")
            command.stdout = data.get("stdout", "")
            command.stderr = data.get("stderr", "")
            command.error = data.get("error", "")
            command.executed_at = executed_at
            command.save(
                update_fields=["success", "status", "return_code", "stdout", "stderr", "error", "executed_at"]
            )

            if data["success"]:
                _apply_service_snapshot_from_command(
                    server=server,
                    service_name=command.service,
                    action=command.action,
                    collected_at=executed_at,
                )

        return Response({"detail": "Command result saved."}, status=status.HTTP_200_OK)
