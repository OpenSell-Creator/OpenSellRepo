from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
import uuid


class Command(BaseCommand):
    help = 'Migrate old SavedProduct data to unified SavedItem system (Raw SQL)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )
        parser.add_argument(
            '--table-name',
            type=str,
            default='Home_savedproduct',
            help='Name of old saved products table (default: Home_savedproduct)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        old_table = options['table_name']

        self.stdout.write(self.style.WARNING('='*60))
        self.stdout.write(self.style.WARNING('🔧 RAW SQL MIGRATION: SavedProduct → SavedItem'))
        self.stdout.write(self.style.WARNING('='*60))
        
        # Check if old table exists
        if not self.table_exists(old_table):
            self.stdout.write(self.style.ERROR(f'❌ Table "{old_table}" does not exist!'))
            self.stdout.write(self.style.SUCCESS('✅ No migration needed - you may have already migrated or never had the old model.'))
            return

        # Get counts
        old_count = self.get_old_count(old_table)
        
        if old_count == 0:
            self.stdout.write(self.style.SUCCESS(f'✅ Table "{old_table}" exists but is empty - no data to migrate.'))
            return

        self.stdout.write(f'📊 Found {old_count} records in "{old_table}"')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - Showing sample data only'))
            self.show_sample_data(old_table)
            return

        # Get Product_Listing ContentType
        try:
            from Home.models import Product_Listing
            product_ct = ContentType.objects.get_for_model(Product_Listing)
            ct_id = product_ct.id
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Could not get ContentType for Product_Listing: {e}'))
            return

        self.stdout.write(f'📝 Product_Listing ContentType ID: {ct_id}')
        
        # Perform migration
        migrated, skipped, errors = self.migrate_data(old_table, ct_id)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS(f'✅ Migrated: {migrated}'))
        self.stdout.write(self.style.WARNING(f'⚠️  Skipped (already exists): {skipped}'))
        self.stdout.write(self.style.ERROR(f'❌ Errors: {errors}'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        if errors == 0 and migrated > 0:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Migration completed successfully!'))
            self.stdout.write(self.style.WARNING(f'\n⚠️  To delete old table, run:'))
            self.stdout.write(f'    python manage.py dbshell')
            self.stdout.write(f'    DROP TABLE {old_table};')

    def table_exists(self, table_name):
        """Check if table exists in database"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables 
                WHERE table_name = %s
            """, [table_name])
            return cursor.fetchone()[0] > 0

    def get_old_count(self, table_name):
        """Get count of records in old table"""
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0]

    def show_sample_data(self, table_name):
        """Show sample of old data"""
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT id, user_id, product_id, saved_at 
                FROM {table_name} 
                LIMIT 10
            """)
            
            rows = cursor.fetchall()
            
            self.stdout.write('\n📋 Sample Data:')
            self.stdout.write('-' * 80)
            self.stdout.write(f'{"ID":<10} {"User ID":<15} {"Product ID":<40} {"Saved At"}')
            self.stdout.write('-' * 80)
            
            for row in rows:
                self.stdout.write(f'{row[0]:<10} {row[1]:<15} {str(row[2]):<40} {row[3]}')
            
            if len(rows) < self.get_old_count(table_name):
                self.stdout.write(f'\n... and {self.get_old_count(table_name) - len(rows)} more records')

    def migrate_data(self, old_table, content_type_id):
        """Migrate data using raw SQL"""
        migrated = 0
        skipped = 0
        errors = 0

        with connection.cursor() as cursor:
            # Get all old saved products
            cursor.execute(f"""
                SELECT id, user_id, product_id, saved_at 
                FROM {old_table}
                ORDER BY saved_at DESC
            """)
            
            rows = cursor.fetchall()
            
            for row in rows:
                old_id, user_id, product_id, saved_at = row
                
                try:
                    # Check if already exists in SavedItem
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM User_saveditem 
                        WHERE user_id = %s 
                        AND content_type_id = %s 
                        AND object_id = %s
                    """, [user_id, content_type_id, str(product_id)])
                    
                    exists = cursor.fetchone()[0] > 0
                    
                    if exists:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠️  Skipped: user_id={user_id}, product_id={product_id} (already exists)'
                            )
                        )
                        skipped += 1
                        continue
                    
                    # Insert into SavedItem
                    cursor.execute("""
                        INSERT INTO User_saveditem (user_id, content_type_id, object_id, saved_at)
                        VALUES (%s, %s, %s, %s)
                    """, [user_id, content_type_id, str(product_id), saved_at])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Migrated: user_id={user_id}, product_id={product_id}'
                        )
                    )
                    migrated += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'❌ Error migrating record {old_id}: {e}'
                        )
                    )
                    errors += 1
        
        return migrated, skipped, errors