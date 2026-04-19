from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse, path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.db.models import Count, Avg, Q

from .models import ServiceListing, ServiceImage, ServiceDocument, ServiceInquiry, ServiceReview, ServiceReviewReply
from User.models import ItemReport


class ServiceImageInline(admin.TabularInline):
    """Inline for service images (following Product_Image pattern)"""
    model = ServiceImage
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('image', 'caption', 'is_primary', 'created_at')

class ServiceDocumentInline(admin.TabularInline):
    """Inline for service documents"""
    model = ServiceDocument
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('document', 'title', 'description', 'document_type', 'created_at')

@admin.register(ServiceListing)
class ServiceListingAdmin(admin.ModelAdmin):
    """Admin for service listings (following ProductAdmin pattern)"""
    list_display = [
        'title', 'provider_link', 'category_display', 'service_type', 'pricing_type', 
        'price_display', 'created_at', 'view_count', 'inquiry_count', 
        'report_count', 'suspension_status'
    ]
    list_filter = [
        'service_type', 'pricing_type', 'experience_level', 'availability', 
        'delivery_method', 'category', 'is_active', 'is_featured', 'is_suspended', 'created_at'
    ]
    search_fields = [
        'title', 'description', 'provider__user__username', 'provider__user__email', 
        'what_you_get', 'skills_offered'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'view_count', 'inquiry_count', 
        'hire_count', 'boost_score', 'suspended_at', 'suspended_by'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    actions = ['suspend_services', 'unsuspend_services', 'feature_services', 'unfeature_services']
    inlines = [ServiceImageInline, ServiceDocumentInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'provider', 'title', 'description', 'service_type')
        }),
        ('Categorization', {
            'fields': ('category', 'skills_offered', 'tools_used')
        }),
        ('Pricing & Details', {
            'fields': (
                'pricing_type', 'base_price', 'min_price', 'max_price',
                'experience_level', 'availability', 'delivery_method', 'delivery_time'
            )
        }),
        ('Service Details', {
            'fields': ('languages', 'requirements', 'what_you_get', 'extra_services', 'portfolio_url')
        }),
        ('Location & Contact', {
            'fields': ('serves_nationwide', 'contact_instructions')
        }),
        ('Status & Management', {
            'fields': (
                'is_active', 'is_featured', 'is_suspended', 'suspension_reason', 
                'suspended_at', 'suspended_by'
            )
        }),
        ('Analytics', {
            'fields': (
                'view_count', 'inquiry_count', 'hire_count', 'boost_score',
                'created_at', 'updated_at'
            )
        }),
        ('Reports', {
            'fields': ('report_summary',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'view_count', 'inquiry_count', 
        'hire_count', 'boost_score', 'suspended_at', 'suspended_by', 'report_summary'
    ]
    
    def report_count(self, obj):
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(ServiceListing)
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
        ct = ContentType.objects.get_for_model(ServiceListing)
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
    
    def provider_link(self, obj):
        """Link to provider profile"""
        url = reverse('admin:User_profile_change', args=[obj.provider.id])
        return format_html('<a href="{}">{}</a>', url, obj.provider.user.username)
    provider_link.short_description = 'Provider'
    
    def category_display(self, obj):
        """Display category name"""
        return obj.category_display
    category_display.short_description = 'Category'
    
    def price_display(self, obj):
        """Display formatted price"""
        return obj.price_display
    price_display.short_description = 'Price'
    
    def report_count(self, obj):
        """Display report count with color coding (following existing pattern)"""
        count = obj.reports.count()
        if count > 0:
            return format_html(
                '<span style="color: {};">{}</span>',
                'red' if count > 2 else 'orange' if count > 0 else 'inherit',
                count
            )
        return count
    report_count.short_description = 'Reports'
    
    def suspension_status(self, obj):
        """Display suspension status (following existing pattern)"""
        if obj.is_suspended:
            return format_html('<span style="color: red;">Suspended</span>')
        return format_html('<span style="color: green;">Active</span>')
    suspension_status.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'provider', 'provider__user'
        ).prefetch_related('reports')
    
    def suspend_services(self, request, queryset):
        """Suspend selected services (following existing pattern)"""
        if 'apply' in request.POST:
            reason = request.POST.get('suspension_reason', '')
            count = 0
            for service in queryset:
                service.suspend(request.user, reason)
                count += 1
            self.message_user(request, f"{count} services were suspended successfully.", messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())
        
        return render(request, 'admin/suspend_services.html', {
            'title': 'Suspend selected services',
            'queryset': queryset,
            'opts': self.model._meta,
        })
    suspend_services.short_description = "Suspend selected services"
    
    def unsuspend_services(self, request, queryset):
        """Unsuspend selected services (following existing pattern)"""
        count = 0
        for service in queryset.filter(is_suspended=True):
            service.unsuspend()
            count += 1
        self.message_user(request, f"{count} services were unsuspended successfully.", messages.SUCCESS)
    unsuspend_services.short_description = "Unsuspend selected services"
    
    def feature_services(self, request, queryset):
        """Feature selected services"""
        count = queryset.update(is_featured=True)
        self.message_user(request, f"{count} services were featured successfully.", messages.SUCCESS)
    feature_services.short_description = "Feature selected services"
    
    def unfeature_services(self, request, queryset):
        """Unfeature selected services"""
        count = queryset.update(is_featured=False)
        self.message_user(request, f"{count} services were unfeatured successfully.", messages.SUCCESS)
    unfeature_services.short_description = "Remove featured status"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'reports/',
                self.admin_site.admin_view(self.service_reports_view),
                name='service_reports',
            ),
            path(
                'analytics/',
                self.admin_site.admin_view(self.service_analytics_view),
                name='service_analytics',
            ),
        ]
        return custom_urls + urls
    
    def service_reports_view(self, request):
        """View to show all reported services"""
        from django.db.models import Count
        
        # Get all services with reports, ordered by report count
        reported_services = ServiceListing.objects.annotate(
            num_reports=Count('reports')
        ).filter(num_reports__gt=0).order_by('-num_reports')
        
        context = {
            'title': 'Reported Services',
            'reported_services': reported_services,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/reported_services.html', context)
    
    def service_analytics_view(self, request):
        """View to show service analytics"""
        from django.db.models import Sum
        
        stats = {
            'total_services': ServiceListing.objects.count(),
            'active_services': ServiceListing.objects.filter(is_active=True, is_suspended=False).count(),
            'suspended_services': ServiceListing.objects.filter(is_suspended=True).count(),
            'total_inquiries': ServiceInquiry.objects.count(),
            'total_views': ServiceListing.objects.aggregate(total=Sum('view_count'))['total'] or 0,
            'avg_rating': ServiceReview.objects.aggregate(avg=Avg('rating'))['avg'] or 0,
        }
        
        # Category breakdown (using simplified categories)
        from .models import get_category_stats
        category_stats = get_category_stats()
        
        context = {
            'title': 'Service Analytics',
            'stats': stats,
            'category_stats': category_stats,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/service_analytics.html', context)

@admin.register(ServiceInquiry)
class ServiceInquiryAdmin(admin.ModelAdmin):
    """Admin for service inquiries (following SellerResponse pattern)"""
    list_display = [
        'service_link', 'client_link', 'formatted_budget', 'status', 
        'preferred_contact', 'created_at', 'responded_at'
    ]
    list_filter = ['status', 'preferred_contact', 'created_at']
    search_fields = [
        'service__title', 'client__user__username', 'message', 'requirements'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'service', 'client', 'status')
        }),
        ('Inquiry Details', {
            'fields': ('message', 'budget', 'timeline', 'requirements')
        }),
        ('Contact Information', {
            'fields': ('contact_phone', 'contact_email', 'preferred_contact')
        }),
        ('Provider Response', {
            'fields': ('provider_response', 'provider_quote', 'responded_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )
    
    def service_link(self, obj):
        """Link to service"""
        url = reverse('admin:Services_servicelisting_change', args=[obj.service.id])
        return format_html('<a href="{}">{}</a>', url, obj.service.title[:50])
    service_link.short_description = 'Service'
    
    def client_link(self, obj):
        """Link to client profile"""
        url = reverse('admin:User_profile_change', args=[obj.client.id])
        return format_html('<a href="{}">{}</a>', url, obj.client.user.username)
    client_link.short_description = 'Client'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'service', 'client__user'
        )

@admin.register(ServiceReview)
class ServiceReviewAdmin(admin.ModelAdmin):
    """Admin for service reviews (following ReviewAdmin pattern)"""
    list_display = [
        'reviewer', 'service_link', 'rating', 'communication_rating', 
        'quality_rating', 'timeliness_rating', 'created_at'
    ]
    list_filter = ['rating', 'communication_rating', 'quality_rating', 'timeliness_rating', 'created_at']
    search_fields = ['reviewer__username', 'service__title', 'review_text']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def service_link(self, obj):
        """Link to service"""
        url = reverse('admin:Services_servicelisting_change', args=[obj.service.id])
        return format_html('<a href="{}">{}</a>', url, obj.service.title[:50])
    service_link.short_description = 'Service'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('reviewer', 'service')

@admin.register(ServiceReviewReply)
class ServiceReviewReplyAdmin(admin.ModelAdmin):
    """Admin for service review replies"""
    list_display = ['replier', 'review_service', 'created_at']
    list_filter = ['created_at']
    search_fields = ['replier__username', 'reply_text', 'review__review_text']
    readonly_fields = ['created_at']
    
    def review_service(self, obj):
        return obj.review.service.title[:50]
    review_service.short_description = 'Service'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('replier', 'review', 'review__service')

# Custom admin actions
@admin.action(description='Mark selected services as inactive')
def mark_as_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)

@admin.action(description='Mark selected services as active')
def mark_as_active(modeladmin, request, queryset):
    queryset.update(is_active=True)

# Add actions to admin classes
ServiceListingAdmin.actions.extend([mark_as_inactive, mark_as_active])