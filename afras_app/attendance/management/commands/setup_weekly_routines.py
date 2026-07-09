# attendance/management/commands/setup_weekly_routines.py
from django.core.management.base import BaseCommand
from attendance.models import AttendanceSession
from attendance.utils import auto_schedule_session

class Command(BaseCommand):
    help = 'Setup weekly routines for existing sessions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        self.stdout.write("="*60)
        self.stdout.write("🔄 SETTING UP WEEKLY ROUTINES FOR EXISTING SESSIONS")
        self.stdout.write("="*60)
        
        # Find sessions without routines
        manual_sessions = AttendanceSession.objects.filter(routine__isnull=True)
        
        self.stdout.write(f"\n📋 Found {manual_sessions.count()} sessions without routines")
        
        if dry_run:
            self.stdout.write("\n📋 DRY RUN - Sessions to process:")
            for s in manual_sessions[:10]:
                self.stdout.write(f"   #{s.id} | {s.subject_name} | {s.date} ({s.date.strftime('%A')})")
            return
        
        # Process each session
        for session in manual_sessions:
            self.stdout.write(f"\n🔄 Processing session #{session.id}: {session.subject_name}")
            result = auto_schedule_session(session)
            
            self.stdout.write(f"   Routines created: {result['routines_created']}")
            self.stdout.write(f"   Sessions created: {result['sessions_created']}")
            
            for r in result.get('routines', []):
                status = "✅" if r['status'] == 'created' else "📌"
                self.stdout.write(f"   {status} {r['day']}: Routine #{r['id']}")
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("✅ Setup complete!"))