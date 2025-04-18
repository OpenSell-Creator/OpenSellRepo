from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver

class AccountStatus(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    benefits = models.TextField(blank=True)
    min_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_listings = models.PositiveIntegerField(default=5)
    listing_discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Percentage discount
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Account Statuses"

class UserAccount(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('listing_fee', 'Listing Fee'),
        ('boost_fee', 'Boost Fee'),
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
        return f"{self.user.username}'s Account"
    
    def add_funds(self, amount, transaction_type='deposit'):
        """Add funds to user account and record transaction"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        self.balance += Decimal(amount)
        self.save()
        
        # Record transaction
        Transaction.objects.create(
            account=self,
            amount=amount,
            transaction_type=transaction_type,
            description=f"{transaction_type.capitalize()} of {amount}"
        )
        
        # Update account status based on new balance
        self.update_status()
        
        return self.balance
    
    def deduct_funds(self, amount, transaction_type='listing_fee', description=None):
        """Deduct funds from user account and record transaction"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if self.balance < Decimal(amount):
            raise ValueError("Insufficient funds")
        
        self.balance -= Decimal(amount)
        self.save()
        
        # Record transaction
        Transaction.objects.create(
            account=self,
            amount=-amount,  # Negative to indicate outgoing
            transaction_type=transaction_type,
            description=description or f"{transaction_type.capitalize()} of {amount}"
        )
        
        # Update account status based on new balance
        self.update_status()
        
        return self.balance
    
    def update_status(self):
        """Update user status based on balance"""
        eligible_statuses = AccountStatus.objects.filter(
            min_balance__lte=self.balance
        ).order_by('-min_balance')
        
        if eligible_statuses.exists():
            new_status = eligible_statuses.first()
            if self.status != new_status:
                self.status = new_status
                self.save()
                # Could trigger notification here

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

class ProductBoost(models.Model):
    BOOST_TYPES = [
        ('featured', 'Featured Product'),
        ('urgent', 'Urgent Sale'),
        ('spotlight', 'Category Spotlight'),
    ]
    
    product = models.ForeignKey('Home.Product_Listing', on_delete=models.CASCADE, related_name='boosts')
    boost_type = models.CharField(max_length=20, choices=BOOST_TYPES)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.boost_type} for {self.product.title}"


