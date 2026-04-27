from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="server",
            name="interval_seconds",
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AddField(
            model_name="server",
            name="process_snapshot_interval_seconds",
            field=models.PositiveIntegerField(default=30),
        ),
        migrations.AddField(
            model_name="server",
            name="service_snapshot_interval_seconds",
            field=models.PositiveIntegerField(default=60),
        ),
    ]
