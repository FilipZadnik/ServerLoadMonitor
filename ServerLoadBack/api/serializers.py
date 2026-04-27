from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import AgentCommand, AndroidDeviceToken, Metric, ProcessSnapshot, Server, ServiceSnapshot, UserSettings

User = get_user_model()


class AgentRegisterSerializer(serializers.Serializer):
    hostname = serializers.CharField(max_length=255)
    ip_address = serializers.IPAddressField()
    os_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    kernel_version = serializers.CharField(max_length=255, required=False, allow_blank=True)
    cpu_model = serializers.CharField(max_length=255, required=False, allow_blank=True)
    cpu_cores = serializers.IntegerField(min_value=1, required=False)
    total_ram_bytes = serializers.IntegerField(min_value=0, required=False)
    total_disk_bytes = serializers.IntegerField(min_value=0, required=False)


class UserRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username is already taken.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
            email=validated_data.get("email", ""),
        )


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)


class IntervalSettingsSerializer(serializers.Serializer):
    interval_seconds = serializers.IntegerField(min_value=1, max_value=3600, required=False)
    process_snapshot_interval_seconds = serializers.IntegerField(min_value=1, max_value=3600, required=False)
    service_snapshot_interval_seconds = serializers.IntegerField(min_value=1, max_value=3600, required=False)
    metric_retention_days = serializers.IntegerField(min_value=1, max_value=3650, required=False)
    notify_on_offline = serializers.BooleanField(required=False)
    notify_on_high_cpu = serializers.BooleanField(required=False)
    notify_on_high_ram = serializers.BooleanField(required=False)
    cpu_alert_threshold_percent = serializers.IntegerField(min_value=1, max_value=100, required=False)
    ram_alert_threshold_percent = serializers.IntegerField(min_value=1, max_value=100, required=False)


class PairServerSerializer(IntervalSettingsSerializer):
    pairing_code = serializers.RegexField(regex=r"^\d{3}-\d{3}$")
    name = serializers.CharField(max_length=120)


class MetricSerializer(serializers.Serializer):
    server_id = serializers.IntegerField()
    cpu_usage = serializers.FloatField()
    ram_usage = serializers.FloatField()
    disk_usage = serializers.FloatField()
    uptime_seconds = serializers.IntegerField(min_value=0, required=False)
    network_upload_bytes = serializers.IntegerField(min_value=0)
    network_download_bytes = serializers.IntegerField(min_value=0)
    collected_at = serializers.DateTimeField(required=False)


class ProcessItemSerializer(serializers.Serializer):
    pid = serializers.IntegerField()
    name = serializers.CharField(max_length=255)
    cpu_usage = serializers.FloatField()
    ram_usage = serializers.FloatField()


class ProcessBatchSerializer(serializers.Serializer):
    server_id = serializers.IntegerField()
    collected_at = serializers.DateTimeField(required=False)
    processes = ProcessItemSerializer(many=True)


class ServiceItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    status = serializers.CharField(max_length=32)
    enabled = serializers.BooleanField()


class ServiceBatchSerializer(serializers.Serializer):
    server_id = serializers.IntegerField()
    collected_at = serializers.DateTimeField(required=False)
    services = ServiceItemSerializer(many=True)


class AgentCommandSerializer(serializers.ModelSerializer):
    command = serializers.SerializerMethodField()

    class Meta:
        model = AgentCommand
        fields = ("id", "action", "service", "command")

    def get_command(self, obj: AgentCommand) -> str:
        return f"systemctl {obj.action} {obj.service}"


class CommandResultSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    action = serializers.ChoiceField(choices=[choice[0] for choice in AgentCommand.ACTION_CHOICES])
    service = serializers.CharField(max_length=255)
    return_code = serializers.IntegerField(required=False, allow_null=True)
    stdout = serializers.CharField(required=False, allow_blank=True)
    stderr = serializers.CharField(required=False, allow_blank=True)
    error = serializers.CharField(required=False, allow_blank=True)
    handled_at = serializers.DateTimeField(required=False)
    server_id = serializers.IntegerField(required=False)


class ServerSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Server
        fields = (
            "name",
            "is_paired",
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


class CreateServerCommandSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[choice[0] for choice in AgentCommand.ACTION_CHOICES])
    service = serializers.CharField(max_length=255)


class ServerCommandStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentCommand
        fields = (
            "id",
            "action",
            "service",
            "status",
            "success",
            "return_code",
            "stdout",
            "stderr",
            "error",
            "created_at",
            "executed_at",
        )


class ReorderServersSerializer(serializers.Serializer):
    server_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_server_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Server IDs must be unique.")
        return value


class ServerSerializer(serializers.ModelSerializer):
    latest_metric = serializers.SerializerMethodField()
    is_online = serializers.ReadOnlyField()
    offline_timeout_seconds = serializers.ReadOnlyField()

    class Meta:
        model = Server
        fields = (
            "id",
            "name",
            "hostname",
            "ip_address",
            "os_name",
            "kernel_version",
            "cpu_model",
            "cpu_cores",
            "total_ram_bytes",
            "total_disk_bytes",
            "is_paired",
            "last_seen",
            "interval_seconds",
            "process_snapshot_interval_seconds",
            "service_snapshot_interval_seconds",
            "metric_retention_days",
            "sort_order",
            "notify_on_offline",
            "notify_on_high_cpu",
            "notify_on_high_ram",
            "cpu_alert_threshold_percent",
            "ram_alert_threshold_percent",
            "is_online",
            "offline_timeout_seconds",
            "latest_metric",
        )

    def get_latest_metric(self, obj: Server):
        metric = obj.metrics.order_by("-collected_at", "-id").first()
        if not metric:
            return None
        return MetricSnapshotSerializer(metric).data


class MetricSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Metric
        fields = (
            "cpu_usage",
            "ram_usage",
            "disk_usage",
            "uptime_seconds",
            "network_upload_bytes",
            "network_download_bytes",
            "collected_at",
        )


class ProcessSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessSnapshot
        fields = ("pid", "name", "cpu_usage", "ram_usage", "collected_at")


class ServiceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceSnapshot
        fields = ("name", "status", "enabled", "collected_at")


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = ("data_refresh_interval_seconds",)


class AndroidPushTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)
    device_name = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def create(self, validated_data):
        user = self.context["user"]
        token = validated_data["token"].strip()
        defaults = {
            "user": user,
            "device_name": validated_data.get("device_name", "").strip(),
            "is_active": True,
            "last_seen": timezone.now(),
        }
        device, _ = AndroidDeviceToken.objects.update_or_create(token=token, defaults=defaults)
        return device
