from django.core.management.base import BaseCommand
from django.utils import timezone
from dashboard.models import Routine
import subprocess

class Command(BaseCommand):
    help = 'Checks if a scheduled session should start now'

    def handle(self, *args, **options):
        now = timezone.now()
        current_day = now.strftime('%A')
        current_time = now.time().replace(second=0, microsecond=0)

        # Look for a class starting exactly now
        session = Routine.objects.filter(day_of_week=current_day, start_time=current_time).first()

        if session:
            self.stdout.write(f"Starting scheduled session: {session.subject}")
            subprocess.Popen(['python', 'recognition/predict.py', '--subject', session.subject])