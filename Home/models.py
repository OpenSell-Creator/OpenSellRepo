import os
import uuid
from django.contrib.auth.models import User
from User.models import Profile, Location
from User import models
from django.urls import reverse, reverse_lazy
from django.core.files.storage import default_storage
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from .utils import user_listing_path, category_image_path
from django.db.models import Avg
from django.db import models
from django.db import models
from imagekit.models import ProcessedImageField, ImageSpecField
from imagekit.processors import ResizeToFit, ResizeToFill
from datetime import date

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to=category_image_path, null=True, blank=True)
    slug = models.SlugField(max_length=100, unique=True, null=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"
        
class Subcategory(models.Model):
    category = models.ForeignKey(Category, related_name='subcategories', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, null=True)

    def __str__(self):
        return f"{self.category.name} - {self.name}"

    class Meta:
        unique_together = ('category', 'name')
        verbose_name_plural = "Subcategories"

class Brand(models.Model):
    categories = models.ManyToManyField(Category, related_name='brands')
    subcategories = models.ManyToManyField(Subcategory, related_name='brands')
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True, null=True)

    def __str__(self):
        return self.name

class Product_Listing(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, unique=True, editable=False)
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('used', 'Used'),
    ]
    LISTING_TYPES = [
        ('standard', 'Standard Listing (45 days)'),
        ('urgent', 'Urgent Sale (30 days)'),
        ('permanent', 'Permanent Retail Listing'),
    ]
    title = models.CharField(max_length=255)
    seller = models.ForeignKey(Profile, on_delete=models.CASCADE)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    subcategory = models.ForeignKey(Subcategory, related_name='products', on_delete=models.SET_NULL, null=True)
    brand = models.ForeignKey(Brand, related_name='products', null=True, blank=True, on_delete=models.SET_NULL)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    location = models.OneToOneField(Location, on_delete=models.SET_NULL, null=True)
    condition = models.CharField(max_length=4, choices=CONDITION_CHOICES, default='new')
    view_count = models.PositiveIntegerField(default=0)

    listing_type = models.CharField(max_length=10, choices=LISTING_TYPES, default='standard')
    quantity = models.PositiveIntegerField(default=1)
    sold_quantity = models.PositiveIntegerField(default=0)
    is_always_available = models.BooleanField(default=False)
    expiration_date = models.DateTimeField(null=True, blank=True)
    last_stock_notification = models.DateTimeField(null=True, blank=True)
    deletion_warning_sent = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True, null=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='suspended_listings'
    )
    boost_score = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Combined score for sorting (boost + pro status)"
    )
    
    def suspend(self, admin_user, reason=None):
        self.is_suspended = True
        self.suspended_at = timezone.now()
        self.suspended_by = admin_user
        if reason:
            self.suspension_reason = reason
        self.save()
        
        # Notify the seller
        from django.core.mail import send_mail
        from django.conf import settings
        from django.template.loader import render_to_string
        
        context = {
            'product': self,
            'reason': reason or 'Policy violation',
            'seller': self.seller
        }
        
        email_body = render_to_string('emails/listing_suspended_email.html', context)
        
        try:
            send_mail(
                subject=f'Your listing "{self.title}" has been suspended',
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.seller.user.email],
                html_message=email_body,
                fail_silently=True,
            )
        except Exception as e:
            import logging
            logging.error(f"Error sending suspension email: {e}")
            
    def unsuspend(self):
        self.is_suspended = False
        self.save()
        
        # Notify the seller
        from django.core.mail import send_mail
        from django.conf import settings
        from django.template.loader import render_to_string
        
        context = {
            'product': self,
            'seller': self.seller
        }
        
        email_body = render_to_string('emails/listing_unsuspended_email.html', context)
        
        try:
            send_mail(
                subject=f'Your listing "{self.title}" has been reinstated',
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.seller.user.email],
                html_message=email_body,
                fail_silently=True,
            )
        except Exception as e:
            import logging
            logging.error(f"Error sending unsuspension email: {e}")

    def increase_view_count(self):
        self.view_count += 1
        self.save()
    
    def primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('product_detail', kwargs={'pk': self.id})
    
    @property
    def seller_is_verified_business(self):
        """Check if the seller is a verified business"""
        try:
            return self.seller.business_verification_status == 'verified'
        except AttributeError:
            return False
    
    @property
    def seller_business_name(self):
        """Get seller's business name if verified"""
        try:
            if self.seller_is_verified_business:
                return self.seller.business_name
        except AttributeError:
            pass
        return None
    
    @property
    def seller_business_info(self):
        if self.seller_is_verified_business:
            try:
                return {
                    'name': self.seller.business_name,
                    'email': self.seller.business_email,
                    'phone': self.seller.business_phone,
                    'website': self.seller.business_website,
                    'address_visible': self.seller.business_address_visible,
                }
            except AttributeError:
                pass
        return None
    
    @property
    def verification_tier_level(self):
        if self.is_boosted:
            boost = self.active_boost
            if boost:
                tier_map = {'premium': 1, 'spotlight': 2, 'featured': 3, 'urgent': 4}
                return tier_map.get(boost.boost_type, 5)
            return 5
        elif self.seller_is_verified_business:
            return 6
        elif self.is_pro_seller:
            return 7
        else:
            return 8
    
    @property
    def average_rating(self):
        return self.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    
    def is_saved_by_user(self, user):
        if not user.is_authenticated:
            return False
        return SavedProduct.objects.filter(
            user=user,
            product=self
        ).exists()
        
    @property
    def stock_status(self):
        if self.is_always_available:
            return 'always_available'
        if self.quantity <= 0:
            return 'out_of_stock'
        if self.quantity <= 5:
            return 'low_stock'
        return 'in_stock'
    
    @property
    def days_until_deletion(self):
        if self.expiration_date:
            delta = (self.expiration_date - timezone.now()).days
            return max(0, delta)
        return None
    
    @property
    def time_remaining(self):
        """Returns detailed time remaining before deletion"""
        if not self.expiration_date or self.listing_type == 'permanent':
            return {
                'days': 0,
                'hours': 0,
                'minutes': 0,
                'seconds': 0,
                'total_seconds': 0
            }
            
        now = timezone.now()
        if now >= self.expiration_date:
            return {
                'days': 0,
                'hours': 0,
                'minutes': 0,
                'seconds': 0,
                'total_seconds': 0
            }
            
        delta = self.expiration_date - now
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        seconds = delta.seconds % 60
        
        return {
            'days': days,
            'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
            'total_seconds': delta.total_seconds()
        }
        
    @property
    def is_boosted(self):
        return self.boosts.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).exists()
    
    @property
    def active_boost(self):
        return self.boosts.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).first()
    
    @property
    def is_pro_seller(self):
        try:
            return self.seller.user.account.is_subscription_active
        except:
            return False
    
    @property
    def boost_type_display(self):
        boost = self.active_boost
        return boost.get_boost_type_display() if boost else None
    
    def calculate_boost_score(self):
        score = 0
        
        # Base score for pro users
        if self.is_pro_seller:
            score += 50  # Pro user base score
        
        # Add boost scores
        if self.is_boosted:
            boost = self.active_boost
            boost_scores = {
                'featured': 100,
                'urgent': 75,
                'spotlight': 150,
                'premium': 200
            }
            score += boost_scores.get(boost.boost_type, 50)
        
        if self.created_at:
            days_old = (timezone.now() - self.created_at).days
            time_score = max(0, 10 - (days_old * 0.1))
            score += time_score
        else:
            score += 10
        
        return score
    
    def reset_expiration(self):
        """Reset the expiration date based on listing type"""
        if self.listing_type == 'permanent':
            self.expiration_date = None
        else:
            duration = {
                'standard': 45,
                'business': 90,
                'urgent': 30,
            }.get(self.listing_type, 45)
            
            self.expiration_date = timezone.now() + timedelta(days=duration)
            self.deletion_warning_sent = False
        self.save()

    def save(self, *args, **kwargs):
        is_new = self.pk is None 
        
        if is_new and self.listing_type != 'permanent':
            duration = {
                'standard': 45,
                'urgent': 30
            }.get(self.listing_type, 45)
            self.expiration_date = timezone.now() + timedelta(days=duration)
        
        if self.pk: 
            try:
                original = Product_Listing.objects.get(pk=self.pk)
        
                if original.listing_type != self.listing_type:
                    self.deletion_warning_sent = False
                    if self.listing_type == 'permanent':
                        self.expiration_date = None
                    else:
                        duration = {
                            'standard': 45,
                            'urgent': 30
                        }.get(self.listing_type, 45)
                        self.expiration_date = timezone.now() + timedelta(days=duration)
                
                # Reset expiration on significant updates
                elif self.listing_type != 'permanent':
                    significant_fields = ['title', 'description', 'price', 'quantity']
                    if any(getattr(original, field) != getattr(self, field) for field in significant_fields):
                        duration = {
                            'standard': 45,
                            'urgent': 30
                        }.get(self.listing_type, 45)
                        self.expiration_date = timezone.now() + timedelta(days=duration)
                        self.deletion_warning_sent = False
                        
            except Product_Listing.DoesNotExist:
                pass
            
        if self.seller.is_verified_business and self.listing_type == 'standard':
            if not self.pk: 
                self.listing_type = 'permanent'
        
        super().save(*args, **kwargs)
        
        calculated_score = self.calculate_boost_score()
        if self.boost_score != calculated_score:

            Product_Listing.objects.filter(pk=self.pk).update(boost_score=calculated_score)

            self.boost_score = calculated_score

        if is_new:

            from django.db.models import F
            Profile.objects.filter(id=self.seller.id).update(
                total_products_listed=F('total_products_listed') + 1
            )

            self.seller.refresh_from_db(fields=['total_products_listed'])
            
    def delete(self, *args, **kwargs):

        for image in self.images.all():
            image.delete()
        product_path = f'product_images/{self.seller.user.username}/{self.title}/'
        if default_storage.exists(product_path):
            default_storage.delete(product_path)
        
        super().delete(*args, **kwargs)

    def send_deletion_warning(self):
        if not self.deletion_warning_sent and self.days_until_deletion in [1, 3]:
            # Send notification logic here
            self.deletion_warning_sent = True
            self.save()
            
    @property
    def seller_average_rating(self):
        return self.seller.seller_average_rating
    
    @property
    def seller_total_reviews(self):
        return self.seller.total_seller_reviews
    
    @classmethod
    def delete_expired_listings(cls):
        from django.db import ProgrammingError, OperationalError, connection
        
        try:
            connection.ensure_connection()
            
            expired = cls.objects.filter(
                expiration_date__lte=timezone.now(),
                listing_type__in=['standard','urgent']
            )
            
            count = expired.count()
            
            batch_size = 50
            total = 0
            
            expired_ids = list(expired.values_list('id', flat=True))
            
            for i in range(0, len(expired_ids), batch_size):
                batch_ids = expired_ids[i:i+batch_size]
                batch = cls.objects.filter(id__in=batch_ids)
                
                for product in batch:
                    try:
                        # Clean up images manually first
                        for image in product.images.all():
                            try:
                                # Delete the image file
                                image.image.delete(save=False)
                            except Exception as img_error:
                                import logging
                                logging.warning(f"Error deleting image for product {product.id}: {img_error}")
                        
                        # Try to delete product directory
                        try:
                            product_path = f'product_images/{product.seller.user.username}/{product.title}/'
                            if default_storage.exists(product_path):
                                default_storage.delete(product_path)
                        except Exception as dir_error:
                            import logging
                            logging.warning(f"Error deleting directory for product {product.id}: {dir_error}")
                            
                        total += 1
                    except Exception as prod_error:
                        import logging
                        logging.warning(f"Error processing product {product.id}: {prod_error}")
                
                batch.delete()
                
            return total
        except ProgrammingError:
            return 0
        except OperationalError as e:
            # Specifically handle connection issues
            import logging
            logging.warning(f"Could not delete expired listings: {e}")
            # Don't raise the error further, just log and continue
            return 0
        except Exception as e:
            # Handle other exceptions
            import logging
            logging.warning(f"Could not delete expired listings: {e}")
            return 0
        
    def get_boost_status(self):
        return self.boosts.filter(is_active=True, end_date__gt=timezone.now()).first()
    
    def can_be_boosted(self, user):
        if not user.is_authenticated:
            return False
        return self.seller.user == user and user.account.balance > 0
        
class Product_Image(models.Model):
    product = models.ForeignKey(Product_Listing, related_name='images', on_delete=models.CASCADE)
    image = ProcessedImageField(
        upload_to=user_listing_path,
        processors=[ResizeToFit(800, 600)],  # Main image size
        format='JPEG',
        options={'quality': 80}
    )
    # Auto-generated thumbnail
    thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFill(200, 200)],  # Square thumbnail
        format='JPEG',
        options={'quality':75}
    )
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.product.title}"
    
    def delete(self, *args, **kwargs):
        # Delete files using storage-agnostic method
        self.image.delete(save=False)
        super().delete(*args, **kwargs)

class SavedProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_products')
    product = models.ForeignKey(Product_Listing, on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.user.username} saved {self.product.title}"
    
    def save(self, *args, **kwargs):
        print(f"Saving product {self.product.id} for user {self.user.id}")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        print(f"Deleting saved product {self.product.id} for user {self.user.id}")
        super().delete(*args, **kwargs)
    
class ProductReport(models.Model):
    REPORT_STATUS = [
        ('pending', 'Pending Review'),
        ('reviewing', 'Under Review'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    REPORT_REASONS = [
        ('spam', 'Spam or Misleading Content'),
        ('fraud', 'Fraudulent Listing'),
        ('inappropriate', 'Inappropriate Content'),
        ('expired', 'Expired or Sold Item'),
        ('other', 'Other Reason')
    ]
    
    product = models.ForeignKey('Product_Listing', on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=20, choices=REPORT_REASONS)
    details = models.TextField()
    reporter_email = models.EmailField(blank=True, null=True)
    reported_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=REPORT_STATUS, default='pending')
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-reported_at']
        
    def __str__(self):
        return f"Report for {self.product.title} - {self.get_reason_display()}"
        
    def mark_as_reviewed(self, admin_user, status='resolved', notes=None):
        self.status = status
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        if notes:
            self.resolution_notes = notes
        self.save()
        
class Banner(models.Model):
    # Simplified - only one banner type since they work the same way
    DISPLAY_LOCATIONS = [
        ('first', 'Homepage - First Position'),
        ('second', 'Homepage - Second Position'), 
        ('global', 'Global - Top of Pages'),
    ]

    # ONLY IMAGE FIELDS - removed title and subtitle
    image = models.ImageField(
        upload_to='banners/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
        help_text="Advertisement image: 1200x200px (desktop). All banner positions use same dimensions."
    )
    mobile_image = models.ImageField(
        upload_to='banners/mobile/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
        help_text="Mobile-optimized version: 800x200px. Same dimensions for all positions.",
        blank=True,
        null=True
    )
    url = models.URLField(help_text="Destination URL when banner is clicked")
    
    display_location = models.CharField(
        max_length=20, 
        choices=DISPLAY_LOCATIONS, 
        default='global'
    )
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=0, 
        help_text="Higher number means higher priority in display order"
    )
    start_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Optional: When to start showing this banner"
    )
    end_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Optional: When to stop showing this banner"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Optional background color (rarely needed for image-only banners)
    background_color = models.CharField(
        max_length=7, 
        blank=True, 
        null=True,
        help_text="Optional: Hex color code for banner background (e.g., #FF5733)"
    )

    class Meta:
        ordering = ['-priority', '-updated_at']
        indexes = [
            models.Index(fields=['is_active', 'display_location']),
            models.Index(fields=['priority', 'updated_at']),
        ]

    def __str__(self):
        return f"Banner #{self.id} - {self.get_display_location_display()}"

    @property
    def is_section_banner(self):
        """Check if this is a section banner (first/second position)"""
        return self.display_location in ['first', 'second']
    
    @property 
    def is_global_banner(self):
        """Check if this is a global banner"""
        return self.display_location == 'global'

    def get_alt_text(self):
        """Generate appropriate alt text for accessibility"""
        location_display = self.get_display_location_display()
        return f"Advertisement - {location_display}"

class Review(models.Model):
    REVIEW_TYPES = (
        ('product', 'Product Review'),
        ('seller', 'Seller Review'),
    )

    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    product = models.ForeignKey(Product_Listing, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    seller = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='seller_reviews', null=True, blank=True)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    review_type = models.CharField(max_length=10, choices=REVIEW_TYPES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['reviewer', 'product'],
                name='unique_product_review'
            ),
            models.UniqueConstraint(
                fields=['reviewer', 'seller'],
                name='unique_seller_review'
            )
        ]

    def __str__(self):
        return f"{self.reviewer.username}'s review - {self.rating} stars"

    def get_replies(self):
        return self.replies.all().select_related('reviewer')

class ReviewReply(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='replies')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='review_replies_given')
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reply to {self.review}'s review by {self.reviewer.username}"

    class Meta:
        verbose_name_plural = 'Review replies'
        
class AIDescriptionUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    count = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ('user', 'date')
        
    @classmethod
    def get_today_count(cls, user):
        today = timezone.now().date()
        usage, created = cls.objects.get_or_create(
            user=user, 
            date=today,
            defaults={'count': 0}
        )
        return usage.count
    
    @classmethod
    def increment_usage(cls, user):
        today = timezone.now().date()
        usage, created = cls.objects.get_or_create(
            user=user, 
            date=today,
            defaults={'count': 0}
        )
        usage.count += 1
        usage.save()
        return usage.count
