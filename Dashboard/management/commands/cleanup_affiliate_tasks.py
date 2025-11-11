# Dashboard/management/commands/cleanup_affiliate_tasks.py
"""
Remove old affiliate-related scheduled tasks that are no longer needed
Run with: python manage.py cleanup_affiliate_tasks
"""

from django.core.management.base import BaseCommand
from django_q.models import Schedule
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Remove obsolete scheduled tasks (release_pending_commissions)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('='*70))
        self.stdout.write(self.style.WARNING('CLEANING UP OBSOLETE TASKS'))
        self.stdout.write(self.style.WARNING('='*70))
        
        # Tasks to remove
        obsolete_tasks = [
            'Dashboard.tasks.release_pending_commissions',
            'release_pending_commissions',
        ]
        
        total_deleted = 0
        
        for task_name in obsolete_tasks:
            try:
                schedules = Schedule.objects.filter(func=task_name)
                count = schedules.count()
                
                if count > 0:
                    self.stdout.write(f'\nFound {count} schedule(s) for: {task_name}')
                    schedules.delete()
                    total_deleted += count
                    self.stdout.write(self.style.SUCCESS(f'✓ Deleted {count} schedule(s)'))
                else:
                    self.stdout.write(f'\nNo schedules found for: {task_name}')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing {task_name}: {str(e)}')
                )
        
        if total_deleted > 0:
            self.stdout.write('\n' + '='*70)
            self.stdout.write(
                self.style.SUCCESS(f'✓ CLEANUP COMPLETE: Deleted {total_deleted} task(s)')
            )
            self.stdout.write('='*70)
            logger.info(f'Cleaned up {total_deleted} obsolete scheduled tasks')
        else:
            self.stdout.write('\n' + self.style.SUCCESS('✓ No obsolete tasks found'))