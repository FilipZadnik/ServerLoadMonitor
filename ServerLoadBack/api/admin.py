from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html, format_html_join

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


try:
    admin.site.unregister(User)
except NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "id",
        "username",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "is_superuser",
        "server_count",
        "data_refresh_interval_seconds_display",
        "last_login",
        "date_joined",
    )
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("data_refresh_interval_seconds_display", "servers_overview")
    fieldsets = (
        (None, {"fields": ("username",)}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Monitoring", {"fields": ("data_refresh_interval_seconds_display",)}),
        ("Servers", {"fields": ("servers_overview",)}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    @admin.display(description="Servers")
    def server_count(self, obj: User) -> int:
        return obj.servers.count()

    @admin.display(description="Refresh (s)")
    def data_refresh_interval_seconds_display(self, obj: User):
        settings = getattr(obj, "settings", None)
        if settings:
            return settings.data_refresh_interval_seconds
        return UserSettings.DEFAULT_DATA_REFRESH_INTERVAL_SECONDS

    @admin.display(description="Assigned servers")
    def servers_overview(self, obj: User):
        servers = obj.servers.order_by("name", "hostname")
        if not servers.exists():
            return "-"

        rows = []
        for server in servers:
            url = reverse("admin:api_server_change", args=[server.id])
            label = server.name or server.hostname
            rows.append((url, label, server.hostname, server.ip_address))

        return format_html(
            "<ul>{}</ul>",
            format_html_join(
                "",
                '<li><a href="{}">{}</a> ({}, {})</li>',
                rows,
            ),
        )


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "sort_order",
        "name",
        "hostname",
        "ip_address",
        "is_paired",
        "online_status",
        "offline_timeout_seconds_display",
        "last_seen",
    )
    search_fields = ("name", "hostname", "ip_address", "pairing_code")
    list_filter = ("is_paired",)
    readonly_fields = ("online_status", "offline_timeout_seconds_display")

    @admin.display(boolean=True, description="Online")
    def online_status(self, obj: Server) -> bool:
        return obj.is_online

    @admin.display(description="Offline timeout (s)")
    def offline_timeout_seconds_display(self, obj: Server) -> int:
        return obj.offline_timeout_seconds


@admin.register(AgentCommand)
class AgentCommandAdmin(admin.ModelAdmin):
    list_display = ("id", "server", "action", "service", "status", "created_at", "executed_at")
    list_filter = ("status", "action")
    search_fields = ("service",)


admin.site.register(Metric)
admin.site.register(ProcessSnapshot)
admin.site.register(ServiceSnapshot)


@admin.register(AndroidDeviceToken)
class AndroidDeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device_name", "is_active", "last_seen", "updated_at")
    search_fields = ("user__username", "device_name", "token")
    list_filter = ("is_active",)


@admin.register(ServerAlertState)
class ServerAlertStateAdmin(admin.ModelAdmin):
    list_display = ("id", "server", "alert_type", "is_active", "last_value", "triggered_at", "resolved_at")
    search_fields = ("server__name", "server__hostname", "alert_type")
    list_filter = ("alert_type", "is_active")
