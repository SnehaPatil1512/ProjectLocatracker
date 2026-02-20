from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from tracking.models import TrackingSession


class Command(BaseCommand):
    help = 'Clean up old tracking sessions and optimize database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete sessions older than this many days (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff_date = timezone.now() - timedelta(days=days)

        # Find old sessions
        old_sessions = TrackingSession.objects.filter(
            started_at__lt=cutoff_date,
            ended_at__isnull=False
        )

        count = old_sessions.count()

        if dry_run:
            self.stdout.write(
                f'Dry run: Would delete {count} sessions older than {days} days'
            )
        else:
            deleted, _ = old_sessions.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {deleted} old tracking sessions'
                )
            )

        # Report on database size
        total_sessions = TrackingSession.objects.count()
        self.stdout.write(f'Total sessions remaining: {total_sessions}')