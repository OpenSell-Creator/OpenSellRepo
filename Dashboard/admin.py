from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    AffiliateProfile, Referral, AffiliateCommission, 
    AffiliateWithdrawal, UserAccount, Transaction
)
from django.utils import timezone
from datetime import timedelta
from .models import AccountStatus, UserAccount, Transaction, ProductBoost, AffiliateProfile, Referral

@admin.register(AccountStatus)
class AccountStatusAdmin(admin.ModelAdmin):
    # UPDATED: Changed yearly_price to two_month_price
    list_display = ('name', 'tier_type', 'colored_tier', 'monthly_price', 'two_month_price', 
                    'max_listings', 'boost_discount', 'is_subscription_based')
    list_filter = ('tier_type',)
    search_fields = ('name',)
    
    # Add fieldsets for better organization
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'tier_type', 'description', 'benefits')
        }),
        ('Pricing', {
            'fields': ('monthly_price', 'two_month_price'),
            'description': 'Monthly: ₦2,000 | Two Months: ₦3,800'
        }),
        ('Benefits & Limits', {
            'fields': ('max_listings', 'listing_discount', 'boost_discount', 
                      'featured_listings', 'priority_support', 'analytics_access')
        }),
        ('Legacy', {
            'fields': ('min_balance',),
            'classes': ('collapse',),
            'description': 'Kept for backward compatibility'
        })
    )
    
    def colored_tier(self, obj):
        colors = {
            'free': '#6c757d',
            'pro': '#007bff',
            'enterprise': '#28a745'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.tier_type, '#000'),
            obj.get_tier_type_display()
        )
    colored_tier.short_description = 'Tier'
    
    def is_subscription_based(self, obj):
        return obj.is_subscription_based
    is_subscription_based.boolean = True
    is_subscription_based.short_description = 'Subscription?'

@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'current_status', 'subscription_status', 
                    'subscription_type_display', 'subscription_end', 'created_at')
    search_fields = ('user__username', 'user__email')
    list_filter = ('status__tier_type', 'status')
    date_hierarchy = 'created_at'
    readonly_fields = ('subscription_info_display', 'balance', 'created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'balance', 'status')
        }),
        ('Subscription Details', {
            'fields': ('subscription_info_display',),
            'description': 'Current subscription information'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_deposit_date'),
            'classes': ('collapse',)
        })
    )
    
    def current_status(self, obj):
        effective = obj.effective_status
        if effective:
            color = '#28a745' if obj.is_subscription_active else '#6c757d'
            return format_html(
                '<span style="color: {};">{}</span>',
                color,
                effective.name
            )
        return '-'
    current_status.short_description = 'Current Status'
    
    def subscription_status(self, obj):
        if obj.subscription_info and obj.subscription_info['active']:
            return format_html('<span style="color: #28a745;">✓ Active</span>')
        elif obj.status and obj.status.is_subscription_based:
            return format_html('<span style="color: #dc3545;">✗ Expired</span>')
        return '-'
    subscription_status.short_description = 'Subscription'
    
    # NEW: Display subscription type (monthly or two_month)
    def subscription_type_display(self, obj):
        if obj.subscription_info and obj.subscription_info['active']:
            sub_type = obj.subscription_info['type']
            if sub_type == 'two_month':
                return format_html('<span style="color: #007bff;">📅 Two Months</span>')
            else:
                return format_html('<span style="color: #17a2b8;">📅 Monthly</span>')
        return '-'
    subscription_type_display.short_description = 'Plan Type'
    
    def subscription_end(self, obj):
        if obj.subscription_info and obj.subscription_info['active']:
            end_date = obj.subscription_info['end_date']
            days_left = (end_date - timezone.now()).days
            color = '#dc3545' if days_left < 7 else '#28a745'
            return format_html(
                '<span style="color: {};">{} ({} days)</span>',
                color,
                end_date.strftime('%Y-%m-%d'),
                days_left
            )
        return '-'
    subscription_end.short_description = 'Expires'
    
    def subscription_info_display(self, obj):
        info = obj.subscription_info
        if not info:
            return format_html('<span style="color: #6c757d;">No active subscription</span>')
        
        # UPDATED: Better display for two_month vs monthly
        plan_type = "Two Months" if info['type'] == 'two_month' else "Monthly"
        status_color = '#28a745' if info['active'] else '#dc3545'
        status_text = 'Active ✓' if info['active'] else 'Expired ✗'
        
        return format_html(
            """
            <div style="line-height: 1.8;">
                <strong>Plan Type:</strong> <span style="color: #007bff;">{}</span><br>
                <strong>Started:</strong> {}<br>
                <strong>Expires:</strong> {}<br>
                <strong>Status:</strong> <span style="color: {}; font-weight: bold;">{}</span>
            </div>
            """,
            plan_type,
            info['start_date'].strftime('%Y-%m-%d %H:%M'),
            info['end_date'].strftime('%Y-%m-%d %H:%M'),
            status_color,
            status_text
        )
    subscription_info_display.short_description = 'Subscription Details'
    
    actions = ['check_and_update_status', 'export_subscribers']
    
    def check_and_update_status(self, request, queryset):
        updated = 0
        for account in queryset:
            old_status = account.status
            account.check_and_update_status()
            if account.status != old_status:
                updated += 1
        
        self.message_user(request, f"Updated {updated} account statuses.")
    check_and_update_status.short_description = "Check and update subscription status"
    
    # NEW: Export subscribers action
    def export_subscribers(self, request, queryset):
        """Export subscriber information"""
        pro_users = queryset.filter(status__tier_type='pro')
        active_count = sum(1 for account in pro_users if account.is_subscription_active)
        
        self.message_user(
            request, 
            f"Found {pro_users.count()} Pro users ({active_count} with active subscriptions)"
        )
    export_subscribers.short_description = "Count Pro subscribers"

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('account', 'colored_amount', 'transaction_type', 'description', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('account__user__username', 'description', 'reference_id')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('account', 'amount', 'transaction_type', 'description')
        }),
        ('Reference', {
            'fields': ('reference_id',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def colored_amount(self, obj):
        color = '#28a745' if obj.amount > 0 else '#dc3545'
        symbol = '+' if obj.amount > 0 else ''
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}₦{:,.2f}</span>',
            color,
            symbol,
            abs(obj.amount)
        )
    colored_amount.short_description = 'Amount'
    
    # Add filter for subscription transactions
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('account', 'account__user')
    
    # NEW: Quick filters
    def has_add_permission(self, request):
        # Prevent manual transaction creation through admin
        return False

@admin.register(ProductBoost)
class ProductBoostAdmin(admin.ModelAdmin):
    list_display = ('product', 'boost_type', 'final_cost', 'original_cost', 'discount_applied', 
                    'product_seller', 'tier_at_purchase', 'start_date', 'end_date', 'boost_status')
    list_filter = ('boost_type', 'is_active', 'start_date', 'tier_at_purchase')
    search_fields = ('product__title', 'product__seller__user__username')
    date_hierarchy = 'start_date'
    readonly_fields = ('start_date', 'transaction', 'tier_at_purchase', 'savings_amount', 
                      'days_remaining_display', 'boost_progress')
    
    fieldsets = (
        ('Product Information', {
            'fields': ('product', 'boost_type', 'duration_days')
        }),
        ('Pricing Details', {
            'fields': ('original_cost', 'final_cost', 'discount_applied', 'savings_amount', 'tier_at_purchase')
        }),
        ('Timing & Status', {
            'fields': ('start_date', 'end_date', 'is_active', 'days_remaining_display', 'boost_progress')
        }),
        ('Related Records', {
            'fields': ('user_account', 'transaction'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queries by selecting related objects"""
        return super().get_queryset(request).select_related(
            'product', 'product__seller', 'product__seller__user', 'user_account', 'transaction'
        )
    
    def product_seller(self, obj):
        """Display the seller's username"""
        return obj.product.seller.user.username if obj.product.seller else 'N/A'
    product_seller.short_description = 'Seller'
    product_seller.admin_order_field = 'product__seller__user__username'
    
    def savings_amount(self, obj):
        """Display the amount saved with discount"""
        savings = obj.original_cost - obj.final_cost
        if savings > 0:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">₦{:,.2f}</span>',
                savings
            )
        return "₦0.00"
    savings_amount.short_description = 'Savings'
    
    def days_remaining_display(self, obj):
        """Display remaining days for active boosts"""
        if obj.is_expired:
            return format_html('<span style="color: #dc3545;">Expired</span>')
        elif obj.is_active:
            days = obj.days_remaining
            color = '#dc3545' if days < 2 else '#28a745'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} days</span>',
                color,
                days
            )
        else:
            return format_html('<span style="color: #6c757d;">Inactive</span>')
    days_remaining_display.short_description = 'Days Left'
    
    def boost_status(self, obj):
        """Display boost status with icon"""
        if obj.is_expired:
            return format_html('<span style="color: #dc3545;">⏹ Expired</span>')
        elif obj.is_active:
            return format_html('<span style="color: #28a745;">▶ Active</span>')
        else:
            return format_html('<span style="color: #6c757d;">⏸ Inactive</span>')
    boost_status.short_description = 'Status'
    
    def boost_progress(self, obj):
        """Display a visual progress bar"""
        if obj.is_expired or not obj.is_active:
            return '-'
        
        total_seconds = (obj.end_date - obj.start_date).total_seconds()
        elapsed_seconds = (timezone.now() - obj.start_date).total_seconds()
        percentage = min(100, max(0, (elapsed_seconds / total_seconds) * 100))
        
        color = '#28a745' if percentage < 75 else '#ffc107' if percentage < 90 else '#dc3545'
        
        return format_html(
            '''
            <div style="width: 100px; background-color: #e9ecef; border-radius: 4px; overflow: hidden;">
                <div style="width: {}%; background-color: {}; height: 20px; text-align: center; color: white; font-size: 11px; line-height: 20px;">
                    {}%
                </div>
            </div>
            ''',
            percentage,
            color,
            int(percentage)
        )
    boost_progress.short_description = 'Progress'
    
    actions = ['deactivate_boosts', 'activate_boosts', 'export_boost_stats']
    
    def deactivate_boosts(self, request, queryset):
        """Admin action to deactivate selected boosts"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Successfully deactivated {updated} boosts.")
    deactivate_boosts.short_description = "Deactivate selected boosts"
    
    def activate_boosts(self, request, queryset):
        """Admin action to activate selected boosts (only non-expired ones)"""
        active_queryset = queryset.filter(end_date__gt=timezone.now())
        updated = active_queryset.update(is_active=True)
        expired_count = queryset.count() - updated
        
        if updated:
            self.message_user(request, f"Successfully activated {updated} boosts.")
        if expired_count:
            self.message_user(
                request, 
                f"{expired_count} boosts could not be activated because they have expired.", 
                level='WARNING'
            )
    activate_boosts.short_description = "Activate selected boosts (non-expired only)"
    
    def export_boost_stats(self, request, queryset):
        """Export boost statistics"""
        from decimal import Decimal
        
        total_revenue = sum(boost.final_cost for boost in queryset)
        total_discount_given = sum(boost.original_cost - boost.final_cost for boost in queryset)
        pro_boosts = queryset.filter(tier_at_purchase__icontains='Pro').count()
        
        self.message_user(
            request,
            f"Stats: {queryset.count()} boosts | "
            f"Revenue: ₦{total_revenue:,.2f} | "
            f"Discounts: ₦{total_discount_given:,.2f} | "
            f"Pro Users: {pro_boosts}"
        )
    export_boost_stats.short_description = "View boost statistics"
    
@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(admin.ModelAdmin):
    list_display = [
        'referral_code', 'user_link', 'status', 'total_referrals_count', 
        'active_referrals_count', 'pending_balance_display', 
        'available_balance_display', 'total_earned_display', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'approved_at']
    search_fields = ['user__username', 'user__email', 'referral_code']
    readonly_fields = [
        'referral_code', 'pending_balance', 'available_balance', 
        'total_earned', 'total_withdrawn', 'created_at', 'updated_at',
        'approved_at', 'approved_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'referral_code', 'status')
        }),
        ('Commission Rates (%)', {
            'fields': ('funding_commission_rate', 'boost_commission_rate', 'subscription_commission_rate')
        }),
        ('Balance Information', {
            'fields': ('pending_balance', 'available_balance', 'total_earned', 'total_withdrawn', 'minimum_withdrawal')
        }),
        ('Application Details', {
            'fields': ('application_reason', 'admin_notes')
        }),
        ('Approval Information', {
            'fields': ('approved_by', 'approved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['approve_affiliates', 'suspend_affiliates', 'reject_affiliates']
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def total_referrals_count(self, obj):
        count = obj.referrals.count()
        url = reverse('admin:Dashboard_referral_changelist') + f'?affiliate__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    total_referrals_count.short_description = 'Total Referrals'
    
    def active_referrals_count(self, obj):
        count = obj.referrals.filter(status='active').count()
        return count
    active_referrals_count.short_description = 'Active'
    
    def pending_balance_display(self, obj):
        # FIXED: Format the value first, then pass to format_html
        amount = f'{float(obj.pending_balance):,.2f}'
        return format_html('<span style="color: orange;">₦{}</span>', amount)
    pending_balance_display.short_description = 'Pending'
    
    def available_balance_display(self, obj):
        # FIXED: Format the value first, then pass to format_html
        amount = f'{float(obj.available_balance):,.2f}'
        return format_html('<span style="color: green; font-weight: bold;">₦{}</span>', amount)
    available_balance_display.short_description = 'Available'
    
    def total_earned_display(self, obj):
        return f'₦{float(obj.total_earned):,.2f}'
    total_earned_display.short_description = 'Total Earned'
    
    def approve_affiliates(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='active',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} affiliate(s) approved successfully.')
    approve_affiliates.short_description = "✅ Approve selected affiliates"
    
    def suspend_affiliates(self, request, queryset):
        updated = queryset.update(status='suspended')
        self.message_user(request, f'{updated} affiliate(s) suspended.')
    suspend_affiliates.short_description = "⏸️ Suspend selected affiliates"
    
    def reject_affiliates(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, f'{updated} affiliate(s) rejected.')
    reject_affiliates.short_description = "❌ Reject selected affiliates"

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = [
        'referred_user_link', 'affiliate_link', 'status', 'signup_date', 
        'first_qualifying_transaction', 'total_revenue_display', 
        'total_commission_display', 'flagged_for_review'
    ]
    list_filter = ['status', 'signup_date', 'flagged_for_review']
    search_fields = ['referred_user__username', 'affiliate__referral_code', 'signup_ip']
    readonly_fields = [
        'signup_date', 'signup_ip', 'first_qualifying_transaction',
        'total_revenue_generated', 'total_commission_earned'
    ]
    
    fieldsets = (
        ('Referral Information', {
            'fields': ('affiliate', 'referred_user', 'referral_code_used', 'status')
        }),
        ('Tracking', {
            'fields': ('signup_ip', 'signup_date', 'first_qualifying_transaction')
        }),
        ('Performance', {
            'fields': ('total_revenue_generated', 'total_commission_earned')
        }),
        ('Fraud Detection', {
            'fields': ('flagged_for_review', 'fraud_reason'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_fraud', 'mark_as_active']
    
    def referred_user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.referred_user.id])
        return format_html('<a href="{}">{}</a>', url, obj.referred_user.username)
    referred_user_link.short_description = 'Referred User'
    
    def affiliate_link(self, obj):
        url = reverse('admin:Dashboard_affiliateprofile_change', args=[obj.affiliate.id])
        return format_html('<a href="{}">{}</a>', url, obj.affiliate.referral_code)
    affiliate_link.short_description = 'Affiliate'
    
    def total_revenue_display(self, obj):
        return f'₦{float(obj.total_revenue_generated):,.2f}'
    total_revenue_display.short_description = 'Revenue Generated'
    
    def total_commission_display(self, obj):
        return f'₦{float(obj.total_commission_earned):,.2f}'
    total_commission_display.short_description = 'Commission Earned'
    
    def mark_as_fraud(self, request, queryset):
        updated = queryset.update(status='fraud', flagged_for_review=True)
        self.message_user(request, f'{updated} referral(s) marked as fraud.')
    mark_as_fraud.short_description = "🚨 Mark as fraud"
    
    def mark_as_active(self, request, queryset):
        updated = queryset.update(status='active', flagged_for_review=False, fraud_reason='')
        self.message_user(request, f'{updated} referral(s) marked as active.')
    mark_as_active.short_description = "✅ Mark as active"


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(admin.ModelAdmin):
    list_display = [
        'affiliate_link', 'referral_link', 'transaction_type', 
        'base_amount_display', 'commission_rate', 'commission_amount_display',
        'status', 'created_at', 'instant_availability_badge'
    ]
    list_filter = ['status', 'transaction_type', 'created_at']
    search_fields = ['affiliate__referral_code', 'referral__referred_user__username']
    readonly_fields = [
        'affiliate', 'referral', 'transaction_type', 'base_amount', 
        'commission_rate', 'commission_amount', 'source_transaction',
        'created_at', 'available_at'
    ]
    
    fieldsets = (
        ('Commission Details', {
            'fields': ('affiliate', 'referral', 'transaction_type', 'status')
        }),
        ('Amounts', {
            'fields': ('base_amount', 'commission_rate', 'commission_amount')
        }),
        ('Related Transaction', {
            'fields': ('source_transaction',)
        }),
        ('Timing', {
            'fields': ('created_at', 'available_at'),
            'description': 'Commissions are INSTANTLY available (no hold period)'
        }),
    )
    
    def affiliate_link(self, obj):
        url = reverse('admin:Dashboard_affiliateprofile_change', args=[obj.affiliate.id])
        return format_html('<a href="{}">{}</a>', url, obj.affiliate.referral_code)
    affiliate_link.short_description = 'Affiliate'
    
    def referral_link(self, obj):
        url = reverse('admin:Dashboard_referral_change', args=[obj.referral.id])
        return format_html('<a href="{}">{}</a>', url, obj.referral.referred_user.username)
    referral_link.short_description = 'Referred User'
    
    def base_amount_display(self, obj):
        return f'N{float(obj.base_amount):,.2f}'
    base_amount_display.short_description = 'Base Amount'
    
    def commission_amount_display(self, obj):
        amount = f'{float(obj.commission_amount):,.2f}'
        # Show green for available/paid, orange for pending
        color = 'green' if obj.status == 'available' else 'orange' if obj.status == 'pending' else 'gray'
        return format_html(
            '<span style="color: {}; font-weight: bold;">N{}</span>', 
            color, amount
        )
    commission_amount_display.short_description = 'Commission'
    
    def instant_availability_badge(self, obj):
        """Show instant availability badge"""
        if obj.status == 'available':
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Instant</span>'
            )
        elif obj.status == 'pending':
            return format_html(
                '<span style="color: orange;">⏳ Pending</span>'
            )
        else:
            return format_html(
                '<span style="color: gray;">● {}</span>', obj.get_status_display()
            )
    instant_availability_badge.short_description = 'Availability'
    
@admin.register(AffiliateWithdrawal)
class AffiliateWithdrawalAdmin(admin.ModelAdmin):
    list_display = [
        'affiliate_link', 'amount_display', 'status', 'payment_method',
        'account_details', 'requested_at', 'processed_at'
    ]
    list_filter = ['status', 'payment_method', 'requested_at']
    search_fields = ['affiliate__referral_code', 'account_number', 'account_name']
    readonly_fields = ['affiliate', 'amount', 'requested_at']
    
    fieldsets = (
        ('Withdrawal Information', {
            'fields': ('affiliate', 'amount', 'status')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'bank_name', 'account_number', 'account_name')
        }),
        ('Processing', {
            'fields': ('processed_by', 'processed_at', 'payment_reference', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('requested_at',)
        }),
    )
    
    actions = ['approve_withdrawals', 'mark_as_completed', 'reject_withdrawals']
    
    def affiliate_link(self, obj):
        url = reverse('admin:Dashboard_affiliateprofile_change', args=[obj.affiliate.id])
        return format_html('<a href="{}">{}</a>', url, obj.affiliate.referral_code)
    affiliate_link.short_description = 'Affiliate'
    
    def amount_display(self, obj):
        amount = f'{float(obj.amount):,.2f}'
        return format_html('<span style="font-weight: bold;">N{}</span>', amount)
    amount_display.short_description = 'Amount'
    
    def account_details(self, obj):
        return f'{obj.bank_name} - {obj.account_number}'
    account_details.short_description = 'Account'
    
    def approve_withdrawals(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='approved',
            processed_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f'{updated} withdrawal(s) approved.')
    approve_withdrawals.short_description = "✅ Approve withdrawals"
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.filter(status__in=['pending', 'approved', 'processing']).update(
            status='completed',
            processed_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f'{updated} withdrawal(s) marked as completed.')
    mark_as_completed.short_description = "✔️ Mark as completed"
    
    def reject_withdrawals(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='rejected',
            processed_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f'{updated} withdrawal(s) rejected.')
    reject_withdrawals.short_description = "❌ Reject withdrawals"