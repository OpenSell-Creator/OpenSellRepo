from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.db.models import Q, Count, Avg, Sum, F
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


def format_budget_display(budget_range, budget_min=None, budget_max=None):
    """Format budget for display (following existing price formatting pattern)"""
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

def get_user_access_status(user):
    """Get user's access status and limits"""
    if not user.is_authenticated:
        return {
            'is_pro': False,
            'daily_limit': 0,
            'has_unlimited': False
        }
    
    try:
        is_pro = user.account.effective_status.tier_type == 'pro'
        return {
            'is_pro': is_pro,
            'daily_limit': None if is_pro else 5,
            'has_unlimited': is_pro
        }
    except:
        return {
            'is_pro': False,
            'daily_limit': 5,
            'has_unlimited': False
        }

def can_user_access_request(user, request_obj):
    """Check if user can access a specific request"""
    # Owner can always access
    if user.is_authenticated and hasattr(user, 'profile') and user.profile == request_obj.buyer:
        return True, "owner"
    
    # Admin can always access
    if user.is_staff or user.is_superuser:
        return True, "admin"
    
    # Check if request is suspended or expired
    if request_obj.is_suspended or not request_obj.is_active:
        return False, "unavailable"
    
    # Check access limits for authenticated users
    if user.is_authenticated:
        from .models import RequestAccess
        
        # Check if user can access this request
        can_access, reason = RequestAccess.can_access_request(user, request_obj)
        return can_access, reason
    
    # Anonymous users can view but with limited functionality
    return True, "anonymous"

def get_similar_requests(request_obj, limit=5):
    """Get similar requests based on category and other factors"""
    from .models import BuyerRequest
    
    similar = BuyerRequest.objects.filter(
        status='active',
        is_suspended=False
    ).exclude(id=request_obj.id)
    
    # Prioritize same category
    if request_obj.category:
        similar = similar.filter(category=request_obj.category)
        
        # Further narrow by subcategory if available
        if request_obj.subcategory:
            similar = similar.filter(subcategory=request_obj.subcategory)
    elif request_obj.service_category:
        similar = similar.filter(service_category=request_obj.service_category)
    
    # Consider similar budget range
    if request_obj.budget_range != 'negotiable':
        similar = similar.filter(budget_range=request_obj.budget_range)
    
    # Consider urgency
    if request_obj.urgency in ['urgent', 'high']:
        similar = similar.filter(urgency__in=['urgent', 'high'])
    
    return similar.order_by('-boost_score', '-created_at')[:limit]

def calculate_request_match_score(request_obj, seller_profile):
    """Calculate how well a seller matches a request (for future matching features)"""
    score = 0.0
    
    # Category match (basic requirement)
    category_match = False
    if request_obj.category:
        # Check if seller has products in this category
        try:
            if seller_profile.seller_listings.filter(category=request_obj.category).exists():
                score += 40
                category_match = True
        except:
            pass
    
    if request_obj.service_category:
        # Check if seller has services in this category
        try:
            if seller_profile.service_listings.filter(category=request_obj.service_category).exists():
                score += 40
                category_match = True
        except:
            pass
    
    # If no category match, return low score
    if not category_match:
        return score
    
    # Verification bonus
    try:
        if seller_profile.business_verification_status == 'verified':
            score += 20
    except:
        pass
    
    # Pro user bonus
    try:
        if seller_profile.user.account.effective_status.tier_type == 'pro':
            score += 15
    except:
        pass
    
    # Rating bonus
    try:
        if hasattr(seller_profile, 'combined_rating'):
            rating = seller_profile.combined_rating
            if rating >= 4.5:
                score += 15
            elif rating >= 4.0:
                score += 10
            elif rating >= 3.5:
                score += 5
    except:
        pass
    
    # Location match bonus
    if (hasattr(request_obj, 'location') and request_obj.location and 
        hasattr(seller_profile, 'location') and seller_profile.location):
        
        if request_obj.location.state == seller_profile.location.state:
            score += 10
            if request_obj.location.lga == seller_profile.location.lga:
                score += 5
    
    # Response history bonus
    try:
        response_count = seller_profile.seller_responses.count()
        if response_count > 0:
            avg_score = seller_profile.seller_responses.aggregate(
                avg=Avg('response_score')
            )['avg'] or 0
            score += min(10, avg_score / 10)  # Up to 10 points based on response quality
    except:
        pass
    
    return min(score, 100.0)  # Cap at 100

def send_request_notification_email(request_obj, notification_type, extra_context=None):
    """Send notification email for request events"""
    try:
        context = {
            'request': request_obj,
            'user': request_obj.buyer.user,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'site_domain': getattr(settings, 'SITE_DOMAIN', ''),
        }
        
        if extra_context:
            context.update(extra_context)
        
        email_templates = {
            'new_response': {
                'subject': f'New response to your request "{request_obj.title}"',
                'template': 'emails/new_response_notification.html'
            },
            'request_expiring': {
                'subject': f'Your request "{request_obj.title}" expires soon',
                'template': 'emails/request_expiring.html'
            },
            'request_expired': {
                'subject': f'Your request "{request_obj.title}" has expired',
                'template': 'emails/request_expired.html'
            },
            'request_suspended': {
                'subject': f'Your request "{request_obj.title}" has been suspended',
                'template': 'emails/request_suspended.html'
            },
            'request_fulfilled': {
                'subject': f'Congratulations! Your request "{request_obj.title}" has been fulfilled',
                'template': 'emails/request_fulfilled.html'
            }
        }
        
        if notification_type not in email_templates:
            return False
        
        template_info = email_templates[notification_type]
        
        html_message = render_to_string(template_info['template'], context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=template_info['subject'],
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request_obj.buyer.user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending request notification email: {str(e)}")
        return False

def get_request_statistics(user=None, date_range=None):
    """Get request statistics for analytics"""
    from .models import BuyerRequest, SellerResponse
    from django.utils import timezone
    from datetime import timedelta
    
    # Base querysets
    requests_qs = BuyerRequest.objects.all()
    responses_qs = SellerResponse.objects.all()
    
    # Filter by user if specified
    if user:
        requests_qs = requests_qs.filter(buyer=user.profile)
        responses_qs = responses_qs.filter(buyer_request__buyer=user.profile)
    
    # Filter by date range if specified
    if date_range:
        start_date, end_date = date_range
        requests_qs = requests_qs.filter(created_at__range=[start_date, end_date])
        responses_qs = responses_qs.filter(created_at__range=[start_date, end_date])
    
    # Calculate statistics
    stats = {
        'total_requests': requests_qs.count(),
        'active_requests': requests_qs.filter(status='active', is_suspended=False).count(),
        'fulfilled_requests': requests_qs.filter(status='fulfilled').count(),
        'expired_requests': requests_qs.filter(status='expired').count(),
        'total_responses': responses_qs.count(),
        'total_views': requests_qs.aggregate(total=Sum('view_count'))['total'] or 0,
        'avg_responses_per_request': responses_qs.values('buyer_request').distinct().count(),
    }
    
    # Calculate fulfillment rate
    if stats['total_requests'] > 0:
        stats['fulfillment_rate'] = (stats['fulfilled_requests'] / stats['total_requests']) * 100
    else:
        stats['fulfillment_rate'] = 0
    
    # Calculate average response time (time between request creation and first response)
    if responses_qs.exists():
        first_responses = responses_qs.filter(
            buyer_request__in=requests_qs
        ).values('buyer_request').annotate(
            first_response_time=F('created_at') - F('buyer_request__created_at')
        )
        
        total_response_time = sum([
            r['first_response_time'].total_seconds() 
            for r in first_responses if r['first_response_time']
        ], 0)
        
        if len(first_responses) > 0:
            avg_response_time_hours = (total_response_time / len(first_responses)) / 3600
            stats['avg_response_time_hours'] = round(avg_response_time_hours, 2)
        else:
            stats['avg_response_time_hours'] = 0
    else:
        stats['avg_response_time_hours'] = 0
    
    # Category breakdown
    stats['category_breakdown'] = requests_qs.values(
        'category__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Service category breakdown
    stats['service_category_breakdown'] = requests_qs.filter(
        service_category__isnull=False
    ).values(
        'service_category'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Budget range breakdown
    stats['budget_breakdown'] = requests_qs.values(
        'budget_range'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Urgency breakdown
    stats['urgency_breakdown'] = requests_qs.values(
        'urgency'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    return stats

def validate_request_access_limit(user, current_date=None):
    """Validate if user has reached daily access limit"""
    if not user.is_authenticated:
        return False, "User not authenticated"
    
    # Pro users have unlimited access
    try:
        if user.account.effective_status.tier_type == 'pro':
            return True, "unlimited"
    except:
        pass
    
    from .models import RequestAccess
    
    if current_date is None:
        from django.utils import timezone
        current_date = timezone.now().date()
    
    daily_count = RequestAccess.get_daily_access_count(user, current_date)
    daily_limit = 5  # Free users get 5 requests per day
    
    if daily_count >= daily_limit:
        return False, f"Daily limit of {daily_limit} requests reached"
    
    return True, f"{daily_limit - daily_count} requests remaining today"

def get_trending_categories():
    """Get trending categories based on recent request activity"""
    from .models import BuyerRequest
    from django.utils import timezone
    from datetime import timedelta
    
    # Get categories with most requests in the last 7 days
    last_week = timezone.now() - timedelta(days=7)
    
    # Product categories
    trending_products = BuyerRequest.objects.filter(
        created_at__gte=last_week,
        status='active',
        is_suspended=False,
        category__isnull=False
    ).values(
        'category__id', 'category__name'
    ).annotate(
        request_count=Count('id')
    ).order_by('-request_count')[:5]
    
    # Service categories
    trending_services = BuyerRequest.objects.filter(
        created_at__gte=last_week,
        status='active',
        is_suspended=False,
        service_category__isnull=False
    ).values(
        'service_category'
    ).annotate(
        request_count=Count('id')
    ).order_by('-request_count')[:5]
    
    return {
        'products': trending_products,
        'services': trending_services
    }

def get_user_request_insights(user):
    """Get insights for user's requests (Pro feature)"""
    from .models import BuyerRequest, SellerResponse
    from django.db.models import Avg, Sum
    from django.utils import timezone
    from datetime import timedelta
    
    user_requests = BuyerRequest.objects.filter(buyer=user.profile)
    
    if not user_requests.exists():
        return None
    
    # Basic insights
    insights = {
        'total_requests': user_requests.count(),
        'total_views': user_requests.aggregate(total=Sum('view_count'))['total'] or 0,
        'total_responses': user_requests.aggregate(total=Sum('response_count'))['total'] or 0,
        'avg_views_per_request': user_requests.aggregate(avg=Avg('view_count'))['avg'] or 0,
        'avg_responses_per_request': user_requests.aggregate(avg=Avg('response_count'))['avg'] or 0,
        'most_viewed_request': user_requests.order_by('-view_count').first(),
        'most_responded_request': user_requests.order_by('-response_count').first(),
    }
    
    # Calculate conversion rate (responses per view)
    if insights['total_views'] > 0:
        insights['conversion_rate'] = (insights['total_responses'] / insights['total_views']) * 100
    else:
        insights['conversion_rate'] = 0
    
    # Status breakdown
    insights['status_breakdown'] = user_requests.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_requests = user_requests.filter(created_at__gte=thirty_days_ago)
    
    insights['recent_activity'] = {
        'requests_posted': recent_requests.count(),
        'responses_received': SellerResponse.objects.filter(
            buyer_request__in=recent_requests
        ).count(),
        'views_received': recent_requests.aggregate(total=Sum('view_count'))['total'] or 0,
    }
    
    # Performance trends (compare this month vs last month)
    this_month = timezone.now().replace(day=1)
    last_month = (this_month - timedelta(days=1)).replace(day=1)
    
    this_month_requests = user_requests.filter(created_at__gte=this_month)
    last_month_requests = user_requests.filter(
        created_at__gte=last_month,
        created_at__lt=this_month
    )
    
    insights['trends'] = {
        'requests_this_month': this_month_requests.count(),
        'requests_last_month': last_month_requests.count(),
        'views_this_month': this_month_requests.aggregate(total=Sum('view_count'))['total'] or 0,
        'views_last_month': last_month_requests.aggregate(total=Sum('view_count'))['total'] or 0,
    }
    
    # Calculate growth rates
    if insights['trends']['requests_last_month'] > 0:
        insights['trends']['request_growth'] = (
            (insights['trends']['requests_this_month'] - insights['trends']['requests_last_month']) /
            insights['trends']['requests_last_month']
        ) * 100
    else:
        insights['trends']['request_growth'] = 0
    
    return insights

def get_smart_suggestions_for_request(request_obj, limit=3):
    """Get smart suggestions for improving a request"""
    suggestions = []
    
    # Check if request has low response rate
    if request_obj.view_count > 10 and request_obj.response_count == 0:
        suggestions.append({
            'type': 'improvement',
            'title': 'Improve Request Details',
            'message': 'Your request has been viewed but received no responses. Consider adding more details or adjusting your budget range.',
            'action': 'Edit Request'
        })
    
    # Check if request is about to expire
    if request_obj.days_remaining <= 3 and request_obj.status == 'active':
        suggestions.append({
            'type': 'urgent',
            'title': 'Request Expiring Soon',
            'message': f'Your request expires in {request_obj.days_remaining} days. Consider bumping it to get more visibility.',
            'action': 'Bump Request'
        })
    
    # Check if request has low visibility
    if request_obj.view_count < 5 and request_obj.created_at < timezone.now() - timedelta(days=2):
        suggestions.append({
            'type': 'visibility',
            'title': 'Low Visibility',
            'message': 'Your request has received few views. Try adding images or improving the title to attract more attention.',
            'action': 'Add Images'
        })
    
    # Budget suggestions
    if request_obj.budget_range == 'negotiable' and request_obj.response_count == 0:
        suggestions.append({
            'type': 'budget',
            'title': 'Add Budget Range',
            'message': 'Specifying a budget range might help sellers understand your expectations and respond more readily.',
            'action': 'Update Budget'
        })
    
    return suggestions[:limit]

def cleanup_orphaned_images():
    """Clean up orphaned request images (for maintenance)"""
    from .models import BuyerRequestImage
    import os
    
    orphaned_count = 0
    
    for image in BuyerRequestImage.objects.all():
        try:
            if not os.path.exists(image.image.path):
                image.delete()
                orphaned_count += 1
        except:
            # File doesn't exist or other error
            image.delete()
            orphaned_count += 1
    
    return orphaned_count

def bulk_update_request_status(request_ids, new_status, user=None):
    """Bulk update request status (admin function)"""
    from .models import BuyerRequest
    
    try:
        requests = BuyerRequest.objects.filter(id__in=request_ids)
        
        # Add any business logic for status changes
        if new_status == 'suspended' and user:
            for request in requests:
                request.suspend(user, "Bulk suspension by admin")
        else:
            updated_count = requests.update(status=new_status)
            return updated_count, None
        
        return len(request_ids), None
        
    except Exception as e:
        return 0, str(e)

def generate_request_export_data(user, format='csv'):
    """Generate export data for user's requests"""
    from .models import BuyerRequest
    import csv
    import io
    
    user_requests = BuyerRequest.objects.filter(buyer=user.profile).order_by('-created_at')
    
    if format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Title', 'Category', 'Request Type', 'Status', 'Budget Range',
            'Urgency', 'Views', 'Responses', 'Created', 'Expires'
        ])
        
        # Write data
        for request in user_requests:
            writer.writerow([
                request.title,
                request.category.name if request.category else request.service_category,
                request.get_request_type_display(),
                request.get_status_display(),
                request.budget_display,
                request.get_urgency_display(),
                request.view_count,
                request.response_count,
                request.created_at.strftime('%Y-%m-%d %H:%M'),
                request.expires_at.strftime('%Y-%m-%d %H:%M')
            ])
        
        return output.getvalue()
    
    # Add support for other formats (JSON, Excel) as needed
    return None

# Intelligent matching utilities
def find_matching_sellers(request_obj, limit=10):
    """Find sellers who might be interested in a request"""
    from User.models import Profile
    
    matching_sellers = []
    
    # Find sellers with products in the same category
    if request_obj.category:
        product_sellers = Profile.objects.filter(
            seller_listings__category=request_obj.category,
            seller_listings__is_suspended=False
        ).distinct()
        
        for seller in product_sellers:
            score = calculate_request_match_score(request_obj, seller)
            if score > 30:  # Minimum threshold
                matching_sellers.append((seller, score))
    
    # Find sellers with services in the same category
    if request_obj.service_category:
        try:
            service_sellers = Profile.objects.filter(
                service_listings__category=request_obj.service_category,
                service_listings__is_suspended=False
            ).distinct()
            
            for seller in service_sellers:
                score = calculate_request_match_score(request_obj, seller)
                if score > 30:  # Minimum threshold
                    matching_sellers.append((seller, score))
        except:
            pass  # Services app might not be available
    
    # Sort by score and return top matches
    matching_sellers.sort(key=lambda x: x[1], reverse=True)
    return [seller for seller, score in matching_sellers[:limit]]