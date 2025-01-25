from django.contrib import admin
from .models import Category, Subcategory, Brand, Product_Listing, Banner, Review, ReviewReply
from django.utils.html import format_html

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

@admin.register(Product_Listing)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'subcategory', 'brand', 'price', 'condition', 'created_at')
    list_filter = ('category', 'subcategory', 'brand', 'condition', 'created_at')
    search_fields = ('title', 'description', 'seller__username', 'category__name', 'subcategory__name', 'brand__name')
    date_hierarchy = 'created_at'
    list_per_page = 20

    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'seller', 'price', 'condition')
        }),
        ('Categories', {
            'fields': ('category', 'subcategory', 'brand')
        }),
        ('Images', {
            'fields': ('image',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return ('created_at', 'updated_at')
        return ()
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category', 'subcategory', 'brand', 'seller')

    def seller_email(self, obj):
        return obj.seller.user.email
    seller_email.short_description = 'Seller Email'

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return "No Image"
    image_preview.short_description = 'Image Preview'
    
@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('id', 'url', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('url',)
    
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