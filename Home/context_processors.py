# In context_processors.py

from django.db.models import Count, Prefetch
from .models import Category, Subcategory

def categories_with_counts(request):
    """
    Context processor to provide categories with counts to all templates
    """
    # Get category counts using annotation
    categories = Category.objects.annotate(
        product_count=Count('product_listing')
    )
    
    # Get subcategory counts
    subcategories = Subcategory.objects.annotate(
        product_count=Count('products')
    )
    
    # Prefetch annotated subcategories with categories
    categories = categories.prefetch_related(
        Prefetch('subcategories', queryset=subcategories)
    )
    
    # Get selected category and subcategory from request (will be None on non-product pages)
    category_slug = request.GET.get('category')
    subcategory_slug = request.GET.get('subcategory')
    
    # Default values
    selected_category_id = None
    selected_subcategory_id = None
    
    # Get ID from slug if available
    if category_slug:
        try:
            category = Category.objects.get(slug=category_slug)
            selected_category_id = category.id
        except Category.DoesNotExist:
            pass
    
    if subcategory_slug:
        try:
            subcategory = Subcategory.objects.get(slug=subcategory_slug)
            selected_subcategory_id = subcategory.id
        except Subcategory.DoesNotExist:
            pass
    
    return {
        'global_categories': categories,
        'selected_category': selected_category_id,
        'selected_subcategory': selected_subcategory_id,
    }