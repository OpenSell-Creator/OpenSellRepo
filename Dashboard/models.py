from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
logger = logging.getLogger(__name__)

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
    
    # Pricing (stored but can be overridden by properties)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Benefits
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
        """Check if this tier requires subscription"""
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
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='account')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.ForeignKey(AccountStatus, on_delete=models.SET_NULL, null=True, related_name='accounts')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_deposit_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s Account ({self.current_tier_display})"
    
    @property
    def current_tier_display(self):
        """Get current tier display name"""
        if self.is_subscription_active:
            return self.status.get_tier_type_display() if self.status else 'Free'
        return 'Free'
    
    @property
    def subscription_info(self):
        """Get active subscription info from transaction history"""
        if not self.status or not self.status.is_subscription_based:
            return None
            
        # Find the latest subscription transaction
        latest_sub = self.transactions.filter(
            transaction_type='subscription',
            amount__lt=0  # Negative amount (payment)
        ).order_by('-created_at').first()
        
        if not latest_sub:
            return None
        
        # Calculate subscription details
        is_yearly = 'yearly' in latest_sub.description.lower()
        duration = timedelta(days=365 if is_yearly else 30)
        end_date = latest_sub.created_at + duration
        
        return {
            'active': end_date > timezone.now(),
            'type': 'yearly' if is_yearly else 'monthly',
            'start_date': latest_sub.created_at,
            'end_date': end_date,
            'transaction': latest_sub
        }
    
    @property
    def is_subscription_active(self):
        """Check if user has an active subscription"""
        sub_info = self.subscription_info
        return sub_info and sub_info['active'] if sub_info else False
    
    @property
    def effective_status(self):
        """Get the user's effective status (considering subscription expiry)"""
        # Ensure we have a status
        if not self.status:
            return self.get_or_create_default_status()
        
        if self.status.is_subscription_based:
            if self.is_subscription_active:
                return self.status
            else:
                # Subscription expired, return free status
                free_status = AccountStatus.objects.filter(tier_type='free').first()
                if not free_status:
                    return self.get_or_create_default_status()
                return free_status
        
        return self.status
    
    def subscribe_to_tier(self, tier_type='pro', subscription_type='monthly'):
        """Subscribe user to a specific tier"""
        # Use get() with better error handling
        try:
            target_status = AccountStatus.objects.get(tier_type=tier_type)
        except AccountStatus.DoesNotExist:
            raise ValueError(f"Tier '{tier_type}' not found. Please ensure account tiers are properly set up.")
        
        if not target_status.is_subscription_based:
            raise ValueError(f"Tier '{tier_type}' does not require subscription")
        
        # Calculate price
        if subscription_type == 'yearly':
            price = target_status.yearly_price
        else:
            price = target_status.monthly_price
        
        if self.balance < price:
            raise ValueError(f"Insufficient funds for subscription. Required: ₦{price:,.2f}, Available: ₦{self.balance:,.2f}")
        
        # Deduct funds
        self.deduct_funds(
            amount=price,
            transaction_type='subscription',
            description=f"{target_status.name} {subscription_type} subscription"
        )
        
        # Update status
        self.status = target_status
        self.save()
        
        return self.subscription_info
    
    def cancel_subscription(self):
        """Cancel current subscription (will expire naturally)"""
        # Just record the cancellation - subscription will expire based on transaction date
        if self.is_subscription_active:
            Transaction.objects.create(
                account=self,
                amount=0,
                transaction_type='subscription',
                description="Subscription cancelled - will not auto-renew"
            )
        return True
    
    def check_and_update_status(self):
        """Check subscription status and update if needed"""
        if self.status and self.status.is_subscription_based:
            if not self.is_subscription_active:
                # Downgrade to free
                free_status = AccountStatus.objects.filter(tier_type='free').first()
                self.status = free_status
                self.save()
        else:
            # For balance-based tiers, update based on balance
            self.update_status_by_balance()
    
    def update_status_by_balance(self):
        """Update status based on balance (for non-subscription tiers)"""
        eligible_statuses = AccountStatus.objects.filter(
            min_balance__lte=self.balance,
            tier_type='free'  # Only consider free tiers for balance-based upgrades
        ).order_by('-min_balance')
        
        if eligible_statuses.exists():
            new_status = eligible_statuses.first()
            if self.status != new_status:
                self.status = new_status
                self.save()
    
    def get_boost_price(self, base_price):
        """Calculate boost price with tier discount"""
        effective_status = self.effective_status
        if effective_status and effective_status.boost_discount > 0:
            return base_price * (1 - effective_status.boost_discount / 100)
        return base_price
    
    # Keep existing fund management methods
    def add_funds(self, amount, transaction_type='deposit', description=None):
        """Add funds to user account"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        self.balance += Decimal(amount)
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
        """Deduct funds from user account"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if self.balance < Decimal(amount):
            raise ValueError("Insufficient funds")
        
        self.balance -= Decimal(amount)
        self.save()
        
        Transaction.objects.create(
            account=self,
            amount=-amount,
            transaction_type=transaction_type,
            description=description or f"{transaction_type.capitalize()} of {amount}"
        )
        
        return self.balance
    def get_or_create_default_status(self):
        """Ensure user has a valid status"""
        if not self.status:
            free_status, created = AccountStatus.objects.get_or_create(
                tier_type='free',
                defaults={
                    'name': 'Free User',
                    'description': 'Basic free account',
                    'max_listings': 5,
                    'monthly_price': 0,
                    'yearly_price': 0
                }
            )
            self.status = free_status
            self.save()
        return self.status
    
class Transaction(models.Model):
    account = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=UserAccount.TRANSACTION_TYPES)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reference_id = models.CharField(max_length=50, blank=True, null=True)
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.created_at.strftime('%Y-%m-%d')}"
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'transaction_type', '-created_at']),
        ]

class ProductBoost(models.Model):
    """Product boost functionality with tier-based pricing"""
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
    
    # Base prices per day (before discounts)
    BASE_PRICES = {
        'featured': Decimal('5.00'),
        'urgent': Decimal('3.00'),
        'spotlight': Decimal('7.50'),
        'premium': Decimal('10.00'),
    }
    
    product = models.ForeignKey('Home.Product_Listing', on_delete=models.CASCADE, related_name='boosts')
    boost_type = models.CharField(max_length=20, choices=BOOST_TYPES)
    duration_days = models.PositiveIntegerField(choices=DURATION_CHOICES, default=1)
    
    # Pricing details
    original_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost before any discounts")
    final_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Actual amount charged")
    discount_applied = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Discount percentage applied")
    tier_at_purchase = models.CharField(max_length=50, blank=True, help_text="User's tier when boost was purchased")
    
    # Timing
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Relations
    transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL, null=True, blank=True)
    user_account = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='product_boosts')
    
    def save(self, *args, **kwargs):
        """Auto-calculate end_date based on duration"""
        # Ensure start_date is set before calculating end_date
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
        """Check if boost has expired"""
        return timezone.now() > self.end_date
    
    @property
    def days_remaining(self):
        """Get remaining days for active boost"""
        if self.is_expired:
            return 0
        return (self.end_date - timezone.now()).days
    
    @classmethod
    def calculate_boost_cost(cls, boost_type, duration_days, user_account):
        """Calculate boost cost with user's tier discount"""
        base_price = cls.BASE_PRICES.get(boost_type, Decimal('5.00'))
        original_cost = base_price * duration_days
        
        # Apply tier discount
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
        """Create a new product boost with payment processing"""
        # Calculate costs
        cost_info = cls.calculate_boost_cost(boost_type, duration_days, user_account)
        
        # Check if user has sufficient funds
        if user_account.balance < cost_info['final_cost']:
            raise ValueError(f"Insufficient funds. Required: {cost_info['final_cost']}, Available: {user_account.balance}")
        
        # Check if product already has active boost of same type
        existing_boost = cls.objects.filter(
            product=product,
            boost_type=boost_type,
            is_active=True,
            end_date__gt=timezone.now()
        ).first()
        
        if existing_boost:
            raise ValueError(f"Product already has an active {boost_type} boost until {existing_boost.end_date.strftime('%Y-%m-%d')}")
        
        # Deduct funds
        user_account.deduct_funds(
            amount=cost_info['final_cost'],
            transaction_type='boost_fee',
            description=f"{boost_type.title()} boost for {product.title} ({duration_days} days)"
        )
        
        # Get the transaction that was just created
        boost_transaction = user_account.transactions.filter(
            transaction_type='boost_fee'
        ).order_by('-created_at').first()
        
        # Create boost with explicit start_date
        start_time = timezone.now()
        boost = cls.objects.create(
            product=product,
            boost_type=boost_type,
            duration_days=duration_days,
            original_cost=cost_info['original_cost'],
            final_cost=cost_info['final_cost'],
            discount_applied=cost_info['discount_percent'],
            tier_at_purchase=user_account.effective_status.name if user_account.effective_status else 'Free',
            transaction=boost_transaction,
            user_account=user_account,
            start_date=start_time,  # Explicitly set start_date
            end_date=start_time + timedelta(days=duration_days)  # Explicitly set end_date
        )
        
        return boost
    
    def extend_boost(self, additional_days):
        """Extend an existing boost"""
        if self.is_expired:
            raise ValueError("Cannot extend expired boost")
        
        # Calculate additional cost
        cost_info = self.calculate_boost_cost(self.boost_type, additional_days, self.user_account)
        
        if self.user_account.balance < cost_info['final_cost']:
            raise ValueError("Insufficient funds to extend boost")
        
        # Deduct funds
        self.user_account.deduct_funds(
            amount=cost_info['final_cost'],
            transaction_type='boost_fee',
            description=f"Extended {self.boost_type} boost for {self.product.title} (+{additional_days} days)"
        )
        
        # Extend duration
        self.end_date += timedelta(days=additional_days)
        self.save()
        
        return self
    
    def cancel_boost(self, refund_percentage=50):
        """Cancel boost and provide partial refund"""
        if self.is_expired:
            raise ValueError("Cannot cancel expired boost")
        
        remaining_days = self.days_remaining
        if remaining_days <= 0:
            raise ValueError("No remaining days to refund")
        
        # Calculate refund (pro-rated)
        daily_cost = self.final_cost / self.duration_days
        full_refund = daily_cost * remaining_days
        actual_refund = full_refund * (refund_percentage / 100)
        
        # Process refund
        self.user_account.add_funds(
            amount=actual_refund,
            transaction_type='refund',
            description=f"Refund for cancelled {self.boost_type} boost ({remaining_days} days remaining)"
        )
        
        # Deactivate boost
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

# Periodic task to check subscription expiry (run this via Celery or cron)
def check_subscription_expiry():
    """Check and handle expired subscriptions"""
    accounts = UserAccount.objects.filter(
        status__tier_type__in=['pro', 'enterprise']
    )
    
    for account in accounts:
        account.check_and_update_status()

def deactivate_expired_boosts():
    """Deactivate expired product boosts (run this via Celery or cron)"""
    expired_boosts = ProductBoost.objects.filter(
        is_active=True,
        end_date__lte=timezone.now()
    )
    
    expired_boosts.update(is_active=False)
    return expired_boosts.count()


class VirtualAccount(models.Model):
    """
    Permanent virtual account for a user (Monnify Reserved Account)
    
    CORRECTED: Reserved accounts in Monnify are PERMANENT, not temporary.
    They don't expire unless manually deleted.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]
    
    user_account = models.ForeignKey(
        'UserAccount',  # Your existing UserAccount model
        on_delete=models.CASCADE,
        related_name='virtual_accounts'
    )
    
    # Monnify Details
    account_reference = models.CharField(max_length=100, db_index=True)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=20, db_index=True)
    bank_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=10)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # KYC Information (OPTIONAL - affects transaction limits)
    bvn = models.CharField(max_length=11, blank=True, null=True)
    nin = models.CharField(max_length=11, blank=True, null=True)
    kyc_verified = models.BooleanField(default=False)
    kyc_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Monnify response data (stored as JSON for reference)
    monnify_response = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account_reference']),
            models.Index(fields=['account_number']),
            models.Index(fields=['user_account', 'status']),
        ]
        # Allow multiple bank accounts for same reference (Monnify provides multiple banks)
        unique_together = [['account_reference', 'bank_code']]
    
    def __str__(self):
        return f"{self.account_name} - {self.account_number} ({self.bank_name})"
    
    @property
    def is_active(self):
        """Check if account is active"""
        return self.status == 'active'
    
    @property
    def has_kyc(self):
        """Check if account has KYC verification"""
        return self.kyc_verified and (self.bvn or self.nin)
    
    @property
    def transaction_limit_info(self):
        """Get transaction limit information based on KYC status"""
        if self.bvn and self.nin:
            return {
                'level': 'Maximum',
                'per_transaction': '5,000,000+',
                'daily': 'Unlimited',
                'description': 'Full KYC verified (BVN + NIN)'
            }
        elif self.bvn or self.nin:
            return {
                'level': 'Medium',
                'per_transaction': '1,000,000',
                'daily': '5,000,000',
                'description': 'Partial KYC verified'
            }
        else:
            return {
                'level': 'Basic',
                'per_transaction': '50,000',
                'daily': '300,000',
                'description': 'No KYC verification'
            }
    
    def deactivate(self):
        """Deactivate the virtual account"""
        self.status = 'inactive'
        self.save()


class MonnifyTransaction(models.Model):
    """
    Track all Monnify payment transactions
    
    CORRECTED: Simplified to handle webhook data correctly
    """
    TRANSACTION_STATUS = [
        ('PAID', 'Paid'),
        ('PENDING', 'Pending'),
        ('OVERPAID', 'Overpaid'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('FAILED', 'Failed'),
        ('REVERSED', 'Reversed'),
    ]
    
    # User & Account Info
    user_account = models.ForeignKey(
        'UserAccount',
        on_delete=models.CASCADE,
        related_name='monnify_transactions'
    )
    virtual_account = models.ForeignKey(
        VirtualAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    
    # Monnify Transaction Details
    transaction_reference = models.CharField(max_length=100, unique=True, db_index=True)
    payment_reference = models.CharField(max_length=100, db_index=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    total_payable = models.DecimalField(max_digits=10, decimal_places=2)
    settlement_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_on = models.DateTimeField()
    payment_status = models.CharField(max_length=20, choices=TRANSACTION_STATUS)
    payment_description = models.TextField(blank=True)
    
    # Payment Method Details
    payment_method = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=3, default='NGN')
    
    # Customer Details
    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    
    # Bank Details (from webhook)
    destination_account_number = models.CharField(max_length=20, blank=True)
    destination_account_name = models.CharField(max_length=255, blank=True)
    destination_bank_name = models.CharField(max_length=100, blank=True)
    destination_bank_code = models.CharField(max_length=10, blank=True)
    
    # Processing Status
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    credited_to_account = models.BooleanField(default=False)
    
    # Dashboard Transaction Link
    dashboard_transaction = models.ForeignKey(
        'Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='monnify_transaction'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Full webhook payload (for debugging)
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
        """Process the payment and credit user account"""
        if self.processed or self.payment_status != 'PAID':
            return False
        
        try:
            # Credit user account
            self.user_account.add_funds(
                amount=self.amount_paid,
                transaction_type='deposit',
                description=f"Monnify deposit via {self.payment_method} - {self.transaction_reference}"
            )
            
            # Get the transaction that was just created
            dashboard_transaction = self.user_account.transactions.filter(
                transaction_type='deposit'
            ).order_by('-created_at').first()
            
            # Link to dashboard transaction
            self.dashboard_transaction = dashboard_transaction
            self.processed = True
            self.processed_at = timezone.now()
            self.credited_to_account = True
            self.save()
            
            logger.info(
                f"Payment processed: {self.transaction_reference} - "
                f"₦{self.amount_paid} credited to {self.user_account.user.username}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"Error processing Monnify payment {self.transaction_reference}: {str(e)}",
                exc_info=True
            )
            return False


class PaymentNotification(models.Model):
    """
    Store all webhook notifications from Monnify
    Used for debugging and audit trail
    """
    NOTIFICATION_TYPES = [
        ('SUCCESSFUL_TRANSACTION', 'Successful Transaction'),
        ('FAILED_TRANSACTION', 'Failed Transaction'),
        ('REVERSED_TRANSACTION', 'Reversed Transaction'),
    ]
    
    # Basic Info
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    transaction_reference = models.CharField(max_length=100, db_index=True)
    
    # Processing Status
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True)
    
    # Linked Records
    monnify_transaction = models.ForeignKey(
        MonnifyTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    # Raw Data
    raw_payload = models.JSONField()
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['transaction_reference', 'processed']),
            models.Index(fields=['-received_at']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} - {self.transaction_reference} ({'Processed' if self.processed else 'Pending'})"


# Helper functions for background tasks

def process_pending_monnify_transactions():
    """Background task to process pending Monnify transactions"""
    pending_transactions = MonnifyTransaction.objects.filter(
        payment_status='PAID',
        processed=False
    )
    
    success_count = 0
    for transaction in pending_transactions:
        if transaction.process_payment():
            success_count += 1
    
    logger.info(f"Processed {success_count} pending Monnify transactions")
    return success_count
    """Background task to process pending Monnify transactions"""
    pending_transactions = MonnifyTransaction.objects.filter(
        payment_status='PAID',
        processed=False
    )
    
    success_count = 0
    for transaction in pending_transactions:
        if transaction.process_payment():
            success_count += 1
    
    logger.info(f"Processed {success_count} pending Monnify transactions")
    return success_count