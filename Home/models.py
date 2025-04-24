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
from mptt.models import MPTTModel, TreeForeignKey

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
        ('standard', 'Standard Listing (7 days)'),
        ('premium', 'Premium Listing (30 days)'),
        ('emergency', 'Emergency Sale (3 days)'),
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

    def increase_view_count(self):
        self.view_count += 1
        self.save()
    
    def primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()

    def __str__(self):
        return self.title
    
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
        
    def reset_expiration(self):
        """Reset the expiration date based on listing type"""
        if self.listing_type == 'permanent':
            self.expiration_date = None
        else:
            duration = {
                'standard': 7,
                'premium': 30,
                'emergency': 3,
            }.get(self.listing_type, 7)
            
            self.expiration_date = timezone.now() + timedelta(days=duration)
            self.deletion_warning_sent = False
        self.save()

    def save(self, *args, **kwargs):
        if self.pk:  # Only for existing instances
            try:
                original = Product_Listing.objects.get(pk=self.pk)
         
                # Reset expiration date if listing type changes
                if original.listing_type != self.listing_type:
                    self.deletion_warning_sent = False
                    if self.listing_type == 'permanent':
                        self.expiration_date = None
                    else:
                        duration = {
                            'standard': 7,
                            'premium': 30,
                            'emergency': 3
                        }.get(self.listing_type, 7)
                        self.expiration_date = timezone.now() + timedelta(days=duration)
                
                # Reset expiration on significant updates
                elif self.listing_type != 'permanent':
                    significant_fields = ['title', 'description', 'price', 'quantity']
                    if any(getattr(original, field) != getattr(self, field) for field in significant_fields):
                        duration = {
                            'standard': 7,
                            'premium': 30,
                            'emergency': 3
                        }.get(self.listing_type, 7)
                        self.expiration_date = timezone.now() + timedelta(days=duration)
                        self.deletion_warning_sent = False
                        
            except Product_Listing.DoesNotExist:
                pass
        else:  # New instance
            if self.listing_type != 'permanent':
                duration = {
                    'standard': 7,
                    'premium': 30,
                    'emergency': 3
                }.get(self.listing_type, 7)
                self.expiration_date = timezone.now() + timedelta(days=duration)
                print(f"Setting expiration date to: {self.expiration_date}")  # Debug line

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Delete all images first
        for image in self.images.all():
            image.delete()
        
        # Delete the product's image directory if it exists
        product_path = f'product_images/{self.seller.user.username}/{self.title}/'
        if default_storage.exists(product_path):
            default_storage.delete(product_path)
        
        super().delete(*args, **kwargs)

    def send_deletion_warning(self):
        if not self.deletion_warning_sent and self.days_until_deletion in [1, 3]:
            # Send notification logic here
            self.deletion_warning_sent = True
            self.save()
            
            
    @classmethod
    def delete_expired_listings(cls):
        """Delete all expired listings regardless of user status"""
        from django.db import ProgrammingError, OperationalError, connection
        
        try:
            # First check if we can connect to the database
            connection.ensure_connection()
            
            # Then proceed with deletion
            expired = cls.objects.filter(
                expiration_date__lte=timezone.now(),
                listing_type__in=['standard', 'premium', 'emergency']
            )
            count = expired.count()
            expired.delete()
            return count
        except ProgrammingError:
            # Handle case when table doesn't exist yet
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
        """Return active boosts for this product"""
        return self.boosts.filter(is_active=True, end_date__gt=timezone.now()).first()
    
    def can_be_boosted(self, user):
        """Check if user can boost this product"""
        if not user.is_authenticated:
            return False
        return self.seller.user == user and user.account.balance > 0
        
class Product_Image(models.Model):
    product = models.ForeignKey(Product_Listing, related_name='images', on_delete=models.CASCADE)
    image = ProcessedImageField(
        upload_to=user_listing_path,
        processors=[ResizeToFit(800, 600)],  # Main image size
        format='JPEG',
        options={'quality': 85}
    )
    # Auto-generated thumbnail
    thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFill(200, 200)],  # Square thumbnail
        format='JPEG',
        options={'quality': 80}
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
    
class Banner(models.Model):
    BANNER_TYPES = [
        ('hero', 'Hero Banner'),
        ('promotional', 'Promotional Banner'),
        ('announcement', 'Announcement Banner'),
    ]
    
    DISPLAY_LOCATIONS = [
        ('home_top', 'Home Page Top'),
        ('home_middle', 'Home Page Middle'),
        ('category', 'Category Pages'),
        ('global', 'Global'),
    ]

    title = models.CharField(max_length=100, default="Advertisement Banner")  # Added default
    subtitle = models.CharField(max_length=200, blank=True, null=True)  # Made nullable
    image = models.ImageField(
        upload_to='banners/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])]
    )
    mobile_image = models.ImageField(
        upload_to='banners/mobile/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
        help_text="Optimized image for mobile devices",
        blank=True,
        null=True  # Made nullable
    )
    url = models.URLField()
    banner_type = models.CharField(
        max_length=20, 
        choices=BANNER_TYPES, 
        default='promotional'
    )
    display_location = models.CharField(
        max_length=20, 
        choices=DISPLAY_LOCATIONS, 
        default='home_top'
    )
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, help_text="Higher number means higher priority")
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-updated_at']
        indexes = [
            models.Index(fields=['is_active', 'display_location']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Set default title if none provided
        if not self.title:
            self.title = f"Advertisement Banner {Banner.objects.count() + 1}"
        super().save(*args, **kwargs)

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