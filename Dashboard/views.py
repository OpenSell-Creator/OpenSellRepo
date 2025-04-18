from django.shortcuts import render

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal

from .models import UserAccount, Transaction, ProductBoost, AccountStatus
from Home.models import Product_Listing
from .forms import DepositForm, BoostProductForm

@login_required
def dashboard_home(request):
    """Main dashboard view showing account summary"""
    try:
        account = request.user.account
    except UserAccount.DoesNotExist:
        # Create account if it doesn't exist (fallback)
        default_status = AccountStatus.objects.filter(min_balance=0).first()
        account = UserAccount.objects.create(user=request.user, status=default_status)
    
    # Get recent transactions
    recent_transactions = Transaction.objects.filter(account=account).order_by('-created_at')[:5]
    
    # Get user's listings
    user_listings = Product_Listing.objects.filter(seller=request.user.profile).order_by('-created_at')
    
    # Calculate account stats
    total_spent = Transaction.objects.filter(
        account=account, 
        amount__lt=0
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    active_boosts = ProductBoost.objects.filter(
        product__seller=request.user.profile,
        is_active=True,
        end_date__gt=timezone.now()
    ).count()
    
    next_status = AccountStatus.objects.filter(
        min_balance__gt=account.balance
    ).order_by('min_balance').first()
    
    progress_percentage = 0
    if next_status:
        if next_status.min_balance > 0:
            progress_percentage = min(100, int((account.balance / next_status.min_balance) * 100))
            
    context = {
        'account': account,
        'recent_transactions': recent_transactions,
        'user_listings': user_listings[:5],
        'listings_count': user_listings.count(),
        'total_spent': abs(total_spent),
        'active_boosts': active_boosts,
        'next_status': next_status,
        'progress_percentage': progress_percentage,
    }
    
    return render(request, 'dashboard/dashboard_home.html', context)

@login_required
def transaction_history(request):
    """View for listing all transactions"""
    transactions = Transaction.objects.filter(account=request.user.account).order_by('-created_at')
    
    context = {
        'transactions': transactions
    }
    
    return render(request, 'dashboard/transaction_history.html', context)

@login_required
def deposit_funds(request):
    """View for adding funds to account"""
    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            
            # Here you would typically integrate with a payment gateway
            # For now, we'll just add the funds directly
            try:
                request.user.account.add_funds(amount)
                messages.success(request, f"Successfully added {amount} to your account!")
                return redirect('dashboard_home')
            except Exception as e:
                messages.error(request, f"Error processing deposit: {str(e)}")
    else:
        form = DepositForm()
    
    return render(request, 'dashboard/deposit_funds.html', {'form': form})

@login_required
def boost_product(request, product_id):
    """View for boosting a product"""
    product = get_object_or_404(Product_Listing, id=product_id, seller=request.user.profile)
    
    if request.method == 'POST':
        form = BoostProductForm(request.POST)
        if form.is_valid():
            boost_type = form.cleaned_data['boost_type']
            duration_days = form.cleaned_data['duration']
            
            # Calculate cost based on boost type and duration
            boost_costs = {
                'featured': Decimal('5.00'),
                'urgent': Decimal('3.00'),
                'spotlight': Decimal('7.50'),
            }
            
            base_cost = boost_costs.get(boost_type, Decimal('5.00'))
            total_cost = base_cost * duration_days
            
            # Check if user has enough funds
            account = request.user.account
            if account.balance < total_cost:
                messages.error(request, f"Insufficient funds. You need {total_cost} but have {account.balance}.")
                return redirect('deposit_funds')
            
            try:
                # Deduct funds
                transaction = Transaction.objects.create(
                    account=account,
                    amount=-total_cost,
                    transaction_type='boost_fee',
                    description=f"Boost fee for {product.title} ({boost_type})"
                )
                
                # Update account balance
                account.balance -= total_cost
                account.save()
                
                # Create boost record
                end_date = timezone.now() + timezone.timedelta(days=duration_days)
                ProductBoost.objects.create(
                    product=product,
                    boost_type=boost_type,
                    cost=total_cost,
                    end_date=end_date,
                    transaction=transaction
                )
                
                messages.success(request, f"Your product has been boosted with {boost_type} for {duration_days} days!")
                return redirect('dashboard_home')
            except Exception as e:
                messages.error(request, f"Error processing boost: {str(e)}")
    else:
        form = BoostProductForm()
    
    return render(request, 'dashboard/boost_product.html', {'form': form, 'product': product})

@login_required
def account_status(request):
    """View showing account status details and benefits"""
    account = request.user.account
    all_statuses = AccountStatus.objects.all().order_by('min_balance')
    
    context = {
        'account': account,
        'all_statuses': all_statuses
    }
    
    return render(request, 'dashboard/account_status.html', context)
