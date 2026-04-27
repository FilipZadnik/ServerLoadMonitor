from django.core.management.base import BaseCommand

from api.alerts import evaluate_all_servers


class Command(BaseCommand):
    help = "Evaluate server alert thresholds and send Android push notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Evaluate and update alert states, but do not send push notifications.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        processed = evaluate_all_servers(send_notifications=not dry_run)
        mode = "dry-run" if dry_run else "live"
        self.stdout.write(self.style.SUCCESS(f"Processed {processed} servers ({mode})."))
