# Generated manually for student project setup.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Server",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=120)),
                ("hostname", models.CharField(max_length=255)),
                ("ip_address", models.GenericIPAddressField()),
                ("pairing_code", models.CharField(blank=True, max_length=7, null=True, unique=True)),
                ("agent_token", models.CharField(max_length=128, unique=True)),
                ("is_paired", models.BooleanField(default=False)),
                ("pairing_expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_seen", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="servers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AgentCommand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("start", "start"), ("stop", "stop"), ("enable", "enable"), ("disable", "disable")], max_length=16)),
                ("service", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("pending", "pending"), ("success", "success"), ("failed", "failed")], default="pending", max_length=16)),
                ("success", models.BooleanField(blank=True, null=True)),
                ("return_code", models.IntegerField(blank=True, null=True)),
                ("stdout", models.TextField(blank=True)),
                ("stderr", models.TextField(blank=True)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("executed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commands",
                        to="api.server",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Metric",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cpu_usage", models.FloatField()),
                ("ram_usage", models.FloatField()),
                ("disk_usage", models.FloatField()),
                ("network_upload_bytes", models.BigIntegerField()),
                ("network_download_bytes", models.BigIntegerField()),
                ("collected_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="metrics",
                        to="api.server",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ProcessSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pid", models.IntegerField()),
                ("name", models.CharField(max_length=255)),
                ("cpu_usage", models.FloatField(default=0)),
                ("ram_usage", models.FloatField(default=0)),
                ("collected_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="processes",
                        to="api.server",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ServiceSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("status", models.CharField(max_length=32)),
                ("enabled", models.BooleanField(default=False)),
                ("collected_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="services",
                        to="api.server",
                    ),
                ),
            ],
        ),
    ]
