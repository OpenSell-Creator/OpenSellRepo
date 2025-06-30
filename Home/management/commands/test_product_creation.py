from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Home.models import Category, Product_Listing
from decimal import Decimal

class Command(BaseCommand):
    help = 'Test product creation to debug issues'

    def handle(self, *args, **options):
        try:
            # Get a test user
            user = User.objects.first()
            if not user:
                self.stdout.write(self.style.ERROR('No users found'))
                return
                
            # Get a test category
            category = Category.objects.first()
            if not category:
                self.stdout.write(self.style.ERROR('No categories found'))
                return
            
            # Try to create a test product
            product = Product_Listing.objects.create(
                title="Test Product",
                description="Test description",
                price=Decimal('100.00'),
                category=category,
                seller=user.profile,
                condition='new'
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created test product: {product.id}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating test product: {str(e)}')
            )