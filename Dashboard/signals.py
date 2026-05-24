from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse, NoReverseMatch

from .models import AccountStatus, UserAccount, Transaction

import logging
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_account(sender, instance, created, **kwargs):
    if created:
        free_status = AccountStatus.objects.filter(tier_type='free').first()
        UserAccount.objects.create(user=instance, status=free_status)


def _safe_reverse(name, *args, **kwargs):
    """Return a URL string or None — never raises."""
    try:
        return reverse(name, *args, **kwargs)
    except NoReverseMatch:
        return None


@receiver(post_save, sender=Transaction)
def send_transaction_notification(sender, instance, created, **kwargs):
    """
    Fire an in-app Notification for every new Transaction record.

    Transaction types handled:
        deposit         – wallet funded via Monnify / any deposit
        withdrawal      – funds withdrawn
        transfer_in     – wallet-to-wallet transfer received
        transfer_out    – wallet-to-wallet transfer sent
        subscription    – Pro plan purchased (negative) or credit (positive)
        boost_fee       – product boost purchased
        refund          – refund credited back
        bonus           – bonus / promotional credit
        <anything else> – generic wallet-updated alert
    """
    if not created:
        return

    # Lazy import – avoids circular dependency at module load time.
    try:
        from Notifications.models import (
            create_notification,
            NotificationCategory,
            NotificationPriority,
        )
    except ImportError:
        logger.warning("Notifications app not found – skipping transaction notification.")
        return

    user = instance.account.user
    amount = abs(instance.amount)
    fmt = f"₦{amount:,.2f}"

    # Shared action URLs
    history_url     = _safe_reverse('transaction_history')
    wallet_url      = _safe_reverse('wallet_transfer')
    subscription_url = _safe_reverse('subscription_management')

    tx_type = instance.transaction_type

    # ------------------------------------------------------------------ #
    #  Per-type notification content                                       #
    # ------------------------------------------------------------------ #

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
            f"Your withdrawal of {fmt} has been processed successfully. "
            f"Remaining balance: ₦{instance.account.balance:,.2f}."
        )
        category   = NotificationCategory.SYSTEM
        priority   = NotificationPriority.NORMAL
        action_url = history_url
        action_text = "View Transaction"

    elif tx_type == 'transfer_in':
        # Parse sender hint from description: "Transfer from @username — note"
        sender_hint = ""
        if instance.description and "from @" in instance.description:
            try:
                sender_hint = " from @" + instance.description.split("from @")[1].split()[0]
            except IndexError:
                pass

        title      = f"Transfer Received – {fmt}"
        message    = (
            f"You received a wallet transfer of {fmt}{sender_hint}. "
            f"New balance: ₦{instance.account.balance:,.2f}."
        )
        category   = NotificationCategory.SYSTEM
        priority   = NotificationPriority.NORMAL
        action_url = wallet_url
        action_text = "View Wallet"

    elif tx_type == 'transfer_out':
        # Parse recipient hint from description: "Transfer to @username — note"
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
            # New subscription purchase
            title    = "Pro Subscription Activated 🎉"
            message  = (
                f"Your Pro plan subscription ({fmt}) is now active. "
                "Enjoy unlimited listings, boost discounts, and priority support!"
            )
            priority = NotificationPriority.HIGH
        else:
            # Cancellation credit / partial refund
            title    = "Subscription Credit Applied"
            message  = (
                f"A subscription credit of {fmt} has been added to your wallet."
            )
            priority = NotificationPriority.NORMAL

        category   = NotificationCategory.SYSTEM
        action_url = subscription_url
        action_text = "Manage Subscription"

    elif tx_type == 'boost_fee':
        title      = f"Product Boost Activated – {fmt}"
        message    = (
            f"Your product boost ({fmt}) is now live. "
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
            f"Great news! A bonus of {fmt} has been added to your wallet. "
            f"New balance: ₦{instance.account.balance:,.2f}."
        )
        category   = NotificationCategory.ANNOUNCEMENT
        priority   = NotificationPriority.NORMAL
        action_url = history_url
        action_text = "View Wallet"

    else:
        # Generic fallback for any future transaction types
        title      = "Wallet Updated"
        message    = (
            f"A transaction of {fmt} "
            f"({tx_type.replace('_', ' ').title()}) has been recorded on your account."
        )
        category   = NotificationCategory.SYSTEM
        priority   = NotificationPriority.LOW
        action_url = history_url
        action_text = "View Transactions"


    try:
        create_notification(
            user=user,
            title=title,
            message=message,
            category=category,
            priority=priority,
            content_object=instance,   # links the notification to the Transaction row
            action_url=action_url,
            action_text=action_text,
        )
    except Exception as exc:
        # IMPORTANT: never let a notification failure break a financial transaction.
        logger.error(
            f"Failed to create transaction notification | "
            f"user={user.username} tx_type={tx_type} amount={amount}: {exc}",
            exc_info=True,
        )