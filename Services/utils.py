from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from .models import  ServiceInquiry
from django.db.models import Q, F, Count, Avg, Sum, Case, When, Value, IntegerField
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def format_service_price_display(pricing_type, base_price=None, min_price=None, max_price=None):
    """Format service price for display (following existing price formatting pattern)"""
    if pricing_type == 'fixed' and base_price:
        return f"₦{base_price:,.0f}"
    elif pricing_type == 'hourly' and base_price:
        return f"₦{base_price:,.0f}/hour"
    elif pricing_type == 'project' and base_price:
        return f"₦{base_price:,.0f}/project"
    elif pricing_type == 'package' and base_price:
        return f"From ₦{base_price:,.0f}"
    elif pricing_type == 'negotiable':
        if min_price and max_price:
            return f"₦{min_price:,.0f} - ₦{max_price:,.0f}"
        return "Negotiable"
    return "Contact for pricing"


def get_user_service_access_status(user):
    """Get user's service access status and limits"""
    if not user.is_authenticated:
        return {
            'is_pro': False,
            'daily_limit': 0,
            'has_unlimited': False,
            'can_list_services': False
        }
    
    try:
        is_pro = user.account.effective_status.tier_type == 'pro'
        return {
            'is_pro': is_pro,
            'daily_limit': None if is_pro else 5,
            'has_unlimited': is_pro,
            'can_list_services': True
        }
    except:
        return {
            'is_pro': False,
            'daily_limit': 5,
            'has_unlimited': False,
            'can_list_services': True
        }


def can_user_inquire_about_service(user, service):
    """Check if user can inquire about a specific service"""
    # Owner can't inquire about their own service
    if user.is_authenticated and hasattr(user, 'profile') and user.profile == service.provider:
        return False, "owner"
    
    # Check if service is suspended or inactive
    if service.is_suspended or not service.is_active:
        return False, "unavailable"
    
    # Check if user already has an inquiry
    if user.is_authenticated:
        from .models import ServiceInquiry
        
        existing_inquiry = ServiceInquiry.objects.filter(
            service=service,
            client=user.profile
        ).exists()
        
        if existing_inquiry:
            return False, "already_inquired"
    
    # Must be authenticated to inquire
    if not user.is_authenticated:
        return False, "login_required"
    
    return True, "can_inquire"


def can_user_message_about_service(user, service):
    """Check if user can send messages about a specific service"""
    # Owner can't message themselves
    if user.is_authenticated and hasattr(user, 'profile') and user.profile == service.provider:
        return False, "owner"
    
    # Check if service is suspended or inactive
    if service.is_suspended or not service.is_active:
        return False, "unavailable"
    
    # Must be authenticated to message
    if not user.is_authenticated:
        return False, "login_required"
    
    return True, "can_message"


def get_similar_services(service_obj, limit=6):
    """Get similar services based on category and other factors"""
    from .models import ServiceListing
    
    similar = ServiceListing.objects.filter(
        category=service_obj.category,
        is_active=True,
        is_suspended=False
    ).exclude(id=service_obj.id)
    
    # Consider similar service type
    similar = similar.filter(service_type=service_obj.service_type)
    
    # Consider similar pricing range
    if service_obj.base_price and service_obj.pricing_type in ['fixed', 'hourly', 'project']:
        price_range_min = service_obj.base_price * Decimal('0.7')  # 30% lower
        price_range_max = service_obj.base_price * Decimal('1.3')  # 30% higher
        
        similar = similar.filter(
            base_price__range=[price_range_min, price_range_max]
        )
    
    return similar.order_by('-boost_score', '-created_at')[:limit]


def calculate_service_match_score(service_obj, user_profile):
    """Calculate how well a service matches a user's needs (for future recommendation features)"""
    score = 0.0
    
    # Basic compatibility check
    if not hasattr(user_profile, 'user'):
        return score
    
    # Location match bonus
    if (hasattr(service_obj, 'location') and service_obj.location and 
        hasattr(user_profile, 'location') and user_profile.location):
        
        if service_obj.location.state == user_profile.location.state:
            score += 15
            if service_obj.location.lga == user_profile.location.lga:
                score += 10
    
    # Delivery method preference
    if service_obj.delivery_method in ['remote', 'both']:
        score += 10  # Remote work is often preferred
    
    # Experience level bonus
    experience_scores = {
        'expert': 25,
        'experienced': 20,
        'intermediate': 15,
        'beginner': 10
    }
    score += experience_scores.get(service_obj.experience_level, 0)
    
    # Rating bonus
    avg_rating = service_obj.average_rating
    if avg_rating > 0:
        score += (avg_rating * 5)  # Up to 25 points for 5-star rating
    
    # Verification bonus
    if service_obj.provider_is_verified_business:
        score += 20
    
    return min(score, 100.0)  # Cap at 100


def send_service_notification_email(service_obj, notification_type, extra_context=None):
    """Enhanced service notification email sender"""
    try:
        context = {
            'service': service_obj,
            'provider': service_obj.provider.user,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'site_domain': getattr(settings, 'SITE_DOMAIN', ''),
            'service_url': f"{getattr(settings, 'SITE_DOMAIN', '')}{service_obj.get_absolute_url()}",
        }
        
        if extra_context:
            context.update(extra_context)
        
        email_templates = {
            'new_inquiry': {
                'subject': f'New inquiry for your service "{service_obj.title}"',
                'template': 'emails/services/new_inquiry_notification.html'
            },
            'inquiry_reminder': {
                'subject': f'Reminder: Inquiry about "{service_obj.title}"',
                'template': 'emails/services/inquiry_reminder.html'
            },
            'service_featured': {
                'subject': f'Your service "{service_obj.title}" is now featured',
                'template': 'emails/services/service_featured.html'
            },
            'new_review': {
                'subject': f'New review for "{service_obj.title}"',
                'template': 'emails/services/new_review_notification.html'
            },
            'new_message': {
                'subject': f'New message about your service "{service_obj.title}"',
                'template': 'emails/services/new_message_notification.html'
            },
            'inquiry_response': {
                'subject': f'Response to your inquiry about "{service_obj.title}"',
                'template': 'emails/services/inquiry_response_notification.html'
            },
            'service_suspended': {
                'subject': f'Your service "{service_obj.title}" has been suspended',
                'template': 'emails/services/service_suspended.html'
            },
            'service_expiring': {
                'subject': f'Your service "{service_obj.title}" is expiring soon',
                'template': 'emails/services/service_expiring.html'
            }
        }
        
        if notification_type not in email_templates:
            logger.warning(f"Unknown notification type: {notification_type}")
            return False
        
        template_info = email_templates[notification_type]
        
        # Render email content
        html_message = render_to_string(template_info['template'], context)
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=template_info['subject'],
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[service_obj.provider.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Sent {notification_type} email for service {service_obj.id}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending service notification email: {str(e)}")
        return False

def send_message_notification_email(conversation, message, recipient):
    """Enhanced message notification email sender"""
    try:
        # Decrypt message content for email
        message.decrypt_content()
        
        context = {
            'conversation': conversation,
            'message': message,
            'recipient': recipient,
            'sender': message.sender.user,
            'service': conversation.service,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'site_domain': getattr(settings, 'SITE_DOMAIN', ''),
            'conversation_url': f"{getattr(settings, 'SITE_DOMAIN', '')}{conversation.service.get_absolute_url()}#messages",
            'unsubscribe_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/unsubscribe/messages/"
        }
        
        html_message = render_to_string('emails/services/message_notification.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'New message about "{conversation.service.title}"',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Sent message notification email to {recipient.email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending message notification email: {str(e)}")
        return False


def get_service_statistics(user=None, date_range=None):
    """Get service statistics for analytics"""
    from .models import ServiceListing, ServiceInquiry, ServiceReview
    from django.utils import timezone
    from datetime import timedelta
    
    # Base querysets
    services_qs = ServiceListing.objects.all()
    inquiries_qs = ServiceInquiry.objects.all()
    reviews_qs = ServiceReview.objects.all()
    
    # Filter by user if specified
    if user:
        services_qs = services_qs.filter(provider=user.profile)
        inquiries_qs = inquiries_qs.filter(service__provider=user.profile)
        reviews_qs = reviews_qs.filter(service__provider=user.profile)
    
    # Filter by date range if specified
    if date_range:
        start_date, end_date = date_range
        services_qs = services_qs.filter(created_at__range=[start_date, end_date])
        inquiries_qs = inquiries_qs.filter(created_at__range=[start_date, end_date])
        reviews_qs = reviews_qs.filter(created_at__range=[start_date, end_date])
    
    # Calculate statistics
    stats = {
        'total_services': services_qs.count(),
        'active_services': services_qs.filter(is_active=True, is_suspended=False).count(),
        'suspended_services': services_qs.filter(is_suspended=True).count(),
        'total_inquiries': inquiries_qs.count(),
        'pending_inquiries': inquiries_qs.filter(status='pending').count(),
        'total_reviews': reviews_qs.count(),
        'total_views': services_qs.aggregate(total=Sum('view_count'))['total'] or 0,
        'avg_rating': reviews_qs.aggregate(avg=Avg('rating'))['avg'] or 0,
    }
    
    # Calculate inquiry conversion rate
    if stats['total_services'] > 0:
        stats['avg_inquiries_per_service'] = stats['total_inquiries'] / stats['total_services']
    else:
        stats['avg_inquiries_per_service'] = 0
    
    # Category breakdown (using simplified categories)
    from .models import ServiceListing
    stats['category_breakdown'] = []
    for category_key, category_name in ServiceListing.SERVICE_CATEGORIES:
        category_services = services_qs.filter(category=category_key)
        if category_services.exists():
            stats['category_breakdown'].append({
                'category': category_name,
                'count': category_services.count(),
                'avg_inquiries': category_services.aggregate(avg=Avg('inquiry_count'))['avg'] or 0,
                'avg_rating': ServiceReview.objects.filter(
                    service__in=category_services
                ).aggregate(avg=Avg('rating'))['avg'] or 0
            })
    
    # Service type breakdown
    stats['service_type_breakdown'] = []
    for type_key, type_name in ServiceListing.SERVICE_TYPES:
        type_services = services_qs.filter(service_type=type_key)
        if type_services.exists():
            stats['service_type_breakdown'].append({
                'type': type_name,
                'count': type_services.count()
            })
    
    return stats


def validate_service_pricing(pricing_type, base_price=None, min_price=None, max_price=None):
    """Validate service pricing configuration"""
    errors = []
    
    if pricing_type in ['fixed', 'hourly', 'project']:
        if not base_price or base_price <= 0:
            errors.append(f"Base price is required for {pricing_type} pricing and must be greater than 0.")
    
    elif pricing_type == 'negotiable':
        if min_price and max_price:
            if min_price >= max_price:
                errors.append("Maximum price must be greater than minimum price.")
            if min_price <= 0 or max_price <= 0:
                errors.append("Price range values must be greater than 0.")
    
    return errors


def get_trending_service_categories():
    """Get trending service categories based on recent activity"""
    from .models import ServiceListing
    from django.utils import timezone
    from datetime import timedelta
    
    # Get categories with most activity in the last 30 days
    last_month = timezone.now() - timedelta(days=30)
    
    trending = []
    for category_key, category_name in ServiceListing.SERVICE_CATEGORIES:
        recent_services = ServiceListing.objects.filter(
            category=category_key,
            created_at__gte=last_month,
            is_active=True,
            is_suspended=False
        ).count()
        
        recent_inquiries = ServiceInquiry.objects.filter(
            service__category=category_key,
            created_at__gte=last_month
        ).count()
        
        total_activity = recent_services + recent_inquiries
        
        if total_activity > 0:
            trending.append({
                'category_key': category_key,
                'category_name': category_name,
                'recent_services': recent_services,
                'recent_inquiries': recent_inquiries,
                'total_activity': total_activity
            })
    
    return sorted(trending, key=lambda x: x['total_activity'], reverse=True)[:10]


def get_provider_insights(user):
    """Get insights for service provider (Pro feature)"""
    from .models import ServiceListing, ServiceInquiry, ServiceReview
    from django.db.models import Avg, Sum, Count
    
    user_services = ServiceListing.objects.filter(provider=user.profile)
    
    if not user_services.exists():
        return None
    
    insights = {
        'total_services': user_services.count(),
        'active_services': user_services.filter(is_active=True, is_suspended=False).count(),
        'total_views': user_services.aggregate(total=Sum('view_count'))['total'] or 0,
        'total_inquiries': user_services.aggregate(total=Sum('inquiry_count'))['total'] or 0,
        'avg_views_per_service': user_services.aggregate(avg=Avg('view_count'))['avg'] or 0,
        'avg_inquiries_per_service': user_services.aggregate(avg=Avg('inquiry_count'))['avg'] or 0,
        'avg_rating': ServiceReview.objects.filter(
            service__provider=user.profile
        ).aggregate(avg=Avg('rating'))['avg'] or 0,
        'total_reviews': ServiceReview.objects.filter(
            service__provider=user.profile
        ).count(),
        'most_viewed_service': user_services.order_by('-view_count').first(),
        'most_inquired_service': user_services.order_by('-inquiry_count').first(),
    }
    
    # Calculate inquiry conversion rate (inquiries per view)
    if insights['total_views'] > 0:
        insights['inquiry_conversion_rate'] = (insights['total_inquiries'] / insights['total_views']) * 100
    else:
        insights['inquiry_conversion_rate'] = 0
    
    # Performance compared to category average
    if user_services.first():
        category = user_services.first().category
        category_avg_inquiries = ServiceListing.objects.filter(
            category=category,
            is_active=True,
            is_suspended=False
        ).aggregate(avg=Avg('inquiry_count'))['avg'] or 0
        
        insights['performance_vs_category'] = {
            'category_name': dict(ServiceListing.SERVICE_CATEGORIES).get(category, category),
            'your_avg': insights['avg_inquiries_per_service'],
            'category_avg': category_avg_inquiries,
            'performance_ratio': (insights['avg_inquiries_per_service'] / category_avg_inquiries * 100) if category_avg_inquiries > 0 else 0
        }
    
    return insights


def cleanup_orphaned_service_files():
    """Clean up orphaned service files (for maintenance)"""
    from .models import ServiceImage, ServiceDocument
    import os
    
    orphaned_count = 0
    
    # Clean up orphaned images
    for image in ServiceImage.objects.all():
        if hasattr(image.image, 'path') and not os.path.exists(image.image.path):
            image.delete()
            orphaned_count += 1
    
    # Clean up orphaned documents
    for document in ServiceDocument.objects.all():
        if hasattr(document.document, 'path') and not os.path.exists(document.document.path):
            document.delete()
            orphaned_count += 1
    
    return orphaned_count


def bulk_update_service_status(service_ids, new_status, user=None):
    """Bulk update service status (admin function)"""
    from .models import ServiceListing
    
    try:
        services = ServiceListing.objects.filter(id__in=service_ids)
        
        if new_status == 'suspended' and user:
            for service in services:
                service.suspend(user, "Bulk suspension by admin")
            return len(service_ids), None
        elif new_status == 'active':
            updated_count = services.update(is_active=True, is_suspended=False)
            return updated_count, None
        elif new_status == 'inactive':
            updated_count = services.update(is_active=False)
            return updated_count, None
        
        return 0, "Invalid status"
        
    except Exception as e:
        return 0, str(e)


def generate_service_recommendations(user, limit=10):
    """Generate service recommendations for a user (future feature)"""
    from .models import ServiceListing
    
    if not user.is_authenticated:
        # For anonymous users, show popular services
        return ServiceListing.objects.filter(
            is_active=True,
            is_suspended=False
        ).order_by('-inquiry_count', '-view_count')[:limit]
    
    # For authenticated users, show personalized recommendations
    # This is a simplified version - could be enhanced with ML
    
    user_location = getattr(user.profile, 'location', None)
    recommendations = ServiceListing.objects.filter(
        is_active=True,
        is_suspended=False
    )
    
    # Prioritize local services
    if user_location:
        recommendations = recommendations.annotate(
            is_local=Case(
                When(provider__location__state=user_location.state, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by('-is_local', '-boost_score', '-created_at')
    else:
        recommendations = recommendations.order_by('-boost_score', '-created_at')
    
    return recommendations[:limit]


def calculate_service_popularity_score(service):
    """Calculate a popularity score for a service"""
    score = 0
    
    # View count contribution (up to 30 points)
    if service.view_count > 0:
        score += min(30, service.view_count * 0.1)
    
    # Inquiry count contribution (up to 40 points)
    if service.inquiry_count > 0:
        score += min(40, service.inquiry_count * 2)
    
    # Review count and rating contribution (up to 30 points)
    if service.total_reviews > 0:
        review_score = (service.average_rating * service.total_reviews) / 5 * 6
        score += min(30, review_score)
    
    # Recency bonus (services created in last 30 days get bonus)
    from django.utils import timezone
    from datetime import timedelta
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    if service.created_at > thirty_days_ago:
        days_old = (timezone.now() - service.created_at).days
        recency_bonus = max(0, 10 - (days_old * 0.33))  # Up to 10 points
        score += recency_bonus
    
    return min(score, 100)  # Cap at 100


def get_service_performance_tips(service):
    """Generate performance improvement tips for a service"""
    tips = []
    
    # Check basic completion
    if not service.images.exists():
        tips.append({
            'category': 'Visual Appeal',
            'tip': 'Add high-quality images showcasing your work',
            'impact': 'High',
            'reason': 'Services with images get 3x more inquiries'
        })
    
    if len(service.description) < 200:
        tips.append({
            'category': 'Description',
            'tip': 'Expand your service description to at least 200 characters',
            'impact': 'Medium',
            'reason': 'Detailed descriptions build trust with potential clients'
        })
    
    # Check pricing strategy
    if service.pricing_type == 'negotiable' and not service.min_price:
        tips.append({
            'category': 'Pricing',
            'tip': 'Set a minimum price for negotiable services',
            'impact': 'Medium',
            'reason': 'Clear pricing attracts serious clients'
        })
    
    # Check portfolio
    if not service.portfolio_url and not service.documents.exists():
        tips.append({
            'category': 'Portfolio',
            'tip': 'Add portfolio samples or a portfolio link',
            'impact': 'High',
            'reason': 'Portfolios showcase your skills and increase trust'
        })
    
    # Check response time (if service has inquiries)
    pending_inquiries = service.inquiries.filter(status='pending').count()
    if pending_inquiries > 0:
        tips.append({
            'category': 'Responsiveness',
            'tip': f'Respond to {pending_inquiries} pending inquiries',
            'impact': 'Critical',
            'reason': 'Quick responses improve your reputation and ranking'
        })
    
    # Check reviews
    if not service.reviews.exists() and service.inquiry_count > 0:
        tips.append({
            'category': 'Reviews',
            'tip': 'Ask satisfied clients to leave reviews',
            'impact': 'High',
            'reason': 'Positive reviews significantly boost credibility'
        })
    
    # Check skills and tools
    if not service.skills_offered:
        tips.append({
            'category': 'Skills',
            'tip': 'List your specific skills and expertise',
            'impact': 'Medium',
            'reason': 'Clear skill listing helps clients find you through search'
        })
    
    return tips


def create_service_notification(user, notification_type, service, extra_data=None):
    """Enhanced service notification creator with better error handling"""
    try:
        from Notifications.models import create_notification, NotificationCategory, NotificationPriority
        
        notification_configs = {
            'new_inquiry': {
                'title': 'New Service Inquiry',
                'message': f'Someone is interested in your service "{service.title}"',
                'category': NotificationCategory.INQUIRIES,
                'priority': NotificationPriority.HIGH,
                'action_text': 'View Inquiry'
            },
            'inquiry_response': {
                'title': 'Inquiry Response',
                'message': f'You received a response about "{service.title}"',
                'category': NotificationCategory.RESPONSES,
                'priority': NotificationPriority.MEDIUM,
                'action_text': 'View Response'
            },
            'new_message': {
                'title': 'New Message',
                'message': f'You have a new message about "{service.title}"',
                'category': NotificationCategory.MESSAGES,
                'priority': NotificationPriority.MEDIUM,
                'action_text': 'View Message'
            },
            'service_featured': {
                'title': 'Service Featured',
                'message': f'Your service "{service.title}" is now featured',
                'category': NotificationCategory.SYSTEM,
                'priority': NotificationPriority.LOW,
                'action_text': 'View Service'
            },
            'service_review': {
                'title': 'New Review',
                'message': f'Someone reviewed your service "{service.title}"',
                'category': NotificationCategory.REVIEWS,
                'priority': NotificationPriority.MEDIUM,
                'action_text': 'View Review'
            },
            'service_saved': {
                'title': 'Service Saved',
                'message': f'Someone saved your service "{service.title}"',
                'category': NotificationCategory.SAVES,
                'priority': NotificationPriority.LOW,
                'action_text': 'View Service'
            },
            'service_expiring': {
                'title': 'Service Expiring Soon',
                'message': f'Your service "{service.title}" will expire soon',
                'category': NotificationCategory.ALERTS,
                'priority': NotificationPriority.HIGH,
                'action_text': 'Renew Service'
            },
            'service_suspended': {
                'title': 'Service Suspended',
                'message': f'Your service "{service.title}" has been suspended',
                'category': NotificationCategory.ALERTS,
                'priority': NotificationPriority.CRITICAL,
                'action_text': 'View Details'
            }
        }
        
        if notification_type in notification_configs:
            config = notification_configs[notification_type]
            
            # Override message if extra_data provided
            if extra_data and 'message' in extra_data:
                config['message'] = extra_data['message']
            
            create_notification(
                user=user,
                title=config['title'],
                message=config['message'],
                category=config['category'],
                priority=config['priority'],
                content_object=service,
                action_url=service.get_absolute_url(),
                action_text=config['action_text']
            )
            
            logger.info(f"Created {notification_type} notification for user {user.id}")
            return True
        else:
            logger.warning(f"Unknown notification type: {notification_type}")
            return False
            
    except ImportError:
        logger.warning("Notifications app not available")
        return False
    except Exception as e:
        logger.error(f"Error creating service notification: {str(e)}")
        return False



def get_service_conversation_for_users(service, user1, user2):
    """Enhanced conversation getter with better error handling"""
    try:
        from .models import ServiceConversation
        
        # Use the improved method from the model
        conversation = ServiceConversation.get_or_create_conversation(
            service=service,
            user1_profile=user1.profile,
            user2_profile=user2.profile
        )
        
        return conversation
        
    except Exception as e:
        logger.error(f"Error getting service conversation: {str(e)}")
        return None


def mark_service_messages_as_read(conversation, user):
    """Enhanced message marking with error handling"""
    try:
        return conversation.mark_messages_read_for_user(user.profile)
    except Exception as e:
        logger.error(f"Error marking messages as read: {str(e)}")
        return 0


def get_unread_service_messages_count(user):
    """Enhanced unread messages count with error handling"""
    try:
        from .models import ServiceConversation
        return ServiceConversation.get_unread_messages_count(user.profile)
    except Exception as e:
        logger.error(f"Error getting unread messages count: {str(e)}")
        return 0


def send_inquiry_response_notification(inquiry):
    """Enhanced inquiry response notification"""
    try:
        # Create in-app notification
        success = create_service_notification(
            user=inquiry.client.user,
            notification_type='inquiry_response',
            service=inquiry.service,
            extra_data={
                'message': f'{inquiry.service.provider.user.username} responded to your inquiry about "{inquiry.service.title}"'
            }
        )
        
        # Send email notification
        email_success = send_service_notification_email(
            service_obj=inquiry.service,
            notification_type='inquiry_response',
            extra_context={
                'inquiry': inquiry,
                'client': inquiry.client.user,
                'provider_response': inquiry.provider_response,
                'provider_quote': inquiry.provider_quote
            }
        )
        
        return success and email_success
        
    except Exception as e:
        logger.error(f"Error sending inquiry response notification: {str(e)}")
        return False

def bulk_create_service_notifications(notifications_data):
    """Bulk create notifications for better performance"""
    try:
        from Notifications.models import Notification
        
        notifications = []
        for data in notifications_data:
            notifications.append(Notification(
                user=data['user'],
                title=data['title'],
                message=data['message'],
                category=data.get('category', 'SYSTEM'),
                priority=data.get('priority', 'MEDIUM'),
                content_type=data.get('content_type'),
                object_id=data.get('object_id'),
                action_url=data.get('action_url'),
                action_text=data.get('action_text')
            ))
        
        # Bulk create for better performance
        created_notifications = Notification.objects.bulk_create(notifications)
        logger.info(f"Bulk created {len(created_notifications)} notifications")
        
        return len(created_notifications)
        
    except ImportError:
        logger.warning("Notifications app not available for bulk create")
        return 0
    except Exception as e:
        logger.error(f"Error bulk creating notifications: {str(e)}")
        return 0

def get_service_search_suggestions(query, limit=5):
    """Get search suggestions for services based on query"""
    from .models import ServiceListing
    
    if not query or len(query) < 2:
        return []
    
    # Search in titles and skills
    suggestions = ServiceListing.objects.filter(
        Q(title__icontains=query) | Q(skills_offered__icontains=query),
        is_active=True,
        is_suspended=False
    ).values_list('title', flat=True).distinct()[:limit]
    
    return list(suggestions)

def validate_service_messaging_permissions(service, user):
    """Validate if user can message about a service"""
    try:
        # Owner can't message themselves
        if hasattr(user, 'profile') and user.profile == service.provider:
            return False, "You cannot message yourself about your own service."
        
        # Check if service is suspended or inactive
        if service.is_suspended:
            return False, "This service is currently suspended."
        
        if not service.is_active:
            return False, "This service is not currently active."
        
        # Must be authenticated
        if not user.is_authenticated:
            return False, "You must be logged in to send messages."
        
        return True, "Can send message"
        
    except Exception as e:
        logger.error(f"Error validating messaging permissions: {str(e)}")
        return 