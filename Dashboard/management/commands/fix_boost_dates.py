from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from Dashboard.models import ProductBoost

class Command(BaseCommand):
    help = 'Fix ProductBoost records with None dates'

    def handle(self, *args, **options):
        # Fix boosts with None start_date
        boosts_with_none_start = ProductBoost.objects.filter(start_date__isnull=True)
        for boost in boosts_with_none_start:
            boost.start_date = timezone.now()
            if not boost.end_date:
                boost.end_date = boost.start_date + timedelta(days=boost.duration_days)
            boost.save()
            
        # Fix boosts with None end_date but valid start_date
        boosts_with_none_end = ProductBoost.objects.filter(
            start_date__isnull=False, 
            end_date__isnull=True
        )
        for boost in boosts_with_none_end:
            boost.end_date = boost.start_date + timedelta(days=boost.duration_days)
            boost.save()
            
        self.stdout.write(
            self.style.SUCCESS(
                f'Fixed {boosts_with_none_start.count() + boosts_with_none_end.count()} boost records'
            )
        )