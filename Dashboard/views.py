from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Sum, Count, Q, Avg
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.urls import reverse
import csv
import logging

from .models import UserAccount, Transaction, ProductBoost, AccountStatus
from Home.models import Product_Listing
from .forms import DepositForm, BoostProductForm
from django.contrib.admin.views.decorators import staff_member_required
from django_q.models import Task, Schedule
from django_q.tasks import async_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

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
def deposit_funds(request):
    """Enhanced deposit funds view with better UX"""
    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            
            # Here you would typically integrate with a payment gateway
            # For now, we'll just add the funds directly (for demo purposes)
            try:
                request.user.account.add_funds(amount)
                
                # Create transaction record
                Transaction.objects.create(
                    account=request.user.account,
                    transaction_type='deposit',
                    amount=amount,
                    balance_after=request.user.account.balance,
                    reference=f"DEP-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                )
                
                messages.success(request, f"Successfully added ₦{amount:,.0f} to your account!")
                return redirect('dashboard_home')
            except Exception as e:
                messages.error(request, f"Error processing deposit: {str(e)}")
    else:
        form = DepositForm()
    
    # Get recent deposits for history section
    recent_deposits = Transaction.objects.filter(
        account=request.user.account,
        transaction_type='deposit'
    ).order_by('-created_at')[:5]
    
    context = {
        'form': form,
        'recent_deposits': recent_deposits,
    }
    
    return render(request, 'dashboard/deposit_funds.html', context)

@login_required
def subscription_management(request):
    """Enhanced subscription management view"""
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
            yearly_price=0
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
            
            # Validate subscription_type
            if subscription_type not in ['monthly', 'yearly']:
                messages.error(request, 'Invalid subscription type selected.')
                return redirect('subscription_management')
            
            try:
                subscription_info = account.subscribe_to_tier(tier_type, subscription_type)
                
                # Enhanced subscription info for email
                subscription_info['tier_name'] = pro_tier.name
                
                messages.success(
                    request, 
                    f"Successfully subscribed to {tier_type.title()} tier! "
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
        
        elif action == 'reactivate':
            if account.subscription_info and not account.subscription_info['active']:
                try:
                    # Reactivate subscription
                    account.reactivate_subscription()
                    messages.success(request, "Your subscription has been reactivated!")
                    return redirect('subscription_management')
                    
                except ValueError as e:
                    messages.error(request, str(e))
                except Exception as e:
                    logger.error(f"Subscription reactivation error for user {request.user.id}: {str(e)}")
                    messages.error(request, "An error occurred while reactivating your subscription.")
    
    # Calculate potential savings and benefits
    monthly_boost_savings = 0
    yearly_boost_savings = 0
    yearly_savings = 0
    
    if pro_tier:
        avg_boosts_per_month = 10  # Estimate - could be dynamic based on user history
        avg_boost_cost = 5
        monthly_boost_savings = (avg_boost_cost * avg_boosts_per_month * pro_tier.boost_discount / 100)
        yearly_boost_savings = monthly_boost_savings * 12
        yearly_savings = (pro_tier.monthly_price * 12) - pro_tier.yearly_price
    
    # Check if subscription is expiring soon (within 7 days)
    subscription_expiring_soon = False
    days_until_expiry = None
    
    if account.subscription_info and account.subscription_info['active']:
        days_until_expiry = (account.subscription_info['end_date'] - timezone.now()).days
        subscription_expiring_soon = days_until_expiry <= 7
    
    # Get subscription history for display
    subscription_history = account.transactions.filter(
        transaction_type='subscription'
    ).order_by('-created_at')[:5]
    
    context = {
        'account': account,
        'effective_status': account.effective_status,
        'subscription_info': account.subscription_info,
        'pro_tier': pro_tier,
        'monthly_boost_savings': monthly_boost_savings,
        'yearly_boost_savings': yearly_boost_savings,
        'yearly_savings': yearly_savings,
        'current_tier': account.effective_status.tier_type if account.effective_status else 'free',
        'subscription_expiring_soon': subscription_expiring_soon,
        'days_until_expiry': days_until_expiry,
        'subscription_history': subscription_history,
        'can_subscribe': account.balance >= (pro_tier.monthly_price if pro_tier else 0),
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