from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Server(models.Model):
    DEFAULT_METRIC_INTERVAL_SECONDS = 5
    DEFAULT_PROCESS_SNAPSHOT_INTERVAL_SECONDS = 30
    DEFAULT_SERVICE_SNAPSHOT_INTERVAL_SECONDS = 60
    DEFAULT_METRIC_RETENTION_DAYS = 30

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servers",
    )
    name = models.CharField(max_length=120, blank=True)
    hostname = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    os_name = models.CharField(max_length=255, blank=True)
    kernel_version = models.CharField(max_length=255, blank=True)
    cpu_model = models.CharField(max_length=255, blank=True)
    cpu_cores = models.PositiveIntegerField(null=True, blank=True)
    total_ram_bytes = models.BigIntegerField(null=True, blank=True)
    total_disk_bytes = models.BigIntegerField(null=True, blank=True)

    pairing_code = models.CharField(max_length=7, null=True, blank=True, unique=True)
    agent_token = models.CharField(max_length=128, unique=True)
    is_paired = models.BooleanField(default=False)
    pairing_expires_at = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    interval_seconds = models.PositiveIntegerField(default=DEFAULT_METRIC_INTERVAL_SECONDS)
    process_snapshot_interval_seconds = models.PositiveIntegerField(
        default=DEFAULT_PROCESS_SNAPSHOT_INTERVAL_SECONDS
    )
    service_snapshot_interval_seconds = models.PositiveIntegerField(
        default=DEFAULT_SERVICE_SNAPSHOT_INTERVAL_SECONDS
    )
    metric_retention_days = models.PositiveIntegerField(default=DEFAULT_METRIC_RETENTION_DAYS)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    notify_on_offline = models.BooleanField(default=True)
    notify_on_high_cpu = models.BooleanField(default=True)
    notify_on_high_ram = models.BooleanField(default=True)
    cpu_alert_threshold_percent = models.PositiveSmallIntegerField(default=85)
    ram_alert_threshold_percent = models.PositiveSmallIntegerField(default=90)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def touch_last_seen(self) -> None:
        self.last_seen = timezone.now()
        self.save(update_fields=["last_seen"])

    @property
    def offline_timeout_seconds(self) -> int:
        return int(self.interval_seconds) * 3

    @property
    def is_online(self) -> bool:
        if self.last_seen is None:
            return False
        deadline = timezone.now() - timedelta(seconds=self.offline_timeout_seconds)
        return self.last_seen >= deadline

    def __str__(self) -> str:
        return self.name or self.hostname


class Metric(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="metrics")
    cpu_usage = models.FloatField()
    ram_usage = models.FloatField()
    disk_usage = models.FloatField()
    uptime_seconds = models.BigIntegerField(default=0)
    network_upload_bytes = models.BigIntegerField()
    network_download_bytes = models.BigIntegerField()
    collected_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)


class ProcessSnapshot(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="processes")
    pid = models.IntegerField()
    name = models.CharField(max_length=255)
    cpu_usage = models.FloatField(default=0)
    ram_usage = models.FloatField(default=0)
    collected_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)


class ServiceSnapshot(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=32)
    enabled = models.BooleanField(default=False)
    collected_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)


class AgentCommand(models.Model):
    ACTION_CHOICES = (
        ("start", "start"),
        ("stop", "stop"),
        ("enable", "enable"),
        ("disable", "disable"),
    )
    STATUS_CHOICES = (
        ("pending", "pending"),
        ("success", "success"),
        ("failed", "failed"),
    )

    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="commands")
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    service = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    success = models.BooleanField(null=True, blank=True)
    return_code = models.IntegerField(null=True, blank=True)
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)


class UserSettings(models.Model):
    DEFAULT_DATA_REFRESH_INTERVAL_SECONDS = 5

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="settings",
    )
    data_refresh_interval_seconds = models.PositiveIntegerField(default=DEFAULT_DATA_REFRESH_INTERVAL_SECONDS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AndroidDeviceToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="android_tokens",
    )
    token = models.CharField(max_length=512, unique=True)
    device_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user_id}:{self.token[:16]}..."


class ServerAlertState(models.Model):
    TYPE_OFFLINE = "offline"
    TYPE_CPU_HIGH = "cpu_high"
    TYPE_RAM_HIGH = "ram_high"
    ALERT_TYPE_CHOICES = (
        (TYPE_OFFLINE, "offline"),
        (TYPE_CPU_HIGH, "cpu_high"),
        (TYPE_RAM_HIGH, "ram_high"),
    )

    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="alert_states")
    alert_type = models.CharField(max_length=32, choices=ALERT_TYPE_CHOICES)
    is_active = models.BooleanField(default=False)
    last_value = models.FloatField(null=True, blank=True)
    triggered_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("server", "alert_type"), name="unique_server_alert_type"),
        ]

    def __str__(self) -> str:
        return f"{self.server_id}:{self.alert_type}:{'active' if self.is_active else 'resolved'}"
