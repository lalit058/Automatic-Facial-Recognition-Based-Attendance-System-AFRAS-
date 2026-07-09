# attendance/management/commands/run_scheduler.py

from django.core.management.base import BaseCommand
from attendance.scheduler import start_scheduler, stop_scheduler, sync_routines_and_sessions, generate_sessions_from_routines
from attendance.models import AttendanceSession
from django.utils import timezone
from django.db.models import Count
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
        parser.add_argument(
            '--generate-all',
            action='store_true',
            help='Generate all missing sessions for the next year',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up duplicate sessions',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show scheduler status and exit',
        )
        parser.add_argument(
            '--stop',
            action='store_true',
            help='Stop the running scheduler',
        )

    def handle(self, *args, **options):
        # ============================================================
        # OPTION 1: Show status
        # ============================================================
        if options.get('status'):
            self.stdout.write(self.style.SUCCESS('📊 Scheduler Status'))
            self.stdout.write('-' * 40)
            
            from attendance.scheduler import get_scheduler
            scheduler = get_scheduler()
            
            self.stdout.write(f"Running: {scheduler.running}")
            self.stdout.write(f"Interval: {scheduler.interval} seconds")
            self.stdout.write(f"Status: {scheduler.status}")
            
            active = AttendanceSession.objects.filter(is_active=True).count()
            total = AttendanceSession.objects.count()
            self.stdout.write(f"\n📚 Sessions: {total} total, {active} active")
            
            # Show next session
            next_session = AttendanceSession.objects.filter(
                start_time__gt=timezone.now()
            ).order_by('start_time').first()
            
            if next_session:
                time_to = (next_session.start_time - timezone.now()).total_seconds()
                hours = int(time_to // 3600)
                mins = int((time_to % 3600) // 60)
                self.stdout.write(f"⏰ Next Session: {next_session.subject_name} at {next_session.start_time.strftime('%I:%M %p')} (in {hours}h {mins}m)")
            else:
                self.stdout.write("⏰ No upcoming sessions")
            
            return

        # ============================================================
        # OPTION 2: Stop the scheduler
        # ============================================================
        if options.get('stop'):
            self.stdout.write(self.style.WARNING('⏹️ Stopping scheduler...'))
            from attendance.scheduler import stop_scheduler
            stop_scheduler()
            self.stdout.write(self.style.SUCCESS('✅ Scheduler stopped'))
            return

        # ============================================================
        # OPTION 3: Clean up duplicates
        # ============================================================
        if options.get('cleanup'):
            self.stdout.write(self.style.WARNING('🧹 Cleaning up duplicate sessions...'))
            self.stdout.write('-' * 60)
            
            # Find duplicate sessions
            duplicates = AttendanceSession.objects.values(
                'subject_name', 'department', 'semester', 'year', 'date', 'start_time'
            ).annotate(count=Count('id')).filter(count__gt=1)
            
            if not duplicates.exists():
                self.stdout.write(self.style.SUCCESS('✅ No duplicate sessions found!'))
                return
            
            self.stdout.write(f"Found {duplicates.count()} duplicate groups")
            
            deleted_count = 0
            for dup in duplicates:
                sessions = AttendanceSession.objects.filter(
                    subject_name=dup['subject_name'],
                    department=dup['department'],
                    semester=dup['semester'],
                    year=dup['year'],
                    date=dup['date'],
                    start_time=dup['start_time']
                )
                keep = sessions.first()
                to_delete = sessions.exclude(id=keep.id)
                count = to_delete.count()
                
                # Delete logs first (cascade will handle it, but let's be explicit)
                for s in to_delete:
                    s.logs.all().delete()
                
                to_delete.delete()
                deleted_count += count
                self.stdout.write(f"   Deleted {count} duplicates for {dup['subject_name']} on {dup['date']}")
            
            self.stdout.write(self.style.SUCCESS(f'✅ Deleted {deleted_count} duplicate sessions'))
            self.stdout.write(self.style.SUCCESS(f'📊 Total sessions now: {AttendanceSession.objects.count()}'))
            return

        # ============================================================
        # OPTION 4: Generate all sessions
        # ============================================================
        if options.get('generate_all'):
            self.stdout.write(self.style.SUCCESS('🔄 Generating all missing sessions for the next year...'))
            self.stdout.write('-' * 60)
            
            result = generate_sessions_from_routines()
            
            self.stdout.write(self.style.SUCCESS(f"✅ Created: {result['created_count']} sessions"))
            self.stdout.write(self.style.SUCCESS(f"✅ Existing: {result['existing_count']} sessions"))
            if result.get('errors'):
                self.stdout.write(self.style.WARNING(f"⚠️ Errors: {len(result['errors'])}"))
                for error in result['errors'][:5]:
                    self.stdout.write(self.style.WARNING(f"   - {error}"))
            
            self.stdout.write(self.style.SUCCESS(f"📊 Total sessions in system: {AttendanceSession.objects.count()}"))
            return

        # ============================================================
        # OPTION 5: Run once
        # ============================================================
        if options.get('once'):
            self.stdout.write(self.style.SUCCESS('🔄 Running scheduled tasks once...'))
            self.stdout.write('-' * 60)
            
            result = sync_routines_and_sessions()
            
            self.stdout.write(self.style.SUCCESS(f"✅ Created: {result['created_count']} sessions"))
            self.stdout.write(self.style.SUCCESS(f"✅ Started: {result['started_count']} sessions"))
            self.stdout.write(self.style.SUCCESS(f"✅ Ended: {result['ended_count']} sessions"))
            
            if result.get('errors'):
                self.stdout.write(self.style.WARNING(f"⚠️ Errors: {len(result['errors'])}"))
                for error in result['errors'][:5]:
                    self.stdout.write(self.style.WARNING(f"   - {error}"))
            
            # Show next sessions
            next_sessions = AttendanceSession.objects.filter(
                start_time__gt=timezone.now()
            ).order_by('start_time')[:5]
            
            if next_sessions.exists():
                self.stdout.write("\n📅 Next 5 Scheduled Sessions:")
                for s in next_sessions:
                    time_to = (s.start_time - timezone.now()).total_seconds()
                    hours = int(time_to // 3600)
                    mins = int((time_to % 3600) // 60)
                    self.stdout.write(f"   #{s.id} | {s.subject_name} | {s.date} | {s.start_time.strftime('%I:%M %p')} | in {hours}h {mins}m")
            
            self.stdout.write(self.style.SUCCESS('✅ Done!'))
            return

        # ============================================================
        # OPTION 6: Start continuous scheduler
        # ============================================================
        self.stdout.write(self.style.SUCCESS('🔄 Starting Session Scheduler...'))
        
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('\n⏹️ Shutting down scheduler...'))
            stop_scheduler()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
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