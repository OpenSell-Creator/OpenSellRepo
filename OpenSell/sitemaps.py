from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from Home.models import Product_Listing, Category, Subcategory  # Update with your actual app name
from django.utils import timezone

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'weekly'
    
    def items(self):
        # Update with your actual URL names for static pages
        return ['home', 'about', 'contact', 'terms', 'privacy']
    
    def location(self, item):
        return reverse(item)

class ProductSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7
    
    def items(self):
        # Using your model's actual name (Product_Listing) and fields
        # Filter out expired products
        return Product_Listing.objects.filter(
            deletion_warning_sent=False,
            # Filter products that are not expired
            expiration_date__gt=timezone.now()
        ).order_by('-updated_at')
    
    def lastmod(self, obj):
        return obj.updated_at
    
    def location(self, obj):
        # Your model already has get_absolute_url method which is perfect!
        return obj.get_absolute_url()

class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    
    def items(self):
        return Category.objects.all()
    
    def location(self, obj):
        # Using category_list view with the category parameter
        return f'/categories/?category={obj.id}'

class SubcategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5
    
    def items(self):
        return Subcategory.objects.all()
    
    def location(self, obj):
        # Using category_list view with both category and subcategory parameters
        return f'/categories/?category={obj.category.id}&subcategory={obj.id}'