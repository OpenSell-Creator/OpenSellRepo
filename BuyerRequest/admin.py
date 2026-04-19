from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render

from .models import BuyerRequest, SellerResponse, RequestAccess, BuyerRequestImage
from User.models import ItemReport

class BuyerRequestImageInline(admin.TabularInline):
    """Inline for request images (following Product_Image pattern)"""
    model = BuyerRequestImage
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('image', 'caption', 'is_primary', 'created_at')

class SellerResponseInline(admin.TabularInline):
    """Inline for seller responses"""
    model = SellerResponse
    extra = 0
    readonly_fields = ('created_at', 'response_score', 'is_verified_seller')
    fields = ('seller', 'response_type', 'offered_price', 'status', 'is_verified_seller', 'response_score', 'created_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('seller__user')

@admin.register(BuyerRequest)
class BuyerRequestAdmin(admin.ModelAdmin):
    """Admin for buyer requests (following ProductAdmin pattern)"""
    list_display = [
        'title', 'buyer_link', 'request_type', 'category_display', 'budget_display', 
        'urgency', 'status', 'response_count', 'view_count', 'created_at', 'expires_at'
    ]
    list_filter = [
        'status', 'request_type', 'urgency', 'category', 'service_category', 'preferred_condition', 
        'is_featured', 'is_suspended', 'created_at', 'expires_at'
    ]
    search_fields = ['title', 'description', 'buyer__user__username', 'buyer__user__email']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'view_count', 'response_count', 'contact_count',
        'boost_score', 'buyer_is_verified_business', 'is_pro_buyer'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    actions = ['suspend_requests', 'unsuspend_requests', 'feature_requests', 'unfeature_requests', 'mark_as_fulfilled']
    inlines = [BuyerRequestImageInline, SellerResponseInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'buyer', 'title', 'description', 'request_type')
        }),
        ('Categorization', {
            'fields': ('category', 'subcategory', 'brand', 'service_category')
        }),
        ('Budget & Requirements', {
            'fields': ('budget_range', 'budget_min', 'budget_max', 'preferred_condition', 'urgency', 'needed_by', 'quantity_needed')
        }),
        ('Service Requirements', {
            'fields': ('project_duration', 'skill_level_required', 'delivery_preference'),
            'classes': ('collapse',)
        }),
        ('Location & Contact', {
            'fields': ('location', 'accept_nationwide', 'show_phone', 'contact_instructions')
        }),
        ('Status & Management', {
            'fields': ('status', 'is_featured', 'is_suspended', 'suspension_reason', 'suspended_at', 'suspended_by')
        }),
        ('Analytics & Quality', {
            'fields': ('view_count', 'response_count', 'contact_count', 'boost_score', 'buyer_is_verified_business', 'is_pro_buyer'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'expires_at', 'last_bumped', 'deletion_warning_sent'),
            'classes': ('collapse',)
        }),
        ('Reports', {
            'fields': ('report_summary',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'view_count', 'response_count', 'contact_count',
        'boost_score', 'buyer_is_verified_business', 'is_pro_buyer', 'report_summary'  # ✅ ADD
    ]
    
    def buyer_link(self, obj):
        """Link to buyer profile"""
        url = reverse('admin:User_profile_change', args=[obj.buyer.id])
        return format_html('<a href="{}">{}</a>', url, obj.buyer.user.username)
    buyer_link.short_description = 'Buyer'
    
    def category_display(self, obj):
        """Display appropriate category"""
        if obj.category:
            return obj.category.name
        elif obj.service_category:
            return dict(obj.SERVICE_CATEGORIES).get(obj.service_category, obj.service_category)
        return 'No category'
    category_display.short_description = 'Category'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'buyer__user', 'category', 'subcategory', 'brand', 'location'
        )
        
    def report_count(self, obj):
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(BuyerRequest)
        count = ItemReport.objects.filter(content_type=ct, object_id=str(obj.id)).count()
        
        if count > 0:
            url = reverse('admin:User_itemreport_changelist') + f'?content_type__id__exact={ct.id}&object_id={obj.id}'
            return format_html(
                '<a href="{}" style="color: {};">{} reports</a>',
                url,
                'red' if count > 2 else 'orange',
                count
            )
        return '0 reports'
    report_count.short_description = 'Reports'
    
    def report_summary(self, obj):
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(BuyerRequest)
        reports = ItemReport.objects.filter(content_type=ct, object_id=str(obj.id)).order_by('-reported_at')
        
        if not reports.exists():
            return format_html('<p>No reports</p>')
        
        html = '<table style="width:100%; border-collapse: collapse;">'
        html += '<tr style="background: #f0f0f0;"><th>Date</th><th>Reason</th><th>Status</th><th>Action</th></tr>'
        
        for report in reports:
            url = reverse('admin:User_itemreport_change', args=[report.id])
            html += f'''
                <tr style="border-bottom: 1px solid #ddd;">
                    <td>{report.reported_at.strftime("%Y-%m-%d %H:%M")}</td>
                    <td>{report.get_reason_display()}</td>
                    <td><span style="color: {"red" if report.status == "pending" else "green"};">{report.get_status_display()}</span></td>
                    <td><a href="{url}">View</a></td>
                </tr>
            '''
        
        html += '</table>'
        return format_html(html)
    report_summary.short_description = 'Reports Summary'
    
    
    def suspend_requests(self, request, queryset):
        """Suspend selected requests"""
        if 'apply' in request.POST:
            reason = request.POST.get('suspension_reason', '')
            count = 0
            for req in queryset:
                req.suspend(request.user, reason)
                count += 1
            self.message_user(request, f"{count} requests were suspended successfully.", messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())
        
        return render(request, 'admin/suspend_requests.html', {
            'title': 'Suspend selected requests',
            'queryset': queryset,
            'opts': self.model._meta,
        })
    suspend_requests.short_description = "Suspend selected requests"
    
    def unsuspend_requests(self, request, queryset):
        """Unsuspend selected requests"""
        count = 0
        for req in queryset.filter(is_suspended=True):
            req.unsuspend()
            count += 1
        self.message_user(request, f"{count} requests were unsuspended successfully.", messages.SUCCESS)
    unsuspend_requests.short_description = "Unsuspend selected requests"
    
    def feature_requests(self, request, queryset):
        """Feature selected requests"""
        count = queryset.update(is_featured=True)
        self.message_user(request, f"{count} requests were featured successfully.", messages.SUCCESS)
    feature_requests.short_description = "Feature selected requests"
    
    def unfeature_requests(self, request, queryset):
        """Unfeature selected requests"""
        count = queryset.update(is_featured=False)
        self.message_user(request, f"{count} requests were unfeatured successfully.", messages.SUCCESS)
    unfeature_requests.short_description = "Remove featured status"
    
    def mark_as_fulfilled(self, request, queryset):
        """Mark selected requests as fulfilled"""
        count = queryset.update(status='fulfilled')
        self.message_user(request, f"{count} requests were marked as fulfilled.", messages.SUCCESS)
    mark_as_fulfilled.short_description = "Mark as fulfilled"

@admin.register(SellerResponse)
class SellerResponseAdmin(admin.ModelAdmin):
    """Admin for seller responses (following existing pattern)"""
    list_display = [
        'buyer_request_link', 'seller_link', 'response_type', 'formatted_price', 
        'status', 'is_verified_seller', 'is_featured_response', 'response_score', 'created_at'
    ]
    list_filter = ['status', 'response_type', 'is_verified_seller', 'is_featured_response', 'created_at']
    search_fields = [
        'buyer_request__title', 'seller__user__username', 'message'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at', 'is_verified_seller', 'response_score']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'buyer_request', 'seller', 'response_type', 'status')
        }),
        ('Related Items', {
            'fields': ('related_product', 'related_service')
        }),
        ('Response Details', {
            'fields': ('message', 'offered_price', 'availability', 'additional_info')
        }),
        ('Product Details', {
            'fields': ('condition_offered', 'quantity_available'),
            'classes': ('collapse',)
        }),
        ('Service Details', {
            'fields': ('delivery_time', 'service_includes'),
            'classes': ('collapse',)
        }),
        ('Contact Information', {
            'fields': ('contact_phone', 'contact_email', 'preferred_contact')
        }),
        ('Quality Indicators', {
            'fields': ('is_verified_seller', 'is_featured_response', 'response_score')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )
    
    def buyer_request_link(self, obj):
        """Link to buyer request"""
        url = reverse('admin:BuyerRequest_buyerrequest_change', args=[obj.buyer_request.id])
        return format_html('<a href="{}">{}</a>', url, obj.buyer_request.title[:50])
    buyer_request_link.short_description = 'Request'
    
    def seller_link(self, obj):
        """Link to seller profile"""
        url = reverse('admin:User_profile_change', args=[obj.seller.id])
        return format_html('<a href="{}">{}</a>', url, obj.seller.user.username)
    seller_link.short_description = 'Seller'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'buyer_request', 'seller__user', 'related_product', 'related_service'
        )

@admin.register(RequestAccess)
class RequestAccessAdmin(admin.ModelAdmin):
    """Admin for request access tracking"""
    list_display = ['user_link', 'request_link', 'accessed_at', 'ip_address']
    list_filter = ['accessed_at']
    search_fields = ['user__username', 'user__email', 'request__title']
    readonly_fields = ['accessed_at']
    date_hierarchy = 'accessed_at'
    ordering = ['-accessed_at']
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def request_link(self, obj):
        url = reverse('admin:BuyerRequest_buyerrequest_change', args=[obj.request.id])
        return format_html('<a href="{}">{}</a>', url, obj.request.title[:50])
    request_link.short_description = 'Request'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'request')

@admin.register(BuyerRequestImage)
class BuyerRequestImageAdmin(admin.ModelAdmin):
    """Admin for request images"""
    list_display = ['request_link', 'image_thumbnail', 'caption', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['buyer_request__title', 'caption']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    def request_link(self, obj):
        url = reverse('admin:BuyerRequest_buyerrequest_change', args=[obj.buyer_request.id])
        return format_html('<a href="{}">{}</a>', url, obj.buyer_request.title[:50])
    request_link.short_description = 'Request'
    
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "No image"
    image_thumbnail.short_description = 'Thumbnail'
