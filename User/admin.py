from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.shortcuts import render
from django.contrib import messages
from django.http import HttpResponseRedirect

from .models import (
    Profile, Location, State, LGA, BusinessVerificationDocument, 
    EmailPreferences, BulkEmail, SavedItem, ItemReport
)

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(LGA)
class LGAAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'is_active')
    list_filter = ('state', 'is_active')
    search_fields = ('name', 'state__name')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('address', 'city', 'state', 'lga')
    list_filter = ('state', 'lga')
    search_fields = ('address', 'city', 'state__name', 'lga__name')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'phone_number', 'get_location', 
        'business_verification_badge', 'business_name',
        'total_products_listed', 'total_services_listed', 'total_requests_posted'
    )
    list_filter = ('business_verification_status', 'email_verified', 'available_for_services')
    search_fields = (
        'user__username', 'phone_number', 'business_name', 
        'user__email', 'business_email', 'professional_title'
    )
    actions = ['verify_business', 'reject_business']
    
    fieldsets = (
        (None, {
            'fields': ('user', 'phone_number', 'photo', 'bio')
        }),
        ('Location', {
            'fields': ('location',)
        }),
        ('Email Verification', {
            'fields': ('email_verified', 'email_otp', 'otp_created_at')
        }),
        ('Professional Information', {
            'fields': (
                'professional_title', 'skills', 'years_of_experience',
                'available_for_services', 'service_availability_note'
            ),
            'classes': ('collapse',)
        }),
        ('Business Information', {
            'fields': (
                'business_name', 'business_registration_number', 'business_type',
                'business_description', 'business_website', 'business_email',
                'business_phone', 'business_address_visible'
            )
        }),
        ('Business Verification', {
            'fields': (
                'business_verification_status', 'business_verified_at', 
                'business_verified_by', 'business_rejection_reason',
                'business_verification_notes'
            )
        }),
        ('Business Features', {
            'fields': (
                'permanent_listing_enabled', 'priority_support', 'featured_store'
            ),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'total_products_listed', 'total_services_listed', 'total_requests_posted',
                'seller_average_rating', 'total_seller_reviews',
                'service_provider_rating', 'total_service_reviews',
                'buyer_rating', 'total_buyer_reviews'
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = (
        'business_verified_at', 'business_verified_by',
        'total_products_listed', 'total_services_listed', 'total_requests_posted',
        'seller_average_rating', 'total_seller_reviews',
        'service_provider_rating', 'total_service_reviews',
        'buyer_rating', 'total_buyer_reviews'
    )
    
    def business_verification_badge(self, obj):
        if obj.business_verification_status == 'verified':
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Verified</span>'
            )
        elif obj.business_verification_status == 'pending':
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳ Pending</span>'
            )
        elif obj.business_verification_status == 'rejected':
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Rejected</span>'
            )
        return format_html(
            '<span style="color: gray;">Not Applied</span>'
        )
    business_verification_badge.short_description = 'Business Status'
    
    def verify_business(self, request, queryset):
        updated = 0
        for profile in queryset:
            profile.verify_business(request.user, "Verified via admin action")
            updated += 1
        self.message_user(request, f'{updated} businesses verified successfully.')
    verify_business.short_description = "Verify selected businesses"
    
    def reject_business(self, request, queryset):
        updated = 0
        for profile in queryset:
            profile.reject_business_verification(reason="Rejected via admin action")
            updated += 1
        self.message_user(request, f'{updated} businesses rejected.')
    reject_business.short_description = "Reject selected businesses"
    
    def get_location(self, obj):
        return str(obj.location) if obj.location else '-'
    get_location.short_description = 'Location'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'location', 'location__state', 'location__lga'
        )

@admin.register(BusinessVerificationDocument)
class BusinessVerificationDocumentAdmin(admin.ModelAdmin):
    list_display = ('profile_link', 'document_type', 'verified', 'uploaded_at')
    list_filter = ('document_type', 'verified', 'uploaded_at')
    search_fields = ('profile__user__username', 'profile__business_name', 'description')
    readonly_fields = ('uploaded_at',)
    actions = ['mark_as_verified', 'mark_as_unverified']
    
    def profile_link(self, obj):
        url = reverse('admin:User_profile_change', args=[obj.profile.id])
        return format_html('<a href="{}">{}</a>', url, obj.profile.user.username)
    profile_link.short_description = 'Profile'
    
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(verified=True)
        self.message_user(request, f'{updated} documents marked as verified.')
    mark_as_verified.short_description = "Mark selected documents as verified"
    
    def mark_as_unverified(self, request, queryset):
        updated = queryset.update(verified=False)
        self.message_user(request, f'{updated} documents marked as unverified.')
    mark_as_unverified.short_description = "Mark selected documents as unverified"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile', 'profile__user')

@admin.register(EmailPreferences)
class EmailPreferencesAdmin(admin.ModelAdmin):
    list_display = ('profile_link', 'receive_marketing', 'receive_announcements', 'receive_notifications', 'is_completely_unsubscribed')
    list_filter = ('receive_marketing', 'receive_announcements', 'receive_notifications')
    search_fields = ('profile__user__username', 'profile__user__email')
    readonly_fields = ('unsubscribe_token', 'token_created_at')
    
    def profile_link(self, obj):
        url = reverse('admin:User_profile_change', args=[obj.profile.id])
        return format_html('<a href="{}">{}</a>', url, obj.profile.user.username)
    profile_link.short_description = 'Profile'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile', 'profile__user')

@admin.register(BulkEmail)
class BulkEmailAdmin(admin.ModelAdmin):
    list_display = ('title', 'campaign_type', 'status', 'total_sent', 'created_by', 'created_at', 'sent_at')
    list_filter = ('campaign_type', 'status', 'created_at')
    search_fields = ('title', 'subject', 'message')
    readonly_fields = ('total_sent', 'sent_at', 'created_at')
    
    fieldsets = (
        ('Campaign Information', {
            'fields': ('title', 'campaign_type', 'subject', 'message')
        }),
        ('Targeting', {
            'fields': ('target_all', 'verified_only', 'business_only')
        }),
        ('Status', {
            'fields': ('status', 'total_sent', 'created_by', 'created_at', 'sent_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')

@admin.register(ItemReport)
class ItemReportAdmin(admin.ModelAdmin):
    """Unified admin for all item reports (Products, Services, Requests)"""
    list_display = [
        'item_type_display', 'item_title_link', 'reason', 'status', 
        'reported_at', 'reviewed_by'
    ]
    list_filter = ['status', 'reason', 'reported_at']
    search_fields = ['object_id', 'details', 'reporter_email']
    date_hierarchy = 'reported_at'
    readonly_fields = ['content_type', 'object_id', 'reported_at', 'item_url']
    actions = ['mark_as_resolved', 'mark_as_dismissed', 'suspend_reported_items']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('content_type', 'object_id', 'item_type_display', 
                      'reason', 'details', 'reporter_email', 'reported_at')
        }),
        ('Review Information', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'resolution_notes')
        }),
        ('Quick Actions', {
            'fields': ('item_url',),
            'description': 'Click to view the reported item'
        }),
    )
    
    def item_type_display(self, obj):
        icons = {
            'product': '📦',
            'service': '🛠️',
            'request': '🔍'
        }
        icon = icons.get(obj.item_type, '📌')
        return format_html(f'{icon} {obj.item_type_display}')
    item_type_display.short_description = 'Type'
    
    def item_title_link(self, obj):
        if obj.item_url:
            return format_html('<a href="{}" target="_blank">{}</a>', 
                             obj.item_url, obj.item_title)
        return obj.item_title
    item_title_link.short_description = 'Item'
    
    def mark_as_resolved(self, request, queryset):
        for report in queryset:
            report.mark_as_reviewed(request.user, 'resolved', 
                                   'Marked as resolved by admin')
        self.message_user(request, f"{queryset.count()} reports resolved.", 
                         messages.SUCCESS)
    mark_as_resolved.short_description = "Mark as resolved"
    
    def mark_as_dismissed(self, request, queryset):
        for report in queryset:
            report.mark_as_reviewed(request.user, 'dismissed', 
                                   'Marked as dismissed by admin')
        self.message_user(request, f"{queryset.count()} reports dismissed.", 
                         messages.SUCCESS)
    mark_as_dismissed.short_description = "Mark as dismissed"
    
    def suspend_reported_items(self, request, queryset):
        """Suspend all reported items in selected reports"""
        if 'apply' in request.POST:
            reason = request.POST.get('suspension_reason', 
                                    'Multiple reports received')
            count = 0
            for report in queryset:
                if report.suspend_item(request.user, reason):
                    count += 1
            self.message_user(request, 
                            f"{count} items suspended successfully.", 
                            messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())
        
        return render(request, 'admin/suspend_reported_items.html', {
            'title': 'Suspend reported items',
            'queryset': queryset,
            'opts': self.model._meta,
        })
    suspend_reported_items.short_description = "Suspend reported items"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'content_type', 'reviewed_by'
        )

@admin.register(SavedItem)
class SavedItemAdmin(admin.ModelAdmin):
    """Admin for unified saved items (products, services, requests)"""
    list_display = ['user_link', 'item_type', 'item_title', 'item_icon_display', 'saved_at']
    list_filter = ['content_type', 'saved_at']
    search_fields = ['user__username', 'user__email', 'object_id']
    readonly_fields = ['saved_at', 'content_type', 'object_id']
    date_hierarchy = 'saved_at'
    ordering = ['-saved_at']
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def item_title(self, obj):
        try:
            content_obj = obj.content_object
            if content_obj:
                if hasattr(content_obj, 'title'):
                    return content_obj.title[:50]
                return str(content_obj)[:50]
            return "[Deleted Item]"
        except Exception:
            return "[Error Loading Item]"
    item_title.short_description = 'Item'
    
    def item_icon_display(self, obj):
        icons = {
            'product': '📦',
            'service': '🛠️',
            'request': '🔍'
        }
        return icons.get(obj.item_type, '📌')
    item_icon_display.short_description = 'Type'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'content_type')
    
    def has_add_permission(self, request):
        # Users save items through the frontend, not admin
        return False