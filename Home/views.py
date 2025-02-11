from django.http import JsonResponse,HttpResponseRedirect
from django.db import IntegrityError
from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Product_Listing, Review, ReviewReply, SavedProduct
from django.core.paginator import Paginator
from django.db.models import Q,F, Avg, Exists, OuterRef
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View
from django.urls import reverse_lazy
from .models import Subcategory,Category,Product_Listing,Brand,Product_Image,Banner
from .forms import ListingForm
from django.db.models import Prefetch
from django.contrib.auth.models import User
from .forms import ProductSearchForm, ReviewForm,ReviewReplyForm, Review
from django.utils import timezone
from decimal import Decimal
from django.db.models import Count
from datetime import timedelta
from django.core.exceptions import ValidationError
from User.models import Profile
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
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

def home(request):
    featured_products = Product_Listing.objects.order_by('-created_at')[:20]
    categories = Category.objects.all()
    
    if request.user.is_authenticated:
        saved_products = SavedProduct.objects.filter(
            user=request.user
        ).values_list('product_id', flat=True)
        saved_products = set(str(id) for id in saved_products)
        
        for product in featured_products:
            product.is_saved = str(product.id) in saved_products
    
    # Fetch all active banners
    active_banners = Banner.objects.filter(is_active=True)
    
    Product_Listing.delete_expired_listings()
    
    # Paginate featured products
    product_paginator = Paginator(featured_products, 20)  # Show 20 featured products per page
    product_page_number = request.GET.get('product_page')
    product_page_obj = product_paginator.get_page(product_page_number)
    
    for product in product_page_obj:
        product.formatted_price = format_price(product.price)
    
    context = {
        'categories': categories,
        'featured_products': product_page_obj,
        'banners': active_banners,
        'active_users_count': User.objects.filter(is_active=True).count(),
        'new_items_last_hour': Product_Listing.objects.filter(created_at__gte=timezone.now()-timedelta(hours=1)).count()
    }
    return render(request, 'home.html', context)
   
class ProductListView(ListView):
    model = Product_Listing
    template_name = 'product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        queryset = Product_Listing.objects.all()
        category_id = self.request.GET.get('category')
        subcategory_id = self.request.GET.get('subcategory')

        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if subcategory_id:
            queryset = queryset.filter(subcategory_id=subcategory_id)

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
        categories = Category.objects.all()
        selected_category_id = self.request.GET.get('category')
        selected_subcategory_id = self.request.GET.get('subcategory')

        context['categories'] = categories
        context['selected_category'] = int(selected_category_id) if selected_category_id else None
        context['selected_subcategory'] = int(selected_subcategory_id) if selected_subcategory_id else None

        if selected_category_id:
            selected_category = Category.objects.get(id=selected_category_id)
            context['selected_category_obj'] = selected_category
            context['subcategories'] = selected_category.subcategories.all()

        for product in context['products']:
            product.formatted_price = self.format_price(product.price)

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
                    'standard': 7,
                    'premium': 30,
                    'emergency': 3
                }.get(self.object.listing_type, 7)
                self.object.expiration_date = timezone.now() + timedelta(days=duration)
                self.object.save()
            
            # Handle images
            images = self.request.FILES.getlist('images')
            for i, image in enumerate(images[:5]):  # Limit to 5 images
                Product_Image.objects.create(
                    product=self.object,
                    image=image,
                    is_primary=(i == 0)
                )
            
            messages.success(self.request, 'Product created successfully.')
            return HttpResponseRedirect(self.get_success_url())
            
        except Exception as e:
            messages.error(self.request, f'Error creating product: {str(e)}')
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
                'standard': 7,
                'premium': 30,
                'emergency': 3
            }.get(self.object.listing_type)
            
            if self.object.listing_type != 'permanent':
                self.object.expiration_date = timezone.now() + timedelta(days=duration)
                self.object.deletion_warning_sent = False
            else:
                self.object.expiration_date = None
            
            self.object.save()
            
            # Handle images
            if form.cleaned_data.get('images'):
                # Delete existing images
                self.object.images.all().delete()
                # Save new images
                self.save_images(form.cleaned_data['images'])
            
            messages.success(self.request, 'Product updated successfully.')
            return HttpResponseRedirect(self.get_success_url())
        except Exception as e:
            messages.error(self.request, f'Error updating product: {str(e)}')
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
        product.is_saved = True  # These are saved products by definition
        products.append(product)
        
    Product_Listing.delete_expired_listings()
    # Add to context
    context = {
        'products': products  # Changed from saved_items to products
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
    # If username is provided, show that user's store, otherwise show current user's store
    store_owner = User.objects.get(username=username) if username else request.user
    
    # Get products for the store owner
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
    
    context = {
        'store_owner': store_owner,  # Changed from 'user' to 'store_owner'
        'products': user_products,
    }
    
    return render(request, 'my_store.html', context)