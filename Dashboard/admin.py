from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import AccountStatus, UserAccount, Transaction, ProductBoost

@admin.register(AccountStatus)
class AccountStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier_type', 'colored_tier', 'monthly_price', 'yearly_price', 
                    'max_listings', 'boost_discount', 'is_subscription_based')
    list_filter = ('tier_type',)
    search_fields = ('name',)
    
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
                    'subscription_end', 'created_at')
    search_fields = ('user__username', 'user__email')
    list_filter = ('status__tier_type', 'status')
    date_hierarchy = 'created_at'
    readonly_fields = ('subscription_info_display',)
    
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
            return "No active subscription"
        
        return format_html(
            """
            <strong>Type:</strong> {}<br>
            <strong>Started:</strong> {}<br>
            <strong>Expires:</strong> {}<br>
            <strong>Status:</strong> {}
            """,
            info['type'].title(),
            info['start_date'].strftime('%Y-%m-%d %H:%M'),
            info['end_date'].strftime('%Y-%m-%d %H:%M'),
            'Active' if info['active'] else 'Expired'
        )
    subscription_info_display.short_description = 'Subscription Details'
    
    actions = ['check_and_update_status']
    
    def check_and_update_status(self, request, queryset):
        updated = 0
        for account in queryset:
            old_status = account.status
            account.check_and_update_status()
            if account.status != old_status:
                updated += 1
        
        self.message_user(request, f"Updated {updated} account statuses.")
    check_and_update_status.short_description = "Check and update subscription status"

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('account', 'colored_amount', 'transaction_type', 'description', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('account__user__username', 'description', 'reference_id')
    date_hierarchy = 'created_at'
    
    def colored_amount(self, obj):
        color = '#28a745' if obj.amount > 0 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">₦{}</span>',
            color,
            abs(obj.amount)
        )
    colored_amount.short_description = 'Amount'
    
@admin.register(ProductBoost)
class ProductBoostAdmin(admin.ModelAdmin):
    list_display = ('product', 'boost_type', 'final_cost', 'original_cost', 'discount_applied', 'start_date', 'end_date', 'is_active')
    list_filter = ('boost_type', 'is_active', 'start_date', 'tier_at_purchase')
    search_fields = ('product__title', 'product__seller__user__username')
    date_hierarchy = 'start_date'
    readonly_fields = ('start_date', 'transaction', 'tier_at_purchase')
    
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
        return f"₦{savings:.2f}" if savings > 0 else "₦0.00"
    savings_amount.short_description = 'Savings'
    
    def days_remaining(self, obj):
        """Display remaining days for active boosts"""
        if obj.is_expired:
            return "Expired"
        elif obj.is_active:
            return f"{obj.days_remaining} days"
        else:
            return "Inactive"
    days_remaining.short_description = 'Status'
    
    # Optional: Add these to list_display if you want them
    # list_display = ('product', 'boost_type', 'final_cost', 'original_cost', 'discount_applied', 'product_seller', 'savings_amount', 'days_remaining', 'start_date', 'end_date', 'is_active')
    
    fieldsets = (
        ('Product Information', {
            'fields': ('product', 'boost_type', 'duration_days')
        }),
        ('Pricing Details', {
            'fields': ('original_cost', 'final_cost', 'discount_applied', 'tier_at_purchase')
        }),
        ('Timing', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Related Records', {
            'fields': ('user_account', 'transaction'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['deactivate_boosts', 'activate_boosts']
    
    def deactivate_boosts(self, request, queryset):
        """Admin action to deactivate selected boosts"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Successfully deactivated {updated} boosts.")
    deactivate_boosts.short_description = "Deactivate selected boosts"
    
    def activate_boosts(self, request, queryset):
        """Admin action to activate selected boosts (only non-expired ones)"""
        from django.utils import timezone
        active_queryset = queryset.filter(end_date__gt=timezone.now())
        updated = active_queryset.update(is_active=True)
        expired_count = queryset.count() - updated
        
        if updated:
            self.message_user(request, f"Successfully activated {updated} boosts.")
        if expired_count:
            self.message_user(request, f"{expired_count} boosts could not be activated because they have expired.", level='WARNING')
    activate_boosts.short_description = "Activate selected boosts (non-expired only)"