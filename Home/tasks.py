from django_q.tasks import async_task, result
from django_q.models import Schedule
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging
from django_q.tasks import async_task


logger = logging.getLogger(__name__)


def delete_expired_listings():
    """Delete expired product listings - runs daily at 1 AM"""
    from .models import Product_Listing
    
    try:
        count = Product_Listing.delete_expired_listings()
        logger.info(f"Deleted {count} expired listings")
        return f"Deleted {count} expired listings"
    except Exception as e:
        logger.error(f"Error deleting expired listings: {str(e)}")
        raise


def update_all_boost_scores():
    """Update boost scores for all products - can be run manually"""
    from .models import Product_Listing
    
    try:
        products = Product_Listing.objects.all()
        updated = 0
        
        for product in products:
            old_score = product.boost_score
            new_score = product.calculate_boost_score()
            
            if old_score != new_score:
                product.boost_score = new_score
                product.save(update_fields=['boost_score'])
                updated += 1
        
        logger.info(f"Updated {updated} product boost scores")
        return f"Updated {updated} boost scores"
        
    except Exception as e:
        logger.error(f"Error updating boost scores: {str(e)}")
        raise


def send_listing_expiry_warning(product_id):
    """Send warning when listing is about to expire"""
    from .models import Product_Listing
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    
    try:
        product = Product_Listing.objects.get(id=product_id)
        
        if product.days_until_deletion in [3, 1]:
            context = {
                'user': product.seller.user,
                'product': product,
                'days_remaining': product.days_until_deletion,
                'site_name': settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'OpenSell',
                'update_url': f"{settings.SITE_DOMAIN}/product/{product.id}/update/" if hasattr(settings, 'SITE_DOMAIN') else '#',
            }
            
            html_message = render_to_string('emails/listing_expiring.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=f'Your Listing Expires in {product.days_until_deletion} Days',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[product.seller.user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            return f"Expiry warning sent for {product.title}"
            
    except Exception as e:
        logger.error(f"Error sending listing expiry warning: {str(e)}")
        # Don't raise - this is not critical