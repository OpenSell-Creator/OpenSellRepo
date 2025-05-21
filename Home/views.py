from django.http import JsonResponse,HttpResponseRedirect
from django.db import IntegrityError
from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Product_Listing, Review, ReviewReply, SavedProduct, ProductReport
from User.models import LGA, State
from Dashboard.models import ProductBoost
from django.core.paginator import Paginator
from django.db.models import Q,F, Avg, Exists, OuterRef
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
from django.db.models import Count
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
import logging
import uuid

logger = logging.getLogger(__name__)

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

def format_price(price):
    return '₦ {:,.0f}'.format(Decimal(price))

def get_active_banners(location='home_top'):
    now = timezone.now()
    return Banner.objects.filter(
        Q(is_active=True) &
        Q(display_location=location) &
        (Q(start_date__isnull=True) | Q(start_date__lte=now)) &
        (Q(end_date__isnull=True) | Q(end_date__gte=now))
    ).order_by('-priority', '-updated_at')

def home(request):
    # Initialize context dictionary first
    context = {}
    
    # Get featured products
    featured_products = Product_Listing.objects.order_by('-created_at')[:20]
    
    # Get categories with product count
    categories = Category.objects.annotate(
        product_count=Count('product_listing')
    ).order_by('-product_count')[:6]
    
    # Handle saved products for authenticated users
    if request.user.is_authenticated:
        saved_products = SavedProduct.objects.filter(
            user=request.user
        ).values_list('product_id', flat=True)
        saved_products = set(str(id) for id in saved_products)
        
        for product in featured_products:
            product.is_saved = str(product.id) in saved_products
    
    # Get active banners
    active_banners = get_active_banners('home_top')
    
    # Clean up expired listings
    Product_Listing.delete_expired_listings()
    
    # Paginate featured products
    product_paginator = Paginator(featured_products, 8)
    product_page_number = request.GET.get('product_page')
    product_page_obj = product_paginator.get_page(product_page_number)
    
    # Format prices for products
    for product in product_page_obj:
        product.formatted_price = format_price(product.price)
    
    # Update context with all required data
    context.update({
        'categories': categories,
        'featured_products': product_page_obj,
        'banners': active_banners,
        'active_users_count': User.objects.filter(is_active=True).count(),
        'new_items_last_hour': Product_Listing.objects.filter(
            created_at__gte=timezone.now()-timedelta(hours=1)
        ).count(),
        'total_products': Product_Listing.objects.count(),
    })
    
    return render(request, 'home.html', context)
   
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
        queryset = Product_Listing.objects.all()
        
        # Try to delete expired listings first
        try:
            Product_Listing.delete_expired_listings()
        except:
            pass  # Silently fail if there's an issue
        
        # Get filter parameters
        category_slug = self.request.GET.get('category')
        subcategory_slug = self.request.GET.get('subcategory')
        query = self.request.GET.get('query')
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        condition = self.request.GET.get('condition')
        state = self.request.GET.get('state')
        lga = self.request.GET.get('lga')
        
        # Apply filters
        if query:
            queryset = queryset.filter(title__icontains=query)
        
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        if subcategory_slug:
            queryset = queryset.filter(subcategory__slug=subcategory_slug)
        
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        
        if condition:
            queryset = queryset.filter(condition=condition)
        
        if state:
            queryset = queryset.filter(seller__location__state=state)
        
        if lga:
            queryset = queryset.filter(seller__location__lga=lga)
        
        # Add saved status annotation for authenticated users
        if self.request.user.is_authenticated:
            queryset = queryset.annotate(
                is_saved=Exists(
                    SavedProduct.objects.filter(
                        user=self.request.user,
                        product_id=OuterRef('pk')
                    )
                )
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get category and subcategory counts using annotation
        categories = Category.objects.annotate(
            product_count=Count('product_listing')
        )
        
        # Prefetch subcategories with their product counts
        subcategories = Subcategory.objects.annotate(
            product_count=Count('products')
        )
        
        # Prefetch annotated subcategories with categories
        categories = categories.prefetch_related(
            Prefetch('subcategories', queryset=subcategories)
        )
        
        category_slug = self.request.GET.get('category')
        subcategory_slug = self.request.GET.get('subcategory')
        
        context['categories'] = categories
        context['global_categories'] = categories  # For the sidebar
        
        # Get states for the filter
        context['states'] = State.objects.all()
        
        # Get LGAs if state is selected
        state_id = self.request.GET.get('state')
        if state_id:
            context['lgas'] = LGA.objects.filter(state_id=state_id)
        
        # Get selected category by slug
        selected_category = None
        if category_slug:
            try:
                selected_category = categories.get(slug=category_slug)
                context['selected_category'] = selected_category.slug
                context['selected_category_obj'] = selected_category
                context['subcategories'] = selected_category.subcategories.all()
            except Category.DoesNotExist:
                pass
        
        # Get selected subcategory by slug
        selected_subcategory = None
        if subcategory_slug and selected_category:
            try:
                selected_subcategory = subcategories.get(slug=subcategory_slug)
                context['selected_subcategory'] = selected_subcategory.slug
            except Subcategory.DoesNotExist:
                pass
        
        # Format price for products
        for product in context['products']:
            product.formatted_price = self.format_price(product.price)
        
        # Check if products are saved by the user
        if self.request.user.is_authenticated:
            for product in context['products']:
                product.is_saved_by_user = product.is_saved_by_user(self.request.user)
        
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
            
            
        # Format the price
        context['formatted_price'] = self.format_price(self.object.price)
        
        # Get images
        context['images'] = self.object.images.all()
        context['primary_image'] = self.object.images.filter(is_primary=True).first() or self.object.images.first()
        
        # Get reviews with their replies
        reviews = self.object.reviews.select_related('reviewer').prefetch_related(
            Prefetch('replies', queryset=ReviewReply.objects.select_related('reviewer').order_by('created_at'))
            ).order_by('-created_at')
        
        total_reviews = reviews.count()
        
        # Calculate star percentages
        star_percentages  = {
            '5': reviews.filter(rating=5).count() / total_reviews * 100 if total_reviews else 0,
            '4': reviews.filter(rating=4).count() / total_reviews * 100 if total_reviews else 0,
            '3': reviews.filter(rating=3).count() / total_reviews * 100 if total_reviews else 0,
            '2': reviews.filter(rating=2).count() / total_reviews * 100 if total_reviews else 0,
            '1': reviews.filter(rating=1).count() / total_reviews * 100 if total_reviews else 0,
            }
        
        context['reviews'] = reviews
        context['star_percentages'] = star_percentages
        
        # Get reviews with their replies
        latest_review = reviews.first()
        context['latest_review'] = latest_review
        context['replies'] = latest_review.replies.all() if latest_review else []
        
        
        # Calculate review statistics
        context['review_count'] = reviews.count()
        context['average_rating'] = self.object.average_rating
        
        # Ensure seller rating is properly calculated
        context['seller_average_rating'] = self.object.seller.average_rating
        
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
    success_url = reverse_lazy('product_list')

    def test_func(self):
        product = self.get_object()
        return self.request.user == product.seller

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Product deleted successfully.')
        return super().delete(request, *args, **kwargs)
       
class ProductSearchView(ListView):
    model = Product_Listing
    template_name = 'product_search.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
    # Try to delete expired listings first
        try:
            Product_Listing.delete_expired_listings()
        except:
            pass  # Silently fail if there's an issue
        
        form = ProductSearchForm(self.request.GET)
        queryset = Product_Listing.objects.all()
        
        if form.is_valid():
            if form.cleaned_data['query']:
                queryset = queryset.filter(title__icontains=form.cleaned_data['query'])
            if form.cleaned_data['category']:
                queryset = queryset.filter(category=form.cleaned_data['category'])
            if form.cleaned_data['min_price']:
                queryset = queryset.filter(price__gte=form.cleaned_data['min_price'])
            if form.cleaned_data['max_price']:
                queryset = queryset.filter(price__lte=form.cleaned_data['max_price'])
            if form.cleaned_data['condition']:
                queryset = queryset.filter(condition=form.cleaned_data['condition'])
            if form.cleaned_data['state']:
                queryset = queryset.filter(seller__location__state=form.cleaned_data['state'])
            if form.cleaned_data['lga']:
                queryset = queryset.filter(seller__location__lga=form.cleaned_data['lga'])
        
        return queryset.order_by('-created_at')
    
    Product_Listing.delete_expired_listings()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ProductSearchForm(self.request.GET)
        
        
        if self.request.user.is_authenticated:
            saved_products = SavedProduct.objects.filter(
                user=self.request.user
            ).values_list('product_id', flat=True)
            
            # Convert to set of strings for faster lookup
            saved_products = set(str(id) for id in saved_products)
            
            # Add saved status and format price for each product
            for product in context['products']:
                product.is_saved = str(product.id) in saved_products
                product.formatted_price = self.format_price(product.price)
        else:
            # Just format prices if user is not authenticated
            for product in context['products']:
                product.formatted_price = self.format_price(product.price)
            
        return context

    def format_price(self, price):
        return '₦ {:,.0f}'.format(Decimal(price))
    
def get_lgas(request, state_id):
    lgas = LGA.objects.filter(state_id=state_id).values('id', 'name')
    return JsonResponse(list(lgas), safe=False)
       
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
def my_store(request, username=None):
    # Get store owner profile with related location data
    store_owner = get_object_or_404(
        User.objects.select_related(
            'profile',
            'profile__location',
            'profile__location__state',
            'profile__location__lga'
        ),
        username=username if username else request.user.username
    )

    # Get products with prefetched saved status
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
    
    if request.user.username == username:
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
                        recipient_list=['opensellmarketplace@gmail.com'],
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