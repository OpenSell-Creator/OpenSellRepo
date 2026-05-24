import logging
from django.urls import reverse, NoReverseMatch

logger = logging.getLogger(__name__)


def _safe_reverse(name, *args, **kwargs):
    try:
        return reverse(name, *args, **kwargs)
    except NoReverseMatch:
        return None


def _send_push_for_user(user, title, message, url=None, icon=None):
    """
    Enqueue a push notification task for all of a user's active subscriptions.
    Separated so it can be retried independently from the DB notification creation.
    """
    from django_q.tasks import async_task
    async_task(
        'Notifications.tasks.dispatch_push_notifications',
        user.id,
        title,
        message,
        url,
        icon,
        task_name=f'push_{user.id}_{title[:30]}',
    )


# ---------------------------------------------------------------------------
# Transaction notification
# ---------------------------------------------------------------------------

def create_transaction_notification(transaction_id: int):
    """
    Create an in-app Notification for a Transaction and queue a push notification.
    Handles: deposit, withdrawal, transfer_in, transfer_out, subscription,
             boost_fee, refund, bonus, and any future types (generic fallback).
    """
    try:
        from Dashboard.models import Transaction
        from .models import (
            create_notification,
            NotificationCategory,
            NotificationPriority,
            NotificationPreference,
        )

        try:
            instance = Transaction.objects.select_related('account__user').get(
                id=transaction_id
            )
        except Transaction.DoesNotExist:
            logger.warning(f"Transaction {transaction_id} not found — skipped.")
            return

        user = instance.account.user
        preferences = NotificationPreference.get_or_create_preferences(user)

        # Respect the user's transaction notification preference
        if not preferences.transaction_notifications:
            return

        amount = abs(instance.amount)
        fmt = f"₦{amount:,.2f}"
        tx_type = instance.transaction_type

        history_url      = _safe_reverse('transaction_history')
        wallet_url       = _safe_reverse('wallet_transfer')
        subscription_url = _safe_reverse('subscription_management')

        # --- Per-type content ---
        if tx_type == 'deposit':
            title      = f"Wallet Funded – {fmt}"
            message    = (
                f"Your wallet has been credited with {fmt}. "
                f"Updated balance: ₦{instance.account.balance:,.2f}."
            )
            category   = NotificationCategory.SYSTEM
            priority   = NotificationPriority.NORMAL
            action_url = history_url
            action_text = "View Transaction"

        elif tx_type == 'withdrawal':
            title      = f"Withdrawal of {fmt} Processed"
            message    = (
                f"Your withdrawal of {fmt} has been processed. "
                f"Remaining balance: ₦{instance.account.balance:,.2f}."
            )
            category   = NotificationCategory.SYSTEM
            priority   = NotificationPriority.NORMAL
            action_url = history_url
            action_text = "View Transaction"

        elif tx_type == 'transfer_in':
            sender_hint = ""
            if instance.description and "from @" in instance.description:
                try:
                    sender_hint = " from @" + instance.description.split("from @")[1].split()[0]
                except IndexError:
                    pass
            title      = f"Transfer Received – {fmt}"
            message    = (
                f"You received {fmt}{sender_hint}. "
                f"New balance: ₦{instance.account.balance:,.2f}."
            )
            category   = NotificationCategory.SYSTEM
            priority   = NotificationPriority.NORMAL
            action_url = wallet_url
            action_text = "View Wallet"

        elif tx_type == 'transfer_out':
            recipient_hint = ""
            if instance.description and "to @" in instance.description:
                try:
                    recipient_hint = " to @" + instance.description.split("to @")[1].split()[0]
                except IndexError:
                    pass
            title      = f"Transfer Sent – {fmt}"
            message    = (
                f"You sent {fmt}{recipient_hint}. "
                f"Remaining balance: ₦{instance.account.balance:,.2f}."
            )
            category   = NotificationCategory.SYSTEM
            priority   = NotificationPriority.NORMAL
            action_url = wallet_url
            action_text = "View Wallet"

        elif tx_type == 'subscription':
            if instance.amount < 0:
                title    = "Pro Subscription Activated 🎉"
                message  = (
                    f"Your Pro plan ({fmt}) is now active. "
                    "Enjoy unlimited listings, boost discounts, and priority support!"
                )
                priority = NotificationPriority.HIGH
            else:
                title    = "Subscription Credit Applied"
                message  = f"A subscription credit of {fmt} has been added to your wallet."
                priority = NotificationPriority.NORMAL
            category   = NotificationCategory.SYSTEM
            action_url = subscription_url
            action_text = "Manage Subscription"

        elif tx_type == 'boost_fee':
            title      = f"Product Boost Activated – {fmt}"
            message    = (
                f"Your boost ({fmt}) is live. "
                "Your listing will receive increased visibility across the platform."
            )
            category   = NotificationCategory.MILESTONES
            priority   = NotificationPriority.NORMAL
            action_url = history_url
            action_text = "View Details"

        elif tx_type == 'refund':
            title      = f"Refund of {fmt} Credited"
            message    = (
                f"{fmt} has been refunded to your wallet. "
                f"Updated balance: ₦{instance.account.balance:,.2f}."
            )
            category   = NotificationCategory.SYSTEM
            priority   = NotificationPriority.NORMAL
            action_url = history_url
            action_text = "View Transaction"

        elif tx_type == 'bonus':
            title      = f"Bonus Credit – {fmt} 🎁"
            message    = (
                f"A bonus of {fmt} has been added to your wallet. "
                f"New balance: ₦{instance.account.balance:,.2f}."
            )
            category   = NotificationCategory.ANNOUNCEMENT
            priority   = NotificationPriority.NORMAL
            action_url = history_url
            action_text = "View Wallet"

        else:
            title      = "Wallet Updated"
            message    = (
                f"A transaction of {fmt} "
                f"({tx_type.replace('_', ' ').title()}) has been recorded."
            )
            category   = NotificationCategory.SYSTEM
            priority   = NotificationPriority.LOW
            action_url = history_url
            action_text = "View Transactions"

        # Create the in-app notification
        notification = create_notification(
            user=user,
            title=title,
            message=message,
            category=category,
            priority=priority,
            content_object=instance,
            action_url=action_url,
            action_text=action_text,
        )

        # Queue a push notification (if user has push enabled)
        if notification and preferences.push_notifications:
            _send_push_for_user(user, title, message, url=action_url)

    except Exception as exc:
        logger.error(
            f"create_transaction_notification({transaction_id}) failed: {exc}",
            exc_info=True,
        )
        raise  # re-raise so Django-Q can retry


# ---------------------------------------------------------------------------
# Push notification dispatcher (runs per-user, per-event)
# ---------------------------------------------------------------------------

def dispatch_push_notifications(user_id: int, title: str, body: str,
                                    url: str = None, icon: str = None):
    """
    Send a Web Push notification to every active PushSubscription for a user.
    Called by Django-Q, so it can be retried independently if it fails.
    """
    try:
        from django.contrib.auth.models import User
        from django.conf import settings
        from pywebpush import webpush, WebPushException
        from .models import PushSubscription

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return

        subscriptions = PushSubscription.objects.filter(user=user, active=True)
        if not subscriptions.exists():
            return

        vapid_claims = {
            "sub": f"mailto:{getattr(settings, 'VAPID_ADMIN_EMAIL', 'admin@example.com')}"
        }
        vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
        if not vapid_private_key:
            logger.warning("VAPID_PRIVATE_KEY not set — push skipped.")
            return

        import json
        payload = json.dumps({
            "title": title,
            "body": body,
            "url": url or "/notifications/",
            "icon": icon or "/static/icons/icon-192x192.png",
        })

        for sub in subscriptions:
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth,
                },
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims=vapid_claims,
                )
            except WebPushException as exc:
                if exc.response and exc.response.status_code in (404, 410):
                    # Subscription expired/unregistered — deactivate it
                    sub.active = False
                    sub.save(update_fields=['active'])
                    logger.info(f"Deactivated stale push subscription {sub.id}")
                else:
                    logger.error(f"WebPush failed for sub {sub.id}: {exc}")

    except Exception as exc:
        logger.error(
            f"dispatch_push_notifications(user_id={user_id}) failed: {exc}",
            exc_info=True,
        )
        raise


# ---------------------------------------------------------------------------
# Product listing notification tasks
# ---------------------------------------------------------------------------

def create_expiration_notification(listing_id: int, days_left: int):
    try:
        from Home.models import Product_Listing
        from .models import create_notification, NotificationCategory, NotificationPriority, NotificationPreference

        listing = Product_Listing.objects.select_related('seller__user').get(id=listing_id)
        prefs = NotificationPreference.get_or_create_preferences(listing.seller.user)
        if not prefs.deletion_warnings:
            return

        if days_left == 1:
            urgency = "expires today!"
            priority = NotificationPriority.URGENT
        elif days_left == 3:
            urgency = f"expires in {days_left} days"
            priority = NotificationPriority.HIGH
        else:
            urgency = f"expires in {days_left} days"
            priority = NotificationPriority.NORMAL

        notification = create_notification(
            user=listing.seller.user,
            title=f"⚠️ Listing {urgency}",
            message=f"Your listing '{listing.title}' will expire in {days_left} day{'s' if days_left > 1 else ''}. Renew it to keep it active.",
            category=NotificationCategory.ALERTS,
            priority=priority,
            content_object=listing,
        )
        if notification and prefs.push_notifications:
            _send_push_for_user(listing.seller.user, f"⚠️ Listing {urgency}", notification.message)
    except Exception as exc:
        logger.error(f"create_expiration_notification({listing_id}) failed: {exc}", exc_info=True)
        raise


def create_stock_alert_notification(listing_id: int, current_stock: int):
    try:
        from Home.models import Product_Listing
        from .models import create_notification, NotificationCategory, NotificationPriority, NotificationPreference

        listing = Product_Listing.objects.select_related('seller__user').get(id=listing_id)
        prefs = NotificationPreference.get_or_create_preferences(listing.seller.user)
        if not prefs.stock_alerts:
            return

        notification = create_notification(
            user=listing.seller.user,
            title="📦 Low Stock Alert",
            message=f"Your listing '{listing.title}' is running low on stock ({current_stock} remaining).",
            category=NotificationCategory.ALERTS,
            priority=NotificationPriority.HIGH,
            content_object=listing,
        )
        if notification and prefs.push_notifications:
            _send_push_for_user(listing.seller.user, "📦 Low Stock Alert", notification.message)
    except Exception as exc:
        logger.error(f"create_stock_alert_notification({listing_id}) failed: {exc}", exc_info=True)
        raise


def create_listing_milestone_notification(listing_id: int, count: int):
    try:
        from Home.models import Product_Listing
        from .models import create_notification, NotificationCategory, NotificationPriority, NotificationPreference

        listing = Product_Listing.objects.select_related('seller__user').get(id=listing_id)
        prefs = NotificationPreference.get_or_create_preferences(listing.seller.user)

        if count == 1:
            title = "🎉 Welcome to selling!"
            message = f"Your first listing '{listing.title}' is now live! Good luck with your sale."
        else:
            title = f"🌟 {count} Listings Milestone!"
            message = f"Congratulations! You've now created {count} listings. Keep up the great work!"

        notification = create_notification(
            user=listing.seller.user,
            title=title,
            message=message,
            category=NotificationCategory.MILESTONES if count > 1 else NotificationCategory.ANNOUNCEMENT,
            priority=NotificationPriority.NORMAL,
            content_object=listing,
        )
        if notification and prefs.push_notifications:
            _send_push_for_user(listing.seller.user, title, message)
    except Exception as exc:
        logger.error(f"create_listing_milestone_notification({listing_id}) failed: {exc}", exc_info=True)
        raise


def create_price_drop_notifications(listing_id: int, old_price: float, new_price: float):
    try:
        from Home.models import Product_Listing
        from User.models import SavedItem
        from django.contrib.contenttypes.models import ContentType
        from .models import create_notification, NotificationCategory, NotificationPriority, NotificationPreference

        listing = Product_Listing.objects.get(id=listing_id)
        product_ct = ContentType.objects.get_for_model(Product_Listing)
        saved_items = SavedItem.objects.filter(
            content_type=product_ct,
            object_id=str(listing_id),
        ).select_related('user')

        discount_pct = ((old_price - new_price) / old_price) * 100

        for saved_item in saved_items:
            prefs = NotificationPreference.get_or_create_preferences(saved_item.user)
            if not prefs.price_drop_alerts:
                continue

            title = "💰 Price Drop Alert!"
            message = (
                f"'{listing.title}' dropped by {discount_pct:.0f}%! "
                f"Now: ₦{new_price:,.0f} (was ₦{old_price:,.0f})"
            )
            notification = create_notification(
                user=saved_item.user,
                title=title,
                message=message,
                category=NotificationCategory.NEWS,
                priority=NotificationPriority.HIGH,
                content_object=listing,
            )
            if notification and prefs.push_notifications:
                _send_push_for_user(saved_item.user, title, message)
    except Exception as exc:
        logger.error(f"create_price_drop_notifications({listing_id}) failed: {exc}", exc_info=True)
        raise


# ---------------------------------------------------------------------------
# Review notification tasks
# ---------------------------------------------------------------------------

def create_review_notification(review_id: int):
    try:
        from Home.models import Review
        from .models import create_notification, NotificationCategory, NotificationPriority, NotificationPreference

        review = Review.objects.select_related(
            'product__seller__user', 'reviewer'
        ).get(id=review_id)

        if review.product:
            owner = review.product.seller.user
        elif hasattr(review, 'seller') and review.seller:
            owner = review.seller.user
        else:
            return

        prefs = NotificationPreference.get_or_create_preferences(owner)
        if not prefs.review_notifications:
            return

        stars = "⭐" * review.rating
        if review.product:
            title = "📝 New Review Received"
            message = f"{review.reviewer.username} left a {review.rating}-star review on '{review.product.title}': {stars}"
        else:
            title = "📝 New Seller Review"
            message = f"{review.reviewer.username} left you a {review.rating}-star review: {stars}"

        notification = create_notification(
            user=owner,
            title=title,
            message=message,
            category=NotificationCategory.REVIEW,
            priority=NotificationPriority.NORMAL,
            content_object=review,
        )
        if notification and prefs.push_notifications:
            _send_push_for_user(owner, title, message)
    except Exception as exc:
        logger.error(f"create_review_notification({review_id}) failed: {exc}", exc_info=True)
        raise


def create_review_reply_notification(reply_id: int):
    try:
        from Home.models import ReviewReply
        from .models import create_notification, NotificationCategory, NotificationPriority, NotificationPreference

        reply = ReviewReply.objects.select_related(
            'review__reviewer', 'review__product', 'reviewer'
        ).get(id=reply_id)

        recipient = reply.review.reviewer
        prefs = NotificationPreference.get_or_create_preferences(recipient)
        if not prefs.reply_notifications:
            return

        product_name = reply.review.product.title if reply.review.product else 'their profile'
        title = "💬 Seller replied to your review"
        message = f"{reply.reviewer.username} replied to your review on '{product_name}'"

        notification = create_notification(
            user=recipient,
            title=title,
            message=message,
            category=NotificationCategory.REVIEW,
            priority=NotificationPriority.NORMAL,
            content_object=reply,
        )
        if notification and prefs.push_notifications:
            _send_push_for_user(recipient, title, message)
    except Exception as exc:
        logger.error(f"create_review_reply_notification({reply_id}) failed: {exc}", exc_info=True)
        raise


# ---------------------------------------------------------------------------
# Save notification task
# ---------------------------------------------------------------------------

def create_save_notification(saved_item_id: int):
    try:
        from User.models import SavedItem
        from django.contrib.contenttypes.models import ContentType
        from .models import create_notification, NotificationCategory, NotificationPriority, NotificationPreference

        saved = SavedItem.objects.select_related('user').get(id=saved_item_id)
        item = saved.content_object
        if not item:
            return

        owner = None
        item_type = 'item'
        if hasattr(item, 'seller'):
            owner = item.seller.user
            item_type = 'product'
        elif hasattr(item, 'provider'):
            owner = item.provider.user
            item_type = 'service'
        elif hasattr(item, 'buyer'):
            owner = item.buyer.user
            item_type = 'request'

        if not owner or owner == saved.user:
            return

        prefs = NotificationPreference.get_or_create_preferences(owner)
        if not prefs.save_notifications:
            return

        item_title = getattr(item, 'title', str(item))
        content_type = ContentType.objects.get_for_model(item)
        total_saves = SavedItem.objects.filter(
            content_type=content_type,
            object_id=str(item.id),
        ).count()

        titles = {'product': "❤️ Product Saved", 'service': "🔖 Service Saved", 'request': "🔍 Request Saved"}
        messages = {
            'product': f"Someone saved your product '{item_title}' ({total_saves} total saves)",
            'service': f"Someone saved your service '{item_title}' ({total_saves} total saves)",
            'request': f"A seller saved your request '{item_title}' ({total_saves} total saves)",
        }

        title   = titles.get(item_type, "📌 Item Saved")
        message = messages.get(item_type, f"Someone saved your {item_type}")

        notification = create_notification(
            user=owner,
            title=title,
            message=message,
            category=NotificationCategory.SAVES,
            priority=NotificationPriority.LOW,
            content_object=item,
        )
        if notification and prefs.push_notifications:
            _send_push_for_user(owner, title, message)

        # Milestone
        if total_saves in [5, 10, 25, 50, 100]:
            milestone_msgs = {
                'product': f"Your product '{item_title}' has reached {total_saves} saves!",
                'service': f"Your service '{item_title}' has reached {total_saves} saves!",
                'request': f"Your request '{item_title}' has reached {total_saves} saves from sellers!",
            }
            m_title = f"🔥 {total_saves} Saves Milestone!"
            m_msg = milestone_msgs.get(item_type, f"Your {item_type} reached {total_saves} saves!")
            create_notification(
                user=owner,
                title=m_title,
                message=m_msg,
                category=NotificationCategory.MILESTONES,
                priority=NotificationPriority.NORMAL,
                content_object=item,
            )
    except Exception as exc:
        logger.error(f"create_save_notification({saved_item_id}) failed: {exc}", exc_info=True)
        raise


# ---------------------------------------------------------------------------
# Report notification task
# ---------------------------------------------------------------------------

def create_report_notification(report_id: int):
    try:
        from User.models import ItemReport
        from .models import create_notification, NotificationCategory, NotificationPriority

        report = ItemReport.objects.get(id=report_id)
        item = report.content_object
        if not item:
            return

        owner = None
        if hasattr(item, 'seller'):
            owner = item.seller.user
        elif hasattr(item, 'provider'):
            owner = item.provider.user
        elif hasattr(item, 'buyer'):
            owner = item.buyer.user

        if not owner:
            return

        create_notification(
            user=owner,
            title=f"⚠️ {report.item_type_display} Reported",
            message=f'Your {report.item_type} "{report.item_title}" was reported for: {report.get_reason_display()}. Our team will review it.',
            category=NotificationCategory.ALERTS,
            priority=NotificationPriority.HIGH,
            content_object=item,
        )
    except Exception as exc:
        logger.error(f"create_report_notification({report_id}) failed: {exc}", exc_info=True)
        raise


# ---------------------------------------------------------------------------
# View milestone task
# ---------------------------------------------------------------------------

def create_view_milestone_notification(product_id: int, milestone: int):
    try:
        from Home.models import Product_Listing
        from .models import (
            create_notification, Notification,
            NotificationCategory, NotificationPriority, NotificationPreference,
        )

        product = Product_Listing.objects.select_related('seller__user').get(id=product_id)
        prefs = NotificationPreference.get_or_create_preferences(product.seller.user)
        if not prefs.view_milestone_notifications:
            return

        # Idempotency check
        already_sent = Notification.objects.filter(
            recipient=product.seller.user,
            title__contains=f"{milestone} Views",
            object_id=str(product.id),
        ).exists()
        if already_sent:
            return

        title = f"👀 {milestone:,} Views Milestone!"
        message = f"Your listing '{product.title}' has reached {milestone:,} views! Great visibility."
        notification = create_notification(
            user=product.seller.user,
            title=title,
            message=message,
            category=NotificationCategory.MILESTONES,
            priority=NotificationPriority.NORMAL,
            content_object=product,
        )
        if notification and prefs.push_notifications:
            _send_push_for_user(product.seller.user, title, message)
    except Exception as exc:
        logger.error(f"create_view_milestone_notification({product_id}, {milestone}) failed: {exc}", exc_info=True)
        raise