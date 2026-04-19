from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from Services.models import ServiceListing
from Services.tasks import setup_service_tasks

class Command(BaseCommand):
    help = 'Setup Services app - run after migration'
    
    def handle(self, *args, **options):
        self.stdout.write('Setting up Services app...')
        
        # Check if required models exist
        try:
            from User.models import Profile
            self.stdout.write('✓ User.Profile model found')
        except ImportError:
            self.stdout.write(
                self.style.ERROR('✗ User.Profile model not found - please ensure User app is properly configured')
            )
            return
        
        # Create sample data if in development
        if settings.DEBUG:
            self.create_sample_data()
        
        # Setup background tasks
        try:
            setup_service_tasks()
            self.stdout.write('✓ Background tasks configured')
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠ Background tasks setup failed: {e}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Services app setup completed!')
        )
    
    def create_sample_data(self):
        """Create sample data for development"""
        # Create sample service categories data
        sample_services = [
            {
                'title': 'Professional Logo Design',
                'category': 'creative',
                'service_type': 'skill',
                'pricing_type': 'fixed',
                'base_price': 25000,
            },
            {
                'title': 'Website Development',
                'category': 'technology',
                'service_type': 'service',
                'pricing_type': 'project',
                'base_price': 150000,
            },
            {
                'title': 'House Cleaning Service',
                'category': 'home',
                'service_type': 'service',
                'pricing_type': 'hourly',
                'base_price': 2500,
            }
        ]
        
        # Only create if no services exist
        if not ServiceListing.objects.exists():
            try:
                # Get first user with profile or create one
                user = User.objects.filter(profile__isnull=False).first()
                if not user:
                    self.stdout.write('No users with profiles found - skipping sample data')
                    return
                
                for service_data in sample_services:
                    service_data.update({
                        'provider': user.profile,
                        'description': f'Professional {service_data["title"].lower()} service',
                        'skills_offered': 'Professional, Reliable, Fast delivery',
                        'experience_level': 'experienced',
                        'delivery_method': 'both',
                        'languages': 'English',
                    })
                    
                    ServiceListing.objects.create(**service_data)
                
                self.stdout.write(f'✓ Created {len(sample_services)} sample services')
                
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'⚠ Sample data creation failed: {e}')
                )