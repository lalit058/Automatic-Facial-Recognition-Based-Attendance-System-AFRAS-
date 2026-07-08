# attendance/management/commands/run_scheduler.py

from django.core.management.base import BaseCommand
from attendance.scheduler import start_scheduler, stop_scheduler, sync_routines_and_sessions
import time
import signal
import sys


class Command(BaseCommand):
    help = 'Run the automatic session scheduler'

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run once and exit',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Check interval in seconds (default: 30)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔄 Starting Session Scheduler...'))
        
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('\n⏹️ Shutting down scheduler...'))
            stop_scheduler()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if options['once']:
            self.stdout.write('🔄 Running scheduled tasks once...')
            
            # Sync routines and update sessions
            result = sync_routines_and_sessions()
            
            self.stdout.write(self.style.SUCCESS(f"✅ Created: {result['created_count']} sessions"))
            self.stdout.write(self.style.SUCCESS(f"✅ Started: {result['started_count']} sessions"))
            self.stdout.write(self.style.SUCCESS(f"✅ Ended: {result['ended_count']} sessions"))
            if result.get('errors'):
                self.stdout.write(self.style.WARNING(f"⚠️ Errors: {len(result['errors'])}"))
                for error in result['errors'][:5]:
                    self.stdout.write(self.style.WARNING(f"   - {error}"))
            
            self.stdout.write(self.style.SUCCESS('✅ Done!'))
            return
        
        # Start the background scheduler
        start_scheduler(interval=options['interval'])
        
        self.stdout.write(self.style.SUCCESS(f'✅ Scheduler is running (checking every {options["interval"]}s). Press Ctrl+C to stop.'))
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            stop_scheduler()
            self.stdout.write(self.style.SUCCESS('✅ Scheduler stopped'))