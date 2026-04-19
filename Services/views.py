from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse, Http404, HttpResponseRedirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, F, Count, Avg, Exists, OuterRef, Prefetch, Sum, Case, When, Value, IntegerField
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.exceptions import ValidationError
from datetime import timedelta
from decimal import Decimal
import json
import json as _json
import uuid
import logging

from Messages.models import Conversation, Message
from Messages.forms import MessageForm

from .models import (
    ServiceListing, ServiceInquiry, ServiceReview, ServiceReviewReply,
    ServiceImage, ServiceDocument,
    get_category_stats, get_service_category_choices
)
from .forms import (
    ServiceListingForm, ServiceSearchForm, ServiceInquiryForm,
    ServiceReviewForm, ServiceReviewReplyForm,
    QuickInquiryForm, InquiryResponseForm
)
from User.forms import ItemReportForm 
from User.models import ItemReport, SavedItem, State, LGA

try:
    from Home.views import get_active_banners
except ImportError:
    def get_active_banners(location='global'):
        return []

try:
    from Dashboard.models import ProductBoost
    BOOST_AVAILABLE = True
except ImportError:
    BOOST_AVAILABLE = False

from Notifications.models import (
    create_notification, 
    NotificationCategory, 
    NotificationPriority
)

logger = logging.getLogger(__name__)

def format_service_price(pricing_type, base_price=None, min_price=None, max_price=None):
    """Format service price display (following existing price formatting pattern)"""
    if pricing_type == 'fixed' and base_price:
        return f"₦{base_price:,.0f}"
    elif pricing_type == 'hourly' and base_price:
        return f"₦{base_price:,.0f}/hour"
    elif pricing_type == 'project' and base_price:
        return f"₦{base_price:,.0f}/project"
    elif pricing_type == 'negotiable':
        if min_price and max_price:
            return f"₦{min_price:,.0f} - ₦{max_price:,.0f}"
        return "Negotiable"
    return "Contact for pricing"

def get_client_ip(request):
    """Get client IP address (utility function)"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_sorted_services(base_queryset, user=None, limit=None):
    """
    Efficient service sorting with boost support (following Home app pattern)
    """
    if not base_queryset.exists():
        return base_queryset.none()
    
    try:
        # Use simple, efficient database-level sorting
        sorted_queryset = base_queryset.annotate(
            # Verification priority
            verification_score=Case(
                When(provider__business_verification_status='verified', then=Value(100)),
                default=Value(0),
                output_field=IntegerField()
            ),
            # Pro user priority
            pro_score=Case(
                When(provider__user__account__effective_status__tier_type='pro', then=Value(50)),
                default=Value(0),
                output_field=IntegerField()
            ),
            # Total priority score
            total_score=F('boost_score') + F('verification_score') + F('pro_score')
        ).order_by('-total_score', '-created_at', 'title')
        
        if limit:
            sorted_queryset = sorted_queryset[:limit]
        
        return sorted_queryset
        
    except Exception:
        # Simple fallback
        return base_queryset.order_by('-boost_score', '-created_at')[:limit] if limit else base_queryset.order_by('-boost_score', '-created_at')

class ServiceListView(ListView):
    """List view for services (following ProductListView pattern)"""
    model = ServiceListing
    template_name = 'services/service_list.html'
    context_object_name = 'services'
    paginate_by = 12

    def paginate_queryset(self, queryset, page_size):
        """Simplified pagination with better error handling (following existing pattern)"""
        paginator = self.get_paginator(queryset, page_size)
        page = self.request.GET.get('page', 1)
        
        try:
            page_number = int(page)
            page_obj = paginator.page(page_number)
            return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())
        except (ValueError, EmptyPage):
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Return empty results for AJAX
                dummy_page = paginator.page(1) if paginator.num_pages > 0 else None
                return (paginator, dummy_page, [], False)
            else:
                # Redirect to first page for regular requests
                raise Http404("Page not found")

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                page_obj = context.get('page_obj')
                services = context.get('services', [])
                
                if not page_obj:
                    return JsonResponse({
                        'success': True,
                        'services_html': [],
                        'has_more': False,
                        'current_page': 1,
                        'total_pages': 0
                    })
                
                # Process services for saved status
                if self.request.user.is_authenticated:
                    from django.contrib.contenttypes.models import ContentType
                    
                    service_ct = ContentType.objects.get_for_model(ServiceListing)
                    
                    saved_services = SavedItem.objects.filter(
                        user=self.request.user,
                        content_type=service_ct
                    ).values_list('object_id', flat=True)
                    
                    saved_services_set = set(str(id) for id in saved_services)
                    
                    for service in services:
                        service.is_saved = str(service.id) in saved_services_set
                        service.formatted_price = format_service_price(
                            service.pricing_type, service.base_price, service.min_price, service.max_price
                        )
                else:
                    for service in services:
                        service.formatted_price = format_service_price(
                            service.pricing_type, service.base_price, service.min_price, service.max_price
                        )
                
                # Render service cards
                services_html = []
                for service in services:
                    try:
                        service_html = render_to_string('services/service_card.html', {
                            'service': service,
                            'user': self.request.user
                        }, request=self.request)
                        services_html.append(service_html)
                    except Exception:
                        continue
                
                return JsonResponse({
                    'success': True,
                    'services_html': services_html,
                    'has_more': page_obj.has_next(),
                    'current_page': page_obj.number,
                    'total_pages': page_obj.paginator.num_pages,
                    'total_count': page_obj.paginator.count
                })
                
            except Exception:
                return JsonResponse({
                    'success': False,
                    'error': 'An error occurred while loading more services',
                    'services_html': [],
                    'has_more': False
                }, status=500)
        
        return super().render_to_response(context, **response_kwargs)

    def get_queryset(self):

        # Base queryset with proper select_related
        queryset = ServiceListing.objects.filter(
            is_active=True,
            is_suspended=False
        ).select_related(
            'provider__user',
            'provider__location__state',
            'provider__location__lga',
            'location__state',
            'location__lga',
        ).prefetch_related('images', 'reviews')
        

        get_params = self.request.GET.copy()
        if get_params.get('min_budget') and not get_params.get('min_price'):
            get_params['min_price'] = get_params['min_budget']
        if get_params.get('max_budget') and not get_params.get('max_price'):
            get_params['max_price'] = get_params['max_budget']

        # Handle price_range from sidebar filter first
        price_range = get_params.get('price_range', '')
        if price_range:
            try:
                if '-' in price_range:
                    min_val, max_val = price_range.split('-')
                    min_price_val = Decimal(min_val)
                    max_price_val = Decimal(max_val)
                    
                    queryset = queryset.filter(
                        Q(base_price__gte=min_price_val, base_price__lte=max_price_val) |
                        Q(min_price__gte=min_price_val, max_price__lte=max_price_val)
                    )
            except (ValueError, TypeError, AttributeError):
                pass  
            
        form = ServiceSearchForm(get_params)
        if form.is_valid():
            query = form.cleaned_data.get('query')
            service_type = form.cleaned_data.get('service_type')
            category = form.cleaned_data.get('category')
            pricing_type = form.cleaned_data.get('pricing_type')
            min_price = form.cleaned_data.get('min_price')
            max_price = form.cleaned_data.get('max_price')
            experience_level = form.cleaned_data.get('experience_level')
            availability = form.cleaned_data.get('availability')
            delivery_method = form.cleaned_data.get('delivery_method')
            verified_only = form.cleaned_data.get('verified_only')

            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) | 
                    Q(description__icontains=query) |
                    Q(what_you_get__icontains=query) |
                    Q(skills_offered__icontains=query)
                )
            
            if service_type:
                queryset = queryset.filter(service_type=service_type)
            
            if category:
                queryset = queryset.filter(category=category)
                
            if pricing_type:
                queryset = queryset.filter(pricing_type=pricing_type)
                
            # Only apply individual min/max if price_range not already applied
            if min_price and not get_params.get('price_range'):
                queryset = queryset.filter(
                    Q(base_price__gte=min_price) |
                    Q(min_price__gte=min_price)
                )
                
            if max_price and not get_params.get('price_range'):
                queryset = queryset.filter(
                    Q(base_price__lte=max_price) |
                    Q(max_price__lte=max_price)
                )
                
            if experience_level:
                queryset = queryset.filter(experience_level=experience_level)
                
            if availability:
                queryset = queryset.filter(availability=availability)
                
            if delivery_method:
                queryset = queryset.filter(delivery_method=delivery_method)
                
            if verified_only:
                queryset = queryset.filter(provider__business_verification_status='verified')

        raw_pricing_type = self.request.GET.get('pricing_type', '').strip()
        if raw_pricing_type:
            # Only apply if the form didn't already filter it
            if not (form.is_valid() and form.cleaned_data.get('pricing_type')):
                queryset = queryset.filter(pricing_type=raw_pricing_type)

        # ── NEW from unified sidebar v2: available_only ───────────────────────
        # ?available_only=true  →  provider.available_for_services = True
        if self.request.GET.get('available_only') == 'true':
            queryset = queryset.filter(provider__available_for_services=True)

        state_id_raw = self.request.GET.get('state', '').strip()
        lga_id_raw = self.request.GET.get('lga', '').strip()

        if state_id_raw:
            try:
                state_id_int = int(state_id_raw)

                queryset = queryset.filter(
                    Q(location__state_id=state_id_int) |
                    Q(provider__location__state_id=state_id_int)
                )
            except (ValueError, TypeError):
                pass

        if lga_id_raw:
            try:
                lga_id_int = int(lga_id_raw)
                # Same dual-path approach for LGA
                queryset = queryset.filter(
                    Q(location__lga_id=lga_id_int) |
                    Q(provider__location__lga_id=lga_id_int)
                )
            except (ValueError, TypeError):
                pass 
        # Apply sorting
        sort_by = self.request.GET.get('sort', 'smart')
        
        if sort_by == 'smart':
            return get_sorted_services(queryset)
        else:
            # Simple sorting options
            sort_options = {
                '-created_at': '-created_at',
                'created_at': 'created_at', 
                'price_low': 'base_price',
                'price_high': '-base_price',
                'rating': '-average_rating',
                'title': 'title'
            }
            
            order_by = sort_options.get(sort_by, '-created_at')
            return queryset.order_by(order_by)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get categories with service counts (simplified approach)
        category_stats = get_category_stats()
        
        # Convert category stats to list format expected by unified sidebar.
        # 'id' aliases 'code' so {{ category.id }} in the template renders the
        # same string the <option value= uses, letting JS data-id lookups work.
        categories_list = []
        for category_key, category_data in category_stats.items():
            categories_list.append({
                'code': category_key,
                'id': category_key,          # satisfies {{ category.id }} in sidebar
                'name': category_data['name'],
                'total_services': category_data['total_services']
            })
        
        context['categories'] = categories_list  # For unified sidebar
        context['category_stats'] = category_stats  # For category grid/pills
        context['search_form'] = ServiceSearchForm(self.request.GET)
        context['states'] = State.objects.filter(is_active=True).order_by('name')
        context['item_type'] = 'services'
        context['filter_action_url'] = self.request.path
        context['selected_category']    = self.request.GET.get('category', '')
        # Services have no subcategory/brand — set empty strings so sidebar
        # data-* attributes don't render as the literal string "None"
        context['selected_subcategory'] = ''
        context['selected_brand']       = ''
        context['subcategories']        = []   # sidebar template references this
        context['brands']               = []   # sidebar template references this

        # Handle state/LGA context for sidebar and advanced filters.
        # When ?state= is present we pass the full LGA queryset so the sidebar
        # can render them server-side (no AJAX needed on page load).
        state_id = self.request.GET.get('state', '').strip()
        lga_id = self.request.GET.get('lga', '').strip()
        if state_id:
            try:
                lgas_qs = LGA.objects.filter(
                    state_id=int(state_id),
                    is_active=True
                ).order_by('name')
                context['lgas'] = lgas_qs
                # Pass the raw ID string (not the State object) so that the sidebar
                # data-selected-state attribute renders a numeric ID that matches the
                # state <option value="..."> and JS selection restore works correctly.
                context['selected_state'] = state_id
                context['selected_lga'] = lga_id
            except (ValueError, TypeError):
                context['lgas'] = LGA.objects.none()
                context['selected_state'] = ''
                context['selected_lga'] = ''
        else:
            context['lgas'] = LGA.objects.none()
            context['selected_state'] = ''
            context['selected_lga'] = ''
        
        # Add saved status and format prices
        if self.request.user.is_authenticated:
            from django.contrib.contenttypes.models import ContentType
            
            # Get ContentType for ServiceListing
            service_ct = ContentType.objects.get_for_model(ServiceListing)
            
            # Query using content_type and object_id
            saved_services = SavedItem.objects.filter(
                user=self.request.user,
                content_type=service_ct
            ).values_list('object_id', flat=True)
            
            saved_services_set = set(str(id) for id in saved_services)
            
            for service in context['services']:
                service.is_saved = str(service.id) in saved_services_set
                service.formatted_price = format_service_price(
                    service.pricing_type, service.base_price, service.min_price, service.max_price
                )
        else:
            for service in context['services']:
                service.formatted_price = format_service_price(
                    service.pricing_type, service.base_price, service.min_price, service.max_price
                )
        
        context['current_sort'] = self.request.GET.get('sort', 'smart')
        
        # Get global banners
        global_banners = get_active_banners('global')
        context['global_banners'] = global_banners
        
        return context

class ServiceDetailView(DetailView):
    """Detail view for services (following ProductDetailView pattern)"""
    model = ServiceListing
    template_name = 'services/service_detail.html'
    context_object_name = 'service'

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)

        # Record view count (following existing pattern)
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key

        if f'viewed_service_{self.object.id}' not in request.session:
            self.object.increase_view_count()
            request.session[f'viewed_service_{self.object.id}'] = True
        
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Check if user can inquire and send messages
        if self.request.user.is_authenticated:
            context['can_inquire'] = (
                self.request.user.profile != self.object.provider and
                not ServiceInquiry.objects.filter(
                    service=self.object, 
                    client=self.request.user.profile
                ).exists()
            )
            
            if context['can_inquire']:
                context['inquiry_form'] = ServiceInquiryForm(
                    service=self.object,
                    user=self.request.user
                )
            
            # Check if user has saved this service
            from django.contrib.contenttypes.models import ContentType
            
            service_ct = ContentType.objects.get_for_model(ServiceListing)
            
            context['is_saved'] = SavedItem.objects.filter(
                user=self.request.user,
                content_type=service_ct,
                object_id=str(self.object.id)
            ).exists()
            
            # Get user's inquiry if exists
            context['user_inquiry'] = ServiceInquiry.objects.filter(
                service=self.object,
                client=self.request.user.profile
            ).first()
            
        # Format price (following existing pattern)
        context['formatted_price'] = format_service_price(
            self.object.pricing_type, self.object.base_price, 
            self.object.min_price, self.object.max_price
        )

        # Add images and documents
        context['images'] = self.object.images.all()
        context['documents'] = self.object.documents.all()
        context['primary_image'] = self.object.primary_image

        # Get reviews with replies (following existing pattern)
        reviews = self.object.reviews.select_related('reviewer').prefetch_related(
            Prefetch('replies', queryset=ServiceReviewReply.objects.select_related('replier').order_by('created_at'))
        ).order_by('-created_at')[:5]  # Only show 5 reviews initially

        context['reviews'] = reviews
        context['total_reviews'] = self.object.reviews.count()
        context['average_rating'] = self.object.average_rating
        context['has_more_reviews'] = self.object.reviews.count() > 5

        # Provider details (following existing pattern)
        provider = self.object.provider
        
        provider_services_count = ServiceListing.objects.filter(
            provider=provider,
            is_active=True,
            is_suspended=False
        ).count()

        total_provider_reviews = ServiceReview.objects.filter(
            service__provider=provider
        ).count()
        
        provider_avg_rating = ServiceReview.objects.filter(
            service__provider=provider
        ).aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0

        context['provider_details'] = {
            'name': provider.user.username,
            'phone': provider.phone_number,
            'email': provider.user.email,
            'is_verified_business': provider.business_verification_status == 'verified',
            'business_name': provider.business_name if provider.business_verification_status == 'verified' else None,
            'total_services': provider_services_count,
            'total_reviews': total_provider_reviews,
            'average_rating': provider_avg_rating,
            'member_since': provider.user.date_joined,
        }

        # Related services (following existing pattern)
        related_services = ServiceListing.objects.filter(
            category=self.object.category
        ).exclude(id=self.object.id).filter(
            is_active=True,
            is_suspended=False
        ).distinct()[:4]
        
        if self.request.user.is_authenticated:
            from django.contrib.contenttypes.models import ContentType
            
            service_ct = ContentType.objects.get_for_model(ServiceListing)
            
            # Query related services saved status
            saved_services = SavedItem.objects.filter(
                user=self.request.user,
                content_type=service_ct,
                object_id__in=[str(s.id) for s in related_services]
            ).values_list('object_id', flat=True)
            
            saved_services_set = set(str(id) for id in saved_services)
            
            for service in related_services:
                service.is_saved = str(service.id) in saved_services_set
                
        context['related_services'] = related_services
        
        # Format prices for related services
        for service in context['related_services']:
            service.formatted_price = format_service_price(
                service.pricing_type, service.base_price, service.min_price, service.max_price
            )

        # Add time since creation (following existing pattern)
        context['created_at'] = self.object.created_at
        time_since_creation = timezone.now() - self.object.created_at
        
        if time_since_creation.days > 0:
            context['time_since_creation'] = f"{time_since_creation.days} days ago"
        elif time_since_creation.seconds // 3600 > 0:
            context['time_since_creation'] = f"{time_since_creation.seconds // 3600} hours ago"
        else:
            context['time_since_creation'] = f"{time_since_creation.seconds // 60} minutes ago"

        # Add review form to context
        context['review_form'] = ServiceReviewForm()
        
        # Get global banners (following existing pattern)
        global_banners = get_active_banners('global')
        context['global_banners'] = global_banners
        
        if self.request.user.is_authenticated:
            from Services.views import add_messaging_context
            add_messaging_context(context, self.object, self.request.user)
            
        return context

    def get_queryset(self):
        # Optimize the main query (following existing pattern)
        return super().get_queryset().select_related(
            'provider',
            'provider__user',
            'provider__location',
            'provider__location__state',
            'provider__location__lga',
        )

class ServiceCreateView(LoginRequiredMixin, CreateView):
    """Create view for services - FIXED to prevent duplicates"""
    model = ServiceListing
    form_class = ServiceListingForm
    template_name = 'services/service_form.html'
    success_url = reverse_lazy('services:my_services')
    
    def get_form_kwargs(self):
        """Pass the current user to the form"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        try:
            logger.info("Starting service creation")
            
            # Use commit=False to prevent immediate save
            service = form.save(commit=False)
            
            # Set all required fields
            service.provider = self.request.user.profile
            logger.info(f"Set provider to: {self.request.user.profile}")
            
            # Set expiration date
            if not service.expiration_date:
                try:
                    if self.request.user.account.effective_status.tier_type == 'pro':
                        service.expiration_date = timezone.now() + timedelta(days=90)
                        service.is_featured = True
                        logger.info("Set as Pro user - 90 days expiration, featured")
                    else:
                        service.expiration_date = timezone.now() + timedelta(days=60)
                        logger.info("Set as regular user - 60 days expiration")
                except Exception:
                    service.expiration_date = timezone.now() + timedelta(days=60)
                    logger.info("Exception setting expiration - using 60 days default")
            
            # Ensure integer fields have values
            if service.revision_limit is None:
                service.revision_limit = 2
            
            if service.delivery_days is None:
                service.delivery_days = 7
            
            # SINGLE SAVE - Save ONLY ONCE
            service.save()
            self.object = service
            
            logger.info(f"Service saved successfully with ID: {service.id}")
            
            # Handle images
            images = self.request.FILES.getlist('images')
            logger.info(f"Processing {len(images)} images")
            
            for i, image in enumerate(images[:5]):
                try:
                    if image.size > 5 * 1024 * 1024:  # 5MB
                        messages.warning(
                            self.request, 
                            f'Image "{image.name}" was too large and was skipped.'
                        )
                        logger.warning(f"Image {image.name} too large: {image.size} bytes")
                        continue
                    
                    ServiceImage.objects.create(
                        service=service,
                        image=image,
                        is_primary=(i == 0)
                    )
                    logger.info(f"Created image {i+1}: {image.name}")
                except Exception as img_error:
                    logger.error(f"Error processing image: {str(img_error)}", exc_info=True)
                    messages.warning(
                        self.request, 
                        f'Failed to process image "{image.name}": {str(img_error)}'
                    )
            
            # Handle documents
            documents = self.request.FILES.getlist('documents')
            logger.info(f"Processing {len(documents)} documents")
            
            for document in documents[:10]:
                try:
                    if document.size > 10 * 1024 * 1024:  # 10MB
                        messages.warning(
                            self.request, 
                            f'Document "{document.name}" was too large and was skipped.'
                        )
                        logger.warning(f"Document {document.name} too large: {document.size} bytes")
                        continue
                    
                    ServiceDocument.objects.create(
                        service=service,
                        document=document,
                        title=document.name
                    )
                    logger.info(f"Created document: {document.name}")
                except Exception as doc_error:
                    logger.error(f"Error processing document: {str(doc_error)}", exc_info=True)
                    messages.warning(
                        self.request, 
                        f'Failed to process document "{document.name}": {str(doc_error)}'
                    )
            
            messages.success(self.request, 'Your service has been listed successfully!')
            logger.info("Service creation completed successfully")
            
            # Handle AJAX requests
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': 'Service created successfully',
                    'redirect_url': str(self.get_success_url())
                })
            
            return HttpResponseRedirect(self.get_success_url())
            
        except Exception as e:
            logger.error(f"Error creating service: {str(e)}", exc_info=True)
            messages.error(self.request, f'Error creating service: {str(e)}')
            
            # Handle AJAX requests with error
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error creating service: {str(e)}'
                }, status=500)
            
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Handle invalid form for AJAX requests"""
        logger.error(f"Form validation failed: {form.errors}")
        logger.error(f"Form data: {form.data}")
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_messages = []
            for field, errors in form.errors.items():
                if field == '__all__':
                    error_messages.extend(errors)
                else:
                    field_label = form.fields[field].label or field
                    for error in errors:
                        error_messages.append(f"{field_label}: {error}")
            
            return JsonResponse({
                'success': False,
                'error': ' | '.join(error_messages) if error_messages else 'Form validation failed',
                'errors': dict(form.errors)
            }, status=400)
        
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'List Your Service'
        context['save_button'] = 'List Service'
        return context

class ServiceUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update view for services (following ProductUpdateView pattern)"""
    model = ServiceListing
    form_class = ServiceListingForm
    template_name = 'services/service_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def test_func(self):
        service = self.get_object()
        return self.request.user == service.provider.user

    def form_valid(self, form):
        try:
            self.object = form.save()
            
            # Handle images - ONLY delete and replace if new images are uploaded
            if form.cleaned_data.get('images'):
                # Delete existing images
                for image in self.object.images.all():
                    image.delete()
                
                # Save new images
                images = form.cleaned_data['images']
                for i, image in enumerate(images[:5]):
                    try:
                        if image.size > 5 * 1024 * 1024:  # 5MB
                            messages.warning(
                                self.request, 
                                f'Image "{image.name}" was too large and was skipped.'
                            )
                            continue
                        
                        ServiceImage.objects.create(
                            service=self.object,
                            image=image,
                            is_primary=(i == 0)
                        )
                    except Exception as img_error:
                        messages.warning(
                            self.request, 
                            f'Failed to process image "{image.name}": {str(img_error)}'
                        )
            
            # Handle documents - ONLY delete and replace if new documents are uploaded
            if form.cleaned_data.get('documents'):
                # Delete existing documents
                for document in self.object.documents.all():
                    document.delete()
                
                # Save new documents
                documents = form.cleaned_data['documents']
                for document in documents[:10]:
                    try:
                        if document.size > 10 * 1024 * 1024:  # 10MB
                            messages.warning(
                                self.request, 
                                f'Document "{document.name}" was too large and was skipped.'
                            )
                            continue
                        
                        ServiceDocument.objects.create(
                            service=self.object,
                            document=document,
                            title=document.name
                        )
                    except Exception as doc_error:
                        messages.warning(
                            self.request, 
                            f'Failed to process document "{document.name}": {str(doc_error)}'
                        )
            
            messages.success(self.request, 'Service updated successfully.')

            redirect_url = reverse('services:detail', kwargs={'pk': self.object.pk})

            # AJAX-aware — service_form.html submits via fetch()
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': 'Service updated successfully',
                    'redirect_url': redirect_url,
                })

            return redirect(redirect_url)

        except Exception as e:
            logger.error(f'Error updating service: {str(e)}', exc_info=True)
            error_message = f'Error updating service: {str(e)}'
            messages.error(self.request, error_message)

            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': error_message,
                }, status=500)

            return self.form_invalid(form)

    def form_invalid(self, form):
        """Mirror CreateView behaviour — return JSON for AJAX, HTML otherwise."""
        logger.error(f'Update form validation failed: {form.errors}')

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_messages = []
            for field, errors in form.errors.items():
                if field == '__all__':
                    error_messages.extend(errors)
                else:
                    field_label = form.fields[field].label or field
                    for error in errors:
                        error_messages.append(f'{field_label}: {error}')

            return JsonResponse({
                'status': 'error',
                'message': ' | '.join(error_messages) if error_messages else 'Form validation failed',
                'errors': dict(form.errors),
            }, status=400)

        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Service'
        context['save_button'] = 'Update Service'
        return context

class ServiceDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete view for services (following ProductDeleteView pattern)"""
    model = ServiceListing
    template_name = 'services/service_confirm_delete.html'
    success_url = reverse_lazy('manage_listings')

    def test_func(self):
        service = self.get_object()
        return self.request.user == service.provider.user

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Service deleted successfully.')
        return super().delete(request, *args, **kwargs)

@login_required
def my_services(request):
    """View for user's own services (following my_store pattern)"""
    services_qs = ServiceListing.objects.filter(
        provider=request.user.profile
    ).prefetch_related(
        'inquiries', 'images', 'reviews'
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(services_qs, 10)
    page = request.GET.get('page')
    
    try:
        services = paginator.page(page)
    except PageNotAnInteger:
        services = paginator.page(1)
    except EmptyPage:
        services = paginator.page(paginator.num_pages)
    
    # Statistics (following existing pattern)
    stats = {
        'total': ServiceListing.objects.filter(provider=request.user.profile).count(),
        'active': ServiceListing.objects.filter(provider=request.user.profile, is_active=True).count(),
        'inquiries': ServiceInquiry.objects.filter(service__provider=request.user.profile).count(),
        'total_views': ServiceListing.objects.filter(provider=request.user.profile).aggregate(
            total=Sum('view_count')
        )['total'] or 0,
        'avg_rating': ServiceReview.objects.filter(
            service__provider=request.user.profile
        ).aggregate(avg=Avg('rating'))['avg'] or 0,
    }
    
    # Get recent inquiries
    recent_inquiries = ServiceInquiry.objects.filter(
        service__provider=request.user.profile
    ).select_related('client__user', 'service').order_by('-created_at')[:5]
    
    context = {
        'services': services,
        'stats': stats,
        'recent_inquiries': recent_inquiries,
    }
    
    return render(request, 'services/my_services.html', context)

def can_user_inquire_about_service(user, service):
    """
    Check whether a user is allowed to submit a new inquiry.
    Blocks only active inquiries (pending / responded / negotiating / accepted).
    Allows re-inquiry after a previous one was declined, completed, or cancelled.
    """
    try:
        if not user.is_authenticated:
            return False, 'login_required'

        if hasattr(user, 'profile') and user.profile == service.provider:
            return False, 'owner'

        if service.is_suspended or not service.is_active:
            return False, 'unavailable'

        # Only block if there is an ACTIVE (non-terminal) inquiry
        active_statuses = ('pending', 'responded', 'negotiating', 'accepted')
        active_inquiry_exists = ServiceInquiry.objects.filter(
            service=service,
            client=user.profile,
            status__in=active_statuses
        ).exists()

        if active_inquiry_exists:
            return False, 'already_inquired'

        return True, 'can_inquire'

    except Exception as e:
        logger.error(f"Error checking inquiry permissions: {str(e)}")
        return False, 'error'

def build_inquiry_summary(inquiry):
    """
    Serialize ServiceInquiry structured fields into a JSON string.
    This string is stored as the encrypted message content.
    The template reads inquiry_type == SERVICE_INQUIRY_CARD and
    renders a card instead of a plain bubble.
    """
    return _json.dumps({
        'type':              'SERVICE_INQUIRY_CARD',
        'inquiry_id':        str(inquiry.id),
        'message':           inquiry.message,
        'budget':            str(inquiry.budget) if inquiry.budget else None,
        'timeline':          inquiry.timeline      or '',
        'requirements':      inquiry.requirements  or '',
        'preferred_contact': inquiry.preferred_contact,
        'contact_phone':     inquiry.contact_phone or '',
        'contact_email':     inquiry.contact_email or '',
    })

@login_required
@require_POST
def create_inquiry(request, service_id):
    """
    Create a ServiceInquiry AND bridge it into the messaging system.
    The inquiry is saved, then a conversation is created (or reused),
    and the structured inquiry data is posted as a typed message.
    The user is redirected to the conversation — not the service detail.
    """
    try:
        service = get_object_or_404(ServiceListing, id=service_id)

        # Permission check
        can_inquire, reason = can_user_inquire_about_service(request.user, service)
        if not can_inquire:
            error_messages = {
                'owner':            'You cannot inquire about your own service.',
                'unavailable':      'This service is currently unavailable.',
                'already_inquired': 'You already have an active inquiry for this service.',
                'login_required':   'You must be logged in to make an inquiry.',
            }
            return JsonResponse({
                'success': False,
                'error': error_messages.get(reason, 'You cannot inquire about this service.')
            })

        form = ServiceInquiryForm(request.POST, service=service, user=request.user)

        if form.is_valid():
            from django.db import transaction
            from Messages.models import Conversation

            with transaction.atomic():
                inquiry = form.save(commit=False)
                inquiry.service = service
                inquiry.client  = request.user.profile

                # ── BRIDGE STEP 1: get or create conversation ──────────────
                conversation, _ = Conversation.get_or_create_for_item(
                    item=service,
                    user_profile=request.user.profile
                )
                inquiry.conversation = conversation
                inquiry.save()

                # ── BRIDGE STEP 2: post structured message into conversation ─
                summary = build_inquiry_summary(inquiry)
                conversation.add_message(
                    sender=request.user.profile,
                    content=summary,
                    inquiry_type='SERVICE_INQUIRY_CARD'
                )

                # ── BRIDGE STEP 3: notify provider — point to inbox ────────
                create_notification(
                    user=service.provider.user,
                    title=f"New Inquiry: {service.title}",
                    message=(
                        f"{request.user.username} sent a service inquiry. "
                        f"Open your inbox to respond."
                    ),
                    category=NotificationCategory.ALERTS,
                    priority=NotificationPriority.HIGH,
                    content_object=service,
                    action_url=reverse('conversation_detail', kwargs={'conversation_uuid': conversation.uuid}),
                    action_text='View in Inbox'
                )

            messages.success(request, "Your inquiry has been sent successfully!")


            return JsonResponse({
                'success':  True,
                'redirect': reverse('conversation_detail', kwargs={'conversation_uuid': conversation.uuid})
            })

        else:
            return JsonResponse({'success': False, 'errors': form.errors})

    except Exception as e:
        logger.error(f"Error creating inquiry: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'An error occurred. Please try again.'})

def service_categories(request):
    """View services by categories"""
    category_stats = get_category_stats()
    
    selected_category = request.GET.get('category')
    
    context = {
        'categories': category_stats,
        'selected_category': selected_category,
        'service_categories': get_service_category_choices()
    }
    return render(request, 'services/service_categories.html', context)

@login_required
def submit_service_review(request, service_id):
    """Submit service review"""
    service = get_object_or_404(ServiceListing, id=service_id)
    
    # Check if user can review
    if service.provider.user == request.user:
        messages.error(request, "You cannot review your own service.")
        return redirect('services:detail', pk=service_id)
    
    # Check if user already reviewed
    if ServiceReview.objects.filter(service=service, reviewer=request.user).exists():
        messages.error(request, "You have already reviewed this service.")
        return redirect('services:detail', pk=service_id)

    if request.method == 'POST':
        form = ServiceReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.service = service
            review.reviewer = request.user
            review.save()
            
            # NOTIFY SERVICE PROVIDER
            create_notification(
                user=service.provider.user,
                title=f"New Review: {service.title}",
                message=f"{request.user.username} left a {review.rating}⭐ review on your service.",
                category=NotificationCategory.REVIEW,
                priority=NotificationPriority.NORMAL,
                content_object=service,
                action_url=f'/services/{service.id}/#reviews',
                action_text='View Review'
            )
            
            messages.success(request, "Your review has been submitted successfully.")
            return redirect('services:detail', pk=service_id)
    else:
        form = ServiceReviewForm()

    context = {'form': form, 'service': service}
    return render(request, 'services/submit_review.html', context)

@require_http_methods(["GET", "POST"])
def report_service(request, service_id):
    """
    UNIFIED: Report a service using ItemReport.
    Redirects to unified report view.
    """
    service = get_object_or_404(ServiceListing, id=service_id)
    return redirect('report_item', content_type='service', item_id=service.id)

@login_required
def my_inquiries(request):
    """
    Service provider's inquiry management page.
 
    Supports two independent query-string filters that work together:
      ?status=pending|responded|accepted|declined  — server-side status filter
      ?service=<uuid>                              — filter to one service
                                                     (used by manage.html "Inquiries (N)" button)
 
    Both filters are passed through into every pagination link via the
    `query_params` context variable so page navigation preserves filters.
    """
    base_qs = ServiceInquiry.objects.filter(
        service__provider=request.user.profile
    ).select_related('client__user', 'service').order_by('-created_at')
 
    # ── Status filter (server-side, replaces the old client-side JS tabs) ──
    current_status = request.GET.get('status', '').strip()
    valid_statuses = {'pending', 'responded', 'accepted', 'declined'}
    if current_status in valid_statuses:
        inquiries_qs = base_qs.filter(status=current_status)
    else:
        current_status = ''        # normalise unknown/empty values
        inquiries_qs = base_qs
 
    # ── Optional service filter (used by manage.html per-service button) ──
    service_filter = request.GET.get('service', '').strip()
    if service_filter:
        inquiries_qs = inquiries_qs.filter(service_id=service_filter)
 
    # ── Pagination ────────────────────────────────────────────────────────
    paginator = Paginator(inquiries_qs, 15)
    page = request.GET.get('page')
    try:
        inquiries = paginator.page(page)
    except PageNotAnInteger:
        inquiries = paginator.page(1)
    except EmptyPage:
        inquiries = paginator.page(paginator.num_pages)
 
    # ── Build the query_params string for pagination links that preserves
    #    status + service filters without duplicating ?page= ──────────────
    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()   # e.g. "status=pending&service=abc"
 
    # ── Annotate each inquiry with its linked conversation URL ───────────
    #    so the template can render a direct "View Conversation" link.
    for inq in inquiries:
        conv = getattr(inq, 'conversation', None)
        inq.conversation_url = (
            reverse('conversation_detail', kwargs={'conversation_uuid': conv.uuid})
            if conv else None
        )
 
    # ── Statistics (always over the full provider set, ignoring filters) ─
    stats = {
        'total':     base_qs.count(),
        'pending':   base_qs.filter(status='pending').count(),
        'responded': base_qs.filter(status='responded').count(),
        'accepted':  base_qs.filter(status='accepted').count(),
    }
 
    context = {
        'inquiries':       inquiries,
        'stats':           stats,
        'current_status':  current_status,
        'service_filter':  service_filter,
        'query_string':    query_string,
    }
 
    return render(request, 'services/my_inquiries.html', context)
 
@login_required
def inquiry_detail(request, pk):
    """
    Individual inquiry detail page.
 
    Accessible by both the provider (is_provider=True) and the client
    (is_provider=False).  The context always includes:
 
      conversation      — the linked Conversation object or None
      conversation_url  — ready-to-use URL string or None
    """
    inquiry = get_object_or_404(
        ServiceInquiry.objects.select_related('client__user', 'service', 'conversation'),
        pk=pk,
    )
 
    # ── Permission check ──────────────────────────────────────────────────
    is_provider = inquiry.service.provider.user == request.user
    is_client   = inquiry.client.user == request.user
 
    if not (is_provider or is_client):
        messages.error(request, "You don't have permission to view this inquiry.")
        return redirect('services:list')
 
    # ── Resolve linked conversation and build its URL ────────────────────
    conv = getattr(inquiry, 'conversation', None)
 
    # Fallback: look up by content-type if the FK isn't set
    if conv is None:
        from django.contrib.contenttypes.models import ContentType
        from Messages.models import Conversation as MsgConversation
 
        service_ct = ContentType.objects.get_for_model(inquiry.service.__class__)
        conv = MsgConversation.objects.filter(
            content_type=service_ct,
            object_id=str(inquiry.service.id),
            participants=request.user.profile,
        ).first()
 
    conversation_url = (
        reverse('conversation_detail', kwargs={'conversation_uuid': conv.uuid})
        if conv else None
    )
 
    context = {
        'inquiry':          inquiry,
        'is_provider':      is_provider,
        'conversation':     conv,
        'conversation_url': conversation_url,
        'response_form':    InquiryResponseForm(instance=inquiry) if is_provider else None,
    }
 
    return render(request, 'services/inquiry_detail.html', context)

@login_required
@require_POST
def respond_to_inquiry(request, pk):
    """
    Provider responds to an inquiry.
    Saves the structured response AND posts it as a plain message
    into the existing conversation so the client sees it in their inbox.
    """
    try:
        inquiry = get_object_or_404(ServiceInquiry, pk=pk)

        # Only the service provider can respond
        if inquiry.service.provider.user != request.user:
            return JsonResponse({'success': False, 'error': 'Permission denied.'})

        form = InquiryResponseForm(request.POST, instance=inquiry)

        if form.is_valid():
            from django.db import transaction

            with transaction.atomic():
                inquiry = form.save(commit=False)
                inquiry.responded_at = timezone.now()
                inquiry.save()

                # Post the provider's response into the conversation
                if inquiry.conversation and inquiry.provider_response:
                    inquiry.conversation.add_message(
                        sender=request.user.profile,
                        content=inquiry.provider_response,
                        inquiry_type='CUSTOM'
                    )
                    
                conversation_url = (
                    reverse('conversation_detail', kwargs={'conversation_uuid': inquiry.conversation.uuid})
                    if inquiry.conversation
                    else reverse('services:inquiry_detail', kwargs={'pk': inquiry.pk})
                )
                create_notification(
                    user=inquiry.client.user,
                    title=f"Response to Your Inquiry: {inquiry.service.title}",
                    message=(
                        f"{request.user.username} responded to your inquiry. "
                        f"Open your inbox to read it."
                    ),
                    category=NotificationCategory.ALERTS,
                    priority=NotificationPriority.HIGH,
                    content_object=inquiry.service,
                    action_url=conversation_url,
                    action_text='View in Inbox'
                )

            messages.success(request, "Your response has been sent!")

            redirect_url = (
                reverse('conversation_detail', kwargs={'conversation_uuid': inquiry.conversation.uuid})
                if inquiry.conversation
                else reverse('services:inquiry_detail', kwargs={'pk': inquiry.pk})
            )
            return JsonResponse({'success': True, 'redirect': redirect_url})

        else:
            return JsonResponse({'success': False, 'errors': form.errors})

    except Exception as e:
        logger.error(f"Error responding to inquiry: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'An error occurred.'})

def add_messaging_context(context, service, user):
    """
    Helper to add messaging-related context to service detail view.
    KEY FIX: context key is 'conversation' (not 'existing_conversation')
    to match what service_detail.html reads with {{ conversation }}.
    """
    if not user.is_authenticated:
        return context

    from django.contrib.contenttypes.models import ContentType
    service_ct = ContentType.objects.get_for_model(ServiceListing)

    existing_conversation = Conversation.objects.filter(
        content_type=service_ct,
        object_id=str(service.id),
        participants=user.profile
    ).first()

    # Use 'conversation' — this is what service_detail.html reads
    context['conversation'] = existing_conversation
    context['existing_conversation'] = existing_conversation  # keep for any other templates
    context['can_message'] = (user.profile != service.provider)
    context['message_form'] = MessageForm()

    return context

def load_lgas(request):
    """Load LGAs based on state — GET parameter variant (?state=<id>)"""
    state_id = request.GET.get('state')
    lgas = LGA.objects.filter(
        state_id=state_id,
        is_active=True
    ).order_by('name').values('id', 'name')
    return JsonResponse(list(lgas), safe=False)

def load_lgas_by_path(request, state_id):
    """
    Load LGAs based on state — URL path variant (/api/lgas/<state_id>/).
    Called by unified_filter_sidebar.html JS as: GET /api/lgas/{state_id}/

    Register in urls.py as:
        path('api/lgas/<int:state_id>/', views.load_lgas_by_path, name='api_lgas_by_state'),
    """
    try:
        lgas = LGA.objects.filter(
            state_id=int(state_id),
            is_active=True
        ).order_by('name').values('id', 'name')
        return JsonResponse(list(lgas), safe=False)
    except (ValueError, TypeError):
        return JsonResponse([], safe=False)