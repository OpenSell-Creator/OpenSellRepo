from django.db.models import Case, When
from django.db.models.functions import Lower
from django.http import JsonResponse,HttpResponseRedirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import Http404
import requests
import json
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import IntegrityError
from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .models import Product_Listing, Review, ReviewReply, SavedProduct, ProductReport, AIDescriptionUsage
from User.models import LGA, State
from Dashboard.models import ProductBoost
from django.db.models import Q, Avg, Exists, OuterRef, Count
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View
from django.urls import reverse_lazy
from .models import Subcategory,Category,Product_Listing,Brand,Product_Image,Banner
from django.db.models import Prefetch
from django.contrib.auth.models import User
from .forms import ProductSearchForm, ReviewForm,ReviewReplyForm, Review, ProductReportForm, ListingForm
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from django.core.exceptions import ValidationError
from User.models import Profile
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.urls import resolve, Resolver404
from urllib.parse import urlparse
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.cache import cache
from django.db.models import F, Q, Case, When, IntegerField, Value
from random import shuffle
import random
import hashlib
import logging
import uuid
logger = logging.getLogger(__name__)

import os
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET
import json

#PWA Implementation
@csrf_exempt
@cache_control(max_age=0)
def service_worker_view(request):
    """Serve the service worker file"""
    if request.method not in ['GET', 'HEAD']:
        return HttpResponse(status=405)
    
    try:
        if settings.DEBUG:
            sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
        else:
            sw_path = os.path.join(settings.STATIC_ROOT, 'sw.js')
        
        with open(sw_path, 'r', encoding='utf-8') as f:
            sw_content = f.read()
        
        response = HttpResponse(sw_content, content_type='application/javascript')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
        
    except FileNotFoundError:
        basic_sw = '''
        const CACHE_NAME = 'opensell-basic-v1';
        
        self.addEventListener('install', event => {
            console.log('Service Worker installing...');
            self.skipWaiting();
        });
        
        self.addEventListener('activate', event => {
            console.log('Service Worker activating...');
            self.clients.claim();
        });
        
        self.addEventListener('fetch', event => {
            event.respondWith(fetch(event.request));
        });
        '''
        response = HttpResponse(basic_sw, content_type='application/javascript')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

@csrf_exempt
@cache_control(max_age=0)
def manifest_view(request):
    """Serve the manifest.json file"""
    if request.method not in ['GET', 'HEAD']:
        return HttpResponse(status=405)
    
    manifest_data = {
        "name": "OpenSell MarketPlace",
        "short_name": "OpenSell",
        "description": "Buy and sell products on OpenSell marketplace",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#003366",
        "scope": "/",
        "orientation": "portrait-primary",
        "lang": "en",
        "dir": "ltr",
        "categories": ["shopping", "marketplace", "business"],
        "prefer_related_applications": False,
        "icons": [
            {
                "src": "/static/images/logoicon.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/images/logoicon.png", 
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    
    response = JsonResponse(manifest_data, content_type='application/manifest+json')
    response['Cache-Control'] = 'no-cache'
    return response

def offline_view(request):
    """Offline fallback page"""
    context = {
        'title': 'You are offline',
        'message': 'Please check your internet connection and try again.'
    }
    return render(request, 'offline.html', context)

# Create your views here.
def load_subcategories(request):
    category_id = request.GET.get('category')
    subcategories = Subcategory.objects.filter(category_id=category_id).values('id', 'name')
    return JsonResponse(list(subcategories), safe=False)

def get_subcategories(request):
    category_id = request.GET.get('category')
    subcategories = Subcategory.objects.filter(category_id=category_id).values('id', 'name')
    return JsonResponse(list(subcategories), safe=False)

#for Advanced search form
def get_subcategories(request, category_id):
    subcategories = Subcategory.objects.filter(category_id=category_id).values('id', 'name')
    return JsonResponse(list(subcategories), safe=False)

def load_brands(request):
    subcategory_id = request.GET.get('subcategory')
    brands = Brand.objects.filter(subcategories=subcategory_id).values('id', 'name')
    return JsonResponse(list(brands), safe=False)

def get_brands(request, category_id):
    brands = Brand.objects.filter(
        subcategories__category_id=category_id
    ).distinct().values('id', 'name')
    return JsonResponse(list(brands), safe=False)

def get_lgas(request, state_id):
    lgas = LGA.objects.filter(state_id=state_id).values('id', 'name')
    return JsonResponse(list(lgas), safe=False)

def format_price(price):
    return '₦ {:,.0f}'.format(Decimal(price))

def get_sorted_products(base_queryset, user=None, limit=None):
    """
    Hybrid sorting approach that prioritizes:
    1. Boosted products (with boost type hierarchy)
    2. Pro user products
    3. Regular products
    With randomization within each tier
    """
    
    if not base_queryset.exists():
        return []
    
    # Update boost scores for all products
    for product in base_queryset:
        product.boost_score = product.calculate_boost_score()
        product.save(update_fields=['boost_score'])
    
    # Separate products into tiers
    premium_boosted = []  # Premium boost
    spotlight_boosted = []  # Spotlight boost
    featured_boosted = []  # Featured boost
    urgent_boosted = []  # Urgent boost
    pro_products = []  # Non-boosted pro products
    regular_products = []  # Regular products
    
    # Fetch all products with necessary relationships
    products = base_queryset.select_related(
        'seller__user__account',
        'category',
        'subcategory',
        'brand'
    ).prefetch_related(
        'images',
        'boosts'
    )
    
    for product in products:
        try:
            if product.is_boosted:
                boost = product.active_boost
                if boost and boost.boost_type == 'premium':
                    premium_boosted.append(product)
                elif boost and boost.boost_type == 'spotlight':
                    spotlight_boosted.append(product)
                elif boost and boost.boost_type == 'featured':
                    featured_boosted.append(product)
                elif boost and boost.boost_type == 'urgent':
                    urgent_boosted.append(product)
            elif product.is_pro_seller:
                pro_products.append(product)
            else:
                regular_products.append(product)
        except Exception as e:
            # If there's any error with a product, treat it as regular
            regular_products.append(product)
    
    # Randomize within each tier using the random module correctly
    for tier in [premium_boosted, spotlight_boosted, featured_boosted, 
                urgent_boosted, pro_products, regular_products]:
        shuffle(tier)
    
    # Combine with weighted distribution
    final_products = []
    
    # Add all premium boosted products first
    final_products.extend(premium_boosted)
    
    # Mix spotlight and featured (80% spotlight, 20% featured)
    mixed_spotlight_featured = []
    while spotlight_boosted or featured_boosted:
        if spotlight_boosted and (not featured_boosted or random.random() < 0.8):
            mixed_spotlight_featured.append(spotlight_boosted.pop(0))
        elif featured_boosted:
            mixed_spotlight_featured.append(featured_boosted.pop(0))
    final_products.extend(mixed_spotlight_featured)
    
    # Mix urgent and pro (60% urgent, 40% pro)
    mixed_urgent_pro = []
    while urgent_boosted or pro_products:
        if urgent_boosted and (not pro_products or random.random() < 0.6):
            mixed_urgent_pro.append(urgent_boosted.pop(0))
        elif pro_products:
            mixed_urgent_pro.append(pro_products.pop(0))
    
    # Add some regular products in between (20% chance)
    mixed_with_regular = []
    for product in mixed_urgent_pro:
        mixed_with_regular.append(product)
        if regular_products and random.random() < 0.2:
            mixed_with_regular.append(regular_products.pop(0))
    
    final_products.extend(mixed_with_regular)
    
    # Add remaining regular products
    final_products.extend(regular_products)
    
    # Apply limit if specified
    if limit:
        final_products = final_products[:limit]
    
    return final_products

def home(request):
    context = {}
    
    # Create a unique seed for each user to ensure different random selections
    if request.user.is_authenticated:
        seed_string = f"{request.user.id}_{timezone.now().date()}"
        user_seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
    else:
        session_key = request.session.session_key or request.META.get('REMOTE_ADDR', 'anonymous')
        seed_string = f"{session_key}_{timezone.now().date()}"
        user_seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
    
    # Set seed for reproducible randomness per user per day
    random.seed(user_seed)
    
    # Get quality products for hybrid sorting
    quality_products = Product_Listing.objects.filter(
        is_suspended=False,
        expiration_date__gt=timezone.now(),
        price__gt=0,
    )
    
    # Use hybrid sorting for featured products (limit to 20, no pagination)
    featured_products = get_sorted_products(quality_products, request.user, limit=20)
    
    # Get location-based products for authenticated users
    local_products = []
    location_filter_params = {}
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.location:
        user_location = request.user.profile.location
        
        # Build location filter based on available data
        location_filters = Q()
        
        # Priority order: City > LGA > State
        if user_location.city:
            location_filters |= Q(seller__location__city__iexact=user_location.city)
            location_filter_params['city'] = user_location.city
        
        if user_location.lga:
            location_filters |= Q(seller__location__lga=user_location.lga)
            location_filter_params['lga'] = user_location.lga.id
        
        if user_location.state:
            location_filters |= Q(seller__location__state=user_location.state)
            location_filter_params['state'] = user_location.state.id
        
        if location_filters:
            local_quality_products = quality_products.filter(location_filters).exclude(
                id__in=[p.id for p in featured_products[:10]]  # Exclude first 10 featured products
            )
            local_products = get_sorted_products(local_quality_products, request.user, limit=10)
    
    # Get trending products (different criteria)
    trending_products = []
    trending_quality_products = quality_products.filter(
        created_at__gte=timezone.now() - timedelta(days=7),  # Last 7 days
        view_count__gte=5  # At least 5 views
    ).exclude(
        id__in=[p.id for p in featured_products[:10]] + [p.id for p in local_products[:5]]
    ).order_by('-view_count', '-created_at')
    
    trending_products = get_sorted_products(trending_quality_products, request.user, limit=10)
    
    # Reset random seed
    random.seed()
    
    # Handle saved products for authenticated users
    if request.user.is_authenticated:
        saved_products = SavedProduct.objects.filter(
            user=request.user
        ).values_list('product_id', flat=True)
        saved_products_set = set(str(id) for id in saved_products)
        
        # Apply saved status and format prices to all product lists
        for product_list in [featured_products, local_products, trending_products]:
            for product in product_list:
                product.is_saved = str(product.id) in saved_products_set
                product.formatted_price = format_price(product.price)
    else:
        # Format prices for non-authenticated users
        for product_list in [featured_products, local_products, trending_products]:
            for product in product_list:
                product.formatted_price = format_price(product.price)
    
    # Clean up expired listings
    try:
        Product_Listing.delete_expired_listings()
    except:
        pass
    
    # Get categories with product count
    categories = Category.objects.annotate(
        product_count=Count('product_listing')
    ).order_by('-product_count')[:6]
    
    # UPDATED: Get section banners for each location separately using simplified banner system
    first_position_banners = get_active_banners('first')      # Between Featured & Local Products
    second_position_banners = get_active_banners('second')    # Between Local & Trending Products
    global_banners = get_active_banners('global')
    
    # Get global banners for main carousel (if you want to add that later)
    global_banners = get_active_banners('global')
    
    # Determine location display name for local products section
    location_name = None
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.location:
        user_location = request.user.profile.location
        if user_location.city:
            location_name = user_location.city
        elif user_location.lga:
            location_name = user_location.lga.name
        elif user_location.state:
            location_name = user_location.state.name
    
    # Update context with all required data
    context.update({
        'categories': categories,
        'featured_products': featured_products,
        'local_products': local_products,
        'trending_products': trending_products,
        'location_name': location_name,
        'location_filter_params': location_filter_params,
        'first_position_banners': first_position_banners,
        'second_position_banners': second_position_banners,
        'global_banners': global_banners, 
        'active_users_count': User.objects.filter(is_active=True).count(),
        'new_items_last_hour': Product_Listing.objects.filter(
            created_at__gte=timezone.now()-timedelta(hours=1)
        ).count(),
        'total_products': Product_Listing.objects.count(),
    })
    
    return render(request, 'home.html', context)

def get_active_banners(location='global'):
    now = timezone.now()
    return Banner.objects.filter(
        is_active=True,
        display_location=location
    ).filter(
        Q(start_date__isnull=True) | Q(start_date__lte=now)
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=now)
    ).order_by('-priority', '-updated_at')


def get_random_featured_products():
    """Get cached random featured products that refresh every 30 minutes"""
    cache_key = 'random_featured_products'
    featured_products = cache.get(cache_key)
    
    if not featured_products:
        # Get a larger pool and randomly select from it
        product_pool = list(Product_Listing.objects.order_by('-created_at')[:100])
        featured_products = random.sample(product_pool, min(20, len(product_pool)))
        
        # Cache for 30 minutes
        cache.set(cache_key, featured_products, 30 * 60)
    
    return featured_products

def cookie_policy_view(request):
    return render(request, 'pages/cookie_policy.html')

def category_list(request):
    # First, annotate subcategories with product counts
    subcategories = Subcategory.objects.annotate(
        product_count=Count('products')
    )
    
    # Then, fetch categories with their subcategories
    categories = Category.objects.prefetch_related(
        Prefetch('subcategories', queryset=subcategories)
    ).annotate(
        product_count=Count('product_listing')
    ).order_by('-product_count')
    
    selected_category = request.GET.get('category')
    selected_subcategory = request.GET.get('subcategory')
    
    if selected_category:
        selected_category = int(selected_category)
    
    if selected_subcategory:
        selected_subcategory = int(selected_subcategory)
    
    context = {
        'categories': categories,
        'selected_category': selected_category,
        'selected_subcategory': selected_subcategory
    }
    return render(request, 'category_list.html', context)


class ProductListView(ListView):
    model = Product_Listing
    template_name = 'product_list.html'
    context_object_name = 'products'
    paginate_by = 12
    
    def get_queryset(self):
        # Keep your existing get_queryset logic exactly as is
        # [Your existing get_queryset method remains unchanged]
        try:
            Product_Listing.delete_expired_listings()
        except:
            pass
        
        queryset = Product_Listing.objects.filter(
            is_suspended=False
        ).exclude(
            expiration_date__lte=timezone.now()
        )
        
        # [Rest of your filtering logic remains the same]
        category_slug = self.request.GET.get('category')
        subcategory_slug = self.request.GET.get('subcategory')
        brand_slug = self.request.GET.get('brand')
        query = self.request.GET.get('query')
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        condition = self.request.GET.get('condition')
        state = self.request.GET.get('state')
        lga = self.request.GET.get('lga')
        sort_by = self.request.GET.get('sort', 'smart')
        
        # Apply all your existing filters
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )
        
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        if subcategory_slug:
            queryset = queryset.filter(subcategory__slug=subcategory_slug)
        
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)
            
        if min_price:
            try:
                queryset = queryset.filter(price__gte=min_price)
            except (ValueError, TypeError):
                pass
        
        if max_price:
            try:
                queryset = queryset.filter(price__lte=max_price)
            except (ValueError, TypeError):
                pass
        
        if condition:
            queryset = queryset.filter(condition=condition)
        
        if state:
            try:
                queryset = queryset.filter(seller__location__state=state)
            except (ValueError, TypeError):
                pass
        
        if lga:
            try:
                queryset = queryset.filter(seller__location__lga=lga)
            except (ValueError, TypeError):
                pass
        
        # Apply sorting
        if sort_by == 'smart':
            products_list = get_sorted_products(queryset, self.request.user)
            product_ids = [p.id for p in products_list]
            if product_ids:
                preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(product_ids)])
                return Product_Listing.objects.filter(id__in=product_ids).order_by(preserved)
            else:
                return Product_Listing.objects.none()
        else:
            valid_sort_options = {
                '-created_at': '-created_at',
                'created_at': 'created_at', 
                'price': 'price',
                '-price': '-price',
                'title': Lower('title'),
                '-title': Lower('title').desc(),
                'condition': 'condition',
                '-condition': '-condition'
            }
            
            if sort_by in valid_sort_options:
                return queryset.order_by(valid_sort_options[sort_by])
            else:
                return queryset.order_by('-boost_score', '-created_at')

    def paginate_queryset(self, queryset, page_size):
        """Override to handle pagination errors gracefully"""
        paginator = self.get_paginator(
            queryset, page_size, orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty())
        
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
        
        try:
            page_number = int(page)
        except ValueError:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # For AJAX requests, return empty result instead of raising exception
                return (paginator, paginator.page(1), [], False)
            raise Http404("Page is not a number")
        
        try:
            page = paginator.page(page_number)
            return (paginator, page, page.object_list, page.has_other_pages())
        except EmptyPage:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # For AJAX requests, return empty page gracefully
                try:
                    last_page = paginator.page(paginator.num_pages)
                    # Return empty object list but maintain page structure
                    return (paginator, last_page, [], False)
                except EmptyPage:
                    # If there are no pages at all, return empty result
                    dummy_page = paginator.page(1) if paginator.num_pages > 0 else None
                    return (paginator, dummy_page, [], False)
            
            if page_number == 1:
                raise Http404("No products found matching your criteria")
            else:
                raise Http404("Page does not exist")

    def render_to_response(self, context, **response_kwargs):
        # Handle AJAX requests for infinite scroll
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                # Get pagination info
                page_obj = context.get('page_obj')
                paginator = context.get('paginator')
                products = context.get('products', [])
                
                # Check if we have valid pagination data
                if not page_obj or not paginator:
                    return JsonResponse({
                        'success': True,
                        'products_html': [],
                        'has_more': False,
                        'current_page': 1,
                        'total_pages': 0,
                        'message': 'No more results available'
                    })
                
                # Handle case where no products are found
                if not products or len(products) == 0:
                    return JsonResponse({
                        'success': True,
                        'products_html': [],
                        'has_more': False,
                        'current_page': page_obj.number if page_obj else 1,
                        'total_pages': paginator.num_pages if paginator else 0,
                        'message': 'No more results available'
                    })
                
                # Process products and add saved status
                if self.request.user.is_authenticated:
                    saved_products = SavedProduct.objects.filter(
                        user=self.request.user
                    ).values_list('product_id', flat=True)
                    saved_products_set = set(str(id) for id in saved_products)
                    
                    for product in products:
                        product.is_saved = str(product.id) in saved_products_set
                        product.formatted_price = self.format_price(product.price)
                else:
                    for product in products:
                        product.formatted_price = self.format_price(product.price)
                
                # Render products HTML
                from django.template.loader import render_to_string
                products_html = []
                
                for product in products:
                    try:
                        product_html = render_to_string('product_card.html', {
                            'product': product,
                            'user': self.request.user
                        }, request=self.request)
                        products_html.append(product_html)
                    except Exception as e:
                        logger.error(f"Error rendering product {product.id}: {e}")
                        continue
                
                # Determine if there are more pages
                has_more = page_obj.has_next() if page_obj else False
                
                return JsonResponse({
                    'success': True,
                    'products_html': products_html,
                    'has_more': has_more,
                    'current_page': page_obj.number if page_obj else 1,
                    'total_pages': paginator.num_pages if paginator else 0,
                    'total_count': paginator.count if paginator else 0
                })
                
            except Exception as e:
                logger.error(f"Error in AJAX response: {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'An error occurred while loading more products',
                    'products_html': [],
                    'has_more': False,
                    'current_page': 1,
                    'total_pages': 0
                }, status=500)
        
        # Regular template response
        return super().render_to_response(context, **response_kwargs)
    
    # Keep your existing get_context_data and format_price methods unchanged
    def get_context_data(self, **kwargs):
        # [Your existing get_context_data method remains exactly the same]
        context = super().get_context_data(**kwargs)
        
        categories = Category.objects.annotate(
            product_count=Count('product_listing')
        )
        
        subcategories = Subcategory.objects.annotate(
            product_count=Count('products')
        )
        
        categories = categories.prefetch_related(
            Prefetch('subcategories', queryset=subcategories)
        )
        
        category_slug = self.request.GET.get('category')
        subcategory_slug = self.request.GET.get('subcategory')
        brand_slug = self.request.GET.get('brand')
        
        context['categories'] = categories
        context['global_categories'] = categories
        context['states'] = State.objects.all()
        
        global_banners = get_active_banners('global')
        context['global_banners'] = global_banners
        
        # [Rest of your existing context logic...]
        if category_slug:
            try:
                selected_category = categories.get(slug=category_slug)
                context['selected_category'] = selected_category.slug
                context['selected_category_obj'] = selected_category
                context['subcategories'] = selected_category.subcategories.all()
                
                if subcategory_slug:
                    try:
                        selected_subcategory = subcategories.get(slug=subcategory_slug)
                        context['selected_subcategory'] = selected_subcategory.slug
                        context['selected_subcategory_obj'] = selected_subcategory
                        
                        context['brands'] = Brand.objects.filter(
                            categories=selected_category
                        ).annotate(
                            product_count=Count('products', filter=Q(
                                products__category=selected_category,
                                products__subcategory=selected_subcategory
                            ))
                        ).filter(product_count__gt=0)
                    except Subcategory.DoesNotExist:
                        pass
                else:
                    context['brands'] = Brand.objects.filter(
                        categories=selected_category
                    ).annotate(
                        product_count=Count('products', filter=Q(products__category=selected_category))
                    ).filter(product_count__gt=0)
                    
            except Category.DoesNotExist:
                context['brands'] = Brand.objects.none()
        else:
            context['brands'] = Brand.objects.annotate(
                product_count=Count('products')
            ).filter(product_count__gt=0)
        
        state_id = self.request.GET.get('state')
        if state_id:
            context['lgas'] = LGA.objects.filter(state_id=state_id)
        
        if brand_slug:
            try:
                selected_brand = Brand.objects.get(slug=brand_slug)
                context['selected_brand'] = selected_brand.slug
                context['selected_brand_obj'] = selected_brand
            except Brand.DoesNotExist:
                pass
        
        if self.request.user.is_authenticated:
            saved_products = SavedProduct.objects.filter(
                user=self.request.user
            ).values_list('product_id', flat=True)
            saved_products_set = set(str(id) for id in saved_products)
            
            for product in context['products']:
                product.is_saved = str(product.id) in saved_products_set
                product.formatted_price = self.format_price(product.price)
        else:
            for product in context['products']:
                product.formatted_price = self.format_price(product.price)
        
        context['current_sort'] = self.request.GET.get('sort', 'smart')
        
        return context
    
    def format_price(self, price):
        return '₦ {:,.0f}'.format(Decimal(price))
    
class ProductDetailView(DetailView):
    model = Product_Listing
    template_name = 'product_detail.html'
    context_object_name = 'product'

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        
        # Get or create a session key for the user
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key
        
        # Check if this session has viewed this product before
        if f'viewed_product_{self.object.id}' not in request.session:
            self.object.increase_view_count()
            request.session[f'viewed_product_{self.object.id}'] = True
        
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.is_authenticated and self.object.seller.user == self.request.user:
            try:
                context['user_account'] = self.request.user.account
                context['can_boost'] = context['user_account'].balance > 0
                context['active_boost'] = self.object.get_boost_status()
            except AttributeError:
                pass
        
        time_remaining = self.object.time_remaining
        if time_remaining:
            context['time_remaining'] = time_remaining
            
        if self.request.user.is_authenticated:
            from .models import SavedProduct  # Import if not already imported
            context['product'].is_saved = SavedProduct.objects.filter(
                user=self.request.user,
                product=self.object
            ).exists()
        else:
            context['product'].is_saved = False   
            
        # Format the price
        context['formatted_price'] = self.format_price(self.object.price)
        
        # Get images
        context['images'] = self.object.images.all()
        context['primary_image'] = self.object.images.filter(is_primary=True).first() or self.object.images.first()
        
        # Get ALL reviews for this seller across ALL their products
        seller_products = Product_Listing.objects.filter(seller=self.object.seller)
        all_seller_reviews = Review.objects.filter(
            product__in=seller_products
        ).select_related('reviewer').prefetch_related(
            Prefetch('replies', queryset=ReviewReply.objects.select_related('reviewer').order_by('created_at'))
        ).order_by('-created_at')
        
        # Get only reviews for this specific product (for display)
        product_reviews = all_seller_reviews.filter(product=self.object)[:2]  # Only show 2 reviews
        
        # Calculate seller's overall statistics from ALL reviews
        total_seller_reviews = all_seller_reviews.count()
        seller_avg_rating = all_seller_reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
        
        # Calculate star distribution for seller (from all reviews)
        seller_star_percentages = {
            '5': all_seller_reviews.filter(rating=5).count() / total_seller_reviews * 100 if total_seller_reviews else 0,
            '4': all_seller_reviews.filter(rating=4).count() / total_seller_reviews * 100 if total_seller_reviews else 0,
            '3': all_seller_reviews.filter(rating=3).count() / total_seller_reviews * 100 if total_seller_reviews else 0,
            '2': all_seller_reviews.filter(rating=2).count() / total_seller_reviews * 100 if total_seller_reviews else 0,
            '1': all_seller_reviews.filter(rating=1).count() / total_seller_reviews * 100 if total_seller_reviews else 0,
        }
        
        # In any view
        global_banners = get_active_banners('global')
        context['global_banners'] = global_banners
        
        # Context for reviews (only show 2 product reviews)
        context['reviews'] = product_reviews
        context['total_seller_reviews'] = total_seller_reviews
        context['seller_average_rating'] = seller_avg_rating
        context['seller_star_percentages'] = seller_star_percentages
        context['has_more_reviews'] = total_seller_reviews > 2
        
        # Product specific review count
        product_review_count = Review.objects.filter(product=self.object).count()
        context['product_review_count'] = product_review_count
        
        # Calculate seller product statistics - FIXED VERSION
        seller_profile = self.object.seller
        
        # Get current count of existing products (for comparison only)
        current_products_count = Product_Listing.objects.filter(seller=seller_profile).count()
        
        # Use the counter field, but ensure it's at least as high as current products
        # This handles cases where the counter wasn't properly maintained initially
        total_ever_listed = max(seller_profile.total_products_listed, current_products_count)
        
        # Update the counter if it was lower than current products
        if seller_profile.total_products_listed < current_products_count:
            seller_profile.total_products_listed = current_products_count
            seller_profile.save(update_fields=['total_products_listed'])
            
        if self.request.user.is_authenticated and self.object.seller.user == self.request.user:
            try:
                context['user_account'] = self.request.user.account
                context['can_boost'] = context['user_account'].balance > 0
                active_boost = self.object.get_boost_status()
                context['active_boost'] = active_boost
            except AttributeError:
                context['can_boost'] = False
                context['active_boost'] = None
        
        # Add share URL for social sharing
        context['share_url'] = self.request.build_absolute_uri()
        
        # Check if product is saved by current user
        if self.request.user.is_authenticated:
            context['is_saved'] = self.object.is_saved_by_user(self.request.user)
        
        # Currently active products (not suspended and not expired)
        active_products = Product_Listing.objects.filter(
            seller=seller_profile,
            is_suspended=False
        ).exclude(
            expiration_date__lte=timezone.now()
        ).count()
        
        # Add seller product statistics to context
        context['seller_product_stats'] = {
            'total_ever_listed': total_ever_listed,  # Use the counter field (corrected if needed)
            'active_products': active_products,
        }
        
        # Get related products
        related_products = Product_Listing.objects.filter(
            Q(category=self.object.category) | 
            Q(subcategory=self.object.subcategory)
        ).exclude(id=self.object.id).distinct()[:4]
        
        if self.request.user.is_authenticated:
            saved_products = SavedProduct.objects.filter(
                user=self.request.user,
                product__in=related_products
            ).values_list('product_id', flat=True)
            saved_products = set(str(id) for id in saved_products)
            
            for product in related_products:
                product.is_saved = str(product.id) in saved_products
                
        context['related_products'] = related_products
        for product in context['related_products']:
            product.formatted_price = self.format_price(product.price)
        
        # Get seller details
        seller_user = self.object.seller.user
        seller_profile = get_object_or_404(Profile, user=seller_user)
        
        context['seller_details'] = {
            'name': seller_user.username,
            'phone': seller_profile.phone_number,
            'address': str(seller_profile.location) if seller_profile.location else 'Not provided',
            'is_active': seller_user.is_active
        }
        
        # Handle timestamps
        context['created_at'] = self.object.created_at
        time_since_creation = timezone.now() - self.object.created_at
        
        if time_since_creation.days > 0:
            context['time_since_creation'] = f"{time_since_creation.days} days ago"
        elif time_since_creation.seconds // 3600 > 0:
            context['time_since_creation'] = f"{time_since_creation.seconds // 3600} hours ago"
        else:
            context['time_since_creation'] = f"{time_since_creation.seconds // 60} minutes ago"

        # Add review form to context
        from .forms import ReviewForm
        context['review_form'] = ReviewForm()
        
        return context

    def format_price(self, price):
        return '₦ {:,.0f}'.format(Decimal(price))

    def get_queryset(self):
        # Optimize the main query
        return super().get_queryset().select_related(
            'seller',
            'seller__user',
            'seller__location',
            'category',
            'subcategory',
            'brand'
        )
        
class AllSellerReviewsView(ListView):
    template_name = 'all_seller_reviews.html'
    context_object_name = 'reviews'
    paginate_by = 10

    def get_queryset(self):
        seller_username = self.kwargs['username']
        seller_user = get_object_or_404(User, username=seller_username)
        seller_products = Product_Listing.objects.filter(seller__user=seller_user)
        
        return Review.objects.filter(
            product__in=seller_products
        ).select_related('reviewer', 'product').prefetch_related(
            Prefetch('replies', queryset=ReviewReply.objects.select_related('reviewer').order_by('created_at'))
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        seller_username = self.kwargs['username']
        seller_user = get_object_or_404(User, username=seller_username)
        
        # Get all reviews for this seller
        seller_products = Product_Listing.objects.filter(seller__user=seller_user)
        all_reviews = Review.objects.filter(product__in=seller_products)
        
        # Calculate statistics
        total_reviews = all_reviews.count()
        avg_rating = all_reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
        
        star_percentages = {
            '5': all_reviews.filter(rating=5).count() / total_reviews * 100 if total_reviews else 0,
            '4': all_reviews.filter(rating=4).count() / total_reviews * 100 if total_reviews else 0,
            '3': all_reviews.filter(rating=3).count() / total_reviews * 100 if total_reviews else 0,
            '2': all_reviews.filter(rating=2).count() / total_reviews * 100 if total_reviews else 0,
            '1': all_reviews.filter(rating=1).count() / total_reviews * 100 if total_reviews else 0,
        }
        
        context.update({
            'seller': seller_user,
            'total_reviews': total_reviews,
            'average_rating': avg_rating,
            'star_percentages': star_percentages,
        })
        
        return context

class QuickUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    def post(self, request, pk):
        try:
            product = Product_Listing.objects.get(pk=pk)
            
            # Reset the expiration
            product.reset_expiration()
            
            # If it's an AJAX request, return JSON response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Listing updated successfully',
                    'time_remaining': product.time_remaining,
                    'expiration_date': product.expiration_date.isoformat() if product.expiration_date else None
                })
            
            # For regular requests, redirect with message
            messages.success(request, 'Listing timer has been reset successfully!')
            return redirect('product_detail', pk=pk)
            
        except Product_Listing.DoesNotExist:
            messages.error(request, 'Product not found!')
            return redirect('home')
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')
            return redirect('product_detail', pk=pk)
    
    def test_func(self):
        product = Product_Listing.objects.get(pk=self.kwargs['pk'])
        return self.request.user == product.seller.user          

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product_Listing
    form_class = ListingForm
    template_name = 'product_form.html'
    success_url = reverse_lazy('home')
    
    def form_valid(self, form):
        try:
            # Set the seller
            form.instance.seller = self.request.user.profile
            
            # Save the form manually
            self.object = form.save()
            
            # Set expiration date explicitly before saving images
            if self.object.listing_type != 'permanent':
                duration = {
                    'standard': 45,
                    'business': 90,
                    'urgent': 30
                }.get(self.object.listing_type, 45)
                self.object.expiration_date = timezone.now() + timedelta(days=duration)
                self.object.save()
            
            # Handle images with improved error handling for large files
            images = self.request.FILES.getlist('images')
            for i, image in enumerate(images[:5]):  # Limit to 5 images
                try:
                    # Check file size before processing
                    if image.size > 5 * 1024 * 1024:  # 5MB
                        messages.warning(
                            self.request, 
                            f'Image "{image.name}" was too large and was skipped. Please upload images under 5MB.'
                        )
                        continue
                    
                    # Create the product image
                    Product_Image.objects.create(
                        product=self.object,
                        image=image,
                        is_primary=(i == 0)
                    )
                except Exception as img_error:
                    messages.warning(
                        self.request, 
                        f'Failed to process image "{image.name}": {str(img_error)}'
                    )
            
            messages.success(self.request, 'Product created successfully.')
            
            # Handle AJAX requests
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': 'Product created successfully',
                    'redirect_url': self.get_success_url()
                })
            
            return HttpResponseRedirect(self.get_success_url())
            
        except Exception as e:
            messages.error(self.request, f'Error creating product: {str(e)}')
            
            # Handle AJAX requests with error
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error creating product: {str(e)}'
                }, status=400)
            
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Listing'
        context['save'] = 'List Product'
        context['ai_descriptions_remaining'] = get_remaining_descriptions(self.request.user)
        
        # Add time_remaining to context if object exists
        if hasattr(self, 'object') and self.object:
            context['time_remaining'] = self.object.time_remaining
        return context
    
class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product_Listing
    form_class = ListingForm
    template_name = 'product_form.html'
    success_url = reverse_lazy('product_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs

    def form_valid(self, form):
        try:
            self.object = form.save(commit=False)
            
            # Reset expiration based on listing type
            duration = {
                'standard': 45,
                'business': 90,
                'urgent': 30
            }.get(self.object.listing_type)
            
            if self.object.listing_type != 'permanent':
                self.object.expiration_date = timezone.now() + timedelta(days=duration)
                self.object.deletion_warning_sent = False
            else:
                self.object.expiration_date = None
            
            self.object.save()
            
            # Handle images - ONLY delete and replace if new images are uploaded
            if form.cleaned_data.get('images'):
                # Delete existing images individually
                for image in self.object.images.all():
                    image.delete()
                # Save new images
                self.save_images(form.cleaned_data['images'])
            
            messages.success(self.request, 'Product updated successfully.')
            
            # Handle AJAX requests
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': 'Product updated successfully',
                    'redirect_url': self.get_success_url()
                })
            
            return HttpResponseRedirect(self.get_success_url())
            
        except Exception as e:
            messages.error(self.request, f'Error updating product: {str(e)}')
            
            # Handle AJAX requests with error
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error updating product: {str(e)}'
                }, status=400)
                
            return self.form_invalid(form)
        

    def save_images(self, images):
        for i, image in enumerate(images):
            self.object.images.create(
                image=image,
                is_primary=(i == 0)
            )

    def test_func(self):
        product = self.get_object()
        return self.request.user == product.seller
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Listing'
        context['save'] = 'Update Product'
        return context
    
class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Product_Listing
    template_name = 'product_confirm_delete.html'
    success_url = reverse_lazy('home')

    def test_func(self):
        product = self.get_object()
        return self.request.user == product.seller

    def handle_no_permission(self):
        """Custom handling for permission denied"""
        messages.error(self.request, 'You do not have permission to delete this product.')
        return redirect('product_detail', pk=self.get_object().pk)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Product deleted successfully.')
        return super().delete(request, *args, **kwargs)
    
class ProductSearchView(ListView):
    model = Product_Listing
    template_name = 'product_search.html'
    context_object_name = 'products'
    paginate_by = 12
    
    # Use the exact same paginate_queryset and render_to_response methods as above
    def paginate_queryset(self, queryset, page_size):
        """Override to handle pagination errors gracefully"""
        paginator = self.get_paginator(
            queryset, page_size, orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty())
        
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
        
        try:
            page_number = int(page)
        except ValueError:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return (paginator, paginator.page(1), [], False)
            raise Http404("Page is not a number")
        
        try:
            page = paginator.page(page_number)
            return (paginator, page, page.object_list, page.has_other_pages())
        except EmptyPage:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                try:
                    last_page = paginator.page(paginator.num_pages)
                    return (paginator, last_page, [], False)
                except EmptyPage:
                    dummy_page = paginator.page(1) if paginator.num_pages > 0 else None
                    return (paginator, dummy_page, [], False)
            
            if page_number == 1:
                raise Http404("No products found matching your criteria")
            else:
                raise Http404("Page does not exist")

    def render_to_response(self, context, **response_kwargs):
        # Handle AJAX requests for infinite scroll (same as ProductListView)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                page_obj = context.get('page_obj')
                paginator = context.get('paginator')
                products = context.get('products', [])
                
                if not page_obj or not paginator:
                    return JsonResponse({
                        'success': True,
                        'products_html': [],
                        'has_more': False,
                        'current_page': 1,
                        'total_pages': 0,
                        'message': 'No more results available'
                    })
                
                if not products or len(products) == 0:
                    return JsonResponse({
                        'success': True,
                        'products_html': [],
                        'has_more': False,
                        'current_page': page_obj.number if page_obj else 1,
                        'total_pages': paginator.num_pages if paginator else 0,
                        'message': 'No more results available'
                    })
                
                if self.request.user.is_authenticated:
                    saved_products = SavedProduct.objects.filter(
                        user=self.request.user
                    ).values_list('product_id', flat=True)
                    saved_products_set = set(str(id) for id in saved_products)
                    
                    for product in products:
                        product.is_saved = str(product.id) in saved_products_set
                        product.formatted_price = self.format_price(product.price)
                else:
                    for product in products:
                        product.formatted_price = self.format_price(product.price)
                
                from django.template.loader import render_to_string
                products_html = []
                
                for product in products:
                    try:
                        product_html = render_to_string('product_card.html', {
                            'product': product,
                            'user': self.request.user
                        }, request=self.request)
                        products_html.append(product_html)
                    except Exception as e:
                        logger.error(f"Error rendering product {product.id}: {e}")
                        continue
                
                has_more = page_obj.has_next() if page_obj else False
                
                return JsonResponse({
                    'success': True,
                    'products_html': products_html,
                    'has_more': has_more,
                    'current_page': page_obj.number if page_obj else 1,
                    'total_pages': paginator.num_pages if paginator else 0,
                    'total_count': paginator.count if paginator else 0
                })
                
            except Exception as e:
                logger.error(f"Error in AJAX response: {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'An error occurred while loading more products',
                    'products_html': [],
                    'has_more': False,
                    'current_page': 1,
                    'total_pages': 0
                }, status=500)
        
        return super().render_to_response(context, **response_kwargs)
    
    # Keep your existing get_queryset and get_context_data methods unchanged
    def get_queryset(self):
        # [Your existing get_queryset method remains exactly the same]
        try:
            Product_Listing.delete_expired_listings()
        except:
            pass

        form = ProductSearchForm(self.request.GET)
        queryset = Product_Listing.objects.filter(
            is_suspended=False
        ).exclude(
            expiration_date__lte=timezone.now()
        )

        if form.is_valid():
            if form.cleaned_data['query']:
                queryset = queryset.filter(
                    Q(title__icontains=form.cleaned_data['query']) |
                    Q(description__icontains=form.cleaned_data['query'])
                )
            if form.cleaned_data['category']:
                queryset = queryset.filter(category=form.cleaned_data['category'])
            if form.cleaned_data['subcategory']:
                queryset = queryset.filter(subcategory=form.cleaned_data['subcategory'])
            if form.cleaned_data['brand']:
                queryset = queryset.filter(brand=form.cleaned_data['brand'])
            if form.cleaned_data['min_price']:
                try:
                    queryset = queryset.filter(price__gte=form.cleaned_data['min_price'])
                except (ValueError, TypeError):
                    pass
            if form.cleaned_data['max_price']:
                try:
                    queryset = queryset.filter(price__lte=form.cleaned_data['max_price'])
                except (ValueError, TypeError):
                    pass
            if form.cleaned_data['condition']:
                queryset = queryset.filter(condition=form.cleaned_data['condition'])
            if form.cleaned_data['state']:
                queryset = queryset.filter(seller__location__state=form.cleaned_data['state'])
            if form.cleaned_data['lga']:
                queryset = queryset.filter(seller__location__lga=form.cleaned_data['lga'])
        
        sort_by = self.request.GET.get('sort', 'smart')
        
        if sort_by == 'smart':
            products_list = get_sorted_products(queryset, self.request.user)
            product_ids = [p.id for p in products_list]
            if product_ids:
                preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(product_ids)])
                return Product_Listing.objects.filter(id__in=product_ids).order_by(preserved)
            else:
                return Product_Listing.objects.none()
        else:
            valid_sort_options = {
                '-created_at': '-created_at',
                'created_at': 'created_at', 
                'price': 'price',
                '-price': '-price',
                'title': Lower('title'),
                '-title': Lower('title').desc(),
                'condition': 'condition',
                '-condition': '-condition'
            }
            
            if sort_by in valid_sort_options:
                return queryset.order_by(valid_sort_options[sort_by])
            else:
                return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        # [Your existing get_context_data method remains exactly the same]
        context = super().get_context_data(**kwargs)
        context['form'] = ProductSearchForm(self.request.GET)

        if self.request.user.is_authenticated:
            saved_products = SavedProduct.objects.filter(
                user=self.request.user
            ).values_list('product_id', flat=True)

            saved_products_set = set(str(id) for id in saved_products)

            for product in context['products']:
                product.is_saved = str(product.id) in saved_products_set
                product.formatted_price = self.format_price(product.price)
        else:
            for product in context['products']:
                product.formatted_price = self.format_price(product.price)
        
        context['current_sort'] = self.request.GET.get('sort', 'smart')
        
        global_banners = get_active_banners('global')
        context['global_banners'] = global_banners

        return context
        
    def format_price(self, price):
        return '₦ {:,.0f}'.format(Decimal(price))

class RelatedProductsView(ListView):
    model = Product_Listing
    template_name = 'related_products.html'
    context_object_name = 'related_products'
    paginate_by = 12  # Show 12 products per page

    def get_queryset(self):
        product = Product_Listing.objects.get(id=self.kwargs['pk'])
        return Product_Listing.objects.filter(
            Q(category=product.category) | 
            Q(subcategory=product.subcategory)
        ).exclude(id=product.id).distinct()

class ReportProductView(View):
    def get(self, request, product_id):
        """
        Handle GET requests to the report product page.
        Renders the report form for the specific product.
        """
        try:
            # Fetch the product, return 404 if not found
            product = get_object_or_404(Product_Listing, id=product_id)
            
            # Check if product is already suspended
            if product.is_suspended:
                messages.warning(request, "This listing has already been suspended by the marketplace.")
            
            # Render the report form template
            return render(request, 'report_product.html', {
                'product': product,
                'form': ProductReportForm()
            })
        
        except Exception as e:
            # Log any unexpected errors
            logging.error(f"Error accessing report product page: {e}")
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while accessing the report page.'
            }, status=500)

    def post(self, request, product_id):
        """
        Handle POST requests to submit a product report.
        """
        try:
            # Fetch the product
            product = get_object_or_404(Product_Listing, id=product_id)
            
            # Validate the form
            form = ProductReportForm(request.POST)
            if form.is_valid():
                # Create a new report record
                report = ProductReport(
                    product=product,
                    reason=form.cleaned_data['reason'],
                    details=form.cleaned_data['details'],
                    reporter_email=form.cleaned_data['reporter_email'] or None,
                )
                report.save()
                
                # Check for automatic suspension threshold (e.g., if more than 5 reports)
                report_count = product.reports.count()
                
                # Prepare email content
                report_data = {
                    'product_id': str(product.id),
                    'product_title': product.title,
                    'seller_username': product.seller.user.username,
                    'reason': form.cleaned_data['reason'],
                    'details': form.cleaned_data['details'],
                    'reporter_email': form.cleaned_data['reporter_email'] or 'Anonymous',
                    'report_count': report_count
                }
                
                # Render email content
                email_body = render_to_string('emails/product_report_email.html', report_data)
                
                try:
                    # Send email
                    send_mail(
                        subject=f'Product Report: {product.title} (#{report_count})',
                        message=email_body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=['support@opensell.online'],
                        html_message=email_body,
                        fail_silently=False,
                    )
                    
                    # Auto-suspend if threshold reached
                    if report_count >= 5 and not product.is_suspended:
                        try:
                            # Get a superuser
                            from django.contrib.auth.models import User
                            superuser = User.objects.filter(is_superuser=True).first()
                            
                            if superuser:
                                # Auto-suspend the listing
                                product.suspend(
                                    superuser, 
                                    f"Auto-suspended after receiving {report_count} reports. Last report reason: {report.get_reason_display()}"
                                )
                                
                                # Mark all related reports as resolved
                                product.reports.filter(status='pending').update(
                                    status='resolved',
                                    reviewed_by=superuser,
                                    reviewed_at=timezone.now(),
                                    resolution_notes=f"Auto-resolved due to listing suspension after {report_count} reports."
                                )
                        except Exception as auto_suspend_error:
                            logging.error(f"Error auto-suspending product: {auto_suspend_error}")
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Thank you for reporting this product. We will review it shortly.'
                    })
                
                except Exception as e:
                    # Log email sending error
                    logging.error(f"Error sending report email: {e}")
                    return JsonResponse({
                        'success': False,
                        'message': 'An error occurred while processing your report. Please try again.'
                    }, status=500)
            
            else:
                # Return form validation errors
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
        
        except Product_Listing.DoesNotExist:
            # Handle case where product is not found
            return JsonResponse({
                'success': False,
                'message': 'Product not found'
            }, status=404)
        
        except Exception as e:
            # Log any unexpected errors
            logging.error(f"Unexpected error in report product view: {e}")
            return JsonResponse({
                'success': False,
                'message': 'An unexpected error occurred.'
            }, status=500)
            
@login_required
@require_POST
def toggle_save_product(request):
    product_id = request.POST.get('product_id')
    print(f"Toggle save request received for product {product_id} from user {request.user}")

    if not product_id:
        return JsonResponse({
            'status': 'error',
            'message': 'No product ID provided'
        }, status=400)

    try:
        # Convert string UUID to UUID object if needed
        try:
            product_id = uuid.UUID(product_id)
        except ValueError:
            pass
            
        product = Product_Listing.objects.get(id=product_id)
        saved_product = SavedProduct.objects.filter(
            user=request.user,
            product=product
        ).first()
        
        if saved_product:
            # Product was already saved, so unsave it
            saved_product.delete()
            print(f"Product {product_id} unsaved by user {request.user}")
            return JsonResponse({
                'status': 'removed',
                'message': 'Product removed from saved items'
            })
        else:
            # Product wasn't saved, so save it
            SavedProduct.objects.create(
                user=request.user,
                product=product
            )
            print(f"Product {product_id} saved by user {request.user}")
            return JsonResponse({
                'status': 'saved',
                'message': 'Product saved successfully'
            })
            
    except Product_Listing.DoesNotExist:
        print(f"Product {product_id} not found")
        return JsonResponse({
            'status': 'error',
            'message': 'Product not found'
        }, status=404)
    except Exception as e:
        print(f"Error saving product: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while saving the product'
        }, status=500)

@login_required
def saved_products(request):
    # Get saved items with related product data
    saved_items = SavedProduct.objects.filter(user=request.user).select_related('product')
    
    # Create a list of products and process them
    products = []
    for saved_item in saved_items:
        product = saved_item.product
        product.formatted_price = format_price(product.price)
        product.is_saved = True  
        products.append(product)
        
    Product_Listing.delete_expired_listings()
    # Add to context
    context = {
        'products': products  
    }
    
    return render(request, 'saved_products.html', context)

@login_required
def submit_review(request, review_type, pk):
    if review_type not in ['product', 'seller']:
        messages.error(request, "Invalid review type.")
        return redirect('home')
    
    try:
        reviewed_object = get_object_or_404(
            Product_Listing if review_type == 'product' else Profile, 
            id=pk if review_type == 'product' else pk
        )
    except (ValueError, ValidationError):
        messages.error(request, "Invalid item ID.")
        return redirect('home')
    
    # Check if user can review
    if (review_type == 'product' and reviewed_object.seller.user == request.user) or \
       (review_type == 'seller' and reviewed_object.user == request.user):
        messages.error(request, f"You cannot review your own {review_type}.")
        return redirect(
            'product_detail' if review_type == 'product' else 'seller_profile', 
            pk=pk
        )

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            try:
                review = form.save(commit=False)
                review.reviewer = request.user
                review.review_type = review_type
                
                if review_type == 'product':
                    review.product = reviewed_object
                else:
                    review.seller = reviewed_object
                
                review.save()
                messages.success(request, "Your review has been submitted successfully.")
                
            except IntegrityError:
                messages.error(request, "You have already reviewed this item.")
            
            return redirect(
                'product_detail' if review_type == 'product' else 'seller_profile',
                pk=pk
            )
    else:
        form = ReviewForm()

    # Get review statistics for context
    review_count = reviewed_object.reviews.count() if review_type == 'product' else \
                  reviewed_object.seller_reviews.count()
    
    context = {
        'form': form,
        'reviewed_object': reviewed_object,
        'review_type': review_type,
        'review_count': review_count,
        'average_rating': reviewed_object.average_rating if review_type == 'product' else \
                         reviewed_object.seller_reviews.aggregate(Avg('rating'))['rating__avg'] or 0,
    }
    return render(request, 'submit_review.html', context)

@login_required
def reply_to_review(request, pk, review_id):
    product = get_object_or_404(Product_Listing, id=pk)
    original_review = get_object_or_404(Review, id=review_id)
    
    # Verify the review belongs to this product
    if original_review.product != product:
        messages.error(request, "Review not found for this product.")
        return redirect('product_detail', pk=pk)
    
    # Check if user has permission to reply (must be the seller)
    if product.seller.user != request.user:
        messages.error(request, "You don't have permission to reply to this review.")
        return redirect('product_detail', pk=pk)
    
    # Check if review already has a reply
    existing_reply = original_review.replies.exists()
    
    if existing_reply:
        messages.error(request, "This review already has a reply.")
        return redirect('product_detail', pk=pk)

    if request.method == 'POST':
        form = ReviewReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.reviewer = request.user
            reply.review = original_review
            reply.save()
            
            messages.success(request, "Your reply has been submitted successfully.")
            return redirect('product_detail', pk=pk)
    else:
        form = ReviewReplyForm()

    context = {
        'form': form,
        'original_review': original_review,
        'reviewed_object': product,
    }
    return render(request, 'reply_to_review.html', context)

@login_required
def edit_review(request, pk, review_id):
    review = get_object_or_404(Review, id=review_id)
    product = get_object_or_404(Product_Listing, id=pk)
    
    # Check if user is the review owner
    if review.reviewer != request.user:
        messages.error(request, "You don't have permission to edit this review.")
        return redirect('product_detail', pk=pk)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, "Review updated successfully.")
            return redirect('product_detail', pk=pk)
    else:
        form = ReviewForm(instance=review)
    
    context = {
        'form': form,
        'review': review,
        'product': product
    }
    return render(request, 'edit_review.html', context)

@login_required
def delete_review(request, pk, review_id):
    review = get_object_or_404(Review, id=review_id)
    product = get_object_or_404(Product_Listing, id=pk)
    
    # Check if user is the review owner
    if review.reviewer != request.user:
        messages.error(request, "You don't have permission to delete this review.")
        return redirect('product_detail', pk=pk)
    
    if request.method == 'POST':
        review.delete()
        messages.success(request, "Review deleted successfully.")
        return redirect('product_detail', pk=pk)
    
    context = {
        'review': review,
        'product': product
    }
    return render(request, 'delete_review_confirm.html', context)

@login_required
def edit_reply(request, pk, reply_id):
    reply = get_object_or_404(ReviewReply, id=reply_id)
    product = get_object_or_404(Product_Listing, id=pk)
    
    # Check if user is the reply owner
    if reply.reviewer != request.user:
        messages.error(request, "You don't have permission to edit this reply.")
        return redirect('product_detail', pk=pk)
    
    if request.method == 'POST':
        form = ReviewReplyForm(request.POST, instance=reply)
        if form.is_valid():
            form.save()
            messages.success(request, "Reply updated successfully.")
            return redirect('product_detail', pk=pk)
    else:
        form = ReviewReplyForm(instance=reply)
    
    context = {
        'form': form,
        'reply': reply,
        'product': product
    }
    return render(request, 'edit_reply.html', context)

@login_required
def delete_reply(request, pk, reply_id): 
    reply = get_object_or_404(ReviewReply, id=reply_id)
    product = get_object_or_404(Product_Listing, id=pk)
    
    # Check if user is the reply owner
    if reply.reviewer != request.user:
        messages.error(request, "You don't have permission to delete this reply.")
        return redirect('product_detail', pk=pk)
    
    if request.method == 'POST':
        reply.delete()
        messages.success(request, "Reply deleted successfully.")
        return redirect('product_detail', pk=pk)
    
    context = {
        'reply': reply,
        'product': product
    }
    return render(request, 'delete_reply_confirm.html', context)

@login_required
def my_store(request, username=None):  # Accept username parameter
    # If username is provided in URL, get that user's store
    # Otherwise, show current user's store
    if username:
        store_owner = get_object_or_404(
            User.objects.select_related(
                'profile',
                'profile__location',
                'profile__location__state',
                'profile__location__lga'
            ),
            username=username
        )
    else:
        store_owner = get_object_or_404(
            User.objects.select_related(
                'profile',
                'profile__location',
                'profile__location__state',
                'profile__location__lga'
            ),
            username=request.user.username
        )
    
    # Rest of your code remains the same...
    user_products = Product_Listing.objects.filter(seller=store_owner.profile)
    
    # Handle saved products for authenticated users
    if request.user.is_authenticated:
        saved_products = SavedProduct.objects.filter(
            user=request.user
        ).values_list('product_id', flat=True)
        saved_products = set(str(id) for id in saved_products)
        for product in user_products:
            product.is_saved = str(product.id) in saved_products
            product.formatted_price = format_price(product.price)
    
    # Format location display
    location_display = None
    if store_owner.profile.location:
        location_parts = []
        if store_owner.profile.location.address:
            location_parts.append(store_owner.profile.location.address)
        if store_owner.profile.location.address_2:
            location_parts.append(store_owner.profile.location.address_2)
        if store_owner.profile.location.city:
            location_parts.append(store_owner.profile.location.city)
        if store_owner.profile.location.lga:
            location_parts.append(store_owner.profile.location.lga.name)
        if store_owner.profile.location.state:
            location_parts.append(store_owner.profile.location.state.name)
        location_display = ', '.join(filter(None, location_parts))
    
    context = {
        'store_owner': store_owner,
        'products': user_products,
        'total_products': user_products.count(),
        'location_display': location_display,
    }
    
    # Only show account details if viewing own store
    if store_owner == request.user:
        try:
            context['account'] = request.user.account
            context['boost_count'] = ProductBoost.objects.filter(
                product__seller=store_owner.profile,
                is_active=True,
                end_date__gt=timezone.now()
            ).count()
        except AttributeError:
            pass
        
    return render(request, 'my_store.html', context)

def handler404(request, exception):
    """
    Custom 404 handler that differentiates between product-related 404s and general 404s
    """
    url_path = urlparse(request.build_absolute_uri()).path
    
    context = {
        'is_product_related': False,
        'request_path': url_path,
    }
    
    # Try to determine if this was a product-related 404
    try:
        # Get the resolved view name if possible (to check if it was a product view)
        resolved = resolve(url_path)
        view_name = resolved.view_name
        
        # Check if the URL was intended for a product page
        if 'product' in view_name or 'products' in view_name:
            context['is_product_related'] = True
    except Resolver404:
        # If we can't resolve the URL pattern, use URL path examination as fallback
        product_indicators = ['product', 'products', 'item', 'listings']
        path_segments = url_path.split('/')
        for segment in path_segments:
            if segment in product_indicators or (segment.isdigit() and len(segment) > 4):
                context['is_product_related'] = True
                break
    
    # Return the appropriate template with context
    return render(request, '404.html', context, status=404)
    """
    Fetch categories for the 404 page - only fetch a few popular ones
    """
    try:
        from Home.models import Category  # Replace with your actual import
        # Get popular categories (limited to 6)
        return Category.objects.order_by('-product_count')[:6]
    except:
        # If there's any error, return an empty list
        return []
    
def generate_product_description(title, category=None, brand=None, condition=None):
    """
    Generate comprehensive product description with category-specific details
    """
    try:
        # First try AI generation, then enhance with structured details
        ai_description = generate_ai_base_description(title, category, brand, condition)
        
        # Generate structured details based on category
        structured_details = generate_category_specific_details(title, category, brand, condition)
        
        # Combine AI description with structured details
        if ai_description and structured_details:
            final_description = f"{ai_description}\n\n{structured_details}"
        elif structured_details:
            # Use fallback base description + structured details
            base_description = generate_fallback_description(title, category, brand, condition)
            final_description = f"{base_description}\n\n{structured_details}"
        else:
            final_description = ai_description or generate_fallback_description(title, category, brand, condition)
        
        return final_description
        
    except Exception as e:
        logger.error(f"Error in generate_product_description: {str(e)}")
        return generate_comprehensive_fallback(title, category, brand, condition)

def generate_ai_base_description(title, category=None, brand=None, condition=None):
    """
    Generate base description using Hugging Face API
    """
    try:
        API_URL = "https://api-inference.huggingface.co/models/gpt2"
        
        headers = {
            "Authorization": f"Bearer {settings.HUGGINGFACE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Create enhanced prompt for better AI generation
        prompt_parts = [f"Product: {title}"]
        
        if category:
            prompt_parts.append(f"Category: {category}")
        if brand:
            prompt_parts.append(f"Brand: {brand}")
        if condition:
            prompt_parts.append(f"Condition: {condition}")
            
        prompt_parts.append("Write a detailed product description highlighting key features and benefits:")
        
        prompt = ". ".join(prompt_parts)
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_length": 120,
                "min_length": 40,
                "temperature": 0.7,
                "do_sample": True,
                "pad_token_id": 50256
            }
        }
        
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                generated_text = result[0].get('generated_text', '')
                description = clean_generated_description(generated_text, prompt)
                return description
        
        return None
        
    except Exception as e:
        logger.error(f"AI generation error: {str(e)}")
        return None

def generate_category_specific_details(title, category=None, brand=None, condition=None):
    """
    Generate structured, category-specific details section
    """
    try:
        details_sections = []
        product_type = detect_product_type(title, category)
        
        # Add specification section based on product type
        specs = generate_specifications_section(product_type, title, brand, condition)
        if specs:
            details_sections.append(f"📋 SPECIFICATIONS:\n{specs}")
        
        # Add condition details
        condition_details = generate_condition_details(condition, product_type)
        if condition_details:
            details_sections.append(f"🔍 CONDITION & DETAILS:\n{condition_details}")
        
        # Add features section
        features = generate_features_section(product_type, title)
        if features:
            details_sections.append(f"✨ KEY FEATURES:\n{features}")
        
        # Add compatibility/usage section
        compatibility = generate_compatibility_section(product_type, title)
        if compatibility:
            details_sections.append(f"🔗 COMPATIBILITY & USAGE:\n{compatibility}")
        
        # Add what's included section
        included = generate_included_items(product_type, condition)
        if included:
            details_sections.append(f"📦 WHAT'S INCLUDED:\n{included}")
        
        return "\n\n".join(details_sections) if details_sections else None
        
    except Exception as e:
        logger.error(f"Error generating category-specific details: {str(e)}")
        return None

def detect_product_type(title, category=None):
    """
    Detect product type from title and category for targeted details
    """
    title_lower = title.lower()
    category_lower = category.lower() if category else ""
    
    # Smartphones and Tablets
    if any(phone in title_lower for phone in ['iphone', 'samsung', 'android', 'smartphone', 'phone']) or 'iphones' in category_lower:
        return 'smartphone'
    elif any(tablet in title_lower for tablet in ['ipad', 'tablet']) or 'tablets' in category_lower or 'ipads' in category_lower:
        return 'tablet'
    
    # Electronics
    elif any(laptop in title_lower for laptop in ['laptop', 'macbook', 'thinkpad', 'dell', 'hp', 'lenovo']) or 'computers' in category_lower:
        return 'laptop'
    elif any(tv in title_lower for tv in ['tv', 'television', 'smart tv', 'led', 'oled']) or 'televisions' in category_lower:
        return 'television'
    elif any(audio in title_lower for audio in ['headphone', 'speaker', 'earphone', 'airpods', 'audio']) or 'audio' in category_lower:
        return 'audio_device'
    elif any(gaming in title_lower for gaming in ['ps4', 'ps5', 'xbox', 'nintendo', 'gaming']) or 'gaming' in category_lower:
        return 'gaming_console'
    
    # Vehicles
    elif any(car in title_lower for car in ['car', 'toyota', 'honda', 'mercedes', 'bmw', 'lexus']) or 'cars' in category_lower:
        return 'car'
    elif any(bike in title_lower for bike in ['motorcycle', 'bike', 'yamaha', 'honda', 'suzuki']) or 'motorcycles' in category_lower:
        return 'motorcycle'
    
    # Home Appliances
    elif any(appliance in title_lower for appliance in ['refrigerator', 'washing machine', 'microwave', 'ac', 'air conditioner']):
        return 'home_appliance'
    
    # Fashion
    elif 'fashion' in category_lower or any(fashion in title_lower for fashion in ['shirt', 'dress', 'shoe', 'bag', 'watch']):
        return 'fashion_item'
    
    # Real Estate
    elif 'real estate' in category_lower or any(estate in title_lower for estate in ['house', 'apartment', 'land', 'property']):
        return 'real_estate'
    
    # Solar & Renewable Energy
    elif 'solar' in category_lower or any(solar in title_lower for solar in ['solar', 'inverter', 'battery', 'panel']):
        return 'solar_equipment'
    
    # Default
    return 'general'

def generate_specifications_section(product_type, title, brand, condition):
    """
    Generate specifications based on product type
    """
    specs = []
    
    if product_type == 'smartphone':
        specs.extend([
            "• Brand: [brand/model]",
            "• Storage Capacity: [e.g. 128GB]",
            "• RAM: [e.g. 8GB]",
            "• Color: [e.g., Black]",
            "• Screen Size: [e.g., 6.1 inch]",
            "• Battery Health: [e.g., 85%]",
            "• Operating System: [iOS/Android version]",
            "• Network: [4G/5G compatibility]"
        ])
    
    elif product_type == 'tablet':
        specs.extend([
            "• Brand: [Please specify brand/model]",
            "• Storage Capacity: [e.g. 128GB]",
            "• Screen Size: [e.g. 12.9 inch]",
            "• Color: [e.g. Silver]",
            "• Connectivity: [Wi-Fi only/Wi-Fi + Cellular]",
            "• Battery Life: [Estimated hours of usage]",
            "• Operating System: [iOS/Android version]"
        ])
    
    elif product_type == 'laptop':
        specs.extend([
            "• Brand & Model: [Please specify]",
            "• Processor: [e.g., Intel Core i5, AMD Ryzen 7]",
            "• RAM: [e.g. 16GB]",
            "• Storage: [e.g. 512GB SSD, 1TB HDD]",
            "• Screen Size: [e.g. 15.6 inch]",
            "• Graphics: [Integrated/Dedicated GPU]",
            "• Operating System: [Windows/macOS/Linux]",
            "• Battery Life: [Estimated hours]"
        ])
    
    elif product_type == 'television':
        specs.extend([
            "• Brand & Model: [Please specify]",
            "• Screen Size: [e.g. 32 inch]",
            "• Display Type: [LED, OLED, QLED]",
            "• Resolution: [HD, Full HD, 4K, 8K]",
            "• Smart TV Features: [Yes/No - specify platform]",
            "• Connectivity: [HDMI ports, USB ports, Wi-Fi]",
            "• Audio: [Built-in speakers wattage]"
        ])
    
    elif product_type == 'car':
        specs.extend([
            "• Make & Model: [Please specify]",
            "• Year of Manufacture: [e.g. 2018]",
            "• Mileage: [e.g. 45,000 km]",
            "• Engine Type: [Petrol/Diesel/Hybrid]",
            "• Transmission: [Manual/Automatic]",
            "• Color: [Exterior and Interior colors]",
            "• Fuel Efficiency: [e.g., 12km/L city, 18km/L highway]",
            "• Number of Owners: [First owner, Second owner, etc.]"
        ])
    
    elif product_type == 'motorcycle':
        specs.extend([
            "• Make & Model: [Please specify]",
            "• Engine Capacity: [e.g. 200cc]",
            "• Year: [Year of manufacture]",
            "• Mileage: [Kilometers covered]",
            "• Color: [Primary color]",
            "• Fuel Type: [Petrol/Electric]",
            "• Transmission: [Manual/Automatic]"
        ])
    
    elif product_type == 'home_appliance':
        specs.extend([
            "• Brand & Model: [Please specify]",
            "• Capacity/Size: [Relevant capacity/dimensions]",
            "• Energy Rating: [Energy efficiency rating]",
            "• Power Consumption: [Watts/kWh]",
            "• Color/Finish: [e.g., White, Stainless Steel, Black]",
            "• Special Features: [List key features]"
        ])
    
    elif product_type == 'solar_equipment':
        specs.extend([
            "• Brand & Model: [Please specify]",
            "• Capacity/Rating: [e.g., 200W, 5KVA, 100Ah]",
            "• Type: [Monocrystalline/Polycrystalline/Gel/Lithium]",
            "• Warranty: [Manufacturer warranty period]",
            "• Efficiency: [Conversion efficiency percentage]",
            "• Certifications: [Quality certifications]"
        ])
    
    else:  # general
        specs.extend([
            "• Brand: [Please specify if applicable]",
            "• Model/Type: [Product model or type]",
            "• Size/Dimensions: [Physical dimensions]",
            "• Color: [Available colors]",
            "• Material: [Primary materials used]"
        ])
    
    return "\n".join(specs) if specs else None

def generate_condition_details(condition, product_type):
    """
    Generate condition-specific details
    """
    details = []
    
    if not condition:
        details.append("• Condition: [Please specify - New, Like New, Good, Fair]")
    
    if product_type == 'smartphone':
        details.extend([
            "• Screen Condition: [No cracks, minor scratches, etc.]",
            "• Body Condition: [Excellent, good, minor wear, etc.]",
            "• Button Functionality: [All buttons working perfectly]",
            "• Camera Quality: [Front and back camera condition]",
            "• Charging Port: [Working condition]",
            "• Face ID/Fingerprint: [Working status]",
            "• Known Issues: [Any defects or problems]"
        ])
    
    elif product_type in ['laptop', 'tablet']:
        details.extend([
            "• Screen Condition: [No dead pixels, brightness level]",
            "• Keyboard/Touch: [All keys/touch working]",
            "• Battery Health: [Backup time, charging status]",
            "• Physical Condition: [Scratches, dents, wear level]",
            "• Ports & Connections: [All ports working status]",
            "• Known Issues: [Any hardware/software problems]"
        ])
    
    elif product_type == 'car':
        details.extend([
            "• Engine Condition: [Excellent, Good, Fair]",
            "• Transmission: [Smooth operation status]",
            "• Exterior Condition: [Paint, dents, scratches]",
            "• Interior Condition: [Seats, dashboard, electronics]",
            "• Tire Condition: [Tread depth, replacement needed]",
            "• Service History: [Recent services, maintenance]",
            "• Accident History: [No accidents, minor, etc.]",
            "• Documents: [Complete papers, registration status]"
        ])
    
    else:
        details.extend([
            "• Overall Condition: [Detailed condition description]",
            "• Functionality: [All features working status]",
            "• Physical Appearance: [Wear, scratches, damage]",
            "• Known Issues: [Any defects or limitations]"
        ])
    
    return "\n".join(details) if details else None

def generate_features_section(product_type, title):
    """
    Generate key features based on product type
    """
    features = []
    
    if product_type == 'smartphone':
        features.extend([
            "• High-quality camera for photos and videos",
            "• Fast processing for smooth performance",
            "• Long-lasting battery life",
            "• Secure biometric authentication",
            "• Premium build quality and design",
            "• Latest software updates supported"
        ])
    
    elif product_type == 'laptop':
        features.extend([
            "• Powerful processor for multitasking",
            "• Portable and lightweight design",
            "• High-resolution display",
            "• Fast SSD storage for quick boot-up",
            "• Multiple connectivity options",
            "• Perfect for work, study, or entertainment"
        ])
    
    elif product_type == 'car':
        features.extend([
            "• Reliable and well-maintained vehicle",
            "• Comfortable seating and interior",
            "• Good fuel efficiency",
            "• Safety features included",
            "• Smooth driving experience",
            "• Ready for immediate use"
        ])
    
    return "\n".join(features) if features else None

def generate_compatibility_section(product_type, title):
    """
    Generate compatibility and usage information
    """
    compatibility = []
    
    if product_type == 'smartphone':
        compatibility.extend([
            "• Compatible with all network providers in Nigeria",
            "• Supports 4G/5G networks (where available)",
            "• Works with wireless chargers (if supported)",
            "• Compatible with Bluetooth accessories",
            "• Supports all popular apps and games"
        ])
    
    elif product_type == 'laptop':
        compatibility.extend([
            "• Compatible with all major software applications",
            "• Supports external monitors and peripherals",
            "• Wi-Fi and Bluetooth connectivity",
            "• USB ports for various devices",
            "• Perfect for students, professionals, and creators"
        ])
    
    elif product_type == 'solar_equipment':
        compatibility.extend([
            "• Suitable for Nigerian climate conditions",
            "• Compatible with standard electrical systems",
            "• Works with various appliances and devices",
            "• Easy installation and maintenance",
            "• Reduces electricity bills significantly"
        ])
    
    return "\n".join(compatibility) if compatibility else None

def generate_included_items(product_type, condition):
    """
    Generate what's included with the product
    """
    included = []
    
    if product_type == 'smartphone':
        if condition and condition.lower() == 'new':
            included.extend([
                "• Original retail box and packaging",
                "• Charging cable and adapter",
                "• User manual and warranty card",
                "• Unused accessories (if any)",
                "• Screen protector (may be pre-installed)"
            ])
        else:
            included.extend([
                "• Phone unit only (unless stated otherwise)",
                "• Charging cable (if available)",
                "• May include original box and accessories",
                "• Please confirm included items with seller"
            ])
    
    elif product_type == 'laptop':
        included.extend([
            "• Laptop unit",
            "• Original charger/power adapter",
            "• Battery (condition as described)",
            "• May include original box and manuals",
            "• Pre-installed operating system"
        ])
    
    elif product_type == 'car':
        included.extend([
            "• Complete vehicle documentation",
            "• Spare tire and tools",
            "• Car keys (original and spare if available)",
            "• User manual and service records",
            "• Current registration and insurance details"
        ])
    
    else:
        included.append("• Item as described (please confirm details with seller)")
    
    return "\n".join(included) if included else None

def generate_comprehensive_fallback(title, category=None, brand=None, condition=None):
    """
    Comprehensive fallback when all other methods fail
    """
    try:
        base_description = generate_fallback_description(title, category, brand, condition)
        product_type = detect_product_type(title, category)
        
        # Add basic structured section
        structured_section = f"""
📋 PRODUCT DETAILS:
• Title: {title}
• Category: {category or 'Please specify'}
• Brand: {brand or 'Please specify'}
• Condition: {condition or 'Please specify'}

🔍 ADDITIONAL INFORMATION NEEDED:
Please contact seller for detailed specifications, exact condition, included accessories, and any other relevant information about this {title.lower()}.

📞 SELLER COMMUNICATION:
Feel free to ask questions about specifications, condition, price negotiation, viewing arrangements, and delivery options.
        """
        
        return f"{base_description}\n{structured_section.strip()}"
        
    except Exception as e:
        logger.error(f"Error in comprehensive fallback: {str(e)}")
        return f"Quality {title} available for sale. Contact seller for detailed information about specifications, condition, and pricing."

def clean_generated_description(generated_text, original_prompt):
    """
    Clean and format the generated description (keep existing implementation)
    """
    try:
        if original_prompt in generated_text:
            description = generated_text.replace(original_prompt, '').strip()
        else:
            description = generated_text.strip()
        
        unwanted_patterns = [
            'Write a detailed product description for:',
            'Product:', 'Description should be professional',
            'Category:', 'Brand:', 'Condition:'
        ]
        
        for pattern in unwanted_patterns:
            description = description.replace(pattern, '').strip()
        
        if description and not description[0].isupper():
            description = description[0].upper() + description[1:]
        
        # Limit the AI part to be concise since we're adding structured details
        if len(description) > 200:
            description = description[:197] + '...'
        
        return description if description else None
        
    except Exception as e:
        logger.error(f"Error cleaning generated description: {str(e)}")
        return None

def generate_fallback_description(title, category=None, brand=None, condition=None):
    """
    Generate a basic description when AI generation fails (keep existing but enhance)
    """
    try:
        description_parts = []
        
        if condition:
            if condition.lower() == 'new':
                description_parts.append(f"Brand new {title} in excellent condition, never used.")
            elif condition.lower() in ['like new', 'excellent']:
                description_parts.append(f"Premium quality {title} in like-new condition.")
            elif condition.lower() == 'good':
                description_parts.append(f"Well-maintained {title} in good working condition.")
            elif condition.lower() == 'fair':
                description_parts.append(f"Functional {title} in fair condition, perfect for budget-conscious buyers.")
            else:
                description_parts.append(f"Quality {title} in {condition.lower()} condition.")
        else:
            description_parts.append(f"Premium {title} available for sale.")
        
        if brand:
            description_parts.append(f"Authentic {brand} product ensuring reliability and quality.")
        
        # Category-specific descriptions
        category_descriptions = {
            'smartphones': 'Perfect for communication, entertainment, and productivity.',
            'tablets': 'Ideal for work, study, entertainment, and creative tasks.',
            'laptops': 'Great for professional work, students, and personal computing needs.',
            'electronics': 'Fully functional and ready for immediate use.',
            'vehicles': 'Well-maintained and roadworthy vehicle.',
            'fashion': 'Stylish and trendy fashion item.',
            'home appliances': 'Efficient and reliable home appliance.',
            'real estate': 'Prime property with excellent potential.',
        }
        
        category_key = category.lower() if category else 'general'
        for key, desc in category_descriptions.items():
            if key in category_key:
                description_parts.append(desc)
                break
        else:
            description_parts.append('Excellent value for money and ready for immediate use.')
        
        description_parts.append('Serious buyers only. Inspection welcome before purchase.')
        
        return ' '.join(description_parts)
        
    except Exception as e:
        logger.error(f"Error generating fallback description: {str(e)}")
        return f"Quality {title} available for sale. Contact seller for more information."

def get_remaining_descriptions(user):
    if not user.is_authenticated:
        return 0
    
    DAILY_LIMIT = 3
    today_count = AIDescriptionUsage.get_today_count(user)
    return max(0, DAILY_LIMIT - today_count)

# AJAX View remains the same
@require_http_methods(["POST"])
@csrf_exempt
def generate_ai_description(request):
    try:
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'You must be logged in to generate descriptions.'
            })
        
        # Check daily limit
        DAILY_LIMIT = 3
        today_count = AIDescriptionUsage.get_today_count(request.user)
        
        if today_count >= DAILY_LIMIT:
            return JsonResponse({
                'success': False,
                'error': f'Daily limit reached. You can generate {DAILY_LIMIT} descriptions per day. Try again tomorrow.'
            })
        
        data = json.loads(request.body)
        title = data.get('title', '').strip()
        category = data.get('category', '').strip()
        brand = data.get('brand', '').strip()
        condition = data.get('condition', '').strip()
                 
        if not title:
            return JsonResponse({
                'success': False,
                'error': 'Product title is required to generate description.'
            })
        
        # Generate description
        description = generate_product_description(title, category, brand, condition)
                 
        if description:
            # Increment usage count only on successful generation
            new_count = AIDescriptionUsage.increment_usage(request.user)
            remaining = DAILY_LIMIT - new_count
            
            return JsonResponse({
                'success': True,
                'description': description,
                'message': f'Description generated successfully! ({remaining} remaining today)',
                'remaining_today': remaining
            })
        else:
            fallback_description = generate_comprehensive_fallback(title, category, brand, condition)
            # Increment usage count for fallback too
            new_count = AIDescriptionUsage.increment_usage(request.user)
            remaining = DAILY_LIMIT - new_count
            
            return JsonResponse({
                'success': True,
                'description': fallback_description,
                'message': f'Description generated using template. ({remaining} remaining today)',
                'remaining_today': remaining
            })
                      
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request format.'
        })
    except Exception as e:
        logger.error(f"Error in generate_ai_description view: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while generating the description. Please try again.'
        })
        