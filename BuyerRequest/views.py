from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, F, Count, Avg, Exists, OuterRef, Prefetch, Sum
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.template.loader import render_to_string
from datetime import timedelta
from decimal import Decimal
import json
import json as _json
import uuid

from Messages.models import Conversation, Message
from Messages.forms import MessageForm
from Notifications.models import (
    create_notification,
    NotificationCategory,
    NotificationPriority
)

from .models import BuyerRequest, SellerResponse, RequestAccess, BuyerRequestImage
from .forms import BuyerRequestForm, SellerResponseForm, RequestFilterForm
from Home.models import Category, Subcategory, Brand
from User.models import State, LGA, SavedItem, ItemReport
from User.forms import ItemReportForm


import logging
logger = logging.getLogger(__name__)

def format_budget(budget_range, budget_min=None, budget_max=None):
    """Format budget display (following existing price formatting pattern)"""
    if budget_range == 'custom' and budget_min and budget_max:
        if budget_min == budget_max:
            return f"₦{budget_min:,.0f}"
        return f"₦{budget_min:,.0f} - ₦{budget_max:,.0f}"
    
    budget_map = {
        'under_5k': 'Under ₦5,000',
        '5k_25k': '₦5,000 - ₦25,000',
        '25k_100k': '₦25,000 - ₦100,000',
        '100k_500k': '₦100,000 - ₦500,000',
        '500k_1m': '₦500,000 - ₦1,000,000',
        '1m_plus': 'Above ₦1,000,000',
        'negotiable': 'Negotiable'
    }
    return budget_map.get(budget_range, 'Not specified')

class BuyerRequestListView(ListView):
    """List view for buyer requests (following ProductListView pattern)"""
    model = BuyerRequest
    template_name = 'buyer_requests/request_list.html'
    context_object_name = 'requests'
    paginate_by = 12

    def get_queryset(self):
        """Get filtered queryset (following existing pattern)"""
        try:
            # Clean up expired requests
            BuyerRequest.delete_expired_requests()
        except:
            pass
        
        # Base queryset with proper select_related (following existing pattern)
        queryset = BuyerRequest.objects.filter(
            status='active',
            is_suspended=False
        ).exclude(
            expires_at__lte=timezone.now()
        ).select_related(
            'buyer__user',
            'category',
            'subcategory', 
            'brand'
        ).prefetch_related('images')
        
        # Get filter parameters from GET request
        query           = self.request.GET.get('query', '').strip()
        request_type    = self.request.GET.get('request_type', '').strip()
        category_id     = self.request.GET.get('category', '').strip()
        subcategory_id  = self.request.GET.get('subcategory', '').strip()
        brand_id        = self.request.GET.get('brand', '').strip()
        service_category = self.request.GET.get('service_category', '').strip()
        budget_range    = self.request.GET.get('budget_range', '').strip()
        min_price       = self.request.GET.get('min_price', '').strip()
        max_price       = self.request.GET.get('max_price', '').strip()
        urgency         = self.request.GET.get('urgency', '').strip()
        condition       = self.request.GET.get('condition', '').strip()
        status_filter   = self.request.GET.get('status', '').strip()
        state_id        = self.request.GET.get('state', '').strip()
        lga_id          = self.request.GET.get('lga', '').strip()
        verified_only   = self.request.GET.get('verified_only', '').strip()
        sort            = self.request.GET.get('sort', '').strip()

        # Apply filters
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            )

        if request_type:
            queryset = queryset.filter(request_type=request_type)

        if category_id and category_id.isdigit():
            try:
                queryset = queryset.filter(category_id=int(category_id))
            except (ValueError, TypeError):
                pass

        if subcategory_id:
            try:
                queryset = queryset.filter(subcategory_id=int(subcategory_id))
            except (ValueError, TypeError):
                pass

        if brand_id:
            try:
                queryset = queryset.filter(brand_id=int(brand_id))
            except (ValueError, TypeError):
                pass

        if service_category:
            queryset = queryset.filter(service_category=service_category)

        if budget_range:
            queryset = queryset.filter(budget_range=budget_range)
        else:
            if min_price:
                try:
                    queryset = queryset.filter(
                        Q(budget_max__gte=Decimal(min_price)) |
                        Q(budget_max__isnull=True)
                    )
                except Exception:
                    pass
            if max_price:
                try:
                    queryset = queryset.filter(
                        Q(budget_min__lte=Decimal(max_price)) |
                        Q(budget_min__isnull=True)
                    )
                except Exception:
                    pass

        if urgency:
            queryset = queryset.filter(urgency=urgency)

        if condition:
            queryset = queryset.filter(preferred_condition=condition)

        delivery_preference = self.request.GET.get('delivery_preference', '').strip()
        if delivery_preference:
            queryset = queryset.filter(delivery_preference=delivery_preference)

        skill_level = self.request.GET.get('skill_level_required', '').strip()
        if skill_level:
            queryset = queryset.filter(skill_level_required=skill_level)

        if status_filter == 'expired':

            queryset = BuyerRequest.objects.filter(
                status='expired',
                is_suspended=False,
                buyer=queryset.values('buyer')
            )
            # Re-apply simpler queryset for expired — rebuild cleanly
            queryset = BuyerRequest.objects.filter(
                is_suspended=False,
                expires_at__lte=timezone.now()
            ).select_related(
                'buyer__user', 'category', 'subcategory', 'brand'
            ).prefetch_related('images')
            # Re-apply non-status filters on top of expired base
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) | Q(description__icontains=query)
                )
            if request_type:
                queryset = queryset.filter(request_type=request_type)
            if category_id and category_id.isdigit():
                try:
                    queryset = queryset.filter(category_id=int(category_id))
                except (ValueError, TypeError):
                    pass
            if service_category:
                queryset = queryset.filter(service_category=service_category)
        # 'active' status_filter just keeps the original base queryset as-is

        if state_id:
            try:
                queryset = queryset.filter(buyer__location__state_id=int(state_id))
            except (ValueError, TypeError):
                pass

        if lga_id:
            try:
                queryset = queryset.filter(buyer__location__lga_id=int(lga_id))
            except (ValueError, TypeError):
                pass

        if verified_only == 'true':
            queryset = queryset.filter(buyer__business_verification_status='verified')

        # Apply sorting — cover all sort options exposed in the template
        sort_map = {
            '-created_at':      ['-created_at'],
            'created_at':       ['created_at'],
            '-urgency':         ['-urgency', '-created_at'],
            '-response_count':  ['-response_count', '-created_at'],
            '-view_count':      ['-view_count', '-created_at'],
            'title':            ['title'],
            'budget_max':       ['-budget_max', '-created_at'],
        }
        queryset = queryset.order_by(*sort_map.get(sort, ['-is_featured', '-boost_score', '-created_at']))
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get categories with request counts for the category grid (welcome section)
        categories = Category.objects.annotate(
            request_count=Count('buyer_requests', filter=Q(
                buyer_requests__status='active',
                buyer_requests__expires_at__gt=timezone.now(),
                buyer_requests__is_suspended=False
            ))
        ).filter(request_count__gt=0)
        context['categories'] = categories

        # ALL product categories (unfiltered) for the sidebar filter dropdown
        context['product_categories'] = Category.objects.all().order_by('name')

        context['service_categories'] = [
            {'code': code, 'name': label}
            for code, label in BuyerRequest.SERVICE_CATEGORIES
        ]

        context['item_type'] = 'requests'
        context['filter_action_url'] = self.request.path
        context['states'] = State.objects.all().order_by('name')

        category_id = self.request.GET.get('category', '').strip()
        selected_category = None

        is_numeric_category = category_id.isdigit() if category_id else False

        if category_id and is_numeric_category:
            try:
                selected_category = Category.objects.get(id=int(category_id))
                context['selected_category'] = selected_category
                context['subcategories'] = selected_category.subcategories.all().order_by('name')
                context['brands'] = Brand.objects.filter(categories=selected_category).order_by('name')
            except (Category.DoesNotExist, ValueError, TypeError):
                context['subcategories'] = []
                context['brands'] = []
        else:
            context['subcategories'] = []
            context['brands'] = []
        
        # Handle state/LGA context
        state_id = self.request.GET.get('state')
        if state_id:
            try:
                context['lgas'] = LGA.objects.filter(state_id=int(state_id)).order_by('name')
            except (ValueError, TypeError):
                context['lgas'] = []
        else:
            context['lgas'] = []
        
        # Add saved status for authenticated users (following existing pattern)
        if self.request.user.is_authenticated:
            from django.contrib.contenttypes.models import ContentType
            
            # Get the ContentType for BuyerRequest
            request_ct = ContentType.objects.get_for_model(BuyerRequest)
            
            # Query saved requests using content_type and object_id
            saved_requests = SavedItem.objects.filter(
                user=self.request.user,
                content_type=request_ct
            ).values_list('object_id', flat=True)
            
            saved_requests_set = set(str(id) for id in saved_requests)
            
            for request in context['requests']:
                request.is_saved = str(request.id) in saved_requests_set
                request.formatted_budget = format_budget(
                    request.budget_range, request.budget_min, request.budget_max
                )

        else:
            for request in context['requests']:
                request.formatted_budget = format_budget(
                    request.budget_range, request.budget_min, request.budget_max
                )
        
        # Check daily access limit for free users
        if self.request.user.is_authenticated:
            try:
                if self.request.user.account.effective_status.tier_type != 'pro':
                    daily_count = RequestAccess.get_daily_access_count(self.request.user)
                    context['daily_access_count'] = daily_count
                    context['daily_access_limit'] = 5
            except:
                pass
        
        # Pass selected filter values back to template for persistence
        context['selected_request_type']    = self.request.GET.get('request_type', '')
        context['selected_category']        = self.request.GET.get('category', '') if not context.get('selected_category') else context.get('selected_category')
        context['selected_subcategory']     = self.request.GET.get('subcategory', '')
        context['selected_brand']           = self.request.GET.get('brand', '')
        context['selected_condition']       = self.request.GET.get('condition', '')
        context['selected_service_category'] = self.request.GET.get('service_category', '')
        context['selected_urgency']         = self.request.GET.get('urgency', '')
        context['selected_budget_range']    = self.request.GET.get('budget_range', '')
        context['selected_min_price']       = self.request.GET.get('min_price', '')
        context['selected_max_price']       = self.request.GET.get('max_price', '')
        context['selected_status']          = self.request.GET.get('status', '')
        context['selected_state']           = self.request.GET.get('state', '')
        context['selected_lga']             = self.request.GET.get('lga', '')
        context['selected_verified_only']   = self.request.GET.get('verified_only', '')
        context['selected_sort']               = self.request.GET.get('sort', '')
        context['search_query']                = self.request.GET.get('query', '')
        context['selected_delivery_preference']= self.request.GET.get('delivery_preference', '')
        context['selected_skill_level']        = self.request.GET.get('skill_level_required', '')
        
        return context

class BuyerRequestDetailView(DetailView):
    """Detail view for buyer requests (following ProductDetailView pattern)"""
    model = BuyerRequest
    template_name = 'buyer_requests/request_detail.html'
    context_object_name = 'request'

    def get_object(self):
        obj = get_object_or_404(
            BuyerRequest.objects.select_related(
                'buyer__user', 'category', 'subcategory', 'brand'
            ).prefetch_related(
                'responses__seller__user', 'images'
            ),
            pk=self.kwargs['pk']
        )
        
        # Check if user can view this request
        if not obj.can_be_viewed_by(self.request.user):
            raise Http404("Request not found or you don't have permission to view it.")
        
        return obj

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Handle access control for free users
        if request.user.is_authenticated:
            try:
                if request.user.account.effective_status.tier_type != 'pro':
                    can_access, reason = RequestAccess.can_access_request(request.user, self.object)
                    
                    if not can_access and reason == "daily_limit_exceeded":
                        messages.error(
                            request, 
                            "You've reached your daily limit of 5 request views. "
                            "Upgrade to Pro for unlimited access!"
                        )
                        return redirect('buyer_requests:list')
            except:
                # Handle case where user doesn't have account
                can_access, reason = RequestAccess.can_access_request(request.user, self.object)
                
                if not can_access and reason == "daily_limit_exceeded":
                    messages.error(
                        request, 
                        "You've reached your daily limit of 5 request views. "
                        "Create an account or upgrade to Pro for unlimited access!"
                    )
                    return redirect('buyer_requests:list')
        
        # Record access and increment view count
        # Authenticated users: only count once per request (using RequestAccess dedup).
        # Anonymous users: always count (we can't deduplicate without a session/account).
        if request.user.is_authenticated:
            _access, created = RequestAccess.record_access(
                request.user,
                self.object,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            # record_access already increments view_count internally, so only
            # call increase_view_count if this is NOT a repeat visit.
            # (record_access uses get_or_create so created=True means first visit)
            if not created:
                pass  # already counted on their first visit — don't double-count
        else:
            # Anonymous visitor — always bump the count
            self.object.increase_view_count()
        
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add response form for authenticated users
        if self.request.user.is_authenticated:
            context['can_respond'] = self.object.can_be_contacted_by(self.request.user)
            if context['can_respond']:
                context['response_form'] = SellerResponseForm(
                    buyer_request=self.object,
                    user=self.request.user
                )
            
            # ✅ FIXED: Check if user has saved this request
            from django.contrib.contenttypes.models import ContentType
            
            request_ct = ContentType.objects.get_for_model(BuyerRequest)
            context['is_saved'] = SavedItem.objects.filter(
                user=self.request.user,
                content_type=request_ct,
                object_id=str(self.object.id)
            ).exists()
        
        # Add responses (following existing pattern)
        if self.request.user.is_authenticated:
            if self.request.user.profile == self.object.buyer:
                # Buyer can see all responses, ordered by verification status
                context['responses'] = self.object.responses.select_related(
                    'seller__user'
                ).order_by('-is_featured_response', '-is_verified_seller', '-response_score', '-created_at')
            else:
                # Others can only see their own response
                context['responses'] = self.object.responses.filter(
                    seller=self.request.user.profile
                ).select_related('seller__user')
        
        # Add similar requests
        similar_requests = BuyerRequest.objects.filter(
            status='active',
            is_suspended=False
        ).exclude(
            id=self.object.id,
            expires_at__lte=timezone.now()
        )
        
        # Filter by category or service category
        if self.object.category:
            similar_requests = similar_requests.filter(category=self.object.category)
        elif self.object.service_category:
            similar_requests = similar_requests.filter(service_category=self.object.service_category)
        
        similar_requests = similar_requests[:4]
        

        if self.request.user.is_authenticated:
            from django.contrib.contenttypes.models import ContentType
            
            request_ct = ContentType.objects.get_for_model(BuyerRequest)
            saved_requests = SavedItem.objects.filter(
                user=self.request.user,
                content_type=request_ct,
                object_id__in=[str(r.id) for r in similar_requests]
            ).values_list('object_id', flat=True)
            saved_requests_set = set(str(id) for id in saved_requests)
            
            for request in similar_requests:
                request.is_saved = str(request.id) in saved_requests_set
        
        context['similar_requests'] = similar_requests
        
        # Format budget and add other display properties
        context['request'].formatted_budget = format_budget(
            self.object.budget_range, self.object.budget_min, self.object.budget_max
        )
        
        # Add images
        context['images'] = self.object.images.all()
        context['primary_image'] = self.object.primary_image
        
        # Add report form
        context['report_form'] = ItemReportForm()
        
        if self.request.user.is_authenticated:
            add_request_messaging_context(context, self.object, self.request.user)
        
        return context

class BuyerRequestCreateView(LoginRequiredMixin, CreateView):
    """Create view for buyer requests (following ProductCreateView pattern)"""
    model = BuyerRequest
    form_class = BuyerRequestForm
    template_name = 'buyer_requests/request_form.html'
    success_url = reverse_lazy('buyer_requests:my_requests')
    
    def get_form_kwargs(self):
        """Pass the current user to the form"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        try:
            # Set the buyer BEFORE saving
            form.instance.buyer = self.request.user.profile
            
            if not form.instance.expires_at:
                try:
                    # Pro users get 90 days, free users get 45 days
                    if self.request.user.account.effective_status.tier_type == 'pro':
                        days = 90
                        form.instance.is_featured = True
                    else:
                        days = 45
                except:
                    days = 45
                
                form.instance.expires_at = timezone.now() + timedelta(days=days)
            
            # NOW save the form - expires_at is already set
            self.object = form.save()
            
            # Handle images (following existing pattern)
            images = self.request.FILES.getlist('images')
            for i, image in enumerate(images[:5]):
                try:
                    # Check file size
                    if image.size > 5 * 1024 * 1024:
                        messages.warning(
                            self.request, 
                            f'Image "{image.name}" was too large and was skipped. Please upload images under 5MB.'
                        )
                        continue
                    
                    # Create the request image
                    BuyerRequestImage.objects.create(
                        buyer_request=self.object,
                        image=image,
                        is_primary=(i == 0)
                    )
                except Exception as img_error:
                    messages.warning(
                        self.request, 
                        f'Failed to process image "{image.name}": {str(img_error)}'
                    )
            
            messages.success(self.request, 'Your request has been posted successfully! Sellers can now contact you.')
            
            # Check if this is an AJAX request
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Request posted successfully',
                    'redirect_url': str(self.get_success_url())
                })
            
            return redirect(self.get_success_url())
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error creating request: {str(e)}', exc_info=True)
            
            error_message = f'Error creating request: {str(e)}'
            messages.error(self.request, error_message)
            
            # Handle AJAX error response
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_message
                }, status=400)
            
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Handle invalid form submission"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Log form errors for debugging
        logger.error(f"Form validation failed: {form.errors}")
        logger.error(f"Form data: {form.data}")
        
        # Check if this is an AJAX request
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Format errors in a user-friendly way
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
        context['title'] = 'Post New Request'
        context['save_button'] = 'Post Request'
        return context

class BuyerRequestUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update view for buyer requests (following ProductUpdateView pattern)"""
    model = BuyerRequest
    form_class = BuyerRequestForm
    template_name = 'buyer_requests/request_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def test_func(self):
        request = self.get_object()
        return self.request.user == request.buyer.user

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

                        BuyerRequestImage.objects.create(
                            buyer_request=self.object,
                            image=image,
                            is_primary=(i == 0)
                        )
                    except Exception as img_error:
                        messages.warning(
                            self.request,
                            f'Failed to process image "{image.name}": {str(img_error)}'
                        )

            messages.success(self.request, 'Your request has been updated successfully.')
            success_url = reverse('buyer_requests:detail', kwargs={'pk': self.object.pk})

            # Return JSON for AJAX submissions (the form uses fetch())
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Request updated successfully',
                    'redirect_url': success_url,
                })

            return redirect(success_url)

        except Exception as e:
            logger.error(f'Error updating request: {str(e)}', exc_info=True)
            error_message = f'Error updating request: {str(e)}'
            messages.error(self.request, error_message)

            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_message}, status=400)

            return self.form_invalid(form)

    def form_invalid(self, form):
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
                'success': False,
                'error': ' | '.join(error_messages) if error_messages else 'Form validation failed',
                'errors': dict(form.errors),
            }, status=400)

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Request'
        context['save_button'] = 'Update Request'
        return context

class BuyerRequestDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete view for buyer requests (following ProductDeleteView pattern)"""
    model = BuyerRequest
    template_name = 'buyer_requests/request_confirm_delete.html'
    success_url = reverse_lazy('buyer_requests:my_requests')

    def test_func(self):
        request = self.get_object()
        return self.request.user == request.buyer.user

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Request deleted successfully.')
        return super().delete(request, *args, **kwargs)

@login_required
def my_requests(request):
    """View for user's own buyer requests (following my_store pattern)"""
    requests_qs = BuyerRequest.objects.filter(
        buyer=request.user.profile
    ).select_related(
        'category', 'subcategory'
    ).prefetch_related(
        'responses', 'images'
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(requests_qs, 10)
    page = request.GET.get('page')
    
    try:
        requests = paginator.page(page)
    except PageNotAnInteger:
        requests = paginator.page(1)
    except EmptyPage:
        requests = paginator.page(paginator.num_pages)
    
    # Statistics (following existing pattern)
    stats = {
        'total': BuyerRequest.objects.filter(buyer=request.user.profile).count(),
        'active': BuyerRequest.objects.filter(buyer=request.user.profile, status='active').count(),
        'fulfilled': BuyerRequest.objects.filter(buyer=request.user.profile, status='fulfilled').count(),
        'total_responses': SellerResponse.objects.filter(buyer_request__buyer=request.user.profile).count(),
        'total_views': BuyerRequest.objects.filter(buyer=request.user.profile).aggregate(
            total=Sum('view_count')
        )['total'] or 0,
    }
    
    context = {
        'requests': requests,
        'stats': stats,
    }
    
    return render(request, 'buyer_requests/my_requests.html', context)

def build_response_summary(response):
    """
    Serialize SellerResponse structured fields into a JSON string.
    Stored as encrypted message content.
    Template reads inquiry_type == SELLER_RESPONSE_CARD and renders a card.
    """
    return _json.dumps({
        'type':              'SELLER_RESPONSE_CARD',
        'response_id':       str(response.id),
        'response_type':     response.response_type,
        'message':           response.message,
        'offered_price':     str(response.offered_price) if response.offered_price else None,
        'delivery_time':     response.delivery_time      or '',
        'availability':      response.availability       or '',
        'service_includes':  response.service_includes   or '',
        'additional_info':   response.additional_info    or '',
        'contact_phone':     response.contact_phone      or '',
        'contact_email':     response.contact_email      or '',
        'preferred_contact': response.preferred_contact,
        'related_product_id': str(response.related_product.id) if response.related_product else None,
        'related_service_id': str(response.related_service.id) if response.related_service else None,
    })


@login_required
@require_POST
def create_response(request, request_id):
    """
    Create a SellerResponse AND bridge it into the messaging system.
    The response is saved, a conversation is created (or reused),
    and the structured response data is posted as a typed message.
    The seller is redirected to the conversation — not the request detail.
    """
    buyer_request = get_object_or_404(BuyerRequest, id=request_id)

    # Permission check
    if not buyer_request.can_be_contacted_by(request.user):
        return JsonResponse({
            'success': False,
            'error': 'You cannot respond to this request.'
        })

    form = SellerResponseForm(
        request.POST,
        buyer_request=buyer_request,
        user=request.user
    )

    if form.is_valid():
        try:
            from django.db import transaction
            from Messages.models import Conversation

            with transaction.atomic():
                response = form.save(commit=False)
                response.buyer_request = buyer_request
                response.seller        = request.user.profile

                # ── BRIDGE STEP 1: get or create conversation ──────────────
                conversation, _ = Conversation.get_or_create_for_item(
                    item=buyer_request,
                    user_profile=request.user.profile
                )
                response.conversation = conversation
                response.save()

                # ── BRIDGE STEP 2: post structured message into conversation ─
                summary = build_response_summary(response)
                conversation.add_message(
                    sender=request.user.profile,
                    content=summary,
                    inquiry_type='SELLER_RESPONSE_CARD'
                )

                # ── BRIDGE STEP 3: fix contact_count (use F() — no race) ───
                BuyerRequest.objects.filter(id=buyer_request.id).update(
                    contact_count=F('contact_count') + 1
                )

                # ── BRIDGE STEP 4: notify buyer — point to inbox ───────────
                create_notification(
                    user=buyer_request.buyer.user,
                    title=f"New Response: {buyer_request.title}",
                    message=(
                        f"{request.user.username} responded to your request. "
                        f"Open your inbox to review their offer."
                    ),
                    category=NotificationCategory.ALERTS,
                    priority=NotificationPriority.HIGH,
                    content_object=buyer_request,
                    action_url=reverse('conversation_detail', kwargs={'conversation_uuid': conversation.uuid}),
                    action_text='View in Inbox'
                )

            messages.success(request, "Your response has been sent successfully!")

            # ── BRIDGE STEP 5: redirect to conversation ────────────────────
            return JsonResponse({
                'success':  True,
                'redirect': reverse('conversation_detail', kwargs={'conversation_uuid': conversation.uuid})
            })

        except Exception as e:
            logger.error(f"Error creating response: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'An error occurred. Please try again.'
            })

    else:
        return JsonResponse({'success': False, 'errors': form.errors})


@login_required
@require_POST
def update_response_status(request, response_id):
    """
    Buyer accepts or declines a SellerResponse from within the conversation.
    Posts a status-change message to the conversation thread so both
    parties can see the outcome inline.
    """
    from Messages.models import Conversation

    seller_response = get_object_or_404(SellerResponse, id=response_id)

    # Only the buyer of the original request can accept or decline
    if seller_response.buyer_request.buyer != request.user.profile:
        return JsonResponse({'success': False, 'error': 'Permission denied.'})

    # Validate the requested status transition
    new_status = request.POST.get('status', '').strip()
    if new_status not in ('accepted', 'declined'):
        return JsonResponse({'success': False, 'error': 'Invalid status value.'})

    # Prevent acting on a response that is already terminal
    terminal_statuses = ('accepted', 'declined', 'completed')
    if seller_response.status in terminal_statuses:
        return JsonResponse({
            'success': False,
            'error': f'This response is already {seller_response.status}.'
        })

    try:
        from django.db import transaction

        with transaction.atomic():
            seller_response.status = new_status
            seller_response.save(update_fields=['status', 'updated_at'])

            # Post a status-change message to the conversation thread
            if seller_response.conversation:
                action_label = 'accepted' if new_status == 'accepted' else 'declined'
                seller_response.conversation.add_message(
                    sender=request.user.profile,
                    content=f'The buyer {action_label} this response.',
                    inquiry_type='CUSTOM'
                )

            # Notify the seller of the buyer's decision
            create_notification(
                user=seller_response.seller.user,
                title=f"Response {new_status.capitalize()}: {seller_response.buyer_request.title}",
                message=(
                    f"{request.user.username} {action_label} your response. "
                    f"Open your inbox for details."
                ),
                category=NotificationCategory.ALERTS,
                priority=NotificationPriority.HIGH,
                content_object=seller_response.buyer_request,
                action_url=(
                    reverse('conversation_detail', kwargs={'conversation_uuid': seller_response.conversation.uuid})
                    if seller_response.conversation
                    else reverse('buyer_requests:detail', kwargs={'pk': seller_response.buyer_request.id})
                ),
                action_text='View in Inbox'
            )

        return JsonResponse({
            'success': True,
            'status':  new_status,
            'label':   seller_response.get_status_display()
        })

    except Exception as e:
        logger.error(f"Error updating response status: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'An error occurred.'})
    
@login_required
@require_POST
def bump_request(request, request_id):
    """Bump request to top of listings"""
    buyer_request = get_object_or_404(BuyerRequest, id=request_id, buyer=request.user.profile)
    
    if buyer_request.can_be_bumped():
        if buyer_request.bump_request():
            messages.success(request, "Your request has been bumped to the top!")
        else:
            messages.error(request, "Unable to bump request. Please try again.")
    else:
        messages.warning(request, "You can only bump a request once every 24 hours.")
    
    return redirect('buyer_requests:detail', pk=request_id)

@require_POST
def report_request(request, request_id):
    """
    UNIFIED: Report a buyer request using ItemReport
    """
    buyer_request = get_object_or_404(BuyerRequest, id=request_id)
    
    form = ItemReportForm(request.POST)  # ✅ Use unified form
    if form.is_valid():
        # ✅ Create report using unified ItemReport
        from django.contrib.contenttypes.models import ContentType
        request_ct = ContentType.objects.get_for_model(BuyerRequest)
        
        report = ItemReport(
            content_type=request_ct,  # ✅ Use GenericForeignKey
            object_id=str(buyer_request.id),
            reason=form.cleaned_data['reason'],
            details=form.cleaned_data['details'],
            reporter_email=form.cleaned_data['reporter_email'] or None,
        )
        report.save()
        
        # Get report count
        report_count = ItemReport.get_reports_for_item(buyer_request).count()
        
        # Send email notification
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            context = {
                'request': buyer_request,
                'report': report,
                'report_count': report_count,
                'reporter_email': form.cleaned_data['reporter_email'] or 'Anonymous'
            }
            
            email_body = render_to_string('emails/request_report_email.html', context)
            
            send_mail(
                subject=f'Buyer Request Report: {buyer_request.title} (#{report_count})',
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['support@opensell.ng'],
                html_message=email_body,
                fail_silently=True,
            )
            
            # Check auto-suspension
            should_suspend, count = ItemReport.check_auto_suspension_threshold(buyer_request)
            
            if should_suspend and not buyer_request.is_suspended:
                from django.contrib.auth.models import User
                superuser = User.objects.filter(is_superuser=True).first()
                
                if superuser:
                    buyer_request.suspend(
                        superuser,
                        f"Auto-suspended after {count} reports. Last: {report.get_reason_display()}"
                    )
                    
                    # Mark reports as resolved
                    ItemReport.get_reports_for_item(buyer_request).filter(
                        status='pending'
                    ).update(
                        status='resolved',
                        reviewed_by=superuser,
                        reviewed_at=timezone.now()
                    )
        
        except Exception as e:
            logger.error(f"Error processing request report: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Report submitted successfully. We will review it shortly.'
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)

# AJAX endpoints for dynamic loading
def load_subcategories(request):
    """Load subcategories for a given category (AJAX)"""
    category_id = request.GET.get('category')
    
    if not category_id:
        return JsonResponse([], safe=False)
    
    try:
        subcategories = Subcategory.objects.filter(
            category_id=int(category_id)
        ).order_by('name').values('id', 'name')
        return JsonResponse(list(subcategories), safe=False)
    except (ValueError, TypeError):
        return JsonResponse([], safe=False)


def load_brands(request):
    """Load brands for a given subcategory (AJAX)"""
    subcategory_id = request.GET.get('subcategory')

    if not subcategory_id:
        return JsonResponse([], safe=False)

    try:
        brands = Brand.objects.filter(
            subcategories__id=int(subcategory_id)
        ).distinct().order_by('name').values('id', 'name')
        return JsonResponse(list(brands), safe=False)
    except (ValueError, TypeError):
        return JsonResponse([], safe=False)


def load_lgas(request):
    """Load LGAs for a given state (AJAX)"""
    state_id = request.GET.get('state')
    
    if not state_id:
        return JsonResponse([], safe=False)
    
    try:
        lgas = LGA.objects.filter(
            state_id=int(state_id)
        ).order_by('name').values('id', 'name')
        return JsonResponse(list(lgas), safe=False)
    except (ValueError, TypeError):
        return JsonResponse([], safe=False)


def request_categories(request):
    """Return categories as JSON for API access"""
    categories = Category.objects.annotate(
        request_count=Count('buyer_requests', filter=Q(
            buyer_requests__status='active',
            buyer_requests__expires_at__gt=timezone.now(),
            buyer_requests__is_suspended=False
        ))
    ).filter(request_count__gt=0).values('id', 'name', 'slug', 'request_count')
    
    return JsonResponse(list(categories), safe=False)


def add_request_messaging_context(context, buyer_request, user):
    """
    Helper to add messaging context to buyer request detail
    
    Similar to services, but for buyer requests
    """
    if not user.is_authenticated:
        return context
    
    from django.contrib.contenttypes.models import ContentType
    request_ct = ContentType.objects.get_for_model(BuyerRequest)
    
    # Check if conversation exists between user and request owner
    existing_conversation = Conversation.objects.filter(
        content_type=request_ct,
        object_id=str(buyer_request.id),
        participants=user.profile
    ).first()
    
    context['existing_conversation'] = existing_conversation
    context['can_message'] = (user.profile != buyer_request.buyer)
    context['message_form'] = MessageForm()
    
    return context