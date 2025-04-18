from django.contrib import admin

from django.contrib import admin
from .models import AccountStatus, UserAccount, Transaction, ProductBoost

@admin.register(AccountStatus)
class AccountStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_balance', 'max_listings', 'listing_discount')
    search_fields = ('name',)

@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'status', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    list_filter = ('status',)
    date_hierarchy = 'created_at'

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('account', 'amount', 'transaction_type', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('account__user__username', 'description', 'reference_id')
    date_hierarchy = 'created_at'

@admin.register(ProductBoost)
class ProductBoostAdmin(admin.ModelAdmin):
    list_display = ('product', 'boost_type', 'cost', 'start_date', 'end_date', 'is_active')
    list_filter = ('boost_type', 'is_active', 'start_date')
    search_fields = ('product__title', 'product__seller__user__username')
    date_hierarchy = 'start_date'