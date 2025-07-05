from django.contrib import admin
from .models import Profile, Location, State, LGA, BusinessVerificationDocument
from django.utils.html import format_html
from django.utils import timezone

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
    list_display = ('address', 'state', 'lga')
    list_filter = ('state', 'lga')
    search_fields = ('address', 'state__name', 'lga__name')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'phone_number', 'get_location', 
        'business_verification_badge', 'business_name'
    )
    list_filter = ('business_verification_status', 'email_verified')
    search_fields = (
        'user__username', 'phone_number', 'business_name', 
        'user__email', 'business_email'
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
                'business_verified_by'
            )
        }),
    )
    
    readonly_fields = ('business_verified_at', 'business_verified_by')
    
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
        updated = queryset.update(
            business_verification_status='verified',
            business_verified_at=timezone.now(),
            business_verified_by=request.user
        )
        self.message_user(request, f'{updated} businesses verified successfully.')
    verify_business.short_description = "Verify selected businesses"
    
    def reject_business(self, request, queryset):
        updated = queryset.update(business_verification_status='rejected')
        self.message_user(request, f'{updated} businesses rejected.')
    reject_business.short_description = "Reject selected businesses"
    
    def get_location(self, obj):
        return str(obj.location) if obj.location else '-'
    get_location.short_description = 'Location'


@admin.register(BusinessVerificationDocument)
class BusinessVerificationDocumentAdmin(admin.ModelAdmin):
    list_display = ('profile', 'document_type', 'verified', 'uploaded_at')
    list_filter = ('document_type', 'verified', 'uploaded_at')
    search_fields = ('profile__user__username', 'profile__business_name', 'description')
    actions = ['mark_as_verified']
    
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(verified=True)
        self.message_user(request, f'{updated} documents marked as verified.')
    mark_as_verified.short_description = "Mark selected documents as verified"