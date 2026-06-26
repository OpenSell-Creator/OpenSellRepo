from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
from django.db.models.signals import post_save
from django.db import transaction as db_transaction
from datetime import timedelta
from django.dispatch import receiver
import logging
import uuid

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# ACCOUNT STATUS & PRODUCT BOOST
# ─────────────────────────────────────────────────────────────

class AccountStatus(models.Model):
    """Defines available account tiers with explicit choices"""
    TIER_CHOICES = [
        ('free', 'Free User'),
        ('pro', 'Pro User'),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    tier_type = models.CharField(max_length=15, choices=TIER_CHOICES, default='free')
    description = models.TextField(blank=True)
    benefits = models.TextField(blank=True)
    
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    two_month_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    max_listings = models.PositiveIntegerField(default=5)
    listing_discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    boost_discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    featured_listings = models.PositiveIntegerField(default=0)
    priority_support = models.BooleanField(default=False)
    analytics_access = models.BooleanField(default=False)
    
    # Keep legacy min_balance for backward compatibility
    min_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return f"{self.name} ({self.get_tier_type_display()})"
    
    @property
    def is_subscription_based(self):
        return self.tier_type in ['pro', 'enterprise']
    
    class Meta:
        verbose_name_plural = "Account Statuses"


class UserAccount(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('listing_fee', 'Listing Fee'),
        ('boost_fee', 'Boost Fee'),
        ('subscription', 'Subscription'),
        ('refund', 'Refund'),
        ('bonus', 'Bonus'),
        ('transfer_in', 'Transfer Received'),
        ('transfer_out', 'Transfer Sent'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='account')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.ForeignKey(AccountStatus, on_delete=models.SET_NULL, null=True, related_name='accounts')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_deposit_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s Account ({self.current_tier_display})"
    
    # ── Tier / subscription helpers ───────────────────────────

    @property
    def current_tier_display(self):
        if self.is_subscription_active:
            return self.status.get_tier_type_display() if self.status else 'Free'
        return 'Free'
    
    @property
    def subscription_info(self):
        if not self.status or not self.status.is_subscription_based:
            return None
        latest_sub = self.transactions.filter(
            transaction_type='subscription',
            amount__lt=0
        ).order_by('-created_at').first()
        if not latest_sub:
            return None
        is_two_month = 'two_month' in latest_sub.description.lower() or 'two month' in latest_sub.description.lower()
        duration = timedelta(days=60 if is_two_month else 30)
        end_date = latest_sub.created_at + duration
        return {
            'active': end_date > timezone.now(),
            'type': 'two_month' if is_two_month else 'monthly',
            'start_date': latest_sub.created_at,
            'end_date': end_date,
            'transaction': latest_sub
        }
    
    @property
    def is_subscription_active(self):
        sub_info = self.subscription_info
        return sub_info and sub_info['active'] if sub_info else False
    
    @property
    def effective_status(self):
        if not self.status:
            return self.get_or_create_default_status()
        if self.status.is_subscription_based:
            if self.is_subscription_active:
                return self.status
            free_status = AccountStatus.objects.filter(tier_type='free').first()
            return free_status or self.get_or_create_default_status()
        return self.status

    # ── Withdrawable balance ──────────────────────────────────

    @property
    def deposited_balance(self):
        """
        Sum of all deposit-type transactions credited to this account.
        This is the gross amount the user has ever deposited — not
        reduced by spending, because spending draws from the combined
        balance.  Use withdrawable_balance for the actual eligible amount.
        """
        from django.db.models import Sum
        total_deposits = self.transactions.filter(
            transaction_type='deposit',
            amount__gt=0
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return total_deposits

    @property
    def total_withdrawn(self):
        """Sum of all completed wallet-to-bank withdrawals (stored as negative amounts)."""
        from django.db.models import Sum
        total = self.withdrawal_requests.filter(
            status='completed'
        ).aggregate(total=Sum('requested_amount'))['total'] or Decimal('0')
        return total

    @property
    def bonus_balance(self):
        """Total bonus credits ever added (non-withdrawable, informational)."""
        from django.db.models import Sum
        return self.transactions.filter(
            transaction_type='bonus',
            amount__gt=0
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    @property
    def withdrawable_balance(self):
        """
        The maximum amount the user can request to withdraw.

        Logic:
          deposited_balance  — total deposits ever made
        - total_withdrawn    — deposits already sent back to bank
        = gross withdrawable

        Then capped at the current wallet balance, because spending
        (on boosts, subscriptions, transfers) reduces the actual
        available funds even if not all of those were bonus funds.
        """
        gross = self.deposited_balance - self.total_withdrawn
        # Cannot exceed actual wallet balance
        return max(Decimal('0'), min(gross, self.balance))

    @property
    def has_pending_withdrawal(self):
        """True if there is already an active withdrawal request."""
        return self.withdrawal_requests.filter(
            status__in=['pending', 'under_review']
        ).exists()

    # ── Fund management ───────────────────────────────────────

    def add_funds(self, amount, transaction_type='deposit', description=None):
        """Add funds to user account (deposit or bonus)."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self.balance += Decimal(str(amount))
        self.save()
        Transaction.objects.create(
            account=self,
            amount=amount,
            transaction_type=transaction_type,
            description=description or f"{transaction_type.capitalize()} of {amount}"
        )
        self.check_and_update_status()
        return self.balance
    
    def deduct_funds(self, amount, transaction_type='listing_fee', description=None):
        """Deduct funds from user account."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if self.balance < Decimal(str(amount)):
            raise ValueError("Insufficient funds")
        self.balance -= Decimal(str(amount))
        self.save()
        Transaction.objects.create(
            account=self,
            amount=-amount,
            transaction_type=transaction_type,
            description=description or f"{transaction_type.capitalize()} of {amount}"
        )
        return self.balance

    # ── Subscription management ───────────────────────────────

    def subscribe_to_tier(self, tier_type='pro', subscription_type='monthly'):
        try:
            target_status = AccountStatus.objects.get(tier_type=tier_type)
        except AccountStatus.DoesNotExist:
            raise ValueError(f"Tier '{tier_type}' not found.")
        if not target_status.is_subscription_based:
            raise ValueError(f"Tier '{tier_type}' does not require subscription")
        price = target_status.two_month_price if subscription_type == 'two_month' else target_status.monthly_price
        if self.balance < price:
            raise ValueError(f"Insufficient funds. Required: ₦{price:,.2f}, Available: ₦{self.balance:,.2f}")
        self.deduct_funds(
            amount=price,
            transaction_type='subscription',
            description=f"{target_status.name} {subscription_type} subscription"
        )
        self.status = target_status
        self.save()
        return self.subscription_info
    
    def cancel_subscription(self):
        if self.is_subscription_active:
            Transaction.objects.create(
                account=self,
                amount=0,
                transaction_type='subscription',
                description="Subscription cancelled - will not auto-renew"
            )
        return True
    
    def check_and_update_status(self):
        if self.status and self.status.is_subscription_based:
            if not self.is_subscription_active:
                free_status = AccountStatus.objects.filter(tier_type='free').first()
                self.status = free_status
                self.save()
        else:
            self.update_status_by_balance()
    
    def update_status_by_balance(self):
        eligible = AccountStatus.objects.filter(
            min_balance__lte=self.balance,
            tier_type='free'
        ).order_by('-min_balance')
        if eligible.exists():
            new_status = eligible.first()
            if self.status != new_status:
                self.status = new_status
                self.save()
    
    def get_boost_price(self, base_price):
        effective_status = self.effective_status
        if effective_status and effective_status.boost_discount > 0:
            return base_price * (1 - effective_status.boost_discount / 100)
        return base_price

    def get_or_create_default_status(self):
        if not self.status:
            free_status, _ = AccountStatus.objects.get_or_create(
                tier_type='free',
                defaults={
                    'name': 'Free User',
                    'description': 'Basic free account',
                    'max_listings': 5,
                    'monthly_price': 0,
                    'two_month_price': 0,
                }
            )
            self.status = free_status
            self.save()
        return self.status


# ─────────────────────────────────────────────────────────────
# TRANSACTION
# ─────────────────────────────────────────────────────────────

class Transaction(models.Model):
    account = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=UserAccount.TRANSACTION_TYPES)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reference_id = models.CharField(max_length=100, blank=True, null=True)

    # Link refunds back to their original transaction
    refund_of_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds',
        help_text='Original transaction this refund is for'
    )
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.created_at.strftime('%Y-%m-%d')}"
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'transaction_type', '-created_at']),
            models.Index(fields=['reference_id']),
        ]
    
    def create_refund(self, refund_amount=None, reason=''):
        if refund_amount is None:
            refund_amount = abs(self.amount)
        refund_txn = Transaction.objects.create(
            account=self.account,
            amount=refund_amount,
            transaction_type='refund',
            description=f"Refund: {reason or self.description}",
            reference_id=self.reference_id or f"REF-{self.id}",
            refund_of_transaction=self
        )
        self.account.balance += Decimal(str(refund_amount))
        self.account.save(update_fields=['balance'])
        return refund_txn


# ─────────────────────────────────────────────────────────────
# WALLET TRANSFER
# ─────────────────────────────────────────────────────────────

class WalletTransfer(models.Model):
    """
    Records a balance transfer between two users.
    Linked Transaction records are created on each UserAccount.
    """
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]

    sender        = models.ForeignKey(UserAccount, on_delete=models.PROTECT, related_name='sent_transfers')
    recipient     = models.ForeignKey(UserAccount, on_delete=models.PROTECT, related_name='received_transfers')
    amount        = models.DecimalField(max_digits=10, decimal_places=2)
    note          = models.CharField(max_length=255, blank=True, help_text="Optional message to recipient")

    sender_transaction    = models.OneToOneField(
        'Transaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_sent')
    recipient_transaction = models.OneToOneField(
        'Transaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_received')

    status    = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    reference = models.CharField(max_length=60, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender',    '-created_at']),
            models.Index(fields=['recipient', '-created_at']),
        ]

    def __str__(self):
        return (f"Transfer ₦{self.amount} | "
                f"{self.sender.user.username} → {self.recipient.user.username}")

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"TRF-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# WITHDRAWAL REQUEST  (NEW)
# ─────────────────────────────────────────────────────────────

class WithdrawalRequest(models.Model):
    """
    A user's request to withdraw deposited wallet funds to their bank account.

    Key rules enforced here:
    - Only one pending/under_review request per user at a time (enforced in clean())
    - Withdrawable amount is derived from deposited transactions, not the raw balance
    - Fee and net payout are calculated and locked at submission time
    - Proof of original deposit is required (Monnify reference OR upload)
    - Withdrawal is processed to the user's own account only
    """
    
    DEFAULT_FEE_RATE = Decimal('10.00')

    STATUS_CHOICES = [
        ('pending',     'Pending'),       # Submitted, awaiting initial review
        ('under_review','Under Review'),  # Admin actively reviewing
        ('approved',    'Approved'),      # Approved, queued for payout
        ('processing',  'Processing'),    # Bank transfer in progress
        ('completed',   'Completed'),     # Successfully paid out
        ('rejected',    'Rejected'),      # Rejected by admin
        ('cancelled',   'Cancelled'),     # Cancelled by user before review
    ]

    PROOF_TYPE_CHOICES = [
        ('monnify_reference', 'Monnify Transaction Reference'),
        ('bank_alert',        'Bank Debit Alert Upload'),
        ('both',              'Both Reference and Upload'),
    ]

    # ── Core ─────────────────────────────────────────────────
    reference = models.CharField(
        max_length=60, unique=True, blank=True, null=True,
        help_text="Auto-generated unique reference e.g. WDR-A1B2C3D4E5F6"
    )
    account = models.ForeignKey(
        UserAccount, on_delete=models.PROTECT,
        related_name='withdrawal_requests'
    )

    # ── Amounts (locked at submission time) ───────────────────
    requested_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Amount the user wants to withdraw (before fee)"
    )
    fee_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=DEFAULT_FEE_RATE,
        help_text="Fee percentage locked at submission time (default 10%)"
    )
    fee_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Fee in naira, calculated and locked at submission"
    )
    net_payout = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Amount the user will actually receive (requested - fee)"
    )
    # Snapshot of withdrawable balance at submission time (for audit)
    withdrawable_balance_at_submission = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="User's withdrawable balance at the time of submission"
    )

    # ── Bank details (user's own account only) ─────────────────
    bank_name       = models.CharField(max_length=100)
    account_number  = models.CharField(max_length=20)
    account_name    = models.CharField(
        max_length=255,
        help_text="Must match user's verified identity on OpenSell"
    )

    # ── Proof of original deposit ──────────────────────────────
    proof_type = models.CharField(
        max_length=30, choices=PROOF_TYPE_CHOICES,
        default='monnify_reference'
    )
    monnify_transaction = models.ForeignKey(
        'MonnifyTransaction',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='withdrawal_requests',
        help_text="Select the Monnify deposit transaction as proof"
    )
    monnify_reference_manual = models.CharField(
        max_length=100, blank=True,
        help_text="If user types in their Monnify reference manually"
    )
    proof_upload = models.FileField(
        upload_to='withdrawal_proofs/%Y/%m/',
        null=True, blank=True,
        help_text="Bank debit alert screenshot or PDF"
    )
    proof_notes = models.TextField(
        blank=True,
        help_text="Any additional notes the user provides about the proof"
    )

    # ── Status & workflow ─────────────────────────────────────
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # ── Admin fields ──────────────────────────────────────────
    reviewed_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_withdrawal_requests',
        help_text="Admin who reviewed this request"
    )
    rejection_reason = models.TextField(blank=True)
    admin_notes      = models.TextField(blank=True)
    payment_reference = models.CharField(
        max_length=100, blank=True,
        help_text="Bank transfer reference from payout processor"
    )

    # ── Timestamps ────────────────────────────────────────────
    submitted_at  = models.DateTimeField(auto_now_add=True)
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    completed_at  = models.DateTimeField(null=True, blank=True)

    # ── Linked wallet transaction ─────────────────────────────
    # Created only when status moves to 'completed', deducting balance
    wallet_transaction = models.OneToOneField(
        'Transaction',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='withdrawal_request',
        help_text="The Transaction record created when withdrawal is completed"
    )

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['account', 'status']),
            models.Index(fields=['status', '-submitted_at']),
            models.Index(fields=['reference']),
        ]

    def __str__(self):
        return f"WDR {self.reference} | ₦{self.requested_amount} | {self.account.user.username} | {self.status}"

    # ── Auto-generate reference ────────────────────────────────

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"WDR-{uuid.uuid4().hex[:12].upper()}"
        # Auto-calculate fee and net payout if not already set
        if not self.fee_amount:
            self.fee_amount = (self.requested_amount * self.fee_rate / 100).quantize(Decimal('0.01'))
        if not self.net_payout:
            self.net_payout = self.requested_amount - self.fee_amount
        super().save(*args, **kwargs)

    # ── Validation ────────────────────────────────────────────

    def clean(self):
        from django.core.exceptions import ValidationError

        # Enforce one active request at a time
        active_qs = WithdrawalRequest.objects.filter(
            account=self.account,
            status__in=['pending', 'under_review']
        )
        if self.pk:
            active_qs = active_qs.exclude(pk=self.pk)
        if active_qs.exists():
            raise ValidationError(
                "You already have a pending or under-review withdrawal request. "
                "Please wait for it to be resolved before submitting a new one."
            )

        # Requested amount must not exceed withdrawable balance
        if self.requested_amount > self.withdrawable_balance_at_submission:
            raise ValidationError(
                f"Requested amount (₦{self.requested_amount:,.2f}) exceeds your "
                f"withdrawable balance (₦{self.withdrawable_balance_at_submission:,.2f})."
            )

        # Must have at least one form of proof
        if not self.monnify_transaction and not self.monnify_reference_manual and not self.proof_upload:
            raise ValidationError(
                "You must provide proof of the original deposit: either select your "
                "Monnify transaction, enter the Monnify reference number, or upload a "
                "bank debit alert."
            )

    # ── Status transition helpers ─────────────────────────────

    def approve(self, admin_user):
        """Mark as approved and ready for payout processing."""
        self.status = 'approved'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    def start_processing(self):
        """Mark as actively being sent to bank."""
        self.status = 'processing'
        self.save(update_fields=['status'])

    def complete(self, payment_reference=''):
        """
        Mark as completed and deduct the requested amount from the user's wallet.
        Called by admin/payment processor once bank transfer is confirmed.
        """
        with db_transaction.atomic():
            # Lock the account
            account = UserAccount.objects.select_for_update().get(pk=self.account_id)

            if account.balance < self.requested_amount:
                raise ValueError(
                    f"Wallet balance (₦{account.balance:,.2f}) is lower than "
                    f"withdrawal amount (₦{self.requested_amount:,.2f}). "
                    "This should not happen — investigate before proceeding."
                )

            # Deduct from wallet
            account.balance -= self.requested_amount
            account.save(update_fields=['balance'])

            # Create the wallet transaction record
            txn = Transaction.objects.create(
                account=account,
                amount=-self.requested_amount,
                transaction_type='withdrawal',
                description=(
                    f"Wallet withdrawal — ₦{self.net_payout:,.2f} paid out, "
                    f"₦{self.fee_amount:,.2f} fee. Ref: {self.reference}"
                ),
                reference_id=self.reference,
            )

            self.wallet_transaction = txn
            self.status = 'completed'
            self.completed_at = timezone.now()
            if payment_reference:
                self.payment_reference = payment_reference
            self.save(update_fields=[
                'wallet_transaction', 'status', 'completed_at', 'payment_reference'
            ])

    def reject(self, admin_user, reason=''):
        """Reject the request without touching the wallet."""
        self.status = 'rejected'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason'])

    def cancel(self):
        """User-initiated cancellation before review starts."""
        if self.status not in ('pending',):
            raise ValueError("Only pending requests can be cancelled by the user.")
        self.status = 'cancelled'
        self.save(update_fields=['status'])

    @property
    def is_final(self):
        """True once the request has reached a terminal state."""
        return self.status in ('completed', 'rejected', 'cancelled')

    @classmethod
    def create_for_user(cls, account, requested_amount, bank_name, account_number,
                        account_name, proof_type='monnify_reference',
                        monnify_transaction=None, monnify_reference_manual='',
                        proof_upload=None, proof_notes=''):
        requested_amount = Decimal(str(requested_amount))
        fee_rate = cls.DEFAULT_FEE_RATE
        fee_amount = (requested_amount * fee_rate / 100).quantize(Decimal('0.01'))
        net_payout = requested_amount - fee_amount

        with db_transaction.atomic():
            locked_account = UserAccount.objects.select_for_update().get(pk=account.pk)
            withdrawable = locked_account.withdrawable_balance

            instance = cls(
                account=locked_account,
                requested_amount=requested_amount,
                fee_rate=fee_rate,
                fee_amount=fee_amount,
                net_payout=net_payout,
                withdrawable_balance_at_submission=withdrawable,
                bank_name=bank_name,
                account_number=account_number,
                account_name=account_name,
                proof_type=proof_type,
                monnify_transaction=monnify_transaction,
                monnify_reference_manual=monnify_reference_manual,
                proof_upload=proof_upload,
                proof_notes=proof_notes,
            )
            instance.full_clean()
            instance.save()
            return instance

# PRODUCT BOOST
class ProductBoost(models.Model):
    BOOST_TYPES = [
        ('featured', 'Featured Product'),
        ('urgent', 'Urgent Sale'),
        ('spotlight', 'Category Spotlight'),
        ('premium', 'Premium Placement'),
    ]
    
    DURATION_CHOICES = [
        (1, '1 Day'),
        (3, '3 Days'),
        (7, '1 Week'),
        (14, '2 Weeks'),
        (30, '1 Month'),
    ]
    
    BASE_PRICES = {
        'featured': Decimal('100.00'),
        'urgent': Decimal('75.00'),
        'spotlight': Decimal('200.00'),
        'premium': Decimal('350.00'),
    }
    
    product = models.ForeignKey('Home.Product_Listing', on_delete=models.CASCADE, related_name='boosts')
    boost_type = models.CharField(max_length=20, choices=BOOST_TYPES)
    duration_days = models.PositiveIntegerField(choices=DURATION_CHOICES, default=1)
    
    original_cost = models.DecimalField(max_digits=10, decimal_places=2)
    final_cost = models.DecimalField(max_digits=10, decimal_places=2)
    discount_applied = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tier_at_purchase = models.CharField(max_length=50, blank=True)
    
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL, null=True, blank=True)
    user_account = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='product_boosts')
    
    def save(self, *args, **kwargs):
        if not self.start_date:
            self.start_date = timezone.now()
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.duration_days)
        super().save(*args, **kwargs)
    
    def __str__(self):
        discount_text = f" ({self.discount_applied}% off)" if self.discount_applied > 0 else ""
        return f"{self.get_boost_type_display()} - {self.product.title} - {self.duration_days}d{discount_text}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.end_date
    
    @property
    def days_remaining(self):
        if self.is_expired:
            return 0
        return (self.end_date - timezone.now()).days
    
    @classmethod
    def calculate_boost_cost(cls, boost_type, duration_days, user_account):
        base_price = cls.BASE_PRICES.get(boost_type, Decimal('5.00'))
        original_cost = base_price * duration_days
        effective_status = user_account.effective_status
        if effective_status and effective_status.boost_discount > 0:
            discount_percent = effective_status.boost_discount
            final_cost = original_cost * (1 - discount_percent / 100)
        else:
            discount_percent = 0
            final_cost = original_cost
        return {
            'original_cost': original_cost,
            'final_cost': final_cost,
            'discount_percent': discount_percent,
            'savings': original_cost - final_cost
        }
    
    @classmethod
    def create_boost(cls, product, boost_type, duration_days, user_account):
        cost_info = cls.calculate_boost_cost(boost_type, duration_days, user_account)
        if user_account.balance < cost_info['final_cost']:
            raise ValueError(f"Insufficient funds. Required: {cost_info['final_cost']}, Available: {user_account.balance}")
        existing_boost = cls.objects.filter(
            product=product, boost_type=boost_type,
            is_active=True, end_date__gt=timezone.now()
        ).first()
        if existing_boost:
            raise ValueError(f"Product already has an active {boost_type} boost until {existing_boost.end_date.strftime('%Y-%m-%d')}")
        user_account.deduct_funds(
            amount=cost_info['final_cost'],
            transaction_type='boost_fee',
            description=f"{boost_type.title()} boost for {product.title} ({duration_days} days)"
        )
        boost_transaction = user_account.transactions.filter(
            transaction_type='boost_fee'
        ).order_by('-created_at').first()
        start_time = timezone.now()
        return cls.objects.create(
            product=product,
            boost_type=boost_type,
            duration_days=duration_days,
            original_cost=cost_info['original_cost'],
            final_cost=cost_info['final_cost'],
            discount_applied=cost_info['discount_percent'],
            tier_at_purchase=user_account.effective_status.name if user_account.effective_status else 'Free',
            transaction=boost_transaction,
            user_account=user_account,
            start_date=start_time,
            end_date=start_time + timedelta(days=duration_days)
        )
    
    def extend_boost(self, additional_days):
        if self.is_expired:
            raise ValueError("Cannot extend expired boost")
        cost_info = self.calculate_boost_cost(self.boost_type, additional_days, self.user_account)
        if self.user_account.balance < cost_info['final_cost']:
            raise ValueError("Insufficient funds to extend boost")
        self.user_account.deduct_funds(
            amount=cost_info['final_cost'],
            transaction_type='boost_fee',
            description=f"Extended {self.boost_type} boost for {self.product.title} (+{additional_days} days)"
        )
        self.end_date += timedelta(days=additional_days)
        self.save()
        return self
    
    def cancel_boost(self, refund_percentage=50):
        if self.is_expired:
            raise ValueError("Cannot cancel expired boost")
        remaining_days = self.days_remaining
        if remaining_days <= 0:
            raise ValueError("No remaining days to refund")
        daily_cost = self.final_cost / self.duration_days
        full_refund = daily_cost * remaining_days
        actual_refund = full_refund * (refund_percentage / 100)
        self.user_account.add_funds(
            amount=actual_refund,
            transaction_type='refund',
            description=f"Refund for cancelled {self.boost_type} boost ({remaining_days} days remaining)"
        )
        self.is_active = False
        self.end_date = timezone.now()
        self.save()
        return actual_refund
    
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['product', 'boost_type', 'is_active']),
            models.Index(fields=['user_account', '-start_date']),
            models.Index(fields=['end_date', 'is_active']),
        ]

# BACKGROUND TASK HELPERS

def check_subscription_expiry():
    accounts = UserAccount.objects.filter(status__tier_type__in=['pro', 'enterprise'])
    for account in accounts:
        account.check_and_update_status()


def deactivate_expired_boosts():
    expired = ProductBoost.objects.filter(is_active=True, end_date__lte=timezone.now())
    expired.update(is_active=False)
    return expired.count()

# MONNIFY FUNDING SETUP
class VirtualAccount(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]
    
    user_account = models.ForeignKey(
        'UserAccount', on_delete=models.CASCADE, related_name='virtual_accounts'
    )
    account_reference = models.CharField(max_length=100, db_index=True)
    account_name      = models.CharField(max_length=255)
    account_number    = models.CharField(max_length=20, db_index=True)
    bank_name         = models.CharField(max_length=100)
    bank_code         = models.CharField(max_length=10)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # KYC
    bvn            = models.CharField(max_length=11, blank=True, null=True)
    nin            = models.CharField(max_length=11, blank=True, null=True)
    kyc_verified   = models.BooleanField(default=False)
    kyc_verified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    monnify_response = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account_reference']),
            models.Index(fields=['account_number']),
            models.Index(fields=['user_account', 'status']),
        ]
        unique_together = [['account_reference', 'bank_code']]
    
    def __str__(self):
        return f"{self.account_name} - {self.account_number} ({self.bank_name})"
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def has_kyc(self):
        return self.kyc_verified and (self.bvn or self.nin)
    
    @property
    def transaction_limit_info(self):
        if self.bvn and self.nin:
            return {'level': 'Maximum', 'per_transaction': '5,000,000+', 'daily': 'Unlimited', 'description': 'Full KYC (BVN + NIN)'}
        elif self.bvn or self.nin:
            return {'level': 'Medium', 'per_transaction': '1,000,000', 'daily': '5,000,000', 'description': 'Partial KYC'}
        else:
            return {'level': 'Basic', 'per_transaction': '50,000', 'daily': '300,000', 'description': 'No KYC'}
    
    def deactivate(self):
        self.status = 'inactive'
        self.save()

class MonnifyTransaction(models.Model):
    TRANSACTION_STATUS = [
        ('PAID', 'Paid'),
        ('PENDING', 'Pending'),
        ('OVERPAID', 'Overpaid'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('FAILED', 'Failed'),
        ('REVERSED', 'Reversed'),
    ]
    
    user_account = models.ForeignKey(
        'UserAccount', on_delete=models.CASCADE, related_name='monnify_transactions'
    )
    virtual_account = models.ForeignKey(
        VirtualAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions'
    )
    
    transaction_reference = models.CharField(max_length=100, unique=True, db_index=True)
    payment_reference     = models.CharField(max_length=100, db_index=True)
    amount_paid           = models.DecimalField(max_digits=10, decimal_places=2)
    total_payable         = models.DecimalField(max_digits=10, decimal_places=2)
    settlement_amount     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_on               = models.DateTimeField()
    payment_status        = models.CharField(max_length=20, choices=TRANSACTION_STATUS)
    payment_description   = models.TextField(blank=True)
    payment_method        = models.CharField(max_length=50, blank=True)
    currency              = models.CharField(max_length=3, default='NGN')
    
    customer_name  = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    
    destination_account_number = models.CharField(max_length=20, blank=True)
    destination_account_name   = models.CharField(max_length=255, blank=True)
    destination_bank_name      = models.CharField(max_length=100, blank=True)
    destination_bank_code      = models.CharField(max_length=10, blank=True)
    
    processed            = models.BooleanField(default=False)
    processed_at         = models.DateTimeField(null=True, blank=True)
    credited_to_account  = models.BooleanField(default=False)
    
    dashboard_transaction = models.ForeignKey(
        'Transaction', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='monnify_transaction'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    webhook_payload = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-paid_on']
        indexes = [
            models.Index(fields=['transaction_reference']),
            models.Index(fields=['payment_reference']),
            models.Index(fields=['user_account', '-paid_on']),
            models.Index(fields=['payment_status', 'processed']),
        ]
    
    def __str__(self):
        return f"{self.transaction_reference} - ₦{self.amount_paid} ({self.payment_status})"
    
    def process_payment(self):
        if self.processed or self.payment_status != 'PAID':
            return False
        try:
            self.user_account.add_funds(
                amount=self.amount_paid,
                transaction_type='deposit',
                description=f"Monnify deposit via {self.payment_method} - {self.transaction_reference}"
            )
            dashboard_transaction = self.user_account.transactions.filter(
                transaction_type='deposit'
            ).order_by('-created_at').first()
            self.dashboard_transaction = dashboard_transaction
            self.processed = True
            self.processed_at = timezone.now()
            self.credited_to_account = True
            self.save()
            logger.info(f"Payment processed: {self.transaction_reference} - ₦{self.amount_paid} credited to {self.user_account.user.username}")
            return True
        except Exception as e:
            logger.error(f"Error processing Monnify payment {self.transaction_reference}: {str(e)}", exc_info=True)
            return False

class PaymentNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('SUCCESSFUL_TRANSACTION', 'Successful Transaction'),
        ('FAILED_TRANSACTION', 'Failed Transaction'),
        ('REVERSED_TRANSACTION', 'Reversed Transaction'),
    ]
    
    notification_type     = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    transaction_reference = models.CharField(max_length=100, db_index=True)
    processed             = models.BooleanField(default=False)
    processed_at          = models.DateTimeField(null=True, blank=True)
    processing_error      = models.TextField(blank=True)
    monnify_transaction   = models.ForeignKey(
        MonnifyTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications'
    )
    raw_payload  = models.JSONField()
    received_at  = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['transaction_reference', 'processed']),
            models.Index(fields=['-received_at']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} - {self.transaction_reference} ({'Processed' if self.processed else 'Pending'})"


def process_pending_monnify_transactions():
    pending = MonnifyTransaction.objects.filter(payment_status='PAID', processed=False)
    success_count = 0
    for transaction in pending:
        if transaction.process_payment():
            success_count += 1
    logger.info(f"Processed {success_count} pending Monnify transactions")
    return success_count

# AFFILIATE REFERRAL SETUP
class AffiliateProfile(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('rejected', 'Rejected'),
    ]
    
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate')
    referral_code = models.CharField(max_length=20, unique=True, db_index=True)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    funding_commission_rate      = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)
    boost_commission_rate        = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)
    subscription_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15.0)
    
    pending_balance   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    available_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_earned      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_withdrawn   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    minimum_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=2000)
    
    approved_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_affiliates')
    approved_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    
    application_reason = models.TextField(blank=True)
    admin_notes        = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.referral_code}"
    
    @property
    def total_referrals(self):
        return Referral.objects.filter(affiliate=self, status='active').count()
    
    @property
    def active_referrals(self):
        return Referral.objects.filter(
            affiliate=self, status='active',
            first_qualifying_transaction__isnull=False
        ).count()
    
    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)
    
    def generate_referral_code(self):
        base_code = self.user.username.lower()
        referral_code = base_code
        counter = 1
        while AffiliateProfile.objects.filter(
            referral_code__iexact=referral_code
        ).exclude(id=self.id).exists():
            referral_code = f"{base_code}{counter}"
            counter += 1
        return referral_code
    
    def get_referral_url(self, request=None):
        from django.urls import reverse
        from django.conf import settings
        if request:
            base_url = request.build_absolute_uri('/')
        else:
            base_url = settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://opensell.online/'
        signup_path = reverse('signup')
        return f"{base_url.rstrip('/')}{signup_path}?ref={self.referral_code}"
    
    def get_short_link(self):
        return self.referral_code

class Referral(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('fraud', 'Flagged as Fraud'),
    ]
    
    affiliate     = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='referrals')
    referred_user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referral_info')
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    referral_code_used           = models.CharField(max_length=20)
    signup_ip                    = models.GenericIPAddressField(null=True, blank=True)
    signup_date                  = models.DateTimeField(auto_now_add=True)
    first_qualifying_transaction = models.DateTimeField(null=True, blank=True)
    
    total_revenue_generated = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_commission_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    flagged_for_review = models.BooleanField(default=False)
    fraud_reason       = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-signup_date']
        indexes = [
            models.Index(fields=['affiliate', 'status']),
            models.Index(fields=['referred_user']),
        ]
    
    def __str__(self):
        return f"{self.referred_user.username} referred by {self.affiliate.referral_code}"

class AffiliateCommission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('available', 'Available'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='commissions')
    referral  = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name='commissions')
    
    transaction_type = models.CharField(max_length=20, choices=[
        ('funding', 'Account Funding'),
        ('boost', 'Boost Purchase'),
        ('subscription', 'Pro Subscription'),
    ])
    
    base_amount       = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate   = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    source_transaction = models.ForeignKey(
        'Transaction', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='affiliate_commission'
    )
    
    created_at   = models.DateTimeField(auto_now_add=True)
    available_at = models.DateTimeField()
    paid_at      = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['affiliate', 'status']),
            models.Index(fields=['status', 'available_at']),
        ]
    
    def __str__(self):
        return f"₦{self.commission_amount} - {self.affiliate.referral_code} - {self.transaction_type}"

class AffiliateWithdrawal(models.Model):
    """Affiliate commission withdrawal — separate from wallet WithdrawalRequest."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    
    affiliate      = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='withdrawals')
    amount         = models.DecimalField(max_digits=10, decimal_places=2)
    
    payment_method = models.CharField(max_length=50, default='bank_transfer')
    bank_name      = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    account_name   = models.CharField(max_length=255)
    
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    processed_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_withdrawals')
    processed_at      = models.DateTimeField(null=True, blank=True)
    rejection_reason  = models.TextField(blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    
    requested_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"₦{self.amount} - {self.affiliate.referral_code} - {self.status}"

# SIGNALS

@receiver(post_save, sender=Transaction)
def track_affiliate_commission(sender, instance, created, **kwargs):
    """
    SECURE COMMISSION TRACKING — 7-DAY HOLDING PERIOD
    Commissions are held for 7 days to prevent fraud.
    Only tracks: deposit, boost_fee, subscription transactions.
    Affiliate must be 'active' status. Minimum deposit ₦100.
    """
    if not created:
        return
    
    qualifying_types = ['deposit', 'boost_fee', 'subscription']
    if instance.transaction_type not in qualifying_types:
        return
    
    transaction_amount = abs(instance.amount)
    
    if instance.transaction_type == 'deposit' and transaction_amount < 100:
        logger.info(f"Skipping commission — deposit {transaction_amount} below ₦100 minimum")
        return
    
    try:
        from Dashboard.models import Referral, AffiliateProfile, AffiliateCommission
        
        if AffiliateCommission.objects.filter(source_transaction=instance).exists():
            logger.warning(f"⚠️ Duplicate commission attempt blocked — Transaction {instance.id}")
            return
        
        try:
            referral = Referral.objects.select_related('affiliate').get(
                referred_user=instance.account.user
            )
        except Referral.DoesNotExist:
            return
        
        if referral.affiliate.status != 'active':
            logger.info(f"⚠️ Commission blocked — affiliate {referral.affiliate.referral_code} not active")
            return
        
        commission_type_map = {
            'deposit':      ('funding',      referral.affiliate.funding_commission_rate),
            'boost_fee':    ('boost',        referral.affiliate.boost_commission_rate),
            'subscription': ('subscription', referral.affiliate.subscription_commission_rate),
        }
        commission_type, commission_rate = commission_type_map[instance.transaction_type]
        commission_amount = (transaction_amount * commission_rate / 100)
        
        if commission_amount <= 0:
            return
        
        available_date = timezone.now() + timedelta(days=7)
        
        with db_transaction.atomic():
            affiliate = AffiliateProfile.objects.select_for_update().get(id=referral.affiliate.id)
            
            AffiliateCommission.objects.create(
                affiliate=affiliate,
                referral=referral,
                transaction_type=commission_type,
                base_amount=transaction_amount,
                commission_rate=commission_rate,
                commission_amount=commission_amount,
                status='pending',
                source_transaction=instance,
                available_at=available_date
            )
            
            affiliate.pending_balance += commission_amount
            affiliate.total_earned    += commission_amount
            affiliate.save(update_fields=['pending_balance', 'total_earned'])
            
            if referral.status == 'pending' and transaction_amount >= 100:
                referral.first_qualifying_transaction = timezone.now()
                referral.status = 'active'
            
            referral.total_revenue_generated += transaction_amount
            referral.total_commission_earned += commission_amount
            referral.save(update_fields=[
                'first_qualifying_transaction', 'status',
                'total_revenue_generated', 'total_commission_earned'
            ])
            
            logger.info(
                f"✓ COMMISSION TRACKED (7-DAY HOLD): ₦{commission_amount:.2f} ({commission_rate}%) | "
                f"Affiliate: {affiliate.referral_code} | From: {instance.account.user.username} | "
                f"Type: {commission_type} | Available: {available_date.strftime('%Y-%m-%d')}"
            )
            
    except Exception as e:
        logger.error(
            f"⚠️ Commission tracking error: User: {instance.account.user.username} | "
            f"Amount: ₦{instance.amount} | Type: {instance.transaction_type} | Error: {str(e)}",
            exc_info=True
        )

@receiver(post_save, sender=Transaction)
def handle_commission_reversal(sender, instance, created, **kwargs):
    """
    Reverse commissions when a transaction is refunded.
    Links via reference_id — make sure refunds carry the original reference.
    """
    if not created or instance.transaction_type != 'refund':
        return
    
    try:
        from Dashboard.models import AffiliateCommission, AffiliateProfile
        
        original_ref = instance.reference_id
        if not original_ref:
            return
        
        original_transaction = Transaction.objects.filter(
            reference_id=original_ref,
            account=instance.account
        ).exclude(id=instance.id).first()
        
        if not original_transaction:
            return
        
        commissions = AffiliateCommission.objects.filter(
            source_transaction=original_transaction
        ).exclude(status='cancelled')
        
        with db_transaction.atomic():
            for commission in commissions:
                affiliate = AffiliateProfile.objects.select_for_update().get(id=commission.affiliate.id)
                if commission.status == 'pending':
                    affiliate.pending_balance -= commission.commission_amount
                elif commission.status == 'available':
                    affiliate.available_balance -= commission.commission_amount
                elif commission.status == 'paid':
                    logger.warning(
                        f"⚠️ Commission reversal for PAID commission: "
                        f"₦{commission.commission_amount:.2f} | Affiliate: {affiliate.referral_code}"
                    )
                affiliate.total_earned -= commission.commission_amount
                affiliate.save(update_fields=['pending_balance', 'available_balance', 'total_earned'])
                commission.status = 'cancelled'
                commission.save(update_fields=['status'])
                logger.info(
                    f"✓ COMMISSION REVERSED: ₦{commission.commission_amount:.2f} | "
                    f"Affiliate: {affiliate.referral_code} | Reason: Transaction refunded"
                )
                
    except Exception as e:
        logger.error(f"Commission reversal error: {str(e)}", exc_info=True)