
import logging
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from Home.models import Product_Listing, Review, ReviewReply
from User.models import ItemReport, SavedItem
from .models import NotificationPreference

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: safe Django-Q enqueue
# ---------------------------------------------------------------------------

def _enqueue(task_path: str, *args, task_name: str = None, **kwargs):
    """
    Enqueue a Django-Q async task.
    Falls back to direct synchronous call if Django-Q is not available
    (e.g. during tests or early setup), so nothing is ever silently lost.
    """
    try:
        from django_q.tasks import async_task
        kw = {}
        if task_name:
            kw['task_name'] = task_name
        async_task(task_path, *args, **kw)
    except Exception as exc:
        logger.warning(
            f"Django-Q unavailable — running {task_path} synchronously: {exc}"
        )
        # Resolve and call directly as a fallback
        module_path, func_name = task_path.rsplit('.', 1)
        import importlib
        mod = importlib.import_module(module_path)
        getattr(mod, func_name)(*args)


# ---------------------------------------------------------------------------
# User created → create NotificationPreference
# ---------------------------------------------------------------------------

@receiver(post_save, sender=User)
def create_user_notification_preferences(sender, instance, created, **kwargs):
    if created:
        NotificationPreference.objects.get_or_create(user=instance)


# ---------------------------------------------------------------------------
# Transaction saved → enqueue notification task
# ---------------------------------------------------------------------------

@receiver(post_save, sender='Dashboard.Transaction')
def send_transaction_notification(sender, instance, created, **kwargs):
    """Thin dispatcher — enqueues an async task immediately and returns."""
    if not created:
        return
    _enqueue(
        'Notifications.tasks.create_transaction_notification',
        instance.id,
        task_name=f'txn_notif_{instance.id}',   # idempotency — prevents duplicates
    )


# ---------------------------------------------------------------------------
# Product Listing signals
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=Product_Listing)
def handle_listing_notifications(sender, instance, **kwargs):
    """Expiration warnings + stock alerts (pre-save, needs original value)."""
    if not instance.id:
        return

    try:
        original = Product_Listing.objects.get(id=instance.id)
    except Product_Listing.DoesNotExist:
        return

    # --- Expiration warnings ---
    if hasattr(instance, 'expiration_date') and instance.expiration_date:
        expiration_date = (
            instance.expiration_date.date()
            if hasattr(instance.expiration_date, 'date')
            else instance.expiration_date
        )
        days_left = (expiration_date - timezone.now().date()).days

        if days_left in [1, 3, 7] and not getattr(instance, 'deletion_warning_sent', False):
            prefs = NotificationPreference.objects.filter(
                user=instance.seller.user,
                deletion_warnings=True
            ).first()
            if prefs:
                _enqueue(
                    'Notifications.tasks.create_expiration_notification',
                    instance.id,
                    days_left,
                    task_name=f'expire_notif_{instance.id}_{days_left}d',
                )
                instance.deletion_warning_sent = True

    # --- Stock alerts ---
    if hasattr(instance, 'stock') and hasattr(original, 'stock'):
        if instance.stock <= 5 and original.stock > 5:
            prefs = NotificationPreference.objects.filter(
                user=instance.seller.user,
                stock_alerts=True
            ).first()
            if prefs:
                _enqueue(
                    'Notifications.tasks.create_stock_alert_notification',
                    instance.id,
                    instance.stock,
                    task_name=f'stock_notif_{instance.id}',
                )


@receiver(post_save, sender=Product_Listing)
def handle_new_listing_notifications(sender, instance, created, **kwargs):
    """First-listing welcome + milestone notifications."""
    if not created:
        return

    seller_listings_count = Product_Listing.objects.filter(
        seller=instance.seller
    ).count()

    if seller_listings_count == 1 or seller_listings_count in [5, 10, 25, 50, 100]:
        _enqueue(
            'Notifications.tasks.create_listing_milestone_notification',
            instance.id,
            seller_listings_count,
            task_name=f'listing_milestone_{instance.seller.id}_{seller_listings_count}',
        )


@receiver(pre_save, sender=Product_Listing)
def handle_price_change_notifications(sender, instance, **kwargs):
    """Notify users who saved a product when its price drops."""
    if not instance.id:
        return

    try:
        original = Product_Listing.objects.get(id=instance.id)
    except Product_Listing.DoesNotExist:
        return

    if (
        hasattr(instance, 'price')
        and hasattr(original, 'price')
        and instance.price < original.price
    ):
        _enqueue(
            'Notifications.tasks.create_price_drop_notifications',
            instance.id,
            float(original.price),
            float(instance.price),
            task_name=f'price_drop_{instance.id}',
        )


# ---------------------------------------------------------------------------
# Review signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Review)
def handle_review_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    _enqueue(
        'Notifications.tasks.create_review_notification',
        instance.id,
        task_name=f'review_notif_{instance.id}',
    )


@receiver(post_save, sender=ReviewReply)
def handle_review_reply_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    _enqueue(
        'Notifications.tasks.create_review_reply_notification',
        instance.id,
        task_name=f'reply_notif_{instance.id}',
    )


# ---------------------------------------------------------------------------
# SavedItem signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender=SavedItem)
def handle_product_save_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    _enqueue(
        'Notifications.tasks.create_save_notification',
        instance.id,
        task_name=f'save_notif_{instance.id}',
    )


# ---------------------------------------------------------------------------
# ItemReport signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender=ItemReport)
def handle_item_report_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    _enqueue(
        'Notifications.tasks.create_report_notification',
        instance.id,
        task_name=f'report_notif_{instance.id}',
    )


# ---------------------------------------------------------------------------
# View milestone helper (called from product detail view)
# ---------------------------------------------------------------------------

def check_view_milestones(product, current_views):
    """Call from your product detail view when incrementing view count."""
    milestones = [100, 500, 1000, 5000, 10000]
    for milestone in milestones:
        if current_views >= milestone:
            _enqueue(
                'Notifications.tasks.create_view_milestone_notification',
                product.id,
                milestone,
                task_name=f'view_milestone_{product.id}_{milestone}',
            )


# ---------------------------------------------------------------------------
# Cleanup helper (run periodically via Django-Q scheduled task)
# ---------------------------------------------------------------------------

def cleanup_old_notifications():
    from .models import Notification
    cutoff_date = timezone.now() - timedelta(days=30)
    qs = Notification.objects.filter(created_at__lt=cutoff_date)
    count = qs.count()
    qs.delete()
    return count