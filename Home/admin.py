from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse, path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseRedirect

from .models import Category, Subcategory, Brand, Product_Listing, Banner, Review, ReviewReply, ProductReport

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'slug')
    list_filter = ('category',)
    search_fields = ('name', 'category__name')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

class ProductReportInline(admin.TabularInline):
    model = ProductReport
    extra = 0
    readonly_fields = ('reason', 'details', 'reporter_email', 'reported_at', 'status')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Product_Listing)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'price', 'created_at', 'view_count', 'report_count', 'suspension_status')
    list_filter = ('category', 'subcategory', 'brand', 'condition', 'created_at', 'is_suspended')
    search_fields = ('title', 'description', 'seller__user__username', 'seller__user__email', 'category__name')
    date_hierarchy = 'created_at'
    list_per_page = 20
    actions = ['suspend_listings', 'unsuspend_listings', 'delete_listings']
    inlines = [ProductReportInline]

    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'seller', 'price', 'condition')
        }),
        ('Categories', {
            'fields': ('category', 'subcategory', 'brand')
        }),
        ('Status', {
            'fields': ('is_suspended', 'suspension_reason', 'suspended_at', 'suspended_by')
        }),
    )
    
    readonly_fields = ('suspended_at', 'suspended_by')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'category', 'subcategory', 'brand', 'seller', 'seller__user'
        ).prefetch_related('reports')

    def report_count(self, obj):
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
        if obj.is_suspended:
            return format_html('<span style="color: red;">Suspended</span>')
        return format_html('<span style="color: green;">Active</span>')
    suspension_status.short_description = 'Status'
    
    def suspend_listings(self, request, queryset):
        if 'apply' in request.POST:
            reason = request.POST.get('suspension_reason', '')
            count = 0
            for product in queryset:
                product.suspend(request.user, reason)
                count += 1
            self.message_user(request, f"{count} listings were suspended successfully.", messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())
        
        return render(request, 'admin/suspend_listings.html', {
            'title': 'Suspend selected listings',
            'queryset': queryset,
            'opts': self.model._meta,
        })
    suspend_listings.short_description = "Suspend selected listings"
    
    def unsuspend_listings(self, request, queryset):
        count = 0
        for product in queryset.filter(is_suspended=True):
            product.unsuspend()
            count += 1
        self.message_user(request, f"{count} listings were unsuspended successfully.", messages.SUCCESS)
    unsuspend_listings.short_description = "Unsuspend selected listings"
    
    def delete_listings(self, request, queryset):
        if 'apply' in request.POST:
            count = queryset.count()
            for product in queryset:
                product.delete()
            self.message_user(request, f"{count} listings were deleted successfully.", messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())
        
        return render(request, 'admin/delete_listings.html', {
            'title': 'Delete selected listings',
            'queryset': queryset,
            'opts': self.model._meta,
        })
    delete_listings.short_description = "Delete selected listings permanently"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'reports/',
                self.admin_site.admin_view(self.product_reports_view),
                name='product_reports',
            ),
        ]
        return custom_urls + urls
    
    def product_reports_view(self, request):
        """View to show all reported products"""
        from django.db.models import Count
        
        # Get all products with reports, ordered by report count
        reported_products = Product_Listing.objects.annotate(
            num_reports=Count('reports')
        ).filter(num_reports__gt=0).order_by('-num_reports')
        
        context = {
            'title': 'Reported Listings',
            'reported_products': reported_products,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/reported_listings.html', context)

@admin.register(ProductReport)
class ProductReportAdmin(admin.ModelAdmin):
    list_display = ('product', 'reason', 'status', 'reported_at', 'reviewed_by')
    list_filter = ('status', 'reason', 'reported_at')
    search_fields = ('product__title', 'details', 'reporter_email')
    date_hierarchy = 'reported_at'
    readonly_fields = ('product', 'reason', 'details', 'reporter_email', 'reported_at')
    fieldsets = (
        (None, {
            'fields': ('product', 'reason', 'details', 'reporter_email', 'reported_at')
        }),
        ('Review', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'resolution_notes')
        }),
    )
    actions = ['mark_as_resolved', 'mark_as_dismissed']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'reviewed_by')
    
    def mark_as_resolved(self, request, queryset):
        for report in queryset:
            report.mark_as_reviewed(request.user, status='resolved', notes='Marked as resolved by admin')
        self.message_user(request, f"{queryset.count()} reports marked as resolved.", messages.SUCCESS)
    mark_as_resolved.short_description = "Mark selected reports as resolved"
    
    def mark_as_dismissed(self, request, queryset):
        for report in queryset:
            report.mark_as_reviewed(request.user, status='dismissed', notes='Marked as dismissed by admin')
        self.message_user(request, f"{queryset.count()} reports marked as dismissed.", messages.SUCCESS)
    mark_as_dismissed.short_description = "Mark selected reports as dismissed"
    
@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_display_name', 'display_location', 'is_active', 'priority', 'start_date', 'end_date')
    list_filter = ('is_active', 'display_location', 'created_at')
    list_editable = ('is_active', 'priority')
    search_fields = ('url', 'id')
    ordering = ('-priority', '-updated_at')
    
    fieldsets = (
        ('Banner Content', {
            'fields': ('image', 'mobile_image', 'url')
        }),
        ('Display Settings', {
            'fields': ('display_location', 'is_active', 'priority', 'background_color')
        }),
        ('Schedule (Optional)', {
            'fields': ('start_date', 'end_date'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def get_display_name(self, obj):
        """Show a more readable display name"""
        return obj.get_display_location_display()
    get_display_name.short_description = 'Location'
    get_display_name.admin_order_field = 'display_location'
    
    def get_queryset(self, request):
        """Optimize database queries"""
        return super().get_queryset(request).select_related()
    
    class Media:
        css = {
            'all': ('admin/css/banner_admin.css',)  # Optional: if you want custom admin CSS
        }

    # Optional: Add custom actions
    actions = ['make_active', 'make_inactive']
    
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} banners were successfully activated.')
    make_active.short_description = "Mark selected banners as active"
    
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} banners were successfully deactivated.')
    make_inactive.short_description = "Mark selected banners as inactive"
    
class ReviewReplyInline(admin.TabularInline):
    model = ReviewReply
    extra = 0
    readonly_fields = ('created_at',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('reviewer', 'product', 'seller', 'rating', 'review_type', 'created_at')
    list_filter = ('review_type', 'rating', 'created_at')
    search_fields = ('reviewer__username', 'product__title', 'seller__user__username', 'comment')
    readonly_fields = ('created_at',)
    inlines = [ReviewReplyInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'reviewer', 'product', 'seller'
        )

@admin.register(ReviewReply)
class ReviewReplyAdmin(admin.ModelAdmin):
    list_display = ('reviewer', 'review', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('reviewer__username', 'comment', 'review__comment')
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'reviewer', 'review'
        )