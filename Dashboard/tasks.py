from django_q.tasks import async_task, result
from django_q.models import Schedule
from django.db import transaction as db_transaction
from django.utils import timezone
from django.db.models import F
from django.core.mail import send_mail
from .models import AffiliateCommission
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from .models import AffiliateProfile
import logging

logger = logging.getLogger(__name__)


def deactivate_expired_boosts():
    """Deactivate expired product boosts - runs every hour"""
    from .models import ProductBoost
    
    try:
        expired_boosts = ProductBoost.objects.filter(
            is_active=True,
            end_date__lte=timezone.now()
        )
        
        count = 0
        for boost in expired_boosts:
            boost.is_active = False
            boost.save()
            
            # Update product boost score
            product = boost.product
            product.boost_score = product.calculate_boost_score()
            product.save(update_fields=['boost_score'])
            
            # Send notification to seller
            async_task(
                'Dashboard.tasks.send_boost_expired_notification',
                boost.user_account.user.id,
                boost.product.title,
                boost.get_boost_type_display(),
                task_name=f'boost_expired_notification_{boost.id}'
            )
            
            count += 1
            
        logger.info(f"Deactivated {count} expired boosts")
        return f"Deactivated {count} expired boosts"
        
    except Exception as e:
        logger.error(f"Error deactivating expired boosts: {str(e)}")
        raise

def check_subscription_renewals():
    """Check and handle expired subscriptions - runs daily"""
    from .models import UserAccount, AccountStatus
    
    try:
        accounts = UserAccount.objects.filter(
            status__tier_type='pro'
        ).select_related('user', 'status')
        
        expired_count = 0
        warning_count = 0
        
        for account in accounts:
            sub_info = account.subscription_info
            
            if not sub_info:
                continue
                
            days_remaining = (sub_info['end_date'] - timezone.now()).days
            
            # Handle expired subscriptions
            if not sub_info['active']:
                # Downgrade to free
                free_status = AccountStatus.objects.filter(tier_type='free').first()
                if free_status:
                    account.status = free_status
                    account.save()
                    
                    # Update all products' boost scores
                    from Home.models import Product_Listing
                    products = Product_Listing.objects.filter(
                        seller=account.user.profile
                    )
                    for product in products:
                        product.boost_score = product.calculate_boost_score()
                        product.save(update_fields=['boost_score'])
                    
                    # Send expiry email
                    async_task(
                        'Dashboard.tasks.send_subscription_expired_email',
                        account.user.id,
                        task_name=f'subscription_expired_{account.user.id}'
                    )
                    
                    expired_count += 1
                    
            # Send warning emails
            elif days_remaining in [7, 3, 1]:
                async_task(
                    'Dashboard.tasks.send_subscription_expiry_warnings',
                    account.user.id,
                    days_remaining,
                    task_name=f'subscription_warning_{account.user.id}_{days_remaining}d'
                )
                warning_count += 1
        
        logger.info(f"Processed {expired_count} expired subscriptions, sent {warning_count} warnings")
        return f"Processed {expired_count} expired, {warning_count} warnings"
        
    except Exception as e:
        logger.error(f"Error checking subscription expiry: {str(e)}")
        raise

def send_subscription_expired_email(user_id):
    """Send subscription expired notification"""
    from django.contrib.auth.models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        context = {
            'user': user,
            'site_name': settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'OpenSell',
            'renewal_url': f"{settings.SITE_DOMAIN}/dashboard/subscription/" if hasattr(settings, 'SITE_DOMAIN') else '#',
        }
        
        html_message = render_to_string('emails/subscription_expired.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject='Your Pro Subscription Has Expired',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Sent subscription expired email to {user.email}")
        return f"Email sent to {user.email}"
        
    except Exception as e:
        logger.error(f"Error sending subscription expired email: {str(e)}")
        raise

def send_subscription_expiry_warnings(user_id, days_remaining):
    """Send subscription expiry warning"""
    from django.contrib.auth.models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        context = {
            'user': user,
            'days_remaining': days_remaining,
            'site_name': settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'OpenSell',
            'renewal_url': f"{settings.SITE_DOMAIN}/dashboard/subscription/" if hasattr(settings, 'SITE_DOMAIN') else '#',
        }
        
        html_message = render_to_string('emails/subscription_expiring.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Your Pro Subscription Expires in {days_remaining} Days',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Sent subscription warning email to {user.email}")
        return f"Warning email sent to {user.email}"
        
    except Exception as e:
        logger.error(f"Error sending subscription warning email: {str(e)}")
        raise

def send_boost_expired_notification(user_id, product_title, boost_type):
    """Notify user when their boost expires"""
    from django.contrib.auth.models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        context = {
            'user': user,
            'product_title': product_title,
            'boost_type': boost_type,
            'site_name': settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'OpenSell',
            'boost_url': f"{settings.SITE_DOMAIN}/dashboard/" if hasattr(settings, 'SITE_DOMAIN') else '#',
        }
        
        html_message = render_to_string('emails/boost_expired.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Your {boost_type} Boost Has Expired',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Boost expiry notification sent to {user.email}"
        
    except Exception as e:
        logger.error(f"Error sending boost expiry notification: {str(e)}")
        # Don't raise, just log - this is not critical
        
def release_pending_commissions():
    """
    Release commissions that have passed their 7-day holding period
    Runs every hour
    """
    try:
        from Dashboard.models import AffiliateCommission, AffiliateProfile
        from django.db import transaction as db_transaction
        from django.utils import timezone
        import logging
        
        logger = logging.getLogger(__name__)
        now = timezone.now()
        
        # Find commissions ready to be released
        ready_commissions = AffiliateCommission.objects.filter(
            status='pending',
            available_at__lte=now
        ).select_related('affiliate')
        
        count = ready_commissions.count()
        
        if count == 0:
            logger.info("No commissions ready for release")
            return "No commissions to release"
        
        logger.info(f"Found {count} commissions ready for release")
        
        released_count = 0
        total_amount = 0
        errors = []
        
        for commission in ready_commissions:
            try:
                with db_transaction.atomic():
                    # Lock affiliate record to prevent race conditions
                    affiliate = AffiliateProfile.objects.select_for_update().get(
                        id=commission.affiliate.id
                    )
                    
                    # Verify pending balance has enough funds
                    if affiliate.pending_balance < commission.commission_amount:
                        error_msg = (
                            f"⚠️ Insufficient pending balance for commission {commission.id}: "
                            f"Need ₦{commission.commission_amount:.2f}, "
                            f"Have ₦{affiliate.pending_balance:.2f}"
                        )
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue
                    
                    # Transfer from pending to available
                    affiliate.pending_balance -= commission.commission_amount
                    affiliate.available_balance += commission.commission_amount
                    affiliate.save(update_fields=['pending_balance', 'available_balance', 'updated_at'])
                    
                    # Update commission status
                    commission.status = 'available'
                    commission.save(update_fields=['status'])
                    
                    released_count += 1
                    total_amount += commission.commission_amount
                    
                    logger.info(
                        f"✓ Commission released: ₦{commission.commission_amount:.2f} | "
                        f"Affiliate: {affiliate.referral_code} | "
                        f"New available balance: ₦{affiliate.available_balance:.2f}"
                    )
                    
            except AffiliateProfile.DoesNotExist:
                error_msg = f"⚠️ Affiliate not found for commission {commission.id}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
                
            except Exception as e:
                error_msg = f"⚠️ Error releasing commission {commission.id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
                continue
        
        # Summary
        result_msg = (
            f"✓ Released {released_count}/{count} commissions | "
            f"Total: ₦{total_amount:.2f}"
        )
        
        if errors:
            result_msg += f" | Errors: {len(errors)}"
            for error in errors[:3]:  # Log first 3 errors
                logger.error(error)
        
        logger.info(result_msg)
        return result_msg
        
    except Exception as e:
        error_msg = f"❌ Critical error in release_pending_commissions: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg

def cleanup_old_tasks():
    """Clean up old Django-Q task records - runs weekly"""
    from django_q.models import Task, OrmQ
    from datetime import timedelta
    
    try:
        # Delete tasks older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_tasks = Task.objects.filter(started__lt=cutoff_date)
        count = old_tasks.count()
        old_tasks.delete()
        
        # Clean up orphaned queue items
        OrmQ.objects.all().delete()
        
        logger.info(f"Cleaned up {count} old tasks")
        return f"Cleaned up {count} old tasks"
        
    except Exception as e:
        logger.error(f"Error cleaning up old tasks: {str(e)}")
        raise