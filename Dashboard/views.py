from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Sum, Count, Q, Avg, F
from decimal import Decimal, InvalidOperation
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import UserAccount, Transaction, ProductBoost, AccountStatus
from Home.models import Product_Listing
from Dashboard.models import AffiliateProfile, AffiliateCommission, Referral
from .models import VirtualAccount, MonnifyTransaction
from .monnify_service import monnify_service
from .forms import DepositForm, BoostProductForm
from django.contrib.admin.views.decorators import staff_member_required
from django_q.models import Task, Schedule
from django_q.tasks import async_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import csv
import logging
import json

logger = logging.getLogger(__name__)

def format_price(price):
    """Format price with proper currency formatting"""
    return '₦ {:,.0f}'.format(Decimal(price))

def send_subscription_confirmation_email(user, subscription_info):
    """Send subscription confirmation email using template"""
    try:
        subject = f"Welcome to {subscription_info['type'].title()} Subscription!"
        
        email_context = {
            'user': user,
            'subscription_info': subscription_info,
            'site_name': 'OpenSell',
        }
        
        html_message = render_to_string('emails/subscription_confirmation.html', email_context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Subscription confirmation email sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send subscription confirmation email to {user.email}: {str(e)}")

def send_subscription_expiring_email(user, days_until_expiry):
    """Send subscription expiring warning email"""
    try:
        subject = f"Your OpenSell Pro subscription expires in {days_until_expiry} days"
        
        email_context = {
            'user': user,
            'days_until_expiry': days_until_expiry,
            'renewal_url': settings.SITE_URL + reverse('subscription_management'),
            'site_name': 'OpenSell',
        }
        
        html_message = render_to_string('emails/subscription_expiring.html', email_context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Subscription expiring email sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send subscription expiring email to {user.email}: {str(e)}")

@login_required
def dashboard_home(request):
    """Enhanced main dashboard view showing account summary"""
    try:
        account = request.user.account
    except UserAccount.DoesNotExist:
        # Create account with default free status
        free_status = AccountStatus.objects.filter(tier_type='free').first()
        if not free_status:
            # Create default free status if it doesn't exist
            free_status = AccountStatus.objects.create(
                name='Free User',
                tier_type='free',
                description='Basic free account',
                max_listings=5,
                monthly_price=0,
                yearly_price=0
            )
        account = UserAccount.objects.create(user=request.user, status=free_status)
    
    # Ensure account has a status - fix for None status
    if not account.status:
        free_status = AccountStatus.objects.filter(tier_type='free').first()
        if not free_status:
            # Create default free status if it doesn't exist
            free_status = AccountStatus.objects.create(
                name='Free User',
                tier_type='free',
                description='Basic free account',
                max_listings=5,
                monthly_price=0,
                yearly_price=0
            )
        account.status = free_status
        account.save()
    
    # Check subscription status
    account.check_and_update_status()
    
    # Get effective status with safety check
    effective_status = account.effective_status
    if not effective_status:
        # Fallback to free status
        effective_status = AccountStatus.objects.filter(tier_type='free').first()
        account.status = effective_status
        account.save()
    
    # Get subscription info
    subscription_info = account.subscription_info
    
    # Get recent transactions
    recent_transactions = Transaction.objects.filter(account=account).order_by('-created_at')[:5]
    
    # Get user's listings with boost info
    user_listings = Product_Listing.objects.filter(
        seller=request.user.profile
    ).select_related('category', 'subcategory').prefetch_related('boosts').order_by('-created_at')
    
    # Add boost info to listings - FIXED: Use different attribute names and add safety checks
    for listing in user_listings[:5]:
        try:
            listing.current_boost = listing.get_boost_status()
        except Exception:
            listing.current_boost = None
        listing.formatted_price = format_price(listing.price)
    
    # Calculate account stats
    total_spent = Transaction.objects.filter(
        account=account, 
        amount__lt=0
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Get active boosts with details
    active_boosts = ProductBoost.objects.filter(
        product__seller=request.user.profile,
        is_active=True,
        end_date__gt=timezone.now()
    ).select_related('product')
    
    # Calculate boost metrics (don't assign to properties)
    boost_metrics = {}
    for boost in active_boosts:
        boost_metrics[boost.id] = {
            'days_remaining': (boost.end_date - timezone.now()).days,
            'progress_percentage': min(100, max(0, 
                ((timezone.now() - boost.start_date).total_seconds() / 
                 (boost.end_date - boost.start_date).total_seconds()) * 100
            ))
        }
    
    # Calculate boost revenue
    boost_revenue = Transaction.objects.filter(
        account=account,
        transaction_type='boost_fee'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Get boost statistics
    boost_stats = {
        'total_boosts': ProductBoost.objects.filter(
            product__seller=request.user.profile
        ).count(),
        'active_boosts': active_boosts.count(),
        'total_boost_spent': abs(boost_revenue),
        'average_boost_cost': abs(boost_revenue) / max(1, ProductBoost.objects.filter(
            product__seller=request.user.profile
        ).count())
    }
    
    # Get next tier for upgrade prompt - with safety check
    next_tier = None
    if effective_status and effective_status.tier_type == 'free':
        next_tier = AccountStatus.objects.filter(tier_type='pro').first()
    
    # Calculate potential savings if not Pro
    potential_savings = 0
    if not account.is_subscription_active and boost_stats['total_boosts'] > 0:
        # FIXED: Convert to Decimal for calculation
        potential_savings = boost_stats['total_boost_spent'] * Decimal('0.3')  # 30% discount
    
    context = {
        'account': account,
        'effective_status': effective_status,
        'subscription_info': subscription_info,
        'recent_transactions': recent_transactions,
        'user_listings': user_listings[:5],
        'listings_count': user_listings.count(),
        'total_spent': abs(total_spent),
        'active_boosts': active_boosts,
        'active_boosts_count': active_boosts.count(),
        'boost_metrics': boost_metrics,  # Add boost metrics
        'next_tier': next_tier,
        'boost_stats': boost_stats,
        'potential_savings': potential_savings,
    }
    
    return render(request, 'dashboard/dashboard_home.html', context)

@login_required
def account_status(request):
    """Account status view with timeline - FIXED VERSION"""
    account = request.user.account
    account.check_and_update_status()
    
    # Get account statistics
    total_listings = Product_Listing.objects.filter(seller=request.user.profile).count()
    total_boosts = ProductBoost.objects.filter(product__seller=request.user.profile).count()
    active_boosts = ProductBoost.objects.filter(
        product__seller=request.user.profile,
        is_active=True,
        end_date__gt=timezone.now()
    ).count()
    
    total_transactions = Transaction.objects.filter(account=account).count()
    total_spent = abs(Transaction.objects.filter(
        account=account, 
        amount__lt=0
    ).aggregate(total=Sum('amount'))['total'] or 0)
    
    # Calculate total savings from Pro discounts - FIXED: Handle Decimal/float issue
    total_savings = Decimal('0')  # Initialize as Decimal
    if account.is_subscription_active:
        boost_transactions = Transaction.objects.filter(
            account=account,
            transaction_type='boost_fee'
        )
        for transaction in boost_transactions:
            # Estimate savings (assuming 30% discount)
            # Use Decimal for all calculations to avoid type errors
            original_cost = abs(transaction.amount) / Decimal('0.7')
            total_savings += original_cost - abs(transaction.amount)
    
    # Get timeline dates - FIXED: Use correct field names
    first_listing_date = Product_Listing.objects.filter(
        seller=request.user.profile
    ).order_by('created_at').first()  # Product_Listing has created_at
    
    first_boost_date = ProductBoost.objects.filter(
        product__seller=request.user.profile
    ).order_by('start_date').first()  # ProductBoost uses start_date, not created_at
    
    # Check subscription expiry
    days_until_expiry = None
    if account.subscription_info and account.subscription_info['active']:
        days_until_expiry = (account.subscription_info['end_date'] - timezone.now()).days
    
    context = {
        'account': account,
        'effective_status': account.effective_status,
        'subscription_info': account.subscription_info,
        'total_listings': total_listings,
        'total_boosts': total_boosts,
        'active_boosts': active_boosts,
        'total_transactions': total_transactions,
        'total_spent': total_spent,
        'total_savings': total_savings,
        'first_listing_date': first_listing_date.created_at if first_listing_date else None,
        'first_boost_date': first_boost_date.start_date if first_boost_date else None,  # Use start_date
        'days_until_expiry': days_until_expiry,
    }
    
    return render(request, 'dashboard/account_status.html', context)

@login_required
def transaction_history(request):
    """Enhanced transaction history view with filtering and export"""
    account = request.user.account
    transactions = Transaction.objects.filter(account=account).order_by('-created_at')
    
    # Filtering
    search_query = request.GET.get('search', '')
    transaction_type = request.GET.get('type', '')
    date_range = request.GET.get('date_range', '')
    amount_range = request.GET.get('amount_range', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Apply filters
    if search_query:
        transactions = transactions.filter(
            Q(transaction_type__icontains=search_query) |
            Q(reference__icontains=search_query)
        )
    
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    # Date range filtering
    if date_range:
        now = timezone.now()
        if date_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            transactions = transactions.filter(created_at__gte=start_date)
        elif date_range == 'week':
            start_date = now - timedelta(days=7)
            transactions = transactions.filter(created_at__gte=start_date)
        elif date_range == 'month':
            start_date = now - timedelta(days=30)
            transactions = transactions.filter(created_at__gte=start_date)
        elif date_range == 'quarter':
            start_date = now - timedelta(days=90)
            transactions = transactions.filter(created_at__gte=start_date)
        elif date_range == 'year':
            start_date = now - timedelta(days=365)
            transactions = transactions.filter(created_at__gte=start_date)
        elif date_range == 'custom':
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            if date_from:
                transactions = transactions.filter(created_at__gte=date_from)
            if date_to:
                transactions = transactions.filter(created_at__lte=date_to)
    
    # Amount range filtering
    if amount_range:
        if amount_range == '0-1000':
            transactions = transactions.filter(amount__gte=0, amount__lte=1000)
        elif amount_range == '1000-5000':
            transactions = transactions.filter(amount__gte=1000, amount__lte=5000)
        elif amount_range == '5000-10000':
            transactions = transactions.filter(amount__gte=5000, amount__lte=10000)
        elif amount_range == '10000-50000':
            transactions = transactions.filter(amount__gte=10000, amount__lte=50000)
        elif amount_range == '50000+':
            transactions = transactions.filter(amount__gte=50000)
    
    # Sorting
    if sort_by in ['date', '-date']:
        transactions = transactions.order_by('-created_at' if sort_by == '-date' else 'created_at')
    elif sort_by in ['amount', '-amount']:
        transactions = transactions.order_by('-amount' if sort_by == '-amount' else 'amount')
    
    # Export functionality
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'Type', 'Description', 'Amount', 'Balance After', 'Reference'])
        
        for transaction in transactions:
            writer.writerow([
                transaction.created_at.strftime('%Y-%m-%d %H:%M'),
                transaction.get_transaction_type_display(),
                transaction.get_transaction_type_display(),
                transaction.amount,
                transaction.balance_after or 0,
                transaction.reference or ''
            ])
        
        return response
    
    # Calculate stats for header
    total_deposits = transactions.filter(amount__gt=0).aggregate(
        total=Sum('amount'))['total'] or 0
    total_spent = abs(transactions.filter(amount__lt=0).aggregate(
        total=Sum('amount'))['total'] or 0)
    total_transactions = transactions.count()
    
    # Pagination
    paginator = Paginator(transactions, 20)  # 20 transactions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Recent deposits for sidebar
    recent_deposits = Transaction.objects.filter(
        account=account,
        transaction_type='deposit'
    ).order_by('-created_at')[:5]
    
    context = {
        'transactions': page_obj,
        'total_deposits': total_deposits,
        'total_spent': total_spent,
        'total_transactions': total_transactions,
        'recent_deposits': recent_deposits,
    }
    
    return render(request, 'dashboard/transaction_history.html', context)

@login_required
def subscription_management(request):
    """Enhanced subscription management view with two-month plan"""
    account = request.user.account
    account.check_and_update_status()
    
    # Get available subscription tiers
    try:
        pro_tier = AccountStatus.objects.get(tier_type='pro')
    except AccountStatus.DoesNotExist:
        messages.error(request, 'Pro tier not found. Please contact support.')
        return redirect('dashboard_home')
    
    try:
        free_tier = AccountStatus.objects.get(tier_type='free')
    except AccountStatus.DoesNotExist:
        # Create free tier if it doesn't exist
        free_tier = AccountStatus.objects.create(
            name='Free User',
            tier_type='free',
            description='Basic free account',
            max_listings=5,
            monthly_price=0,
            two_month_price=0
        )
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'subscribe':
            tier_type = request.POST.get('tier_type', 'pro')
            subscription_type = request.POST.get('subscription_type', 'monthly')
            
            # Validate tier_type
            if tier_type not in ['pro']:
                messages.error(request, 'Invalid subscription tier selected.')
                return redirect('subscription_management')
            
            # Validate subscription_type - UPDATED: Accept two_month instead of yearly
            if subscription_type not in ['monthly', 'two_month']:
                messages.error(request, 'Invalid subscription type selected.')
                return redirect('subscription_management')
            
            try:
                subscription_info = account.subscribe_to_tier(tier_type, subscription_type)
                
                # Enhanced subscription info for email
                subscription_info['tier_name'] = pro_tier.name
                
                # Better success message based on subscription type
                plan_name = "Two Month" if subscription_type == 'two_month' else "Monthly"
                messages.success(
                    request, 
                    f"Successfully subscribed to {plan_name} Pro plan! "
                    f"Your subscription is active until {subscription_info['end_date'].strftime('%B %d, %Y')}."
                )
                
                # Send confirmation email asynchronously
                async_task(send_subscription_confirmation_email, request.user, subscription_info)
                
                return redirect('subscription_management')
                
            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Subscription error for user {request.user.id}: {str(e)}")
                messages.error(request, "An error occurred while processing your subscription.")
        
        elif action == 'cancel_auto_renew':
            # Handle auto-renewal cancellation (if implemented)
            messages.info(request, "Auto-renewal has been cancelled. Your subscription will expire on schedule.")
            return redirect('subscription_management')
        
        elif action == 'enable_auto_renew':
            # Handle auto-renewal activation (if implemented)
            messages.success(request, "Auto-renewal has been enabled.")
            return redirect('subscription_management')
    
    # Calculate savings for two-month plan
    two_month_savings = 0
    if pro_tier:
        # Calculate savings: (Monthly * 2) - Two Month Price
        monthly_cost_for_two_months = pro_tier.monthly_price * 2
        two_month_savings = monthly_cost_for_two_months - pro_tier.two_month_price
    
    # Calculate potential boost savings
    monthly_boost_savings = 0
    yearly_boost_savings = 0
    
    if pro_tier:
        avg_boosts_per_month = 10  # Estimate - could be dynamic based on user history
        avg_boost_cost = Decimal('500.00')  # Average boost cost
        monthly_boost_savings = (avg_boost_cost * avg_boosts_per_month * pro_tier.boost_discount / 100)
        yearly_boost_savings = monthly_boost_savings * 12
    
    # Check if subscription is expiring soon (within 7 days)
    subscription_expiring_soon = False
    days_until_expiry = None
    days_remaining = None
    
    if account.subscription_info and account.subscription_info['active']:
        days_until_expiry = (account.subscription_info['end_date'] - timezone.now()).days
        days_remaining = days_until_expiry  # For template
        subscription_expiring_soon = days_until_expiry <= 7
    
    # Get subscription history for display
    subscription_history = account.transactions.filter(
        transaction_type='subscription'
    ).order_by('-created_at')[:5]
    
    # Check if user is currently Pro
    is_pro = account.is_subscription_active
    
    context = {
        'account': account,
        'effective_status': account.effective_status,
        'subscription_info': account.subscription_info,
        'pro_tier': pro_tier,
        'two_month_savings': two_month_savings,  # Savings for choosing two-month plan
        'monthly_boost_savings': monthly_boost_savings,
        'yearly_boost_savings': yearly_boost_savings,
        'current_tier': account.effective_status.tier_type if account.effective_status else 'free',
        'subscription_expiring_soon': subscription_expiring_soon,
        'days_until_expiry': days_until_expiry,
        'days_remaining': days_remaining,  # For template display
        'subscription_history': subscription_history,
        'can_subscribe': account.balance >= (pro_tier.monthly_price if pro_tier else 0),
        'is_pro': is_pro,
    }
    
    return render(request, 'dashboard/subscription_management.html', context)

@login_required
def boost_product(request, product_id):
    """Enhanced boost product view with better pricing display"""
    product = get_object_or_404(Product_Listing, id=product_id, seller=request.user.profile)
    
    # Check if product already has active boost
    try:
        active_boost = product.get_boost_status()
    except:
        active_boost = None
        
    if active_boost:
        messages.warning(
            request, 
            f"This product already has an active {active_boost.get_boost_type_display()} boost "
            f"until {active_boost.end_date.strftime('%B %d, %Y')}."
        )
        return redirect('product_detail', pk=product_id)
    
    if request.method == 'POST':
        form = BoostProductForm(request.POST)
        if form.is_valid():
            boost_type = form.cleaned_data['boost_type']
            duration_days = form.cleaned_data['duration']
            
            try:
                # Create boost using the model method
                boost = ProductBoost.create_boost(
                    product=product,
                    boost_type=boost_type,
                    duration_days=duration_days,
                    user_account=request.user.account
                )
                
                # Update product boost score after creating boost
                product.boost_score = product.calculate_boost_score()
                product.save(update_fields=['boost_score'])
                
                messages.success(
                    request, 
                    f"Product boosted successfully! Your {boost_type} boost is active until "
                    f"{boost.end_date.strftime('%B %d, %Y')}."
                )
                
                if boost.discount_applied > 0:
                    messages.info(
                        request,
                        f"You saved ₦{boost.original_cost - boost.final_cost:.2f} "
                        f"({boost.discount_applied}% Pro discount)!"
                    )
                
                return redirect('dashboard_home')
                
            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Boost creation error: {str(e)}")
                messages.error(request, f"Error: {str(e)}")
    else:
        form = BoostProductForm()
    
    # Get account and check status
    account = request.user.account
    effective_status = account.effective_status
    is_pro = account.is_subscription_active
    
    # Calculate prices for all boost types - Format for template use
    boost_prices = {}
    for boost_type, _ in ProductBoost.BOOST_TYPES:
        cost_info = ProductBoost.calculate_boost_cost(boost_type, 1, account)  # 1 day base
        boost_prices[boost_type] = {
            'original': float(cost_info['original_cost']),
            'discounted': float(cost_info['final_cost']),
            'discount_percent': float(cost_info['discount_percent']),
            'savings': float(cost_info['savings'])
        }
    
    # Create easy-to-use template data
    template_boost_data = []
    for boost_type, display_name in ProductBoost.BOOST_TYPES:
        pricing = boost_prices[boost_type]
        template_boost_data.append({
            'type': boost_type,
            'display_name': display_name,
            'icon': {
                'featured': 'bi-star-fill',
                'urgent': 'bi-clock-fill', 
                'spotlight': 'bi-lightning-fill',
                'premium': 'bi-gem'
            }.get(boost_type, 'bi-rocket'),
            'color': {
                'featured': 'text-warning',
                'urgent': 'text-danger',
                'spotlight': 'text-primary', 
                'premium': 'text-purple'
            }.get(boost_type, 'text-primary'),
            'description': {
                'featured': 'Place your product in the featured section on homepage',
                'urgent': 'Add an "Urgent" badge to make your listing stand out',
                'spotlight': 'Premium placement at the top of search results',
                'premium': 'Ultimate visibility with premium placement everywhere'
            }.get(boost_type, 'Boost your product visibility'),
            'original_price': pricing['original'],
            'discounted_price': pricing['discounted'],
            'discount_percent': pricing['discount_percent'],
            'has_discount': pricing['discount_percent'] > 0
        })
    
    context = {
        'form': form,
        'product': product,
        'boost_prices': boost_prices,  # For JavaScript
        'template_boost_data': template_boost_data,  # For template iteration
        'effective_status': effective_status,
        'is_pro': is_pro,
        'has_discount': effective_status and effective_status.boost_discount > 0,
        'account_balance': float(account.balance),
        'active_boost': active_boost,
    }
    
    return render(request, 'dashboard/boost_product.html', context)

@login_required
def product_boost_status(request):
    """Enhanced product boost status view with analytics"""
    account = request.user.account
    
    # Get active boosts
    active_boosts = ProductBoost.objects.filter(
        product__seller=request.user.profile,
        is_active=True,
        end_date__gt=timezone.now()
    ).select_related('product').order_by('end_date')
    
    # Calculate metrics for active boosts (don't assign to properties)
    active_boost_metrics = {}
    for boost in active_boosts:
        active_boost_metrics[boost.id] = {
            'days_remaining': (boost.end_date - timezone.now()).days,
            'progress_percentage': min(100, max(0, 
                ((timezone.now() - boost.start_date).total_seconds() / 
                 (boost.end_date - boost.start_date).total_seconds()) * 100
            )),
            'views_gained': getattr(boost, 'views_gained', 0)
        }
    
    # Get boost history
    boost_history = ProductBoost.objects.filter(
        product__seller=request.user.profile
    ).select_related('product').order_by('-created_at')[:20]
    
    # Calculate metrics for boost history (don't assign to properties)
    history_boost_metrics = {}
    for boost in boost_history:
        is_currently_active = boost.is_active and boost.end_date > timezone.now()
        metrics = {
            'is_currently_active': is_currently_active,
        }
        
        if is_currently_active:
            metrics.update({
                'days_remaining': (boost.end_date - timezone.now()).days,
                'progress_percentage': min(100, max(0, 
                    ((timezone.now() - boost.start_date).total_seconds() / 
                     (boost.end_date - boost.start_date).total_seconds()) * 100
                ))
            })
        
        history_boost_metrics[boost.id] = metrics
    
    # Calculate overview stats
    total_boosts = ProductBoost.objects.filter(
        product__seller=request.user.profile
    ).count()
    
    active_boosts_count = active_boosts.count()
    
    total_spent = abs(Transaction.objects.filter(
        account=account,
        transaction_type='boost_fee'
    ).aggregate(total=Sum('amount'))['total'] or 0)
    
    # Calculate total savings from Pro discounts
    total_savings = 0
    if account.is_subscription_active:
        boost_transactions = Transaction.objects.filter(
            account=account,
            transaction_type='boost_fee'
        )
        for transaction in boost_transactions:
            # Estimate savings (assuming 30% discount)
            original_cost = abs(transaction.amount) / 0.7  # Reverse calculate original
            total_savings += original_cost - abs(transaction.amount)
    
    # Mock analytics data (you can implement real analytics later)
    boost_analytics = None
    if total_boosts > 0:
        boost_analytics = {
            'total_views': 1250,  # Mock data
            'views_growth': 15,
            'conversion_rate': 3.2,
            'conversion_growth': 8,
            'avg_roi': 2.4,
            'roi_growth': 12,
            'engagement_rate': 7.8,
            'engagement_growth': 5,
        }
    
    context = {
        'active_boosts': active_boosts,
        'active_boosts_count': active_boosts_count,
        'active_boost_metrics': active_boost_metrics,  # Add metrics
        'boost_history': boost_history,
        'history_boost_metrics': history_boost_metrics,  # Add metrics
        'total_boosts': total_boosts,
        'total_spent': total_spent,
        'total_savings': total_savings,
        'boost_analytics': boost_analytics,
    }
    
    return render(request, 'dashboard/product_boost_status.html', context)

@staff_member_required
def task_monitor(request):
    """Simple task monitoring view for staff"""
    recent_tasks = Task.objects.all()[:20]
    schedules = Schedule.objects.all()
    
    # Get task statistics
    total_tasks = Task.objects.count()
    successful_tasks = Task.objects.filter(success=True).count()
    failed_tasks = Task.objects.filter(success=False).count()
    
    context = {
        'recent_tasks': recent_tasks,
        'schedules': schedules,
        'total_tasks': total_tasks,
        'successful_tasks': successful_tasks,
        'failed_tasks': failed_tasks,
    }
    
    return render(request, 'dashboard/task_monitor.html', context)

# AJAX views for dynamic content
@login_required
def get_transaction_details(request, transaction_id):
    """AJAX endpoint to get transaction details for modal"""
    try:
        transaction = Transaction.objects.get(id=transaction_id, account=request.user.account)
        
        data = {
            'id': transaction.id,
            'type': transaction.get_transaction_type_display(),
            'amount': float(transaction.amount),
            'date': transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'reference': transaction.reference or '',
            'balance_after': float(transaction.balance_after or 0),
            'status': getattr(transaction, 'status', 'completed'),
        }
        
        return JsonResponse(data)
    except Transaction.DoesNotExist:
        return JsonResponse({'error': 'Transaction not found'}, status=404)

@login_required
def dashboard_stats_api(request):
    """API endpoint for dashboard statistics"""
    account = request.user.account
    
    # Calculate various stats
    stats = {
        'balance': float(account.balance),
        'total_listings': Product_Listing.objects.filter(seller=request.user.profile).count(),
        'active_boosts': ProductBoost.objects.filter(
            product__seller=request.user.profile,
            is_active=True,
            end_date__gt=timezone.now()
        ).count(),
        'total_spent': abs(Transaction.objects.filter(
            account=account, 
            amount__lt=0
        ).aggregate(total=Sum('amount'))['total'] or 0),
    }
    
    return JsonResponse(stats)

# Task functions for background processing
def check_expiring_subscriptions():
    """Background task to check for expiring subscriptions"""
    try:
        # Find subscriptions expiring in 3 days
        three_days_from_now = timezone.now() + timedelta(days=3)
        
        accounts_with_expiring_subs = UserAccount.objects.filter(
            subscription_end_date__lte=three_days_from_now,
            subscription_end_date__gt=timezone.now(),
            subscription_active=True
        )
        
        for account in accounts_with_expiring_subs:
            days_until_expiry = (account.subscription_end_date - timezone.now()).days
            
            # Send warning email
            async_task(send_subscription_expiring_email, account.user, days_until_expiry)
            
        logger.info(f"Checked {accounts_with_expiring_subs.count()} expiring subscriptions")
        
    except Exception as e:
        logger.error(f"Error checking expiring subscriptions: {str(e)}")

def deactivate_expired_boosts():
    """Background task to deactivate expired boosts"""
    try:
        expired_boosts = ProductBoost.objects.filter(
            end_date__lte=timezone.now(),
            is_active=True
        )
        
        for boost in expired_boosts:
            boost.is_active = False
            boost.save()
            
            # Update product boost score
            boost.product.boost_score = boost.product.calculate_boost_score()
            boost.product.save(update_fields=['boost_score'])
        
        logger.info(f"Deactivated {expired_boosts.count()} expired boosts")
        
    except Exception as e:
        logger.error(f"Error deactivating expired boosts: {str(e)}")

#Monnify Setup
@login_required
def deposit_funds_monnify(request):
    """
    FIXED: Deposit view with correct Monnify implementation
    - Reserved accounts are PERMANENT (not temporary)
    - One-time payments use init-payment API (different from reserved accounts)
    """
    account = request.user.account
    
    # Get user's permanent virtual accounts (can be multiple banks)
    # FIXED: Removed the incorrect prefetch_related('accounts')
    virtual_accounts = VirtualAccount.objects.filter(
        user_account=account,
        status='active'
    ).order_by('bank_name')  # Order by bank name for consistency
    
    # Get recent Monnify transactions
    recent_monnify_transactions = MonnifyTransaction.objects.filter(
        user_account=account,
        payment_status='PAID'
    ).select_related('virtual_account').order_by('-paid_on')[:5]
    
    context = {
        'account': account,
        'virtual_accounts': virtual_accounts,  # Changed from singular to plural
        'has_virtual_account': virtual_accounts.exists(),  # Helper boolean
        'recent_transactions': recent_monnify_transactions,
        'monnify_enabled': True,
    }
    
    return render(request, 'dashboard/deposit_monnify.html', context)

@login_required
@require_http_methods(["POST"])
def create_permanent_virtual_account(request):
    """Create permanent reserved account - KYC REQUIRED by CBN"""
    try:
        logger.info("=== CREATE PERMANENT ACCOUNT REQUEST ===")
        
        account = request.user.account
        
        # Check for existing account
        existing_va = VirtualAccount.objects.filter(
            user_account=account,
            status='active'
        ).first()
        
        if existing_va:
            return JsonResponse({
                'success': False,
                'message': 'You already have an active virtual account'
            }, status=400)
        
        # Parse request data
        try:
            if request.content_type and 'application/json' in request.content_type:
                data = json.loads(request.body)
                bvn = data.get('bvn') or None
                nin = data.get('nin') or None
            else:
                bvn = request.POST.get('bvn') or None
                nin = request.POST.get('nin') or None
            
            # Clean data
            if bvn:
                bvn = bvn.strip()
            if nin:
                nin = nin.strip()
            
            # CRITICAL: BVN or NIN is now REQUIRED by CBN regulation
            if not bvn and not nin:
                logger.warning("Account creation attempted without KYC")
                return JsonResponse({
                    'success': False,
                    'message': 'BVN or NIN is required for account creation (CBN regulation). Please provide at least one.',
                    'error_type': 'kyc_required'
                }, status=400)
            
            # Validate format
            if bvn and (not bvn.isdigit() or len(bvn) != 11):
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid BVN format. Must be 11 digits'
                }, status=400)
            
            if nin and (not nin.isdigit() or len(nin) != 11):
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid NIN format. Must be 11 digits'
                }, status=400)
            
            logger.info(f"KYC provided: BVN={bool(bvn)}, NIN={bool(nin)}")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Invalid request data format'
            }, status=400)
        
        # Call Monnify service with KYC
        logger.info("Calling Monnify service with KYC data...")
        result = monnify_service.create_reserved_account(account, bvn=bvn, nin=nin)
        
        if not result:
            logger.error("Monnify service returned None")
            return JsonResponse({
                'success': False,
                'message': 'Payment service is temporarily unavailable. Please try again in a few minutes.',
                'error_type': 'service_unavailable'
            }, status=503)
        
        # Validate and save accounts
        if not result.get('accounts'):
            logger.error(f"No accounts in result")
            return JsonResponse({
                'success': False,
                'message': 'Unable to create account details. Please try again.'
            }, status=500)
        
        # Save to database
        accounts_data = []
        for bank_account in result['accounts']:
            account_number = bank_account.get('accountNumber') or bank_account.get('account_number')
            bank_name = bank_account.get('bankName') or bank_account.get('bank_name')
            bank_code = bank_account.get('bankCode') or bank_account.get('bank_code')
            
            if not all([account_number, bank_name, bank_code]):
                continue
            
            VirtualAccount.objects.create(
                user_account=account,
                account_reference=result['account_reference'],
                account_name=result['account_name'],
                account_number=account_number,
                bank_name=bank_name,
                bank_code=bank_code,
                status='active',
                bvn=bvn,
                nin=nin,
                kyc_verified=True,  # Always true when KYC provided
                kyc_verified_at=timezone.now(),
                monnify_response=result.get('monnify_response', {})
            )
            
            accounts_data.append({
                'bank_name': bank_name,
                'account_number': account_number,
                'bank_code': bank_code
            })
        
        logger.info(f"SUCCESS: Created {len(accounts_data)} virtual accounts with KYC")
        
        return JsonResponse({
            'success': True,
            'account_reference': result['account_reference'],
            'account_name': result['account_name'],
            'accounts': accounts_data,
            'message': 'Permanent virtual account created successfully'
        })
        
    except Exception as e:
        logger.error("UNEXPECTED ERROR", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'An unexpected error occurred. Please try again later.'
        }, status=500)

@login_required
@require_http_methods(["POST"])
def generate_reserved_account(request):
    """
    Generate one-time payment account with user-specified amount
    """
    try:
        account = request.user.account
        
        # Parse request body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid request data'
            }, status=400)
        
        # Get amount from request
        amount = data.get('amount')
        
        if not amount:
            return JsonResponse({
                'success': False,
                'message': 'Amount is required'
            }, status=400)
        
        # Validate amount
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'message': 'Invalid amount format'
            }, status=400)
        
        if amount < 100:
            return JsonResponse({
                'success': False,
                'message': 'Minimum amount is ₦100'
            }, status=400)
        
        if amount > 5000000:
            return JsonResponse({
                'success': False,
                'message': 'Maximum amount is ₦5,000,000 per transaction'
            }, status=400)
        
        logger.info(f"Generating quick transfer for {account.user.username} - Amount: ₦{amount}")
        
        # Generate one-time payment
        result = monnify_service.init_one_time_payment(account, amount=amount)
        
        if not result:
            logger.error("Failed to generate one-time payment")
            return JsonResponse({
                'success': False,
                'message': 'Payment service is temporarily unavailable. Please try again in a few minutes.',
                'error_type': 'service_unavailable'
            }, status=503)
        
        logger.info(
            f"One-time payment created - Ref: {result['transaction_reference']} - Amount: ₦{amount}"
        )
        
        return JsonResponse({
            'success': True,
            'transaction_reference': result['transaction_reference'],
            'payment_reference': result['payment_reference'],
            'checkout_url': result.get('checkout_url'),
            'account_name': result['account_name'],
            'accounts': result['accounts'],
            'amount': result['amount'],
            'message': f'Payment account generated for ₦{amount:,.2f}'
        })
        
    except Exception as e:
        logger.error(f"Error generating one-time payment: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'An error occurred. Please try again later.'
        }, status=500)

@require_http_methods(["GET", "POST"])
def test_json_response(request):
    """Test endpoint to verify JSON responses work"""
    return JsonResponse({
        'success': True,
        'message': 'JSON endpoint working!',
        'method': request.method,
        'path': request.path
    })

@login_required
def check_payment_status(request, transaction_reference=None):
    """
    FIXED: AJAX endpoint to check payment status
    Prevents duplicate processing with session tracking
    """
    try:
        account = request.user.account
        
        # Get transaction reference from URL param if not in path
        if not transaction_reference:
            transaction_reference = request.GET.get('ref')
        
        if transaction_reference:
            # Check if already processed in this session to prevent duplicate toasts
            processed_key = f'payment_processed_{transaction_reference}'
            if request.session.get(processed_key):
                return JsonResponse({
                    'success': True,
                    'payment_received': False,
                    'already_processed': True,
                    'message': 'Payment already processed'
                })
            
            # Check specific transaction
            monnify_transaction = MonnifyTransaction.objects.filter(
                transaction_reference=transaction_reference,
                user_account=account
            ).first()
            
            if monnify_transaction and monnify_transaction.payment_status == 'PAID':
                # Mark as processed in session
                request.session[processed_key] = True
                request.session.modified = True
                
                return JsonResponse({
                    'success': True,
                    'payment_received': True,
                    'status': monnify_transaction.payment_status,
                    'amount': float(monnify_transaction.amount_paid),
                    'processed': monnify_transaction.credited_to_account,
                    'paid_on': monnify_transaction.paid_on.isoformat(),
                    'transaction_ref': monnify_transaction.transaction_reference,
                    'new_balance': float(account.balance)
                })
            
            # Query Monnify API if not found locally
            result = monnify_service.get_transaction_status(transaction_reference)
            
            if result and result.get('paymentStatus') == 'PAID':
                return JsonResponse({
                    'success': True,
                    'payment_received': True,
                    'status': result.get('paymentStatus'),
                    'amount': float(result.get('amountPaid', 0)),
                    'processed': False,
                    'message': 'Transaction found, processing...'
                })
            
            return JsonResponse({
                'success': True,
                'payment_received': False,
                'message': 'Payment not yet received'
            })
        
        else:
            # General polling - check for any recent payments
            # Only return payments from last 2 minutes to avoid old duplicates
            recent_transaction = MonnifyTransaction.objects.filter(
                user_account=account,
                paid_on__gte=timezone.now() - timedelta(minutes=2),
                payment_status='PAID',
                credited_to_account=True
            ).order_by('-paid_on').first()
            
            if recent_transaction:
                # Check if already notified in session
                processed_key = f'payment_notified_{recent_transaction.transaction_reference}'
                if request.session.get(processed_key):
                    return JsonResponse({
                        'success': True,
                        'payment_received': False,
                        'current_balance': float(account.balance)
                    })
                
                # Mark as notified
                request.session[processed_key] = True
                request.session.modified = True
                
                return JsonResponse({
                    'success': True,
                    'payment_received': True,
                    'amount': float(recent_transaction.amount_paid),
                    'transaction_ref': recent_transaction.transaction_reference,
                    'paid_on': recent_transaction.paid_on.isoformat(),
                    'new_balance': float(account.balance)
                })
            else:
                return JsonResponse({
                    'success': True,
                    'payment_received': False,
                    'current_balance': float(account.balance)
                })
        
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Error checking payment status'
        }, status=500)

@login_required
def get_virtual_account_info(request):
    """
    AJAX endpoint to get user's virtual account information
    """
    try:
        account = request.user.account
        
        # Get all virtual accounts (there can be multiple banks)
        virtual_accounts = VirtualAccount.objects.filter(
            user_account=account,
            status='active'
        )
        
        response_data = {
            'success': True,
            'has_account': virtual_accounts.exists(),
        }
        
        if virtual_accounts.exists():
            accounts_list = []
            first_account = virtual_accounts.first()
            
            for va in virtual_accounts:
                accounts_list.append({
                    'account_name': va.account_name,
                    'account_number': va.account_number,
                    'bank_name': va.bank_name,
                    'bank_code': va.bank_code,
                })
            
            response_data['accounts'] = accounts_list
            response_data['account_reference'] = first_account.account_reference
            response_data['kyc_verified'] = first_account.kyc_verified
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error getting virtual account info: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Error retrieving account information'
        }, status=500)
        
@require_http_methods(["GET"])
def test_monnify_connection(request):
    try:
        success = monnify_service.authenticate()
        return JsonResponse({
            'monnify_reachable': success,
            'base_url': monnify_service.base_url
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

#Affiliate Setup
@login_required
def affiliate_apply(request):
    """
    Apply to become an affiliate
    - Referral code (username) is assigned IMMEDIATELY
    - Affiliate account status is 'pending' until admin approval
    - Users can see their code but can't earn until approved
    """
    # Check if already an affiliate
    if hasattr(request.user, 'affiliate'):
        messages.info(request, "You're already enrolled in the affiliate program!")
        return redirect('affiliate_dashboard')
    
    if request.method == 'POST':
        reason = request.POST.get('application_reason', '')
        
        from Dashboard.models import AffiliateProfile
        
        # Create affiliate profile - CODE IS ASSIGNED AUTOMATICALLY
        affiliate = AffiliateProfile.objects.create(
            user=request.user,
            # referral_code is auto-generated from username in save()
            status='pending',  # Requires admin approval
            application_reason=reason
        )
        
        messages.success(
            request, 
            f"✓ Your affiliate application has been submitted!\n\n"
            f"Your referral code: {affiliate.referral_code}\n\n"
            f"⏳ Status: Pending Approval\n"
            f"Once approved, you can start earning commissions from your referrals."
        )
        return redirect('affiliate_dashboard')
    
    # Show preview of what their referral code will be
    preview_code = request.user.username.lower()
    
    # Check if code would have a conflict (rare)
    from Dashboard.models import AffiliateProfile
    existing = AffiliateProfile.objects.filter(
        referral_code__iexact=preview_code
    ).exists()
    
    if existing:
        # Show what their code will actually be
        counter = 1
        while AffiliateProfile.objects.filter(
            referral_code__iexact=f"{preview_code}{counter}"
        ).exists():
            counter += 1
        preview_code = f"{preview_code}{counter}"
    
    context = {
        'preview_code': preview_code,
        'code_available': not existing,
        'has_conflict': existing,
    }
    
    return render(request, 'dashboard/affiliate_apply.html', context)

@login_required
def affiliate_dashboard(request):
    """
    UPDATED: Affiliate dashboard with leaderboard showing top performers
    """
    try:
        affiliate = request.user.affiliate
    except AffiliateProfile.DoesNotExist:
        return redirect('affiliate_apply')
    
    # Check if affiliate is approved
    if affiliate.status == 'pending':
        return render(request, 'dashboard/affiliate_pending.html', {
            'affiliate': affiliate,
            'message': 'Your affiliate application is pending approval. You will be notified once approved.'
        })
    elif affiliate.status not in ['active']:
        return render(request, 'dashboard/affiliate_inactive.html', {
            'affiliate': affiliate,
            'status': affiliate.get_status_display()
        })
    
    # Get referrals
    referrals = Referral.objects.filter(
        affiliate=affiliate
    ).select_related('referred_user').order_by('-signup_date')
    
    # Get commissions with status breakdown
    recent_commissions = AffiliateCommission.objects.filter(
        affiliate=affiliate
    ).select_related('referral', 'referral__referred_user').order_by('-created_at')[:10]
    
    # Get commissions by status for breakdown
    from django.db.models import Sum, Count
    commission_breakdown = AffiliateCommission.objects.filter(
        affiliate=affiliate
    ).values('status').annotate(
        count=Count('id'),
        total=Sum('commission_amount')
    )
    
    # Stats
    total_referrals = referrals.count()
    active_referrals = referrals.filter(status='active').count()
    pending_referrals = referrals.filter(status='pending').count()
    
    # Commission stats with status breakdown
    pending_commissions = affiliate.pending_balance  # Locked for 7 days
    available_commissions = affiliate.available_balance  # Ready to withdraw
    
    # Calculate commissions releasing soon (within 3 days)
    from datetime import timedelta
    three_days_from_now = timezone.now() + timedelta(days=3)
    releasing_soon = AffiliateCommission.objects.filter(
        affiliate=affiliate,
        status='pending',
        available_at__lte=three_days_from_now
    ).aggregate(total=Sum('commission_amount'))['total'] or 0
    
    # Build referral URL
    from django.urls import reverse
    base_url = request.build_absolute_uri('/')
    signup_path = reverse('signup')
    referral_link = f"{base_url.rstrip('/')}{signup_path}?ref={affiliate.referral_code}"
    
    # Check withdrawal eligibility
    can_withdraw = (
        affiliate.status == 'active' and 
        affiliate.available_balance >= affiliate.minimum_withdrawal
    )
    
    # Commission history with status icons
    for commission in recent_commissions:
        if commission.status == 'pending':
            days_remaining = (commission.available_at - timezone.now()).days
            commission.status_info = {
                'icon': 'bi-clock',
                'color': 'warning',
                'text': f'Releases in {days_remaining} days'
            }
        elif commission.status == 'available':
            commission.status_info = {
                'icon': 'bi-check-circle',
                'color': 'success',
                'text': 'Ready to withdraw'
            }
        elif commission.status == 'paid':
            commission.status_info = {
                'icon': 'bi-cash',
                'color': 'info',
                'text': 'Paid'
            }
        elif commission.status == 'cancelled':
            commission.status_info = {
                'icon': 'bi-x-circle',
                'color': 'danger',
                'text': 'Reversed/Cancelled'
            }
    
    # ===== NEW: LEADERBOARD DATA =====
    # Get top 10 affiliates by total earnings (all time)
    top_earners = AffiliateProfile.objects.filter(
        status='active'
    ).annotate(
        total_active_referrals=Count(
            'referrals',
            filter=Q(referrals__status='active')
        )
    ).order_by('-total_earned')[:10]
    
    # Add rank and check if current user is in top 10
    user_in_leaderboard = False
    user_rank = None
    
    for idx, top_affiliate in enumerate(top_earners, start=1):
        top_affiliate.rank = idx
        top_affiliate.is_current_user = (top_affiliate.id == affiliate.id)
        if top_affiliate.is_current_user:
            user_in_leaderboard = True
            user_rank = idx
    
    # If user not in top 10, calculate their rank
    if not user_in_leaderboard:
        higher_ranked = AffiliateProfile.objects.filter(
            status='active',
            total_earned__gt=affiliate.total_earned
        ).count()
        user_rank = higher_ranked + 1
    
    # Get user's position data
    current_user_stats = {
        'rank': user_rank,
        'total_earned': affiliate.total_earned,
        'active_referrals': active_referrals,
        'in_top_10': user_in_leaderboard
    }
    
    context = {
        'affiliate': affiliate,
        'referrals': referrals[:10],
        'recent_commissions': recent_commissions,
        'commission_breakdown': commission_breakdown,
        'total_referrals': total_referrals,
        'active_referrals': active_referrals,
        'pending_referrals': pending_referrals,
        'pending_commissions': pending_commissions,
        'available_commissions': available_commissions,
        'releasing_soon': releasing_soon,
        'referral_link': referral_link,
        'can_withdraw': can_withdraw,
        'top_earners': top_earners,
        'current_user_stats': current_user_stats,
    }
    
    return render(request, 'dashboard/affiliate_dashboard.html', context)

@login_required
def affiliate_withdraw(request):
    
    """
    FIXED: Withdrawal with proper validation
    """
    try:
        affiliate = request.user.affiliate
    except AffiliateProfile.DoesNotExist:
        messages.error(request, "You are not an affiliate.")
        return redirect('dashboard_home')
    
    # Check if affiliate is active
    if affiliate.status != 'active':
        messages.error(request, "Your affiliate account must be active to withdraw.")
        return redirect('affiliate_dashboard')
    
    # Check minimum balance
    can_withdraw = affiliate.available_balance >= affiliate.minimum_withdrawal
    
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', 0))
        except (ValueError, TypeError, InvalidOperation):
            messages.error(request, "Invalid amount format.")
            return redirect('affiliate_withdraw')
        
        bank_name = request.POST.get('bank_name', '').strip()
        account_number = request.POST.get('account_number', '').strip()
        account_name = request.POST.get('account_name', '').strip()
        
        # Validation
        if not all([bank_name, account_number, account_name]):
            messages.error(request, "All bank details are required.")
            return redirect('affiliate_withdraw')
        
        if amount <= 0:
            messages.error(request, "Amount must be greater than zero.")
            return redirect('affiliate_withdraw')
        
        if amount < affiliate.minimum_withdrawal:
            messages.error(
                request, 
                f"Minimum withdrawal is ₦{affiliate.minimum_withdrawal:,.2f}"
            )
            return redirect('affiliate_withdraw')
        
        if amount > affiliate.available_balance:
            messages.error(
                request, 
                f"Insufficient balance. Available: ₦{affiliate.available_balance:,.2f}"
            )
            return redirect('affiliate_withdraw')
        
        # Validate account number
        if not account_number.isdigit() or len(account_number) != 10:
            messages.error(request, "Account number must be exactly 10 digits.")
            return redirect('affiliate_withdraw')
        
        # Create withdrawal request
        from Dashboard.models import AffiliateWithdrawal
        from django.db import transaction as db_transaction
        
        try:
            with db_transaction.atomic():
                # Lock the affiliate record
                affiliate = AffiliateProfile.objects.select_for_update().get(
                    id=affiliate.id
                )
                
                # Double-check balance
                if amount > affiliate.available_balance:
                    messages.error(request, "Insufficient balance.")
                    return redirect('affiliate_withdraw')
                
                # Deduct from available balance
                affiliate.available_balance -= amount
                affiliate.save(update_fields=['available_balance'])
                
                # Create withdrawal request
                withdrawal = AffiliateWithdrawal.objects.create(
                    affiliate=affiliate,
                    amount=amount,
                    bank_name=bank_name,
                    account_number=account_number,
                    account_name=account_name,
                    status='pending'
                )
                
                messages.success(
                    request,
                    f"✅ Withdrawal request for ₦{amount:,.2f} submitted successfully! "
                    f"Reference: WD-{withdrawal.id}. "
                    "We'll process it within 1-2 business days."
                )
                
                logger.info(
                    f"Withdrawal requested: ₦{amount:.2f} | "
                    f"Affiliate: {affiliate.referral_code} | "
                    f"Withdrawal ID: {withdrawal.id}"
                )
                
        except Exception as e:
            logger.error(f"Withdrawal creation error: {str(e)}", exc_info=True)
            messages.error(request, "An error occurred. Please try again.")
            return redirect('affiliate_withdraw')
        
        return redirect('affiliate_dashboard')
    
    # GET request - show form
    context = {
        'affiliate': affiliate,
        'can_withdraw': can_withdraw,
    }
    
    return render(request, 'dashboard/affiliate_withdraw.html', context)

@login_required
def affiliate_analytics(request):
    try:
        affiliate = request.user.affiliate
    except AffiliateProfile.DoesNotExist:
        return redirect('affiliate_apply')
    
    # Date range filter
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Referral statistics
    total_referrals = affiliate.referrals.count()
    active_referrals = affiliate.referrals.filter(status='active').count()
    
    # Commission statistics
    commissions_by_type = AffiliateCommission.objects.filter(
        affiliate=affiliate,
        created_at__gte=start_date
    ).values('transaction_type').annotate(
        total=Sum('commission_amount'),
        count=Count('id')
    )
    
    # Daily earnings - FIXED: Use proper date truncation
    from django.db.models.functions import TruncDate
    daily_earnings = AffiliateCommission.objects.filter(
        affiliate=affiliate,
        created_at__gte=start_date
    ).annotate(
        day=TruncDate('created_at')
    ).values('day').annotate(
        earnings=Sum('commission_amount')
    ).order_by('day')
    
    # Top performing referrals
    top_referrals = affiliate.referrals.filter(
        status='active'
    ).order_by('-total_commission_earned')[:10]
    
    # Conversion rate
    conversion_rate = 0
    if total_referrals > 0:
        conversion_rate = (active_referrals / total_referrals) * 100
    
    context = {
        'affiliate': affiliate,
        'days': days,
        'total_referrals': total_referrals,
        'active_referrals': active_referrals,
        'conversion_rate': conversion_rate,
        'commissions_by_type': commissions_by_type,
        'daily_earnings': daily_earnings,
        'top_referrals': top_referrals,
    }
    
    return render(request, 'dashboard/affiliate_analytics.html', context)

@login_required
def affiliate_leaderboard(request):
    """
    Standalone leaderboard page showing top affiliates and user's position
    """
    try:
        affiliate = request.user.affiliate
    except AffiliateProfile.DoesNotExist:
        messages.warning(request, "You must be an affiliate to view the leaderboard.")
        return redirect('affiliate_apply')
    
    # Filter options
    timeframe = request.GET.get('timeframe', 'all_time')  # all_time, month, week
    metric = request.GET.get('metric', 'earnings')  # earnings, referrals
    
    # Base queryset - only active affiliates
    queryset = AffiliateProfile.objects.filter(status='active')
    
    # Apply timeframe filter for earnings
    if timeframe == 'month':
        one_month_ago = timezone.now() - timedelta(days=30)
        # Get earnings from last month
        queryset = queryset.annotate(
            period_earnings=Sum(
                'commissions__commission_amount',
                filter=Q(commissions__created_at__gte=one_month_ago)
            )
        )
        sort_field = '-period_earnings'
    elif timeframe == 'week':
        one_week_ago = timezone.now() - timedelta(days=7)
        queryset = queryset.annotate(
            period_earnings=Sum(
                'commissions__commission_amount',
                filter=Q(commissions__created_at__gte=one_week_ago)
            )
        )
        sort_field = '-period_earnings'
    else:
        # All time earnings
        queryset = queryset.annotate(
            period_earnings=F('total_earned')
        )
        sort_field = '-total_earned'
    
    # Add active referrals count
    queryset = queryset.annotate(
        total_active_referrals=Count(
            'referrals',
            filter=Q(referrals__status='active')
        )
    )
    
    # Sort by selected metric
    if metric == 'referrals':
        queryset = queryset.order_by('-total_active_referrals', '-total_earned')
    else:
        queryset = queryset.order_by(sort_field, '-total_active_referrals')
    
    # Get all affiliates for ranking
    all_affiliates = list(queryset)
    
    # Add rank to each affiliate
    for idx, aff in enumerate(all_affiliates, start=1):
        aff.rank = idx
        aff.is_current_user = (aff.id == affiliate.id)
    
    # Get top 50 for display
    top_affiliates = all_affiliates[:50]
    
    # Find current user's position
    user_rank = None
    user_in_top_50 = False
    
    for aff in all_affiliates:
        if aff.is_current_user:
            user_rank = aff.rank
            user_in_top_50 = (user_rank <= 50)
            break
    
    # Get user's stats
    current_user_stats = {
        'rank': user_rank,
        'total_earned': affiliate.total_earned,
        'period_earnings': affiliate.period_earnings if hasattr(affiliate, 'period_earnings') else affiliate.total_earned,
        'active_referrals': affiliate.total_active_referrals if hasattr(affiliate, 'total_active_referrals') else 0,
        'in_top_50': user_in_top_50,
        'total_affiliates': len(all_affiliates)
    }
    
    # Calculate percentile
    if user_rank and len(all_affiliates) > 0:
        percentile = 100 - ((user_rank / len(all_affiliates)) * 100)
        current_user_stats['percentile'] = round(percentile, 1)
    else:
        current_user_stats['percentile'] = 0
    
    # Get leaderboard statistics
    leaderboard_stats = {
        'total_affiliates': len(all_affiliates),
        'total_earnings': sum(aff.period_earnings or 0 for aff in all_affiliates),
        'total_referrals': sum(aff.total_active_referrals for aff in all_affiliates),
        'avg_earnings': sum(aff.period_earnings or 0 for aff in all_affiliates) / max(len(all_affiliates), 1),
    }
    
    context = {
        'affiliate': affiliate,
        'top_affiliates': top_affiliates,
        'current_user_stats': current_user_stats,
        'leaderboard_stats': leaderboard_stats,
        'timeframe': timeframe,
        'metric': metric,
    }
    
    return render(request, 'dashboard/affiliate_leaderboard.html', context)


@require_http_methods(["GET"])
def validate_referral_code(request):
    """
    AJAX endpoint to validate referral code
    """
    code = request.GET.get('code', '').strip()
    
    if not code:
        return JsonResponse({
            'valid': False, 
            'message': 'Please enter a referral code'
        })
    
    try:
        # Case-insensitive lookup, only active affiliates
        affiliate = AffiliateProfile.objects.get(
            referral_code__iexact=code,
            status='active'
        )
        
        return JsonResponse({
            'valid': True,
            'message': f'Valid! Referred by @{affiliate.user.username}',
            'affiliate_username': affiliate.user.username,
            'affiliate_name': affiliate.user.get_full_name() or affiliate.user.username,
            'code': affiliate.referral_code  # Return actual code (correct case)
        })
        
    except AffiliateProfile.DoesNotExist:
        # Check if it exists but is pending/suspended
        try:
            affiliate = AffiliateProfile.objects.get(referral_code__iexact=code)
            return JsonResponse({
                'valid': False,
                'message': f'This referral code is not active (Status: {affiliate.get_status_display()})'
            })
        except AffiliateProfile.DoesNotExist:
            return JsonResponse({
                'valid': False,
                'message': 'Invalid referral code'
            })
    except Exception as e:
        logger.error(f"Error validating referral code: {str(e)}", exc_info=True)
        return JsonResponse({
            'valid': False, 
            'message': 'Validation error'
        }, status=500)
        
@staff_member_required
def debug_affiliate_deposits(request):
    """Admin view to debug affiliate-related deposit issues"""
    from Dashboard.models import Referral, AffiliateCommission
    
    # Get recent deposits with referrals
    recent_deposits = Transaction.objects.filter(
        transaction_type='deposit',
        created_at__gte=timezone.now() - timedelta(days=7)
    ).select_related('account__user').order_by('-created_at')[:50]
    
    deposit_data = []
    for deposit in recent_deposits:
        try:
            referral = Referral.objects.get(referred_user=deposit.account.user)
            has_referral = True
            referral_status = referral.status
            commission_created = AffiliateCommission.objects.filter(
                source_transaction=deposit
            ).exists()
        except Referral.DoesNotExist:
            has_referral = False
            referral_status = 'N/A'
            commission_created = False
        
        deposit_data.append({
            'user': deposit.account.user.username,
            'amount': deposit.amount,
            'date': deposit.created_at,
            'has_referral': has_referral,
            'referral_status': referral_status,
            'commission_created': commission_created,
            'deposit_successful': deposit.amount > 0,
        })
    
    return render(request, 'admin/debug_deposits.html', {
        'deposits': deposit_data
    })
    
@staff_member_required
def admin_affiliate_approvals(request):
    """
    Admin view to approve/reject affiliate applications
    """
    status_filter = request.GET.get('status', 'pending')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    queryset = AffiliateProfile.objects.select_related('user').order_by('-created_at')
    
    # Apply filters
    if status_filter and status_filter != 'all':
        queryset = queryset.filter(status=status_filter)
    
    if search_query:
        queryset = queryset.filter(
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(referral_code__icontains=search_query)
        )
    
    # Status counts
    status_counts = {
        'pending': AffiliateProfile.objects.filter(status='pending').count(),
        'active': AffiliateProfile.objects.filter(status='active').count(),
        'rejected': AffiliateProfile.objects.filter(status='rejected').count(),
        'suspended': AffiliateProfile.objects.filter(status='suspended').count(),
    }
    status_counts['all'] = sum(status_counts.values())
    
    # Pagination
    paginator = Paginator(queryset, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Handle actions
    if request.method == 'POST':
        affiliate_id = request.POST.get('affiliate_id')
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')
        
        try:
            affiliate = AffiliateProfile.objects.get(id=affiliate_id)
            
            if action == 'approve':
                affiliate.status = 'active'
                affiliate.approved_by = request.user
                affiliate.approved_at = timezone.now()
                if admin_notes:
                    affiliate.admin_notes = admin_notes
                affiliate.save()
                
                messages.success(
                    request,
                    f"✓ Approved {affiliate.user.username} ({affiliate.referral_code}). "
                    "They can now start earning commissions."
                )
                
                # TODO: Send approval email to affiliate
                
            elif action == 'reject':
                affiliate.status = 'rejected'
                if admin_notes:
                    affiliate.admin_notes = admin_notes
                affiliate.save()
                
                messages.warning(
                    request,
                    f"Rejected {affiliate.user.username} ({affiliate.referral_code})."
                )
                
                # TODO: Send rejection email
                
            elif action == 'suspend':
                affiliate.status = 'suspended'
                if admin_notes:
                    affiliate.admin_notes = admin_notes
                affiliate.save()
                
                messages.warning(
                    request,
                    f"Suspended {affiliate.user.username} ({affiliate.referral_code})."
                )
            
            return redirect(f"{request.path}?status={status_filter}")
            
        except AffiliateProfile.DoesNotExist:
            messages.error(request, "Affiliate not found.")
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_counts': status_counts,
    }
    
    return render(request, 'admin/affiliate_approvals.html', context)

@staff_member_required
def admin_affiliate_detail(request, affiliate_id):
    """
    Detailed view of a single affiliate for review
    """
    affiliate = get_object_or_404(AffiliateProfile, id=affiliate_id)
    
    # Get referral stats
    referrals = Referral.objects.filter(affiliate=affiliate).select_related('referred_user')
    total_referrals = referrals.count()
    active_referrals = referrals.filter(status='active').count()
    
    # Get commission stats
    commissions = AffiliateCommission.objects.filter(affiliate=affiliate)
    total_commissions = commissions.aggregate(
        total=Sum('commission_amount')
    )['total'] or 0
    
    pending_commissions = commissions.filter(status='pending').aggregate(
        total=Sum('commission_amount')
    )['total'] or 0
    
    # Get recent activity
    recent_referrals = referrals.order_by('-signup_date')[:10]
    recent_commissions = commissions.order_by('-created_at')[:10]
    
    # Flag suspicious patterns
    warnings = []
    
    # Check for multiple referrals from same IP
    ip_counts = referrals.values('signup_ip').annotate(
        count=Count('id')
    ).filter(count__gt=3, signup_ip__isnull=False)
    
    if ip_counts.exists():
        warnings.append({
            'type': 'ip_duplicate',
            'message': f"Multiple referrals from same IP addresses detected",
            'severity': 'warning'
        })
    
    # Check for rapid signups (>10 in 24 hours)
    from datetime import timedelta
    one_day_ago = timezone.now() - timedelta(days=1)
    recent_signup_count = referrals.filter(signup_date__gte=one_day_ago).count()
    
    if recent_signup_count > 10:
        warnings.append({
            'type': 'rapid_signups',
            'message': f"{recent_signup_count} signups in last 24 hours",
            'severity': 'danger'
        })
    
    context = {
        'affiliate': affiliate,
        'total_referrals': total_referrals,
        'active_referrals': active_referrals,
        'total_commissions': total_commissions,
        'pending_commissions': pending_commissions,
        'recent_referrals': recent_referrals,
        'recent_commissions': recent_commissions,
        'warnings': warnings,
    }
    
    return render(request, 'admin/affiliate_detail.html', context)