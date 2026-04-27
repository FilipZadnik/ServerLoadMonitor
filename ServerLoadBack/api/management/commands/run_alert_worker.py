import time

from django.conf import settings
from django.core.management.base import BaseCommand

from api.alerts import evaluate_all_servers


class Command(BaseCommand):
    help = "Run continuous background worker for server alert evaluation and Android push notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Evaluate and update alert states, but do not send push notifications.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=None,
            help="Polling interval in seconds. Defaults to ALERT_WORKER_INTERVAL_SECONDS from settings.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        interval = options.get("interval")
        if interval is None:
            interval = int(getattr(settings, "ALERT_WORKER_INTERVAL_SECONDS", 15))
        interval = max(1, int(interval))

        mode = "dry-run" if dry_run else "live"
        self.stdout.write(self.style.SUCCESS(f"Alert worker started ({mode}), interval={interval}s"))

        try:
            while True:
                started = time.time()
                processed = evaluate_all_servers(send_notifications=not dry_run)
                elapsed = time.time() - started
                self.stdout.write(f"Processed {processed} servers in {elapsed:.2f}s")

                sleep_seconds = max(0.0, interval - elapsed)
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Alert worker stopped by user."))
