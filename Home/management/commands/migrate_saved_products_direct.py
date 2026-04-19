from django.db import connection, transaction
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from datetime import datetime


def check_old_table():
    """Check if old SavedProduct table exists and has data"""
    table_names = [
        'Home_savedproduct',
        'home_savedproduct', 
        'savedproduct',
        'Home_SavedProduct'
    ]
    
    with connection.cursor() as cursor:
        for table_name in table_names:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"✅ Found table '{table_name}' with {count} records")
                return table_name, count
            except Exception:
                continue
    
    print("❌ No old SavedProduct table found")
    print("✅ This means you either:")
    print("   1. Already migrated the data")
    print("   2. Never had SavedProduct in your database")
    print("   3. The table has a different name")
    return None, 0


def check_new_table():
    """Check SavedItem table"""
    try:
        with connection.cursor() as cursor:
            # Get Product_Listing ContentType ID
            from Home.models import Product_Listing
            product_ct = ContentType.objects.get_for_model(Product_Listing)
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM User_saveditem 
                WHERE content_type_id = %s
            """, [product_ct.id])
            
            count = cursor.fetchone()[0]
            print(f"📊 Current SavedItem (products) count: {count}")
            return count
    except Exception as e:
        print(f"❌ Error checking SavedItem: {e}")
        return 0


def migrate_direct():
    """Direct migration using raw SQL"""
    print("\n" + "="*60)
    print("🔧 DIRECT MIGRATION: SavedProduct → SavedItem")
    print("="*60 + "\n")
    
    # Check old table
    old_table, old_count = check_old_table()
    
    if not old_table or old_count == 0:
        print("\n✅ No migration needed!")
        return
    
    # Check new table
    new_count = check_new_table()
    
    # Confirm
    print(f"\n⚠️  About to migrate {old_count} records from '{old_table}'")
    response = input("Continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("❌ Migration cancelled")
        return
    
    # Get ContentType ID
    try:
        from Home.models import Product_Listing
        product_ct = ContentType.objects.get_for_model(Product_Listing)
        ct_id = product_ct.id
        print(f"📝 Using ContentType ID: {ct_id} for Product_Listing")
    except Exception as e:
        print(f"❌ Error getting ContentType: {e}")
        return
    
    # Migrate
    migrated = 0
    skipped = 0
    errors = 0
    
    with connection.cursor() as cursor:
        # Get all old records
        cursor.execute(f"""
            SELECT id, user_id, product_id, saved_at 
            FROM {old_table}
            ORDER BY saved_at DESC
        """)
        
        rows = cursor.fetchall()
        total = len(rows)
        
        print(f"\n🚀 Starting migration of {total} records...\n")
        
        for idx, (old_id, user_id, product_id, saved_at) in enumerate(rows, 1):
            try:
                # Check if already exists
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM User_saveditem 
                    WHERE user_id = %s 
                    AND content_type_id = %s 
                    AND object_id = %s
                """, [user_id, ct_id, str(product_id)])
                
                if cursor.fetchone()[0] > 0:
                    print(f"⚠️  [{idx}/{total}] Skip: user={user_id}, product={product_id} (exists)")
                    skipped += 1
                    continue
                
                # Insert into SavedItem
                cursor.execute("""
                    INSERT INTO User_saveditem (user_id, content_type_id, object_id, saved_at)
                    VALUES (%s, %s, %s, %s)
                """, [user_id, ct_id, str(product_id), saved_at])
                
                print(f"✅ [{idx}/{total}] Migrated: user={user_id}, product={product_id}")
                migrated += 1
                
            except Exception as e:
                print(f"❌ [{idx}/{total}] Error: {e}")
                errors += 1
        
        # Commit transaction
        connection.commit()
    
    # Summary
    print("\n" + "="*60)
    print(f"✅ Migrated: {migrated}")
    print(f"⚠️  Skipped: {skipped}")
    print(f"❌ Errors: {errors}")
    print("="*60)
    
    if errors == 0 and migrated > 0:
        print("\n✅ Migration completed successfully!")
        print("\n⚠️  To verify, run:")
        print("    python manage.py shell")
        print("    >>> exec(open('migrate_saved_products_direct.py').read())")
        print("    >>> check_new_table()")
        
        print("\n⚠️  To delete old table (CAREFUL!):")
        print(f"    python manage.py dbshell")
        print(f"    DROP TABLE {old_table};")


def show_sample_old_data():
    """Show sample of old data"""
    old_table, _ = check_old_table()
    
    if not old_table:
        return
    
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT id, user_id, product_id, saved_at 
            FROM {old_table} 
            LIMIT 10
        """)
        
        rows = cursor.fetchall()
        
        print("\n📋 Sample Old Data:")
        print("-" * 80)
        print(f"{'ID':<10} {'User ID':<15} {'Product ID':<40} {'Saved At'}")
        print("-" * 80)
        
        for row in rows:
            print(f"{row[0]:<10} {row[1]:<15} {str(row[2]):<40} {row[3]}")


def verify_migration():
    """Verify migration by comparing counts"""
    print("\n" + "="*60)
    print("🔍 VERIFICATION")
    print("="*60 + "\n")
    
    old_table, old_count = check_old_table()
    new_count = check_new_table()
    
    if old_count > 0 and new_count >= old_count:
        print(f"\n✅ SUCCESS: All {old_count} records appear to be migrated!")
    elif old_count > new_count:
        print(f"\n⚠️  WARNING: Old table has {old_count} records but new table has {new_count}")
        print("   Some records may not have been migrated. Check for errors.")
    else:
        print("\n✅ Migration verification complete")


# Main execution
if __name__ == '__main__':
    print("\n" + "="*60)
    print("📊 SAVED PRODUCTS MIGRATION TOOL")
    print("="*60)
    print("\nOptions:")
    print("1. Check status")
    print("2. Show sample old data")
    print("3. Run migration")
    print("4. Verify migration")
    print("\nOr run functions directly:")
    print("  check_old_table()")
    print("  check_new_table()")
    print("  show_sample_old_data()")
    print("  migrate_direct()")
    print("  verify_migration()")
    print("="*60 + "\n")
    
    # Auto-check
    check_old_table()
    check_new_table()
    