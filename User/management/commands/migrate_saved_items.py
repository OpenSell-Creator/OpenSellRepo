# User/management/commands/migrate_saved_items.py
"""
Migration script to move SavedProduct, SavedService, SavedRequest 
data into unified SavedItem model.

Usage:
    python manage.py migrate_saved_items
"""

from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from User.models import SavedItem
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate existing saved products/services/requests to unified SavedItem model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made'))
        
        stats = {
            'products_migrated': 0,
            'products_skipped': 0,
            'services_migrated': 0,
            'services_skipped': 0,
            'requests_migrated': 0,
            'requests_skipped': 0,
            'errors': 0,
        }

        # Migrate SavedProduct
        self.stdout.write('\n📦 Migrating saved products...')
        try:
            from Home.models import SavedProduct, Product_Listing
            
            product_ct = ContentType.objects.get_for_model(Product_Listing)
            saved_products = SavedProduct.objects.select_related('user', 'product').all()
            
            self.stdout.write(f'Found {saved_products.count()} saved products')
            
            for saved_product in saved_products:
                try:
                    # Check if already exists
                    exists = SavedItem.objects.filter(
                        user=saved_product.user,
                        content_type=product_ct,
                        object_id=str(saved_product.product.id)
                    ).exists()
                    
                    if exists:
                        stats['products_skipped'] += 1
                        self.stdout.write(f'  ⏭️  Skipped (already exists): {saved_product.product.title}')
                        continue
                    
                    if not dry_run:
                        SavedItem.objects.create(
                            user=saved_product.user,
                            content_type=product_ct,
                            object_id=str(saved_product.product.id),
                            saved_at=saved_product.saved_at
                        )
                    
                    stats['products_migrated'] += 1
                    self.stdout.write(f'  ✅ Migrated: {saved_product.product.title}')
                    
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error migrating saved product {saved_product.id}: {str(e)}")
                    self.stdout.write(self.style.ERROR(f'  ❌ Error: {str(e)}'))
                    
        except ImportError:
            self.stdout.write(self.style.WARNING('  ⚠️  SavedProduct model not found - skipping'))

        # Migrate SavedService
        self.stdout.write('\n🛠️  Migrating saved services...')
        try:
            from Services.models import SavedService, ServiceListing
            
            service_ct = ContentType.objects.get_for_model(ServiceListing)
            saved_services = SavedService.objects.select_related('user', 'service').all()
            
            self.stdout.write(f'Found {saved_services.count()} saved services')
            
            for saved_service in saved_services:
                try:
                    exists = SavedItem.objects.filter(
                        user=saved_service.user,
                        content_type=service_ct,
                        object_id=str(saved_service.service.id)
                    ).exists()
                    
                    if exists:
                        stats['services_skipped'] += 1
                        self.stdout.write(f'  ⏭️  Skipped: {saved_service.service.title}')
                        continue
                    
                    if not dry_run:
                        SavedItem.objects.create(
                            user=saved_service.user,
                            content_type=service_ct,
                            object_id=str(saved_service.service.id),
                            saved_at=saved_service.saved_at
                        )
                    
                    stats['services_migrated'] += 1
                    self.stdout.write(f'  ✅ Migrated: {saved_service.service.title}')
                    
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error migrating saved service: {str(e)}")
                    self.stdout.write(self.style.ERROR(f'  ❌ Error: {str(e)}'))
                    
        except ImportError:
            self.stdout.write(self.style.WARNING('  ⚠️  SavedService model not found - skipping'))

        # Migrate SavedRequest
        self.stdout.write('\n🔍 Migrating saved requests...')
        try:
            from BuyerRequest.models import SavedRequest, BuyerRequest
            
            request_ct = ContentType.objects.get_for_model(BuyerRequest)
            saved_requests = SavedRequest.objects.select_related('user', 'request').all()
            
            self.stdout.write(f'Found {saved_requests.count()} saved requests')
            
            for saved_request in saved_requests:
                try:
                    exists = SavedItem.objects.filter(
                        user=saved_request.user,
                        content_type=request_ct,
                        object_id=str(saved_request.request.id)
                    ).exists()
                    
                    if exists:
                        stats['requests_skipped'] += 1
                        self.stdout.write(f'  ⏭️  Skipped: {saved_request.request.title}')
                        continue
                    
                    if not dry_run:
                        SavedItem.objects.create(
                            user=saved_request.user,
                            content_type=request_ct,
                            object_id=str(saved_request.request.id),
                            saved_at=saved_request.saved_at
                        )
                    
                    stats['requests_migrated'] += 1
                    self.stdout.write(f'  ✅ Migrated: {saved_request.request.title}')
                    
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error migrating saved request: {str(e)}")
                    self.stdout.write(self.style.ERROR(f'  ❌ Error: {str(e)}'))
                    
        except ImportError:
            self.stdout.write(self.style.WARNING('  ⚠️  SavedRequest model not found - skipping'))

        # Print summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('\n📊 MIGRATION SUMMARY:'))
        self.stdout.write(f'  Products: {stats["products_migrated"]} migrated, {stats["products_skipped"]} skipped')
        self.stdout.write(f'  Services: {stats["services_migrated"]} migrated, {stats["services_skipped"]} skipped')
        self.stdout.write(f'  Requests: {stats["requests_migrated"]} migrated, {stats["requests_skipped"]} skipped')
        self.stdout.write(f'  Errors: {stats["errors"]}')
        
        total_migrated = stats['products_migrated'] + stats['services_migrated'] + stats['requests_migrated']
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n⚠️  DRY RUN: Would migrate {total_migrated} items'))
            self.stdout.write(self.style.WARNING('Run without --dry-run to perform actual migration'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully migrated {total_migrated} items!'))
            
            if stats['errors'] > 0:
                self.stdout.write(self.style.WARNING(f'\n⚠️  {stats["errors"]} errors occurred - check logs'))