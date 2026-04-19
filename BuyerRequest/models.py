import uuid
import os
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.db.models import Avg, Count, F, Q
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from User.models import Profile, Location, SavedItem, State, LGA, SavedItem
from Home.models import Category, Subcategory, Brand 
from django.contrib.contenttypes.models import ContentType
from Messages.models import Conversation

def buyer_request_image_path(instance, filename):
    """Generate upload path for buyer request images"""
    request = instance.buyer_request
    return f'buyer_requests/{request.buyer.user.username}/{request.id}/{filename}'

class BuyerRequest(models.Model):
    """
    Intelligent buyer request system that bridges products and services
    Users choose request type, then appropriate category system
    """
    
    REQUEST_TYPES = [
        ('product', 'Looking for a Product'),
        ('service', 'Looking for a Service'),
        ('both', 'Open to Both Products & Services'),
    ]
    
    # Service categories (matches Services app)
    SERVICE_CATEGORIES = [
        ('technology', 'Technology & Digital'),
        ('creative', 'Creative & Design'),
        ('business', 'Business Services'),
        ('home', 'Home & Lifestyle'),
        ('health', 'Health & Beauty'),
        ('professional', 'Professional Services'),
    ]
    
    URGENCY_CHOICES = [
        ('low', 'Low - I can wait'),
        ('medium', 'Medium - Within a week'),
        ('high', 'High - Within 3 days'),
        ('urgent', 'Urgent - ASAP'),
    ]
    
    CONDITION_CHOICES = [
        ('new', 'New Only'),
        ('used', 'Used Only'),
        ('any', 'Any Condition'),
        ('not_applicable', 'Not Applicable'),  # For services
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('fulfilled', 'Fulfilled'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    BUDGET_RANGE_CHOICES = [
        ('under_5k', 'Under ₦5,000'),
        ('5k_25k', '₦5,000 - ₦25,000'),
        ('25k_100k', '₦25,000 - ₦100,000'),
        ('100k_500k', '₦100,000 - ₦500,000'),
        ('500k_1m', '₦500,000 - ₦1,000,000'),
        ('1m_plus', 'Above ₦1,000,000'),
        ('custom', 'Custom Range'),
        ('negotiable', 'Negotiable'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, editable=False)
    buyer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='buyer_requests')
    title = models.CharField(max_length=255, help_text="What are you looking for?")
    description = models.TextField(help_text="Provide detailed information about what you need")
    request_type = models.CharField(max_length=10, choices=REQUEST_TYPES, default='product')
    
    # UNIFIED CATEGORY SYSTEM - Use single 'category' field for consistency with forms/views
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name='buyer_requests',
        null=True, 
        blank=True,
        help_text="Product category (for product requests)"
    )
    subcategory = models.ForeignKey(
        Subcategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='buyer_requests',
        help_text="Product subcategory (optional)"
    )
    brand = models.ForeignKey(
        Brand, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='buyer_requests',
        help_text="Preferred brand (for products)"
    )
    
    # For SERVICES (uses simple 6-category system)
    service_category = models.CharField(
        max_length=20,
        choices=SERVICE_CATEGORIES,
        null=True, 
        blank=True,
        help_text="Select if looking for a service"
    )
    
    # Budget Information
    budget_range = models.CharField(max_length=20, choices=BUDGET_RANGE_CHOICES, default='negotiable')
    budget_min = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Minimum budget"
    )
    budget_max = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Maximum budget"
    )
    
    # Requirements (adaptable for both products and services)
    preferred_condition = models.CharField(max_length=15, choices=CONDITION_CHOICES, default='any')
    urgency = models.CharField(max_length=10, choices=URGENCY_CHOICES, default='medium')
    needed_by = models.DateTimeField(null=True, blank=True, help_text="When do you need this?")
    quantity_needed = models.PositiveIntegerField(default=1, help_text="Quantity needed (for products)")
    
    # Service-specific requirements
    project_duration = models.CharField(max_length=100, blank=True, help_text="Expected project duration (for services)")
    skill_level_required = models.CharField(max_length=20, choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('experienced', 'Experienced'),
        ('expert', 'Expert'),
        ('any', 'Any Level'),
    ], default='any', help_text="Required skill level (for services)")
    delivery_preference = models.CharField(max_length=20, choices=[
        ('remote', 'Remote/Online'),
        ('onsite', 'On-site'),
        ('both', 'Either'),
        ('no_preference', 'No Preference'),
    ], default='no_preference', help_text="Delivery preference (for services)")
    
    # Location
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    accept_nationwide = models.BooleanField(default=True, help_text="Accept responses from anywhere in Nigeria")
    
    # Contact Information
    show_phone = models.BooleanField(default=False, help_text="Show your phone number to responders")
    contact_instructions = models.TextField(blank=True, help_text="Additional contact instructions")
    
    # Status and Management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_featured = models.BooleanField(default=False, help_text="Featured request")
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True, null=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='suspended_requests'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    last_bumped = models.DateTimeField(null=True, blank=True)
    deletion_warning_sent = models.BooleanField(default=False)
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    response_count = models.PositiveIntegerField(default=0)
    contact_count = models.PositiveIntegerField(default=0)
    
    # Boost system (same as products/services)
    boost_score = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Combined score for sorting (boost + pro status)"
    )
    
    class Meta:
        ordering = ['-is_featured', '-boost_score', '-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['service_category', 'status']),
            models.Index(fields=['buyer', '-created_at']),
            models.Index(fields=['expires_at', 'status']),
            models.Index(fields=['is_featured', '-boost_score']),
            models.Index(fields=['request_type', 'status']),
        ]
        verbose_name = 'Buyer Request'
        verbose_name_plural = 'Buyer Requests'
    
    def __str__(self):
        return f"{self.title} - {self.buyer.user.username}"
    
    def clean(self):
        """Validate that appropriate categories are selected based on request type"""
        from django.core.exceptions import ValidationError
        
        if self.request_type == 'product':
            if not self.category:
                raise ValidationError("Product category is required for product requests")
        elif self.request_type == 'service':
            if not self.service_category:
                raise ValidationError("Service category is required for service requests")
        elif self.request_type == 'both':
            if not self.category and not self.service_category:
                raise ValidationError("At least one category is required")
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Set expiration date if new
        if is_new and not self.expires_at:
            try:
                # Pro users get 90 days, free users get 45 days
                if self.buyer.user.account.effective_status.tier_type == 'pro':
                    days = 90
                    self.is_featured = True  # Auto-feature for Pro users
                else:
                    days = 45
            except:
                days = 45
            self.expires_at = timezone.now() + timedelta(days=days)
        
        super().save(*args, **kwargs)
        
        # Update boost score
        calculated_score = self.calculate_boost_score()
        if self.boost_score != calculated_score:
            BuyerRequest.objects.filter(pk=self.pk).update(boost_score=calculated_score)
            self.boost_score = calculated_score

        # Update buyer stats on creation
        if is_new:
            Profile.objects.filter(id=self.buyer.id).update(
                total_requests_posted=F('total_requests_posted') + 1
            )
            self.buyer.refresh_from_db(fields=['total_requests_posted'])
    
    def delete(self, *args, **kwargs):
        # Clean up images and conversations
        for image in self.images.all():
            image.delete()
        
        
        content_type = ContentType.objects.get_for_model(self.__class__)
        for conversation in Conversation.objects.filter(content_type=content_type, object_id=str(self.id)):
            conversation.delete()
        
        request_path = f'buyer_requests/{self.buyer.user.username}/{self.id}/'
        if default_storage.exists(request_path):
            default_storage.delete(request_path)
        
        super().delete(*args, **kwargs)
    
    @property
    def primary_category(self):
        """Get the primary category for this request"""
        if self.request_type == 'product':
            return self.category
        elif self.request_type == 'service':
            return dict(self.SERVICE_CATEGORIES).get(self.service_category)
        else:  # both
            return self.category or dict(self.SERVICE_CATEGORIES).get(self.service_category)
    
    @property
    def category_type(self):
        """Get the type of category (product or service)"""
        if self.category and not self.service_category:
            return 'product'
        elif self.service_category and not self.category:
            return 'service'
        else:
            return 'both'
    
    def increase_view_count(self):
        """Increase view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    @property
    def primary_image(self):
        """Get primary image"""
        return self.images.filter(is_primary=True).first() or self.images.first()
    
    def calculate_boost_score(self):
        """Calculate boost score for ranking"""
        score = 0
        
        # Base score for pro users
        try:
            if self.buyer.user.account.effective_status.tier_type == 'pro':
                score += 50
        except:
            pass
        
        # Verification bonus
        try:
            if self.buyer.business_verification_status == 'verified':
                score += 30
        except:
            pass
        
        # Urgency bonus
        urgency_scores = {
            'urgent': 30,
            'high': 25,
            'medium': 15,
            'low': 5
        }
        score += urgency_scores.get(self.urgency, 0)
        
        # Budget bonus (higher budget = higher score)
        if self.budget_max:
            if self.budget_max >= 1000000:  # 1M+
                score += 25
            elif self.budget_max >= 500000:  # 500K+
                score += 20
            elif self.budget_max >= 100000:  # 100K+
                score += 15
            elif self.budget_max >= 25000:   # 25K+
                score += 10
            else:
                score += 5
        
        # Request type bonus (services typically get slight boost as they're often higher value)
        if self.request_type == 'service':
            score += 10
        elif self.request_type == 'both':
            score += 15  # Both types get highest boost as they're most flexible
        
        # Activity bonus (time-based)
        if self.created_at:
            days_old = (timezone.now() - self.created_at).days
            time_score = max(0, 20 - (days_old * 0.3))  # Requests decay faster than listings
            score += time_score
        
        # Response bonus (popular requests)
        if self.response_count > 0:
            score += min(25, self.response_count * 3)  # Up to 25 points
        
        # Bump bonus
        if self.last_bumped:
            hours_since_bump = (timezone.now() - self.last_bumped).total_seconds() / 3600
            if hours_since_bump < 24:  # Recent bump
                score += (24 - hours_since_bump) / 2  # Up to 12 points
        
        return score
    
    @property
    def is_active(self):
        """Check if request is active"""
        return self.status == 'active' and self.expires_at > timezone.now() and not self.is_suspended
    
    @property
    def is_expired(self):
        """Check if request has expired"""
        return timezone.now() > self.expires_at
    
    @property
    def days_remaining(self):
        """Get days remaining before expiration"""
        if self.is_expired:
            return 0
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)
    
    @property
    def urgency_color(self):
        """Return color class based on urgency"""
        colors = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
            'urgent': 'danger'
        }
        return colors.get(self.urgency, 'secondary')
    
    @property
    def budget_display(self):
        """Display budget in user-friendly format"""
        if self.budget_range == 'custom' and self.budget_min and self.budget_max:
            if self.budget_min == self.budget_max:
                return f"₦{self.budget_min:,.0f}"
            return f"₦{self.budget_min:,.0f} - ₦{self.budget_max:,.0f}"
        
        budget_map = {
            'under_5k': 'Under ₦5,000',
            '5k_25k': '₦5,000 - ₦25,000',
            '25k_100k': '₦25,000 - ₦100,000',
            '100k_500k': '₦100,000 - ₦500,000',
            '500k_1m': '₦500,000 - ₦1,000,000',
            '1m_plus': 'Above ₦1,000,000',
            'negotiable': 'Negotiable'
        }
        return budget_map.get(self.budget_range, 'Not specified')
    
    @property
    def buyer_is_verified_business(self):
        """Check if buyer is verified business"""
        try:
            return self.buyer.business_verification_status == 'verified'
        except AttributeError:
            return False
    
    @property
    def is_pro_buyer(self):
        """Check if buyer is pro user"""
        try:
            return self.buyer.user.account.is_subscription_active
        except:
            return False
    
    def can_be_viewed_by(self, user):
        """Check if request can be viewed by user"""
        if self.is_suspended and not (user.is_staff or user.is_superuser):
            return False
        return self.is_active or (user.is_authenticated and user.profile == self.buyer)
    
    def can_be_contacted_by(self, user):
        """Check if user can contact/respond to this request"""
        if not user.is_authenticated:
            return False
        
        # Owner cannot respond to own request
        if user.profile == self.buyer:
            return False
        
        # Check if request is active
        if not self.is_active:
            return False
        
        # Check if user already responded
        if SellerResponse.objects.filter(buyer_request=self, seller=user.profile).exists():
            return False
        
        return True
    
    def get_absolute_url(self):
        return reverse('buyer_requests:detail', kwargs={'pk': self.pk})
    
    def is_saved_by_user(self, user):
        """Check if request is saved by user"""
        if not user.is_authenticated:
            return False
        return SavedItem.objects.filter(user=user, request=self).exists()
    
    def can_be_bumped(self):
        """Check if request can be bumped (24-hour cooldown)"""
        if not self.last_bumped:
            return True
        return timezone.now() - self.last_bumped >= timedelta(hours=24)
    
    def bump_request(self):
        """Bump request to top of listings"""
        if self.can_be_bumped():
            self.last_bumped = timezone.now()
            self.save(update_fields=['last_bumped'])
            return True
        return False
    
    def suspend(self, admin_user, reason):
        """Suspend this request"""
        self.is_suspended = True
        self.suspension_reason = reason
        self.suspended_at = timezone.now()
        self.suspended_by = admin_user
        self.save(update_fields=['is_suspended', 'suspension_reason', 'suspended_at', 'suspended_by'])
    
    def unsuspend(self):
        """Unsuspend this request"""
        self.is_suspended = False
        self.suspension_reason = ""
        self.suspended_at = None
        self.suspended_by = None
        self.save(update_fields=['is_suspended', 'suspension_reason', 'suspended_at', 'suspended_by'])
    
    @classmethod
    def delete_expired_requests(cls):
        """Delete expired requests"""
        try:
            expired = cls.objects.filter(
                expires_at__lte=timezone.now(),
                status__in=['active', 'paused']
            )
            
            count = expired.count()
            
            for request in expired:
                try:
                    request.delete()
                except Exception:
                    pass
            
            return count
        except Exception as e:
            import logging
            logging.warning(f"Could not delete expired requests: {e}")
            return 0

class BuyerRequestImage(models.Model):
    """Request images (same pattern as Product_Image)"""
    
    buyer_request = models.ForeignKey(BuyerRequest, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to=buyer_request_image_path)
    is_primary = models.BooleanField(default=False)
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_primary', 'created_at']
    
    def __str__(self):
        return f"Image for {self.buyer_request.title}"
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            BuyerRequestImage.objects.filter(
                buyer_request=self.buyer_request, 
                is_primary=True
            ).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        self.image.delete(save=False)
        super().delete(*args, **kwargs)

class SellerResponse(models.Model):
    """
    Unified seller responses to buyer requests
    Can link to existing products OR services, or offer custom solutions
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('viewed', 'Viewed by Buyer'),
        ('interested', 'Buyer Interested'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('completed', 'Completed'),
    ]
    
    RESPONSE_TYPE_CHOICES = [
        ('existing_product', 'I have a product that matches'),
        ('existing_service', 'I offer a service that matches'),
        ('custom_product', 'I can source/create this product'),
        ('custom_service', 'I can provide this service'),
        ('hybrid', 'I can provide both product & service'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, editable=False)
    buyer_request = models.ForeignKey(BuyerRequest, on_delete=models.CASCADE, related_name='responses')
    seller = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='seller_responses')
    
    # Response Type and Links
    response_type = models.CharField(max_length=20, choices=RESPONSE_TYPE_CHOICES, default='custom_product')
    conversation = models.OneToOneField(
    'Messages.Conversation',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='seller_response')
    
    # Link to existing product (if responding with existing product)
    related_product = models.ForeignKey(
        'Home.Product_Listing', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='buyer_request_responses',
        help_text="Link to your existing product"
    )
    
    # Link to existing service (if responding with existing service)
    related_service = models.ForeignKey(
        'Services.ServiceListing', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='buyer_request_responses',
        help_text="Link to your existing service"
    )
    
    # Response Details
    message = models.TextField(help_text="Describe how you can help with this request")
    offered_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Your offered price"
    )
    
    # Product-specific details
    condition_offered = models.CharField(max_length=15, choices=BuyerRequest.CONDITION_CHOICES, blank=True)
    quantity_available = models.PositiveIntegerField(null=True, blank=True, help_text="Quantity available")
    
    # Service-specific details
    delivery_time = models.CharField(max_length=100, blank=True, help_text="Delivery/completion time")
    service_includes = models.TextField(blank=True, help_text="What's included in the service")
    
    # General details
    availability = models.CharField(max_length=255, blank=True, help_text="When can you deliver/provide this?")
    additional_info = models.TextField(blank=True, help_text="Any additional information")
    
    # Contact Information
    contact_phone = models.CharField(max_length=15, blank=True)
    contact_email = models.EmailField(blank=True)
    preferred_contact = models.CharField(max_length=20, choices=[
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('whatsapp', 'WhatsApp'),
        ('platform', 'Through Platform'),
    ], default='platform')
    
    # Status and Timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Quality Indicators
    is_verified_seller = models.BooleanField(default=False)
    is_featured_response = models.BooleanField(default=False)
    
    # Response score for sorting
    response_score = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Response quality score"
    )
    
    class Meta:
        ordering = ['-is_featured_response', '-response_score', '-created_at']
        indexes = [
            models.Index(fields=['buyer_request', '-created_at']),
            models.Index(fields=['seller', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['-is_featured_response', '-response_score']),
            models.Index(fields=['response_type']),
        ]
    
    def __str__(self):
        return f"Response to '{self.buyer_request.title}' by {self.seller.user.username}"
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        
        # Set verified seller status
        try:
            self.is_verified_seller = (
                self.seller.business_verification_status == 'verified' or
                self.seller.user.account.effective_status.tier_type == 'pro'
            )
            
            # Feature response for Pro sellers
            if self.seller.user.account.effective_status.tier_type == 'pro':
                self.is_featured_response = True
        except:
            pass
        
        # Calculate response score
        self.response_score = self.calculate_response_score()
        
        super().save(*args, **kwargs)
        
        # Update response count on buyer request
        if is_new:
            BuyerRequest.objects.filter(id=self.buyer_request.id).update(
                response_count=F('response_count') + 1
            )
            
    
    def calculate_response_score(self):
        """Calculate response quality score"""
        score = 0
        
        # Verification bonus
        if self.is_verified_seller:
            score += 50
        
        # Pro user bonus
        try:
            if self.seller.user.account.effective_status.tier_type == 'pro':
                score += 30
        except:
            pass
        
        # Response type bonus (existing items score higher than custom)
        type_scores = {
            'existing_product': 30,
            'existing_service': 30,
            'custom_product': 20,
            'custom_service': 20,
            'hybrid': 40,  # Highest as it offers both
        }
        score += type_scores.get(self.response_type, 15)
        
        # Response quality factors
        if self.offered_price:
            score += 15  # Has pricing
        
        if self.availability:
            score += 10  # Has availability info
        
        if len(self.message) > 100:
            score += 15  # Detailed message
        
        if self.contact_phone or self.contact_email:
            score += 10  # Contact info provided
        
        if self.delivery_time:
            score += 10  # Has delivery info
        
        # Link to existing item bonus
        if self.related_product or self.related_service:
            score += 25
        
        # Seller rating bonus
        try:
            seller_rating = self.seller.combined_rating
            if seller_rating >= 4.5:
                score += 25
            elif seller_rating >= 4.0:
                score += 15
        except:
            pass
        
        return score
    
    @property
    def formatted_price(self):
        """Format price display"""
        if self.offered_price:
            return f"₦{self.offered_price:,.0f}"
        return "Price on request"
    
    @property
    def seller_is_verified_business(self):
        """Check if seller is verified business"""
        try:
            return self.seller.business_verification_status == 'verified'
        except AttributeError:
            return False
    
    @property
    def related_item_url(self):
        """Get URL for related product or service"""
        if self.related_product:
            return self.related_product.get_absolute_url()
        elif self.related_service:
            return self.related_service.get_absolute_url()
        return None
    
    @property
    def related_item_title(self):
        """Get title of related product or service"""
        if self.related_product:
            return self.related_product.title
        elif self.related_service:
            return self.related_service.title
        return None

class RequestAccess(models.Model):
    """Track user access to requests for daily limits (following existing access pattern)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='request_accesses')
    request = models.ForeignKey(BuyerRequest, on_delete=models.CASCADE, related_name='accesses')
    accessed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        unique_together = ('user', 'request')
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['user', '-accessed_at']),
            models.Index(fields=['request', '-accessed_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} accessed {self.request.title}"
    
    @classmethod
    def can_access_request(cls, user, request_obj):
        """Check if user can access request (pro users unlimited, free users limited)"""
        if not user.is_authenticated:
            return True, "anonymous"
        
        # Pro users have unlimited access
        try:
            if user.account.effective_status.tier_type == 'pro':
                return True, "pro_unlimited"
        except:
            pass
        
        # Check daily limit for free users
        today = timezone.now().date()
        daily_count = cls.get_daily_access_count(user, today)
        
        # Free users get 5 requests per day
        if daily_count >= 5:
            return False, "daily_limit_exceeded"
        
        return True, "within_limit"
    
    @classmethod
    def record_access(cls, user, request_obj, ip_address=None):
        """Record access and increment view count"""
        access, created = cls.objects.get_or_create(
            user=user,
            request=request_obj,
            defaults={'ip_address': ip_address}
        )
        
        # Always increment view count (even for repeated views)
        BuyerRequest.objects.filter(id=request_obj.id).update(
            view_count=F('view_count') + 1
        )
        
        return access, created
    
    @classmethod
    def get_daily_access_count(cls, user, date=None):
        """Get user's daily access count"""
        if date is None:
            date = timezone.now().date()
        
        return cls.objects.filter(
            user=user,
            accessed_at__date=date
        ).count()

# Utility functions for category management and suggestions
def get_request_suggestions_for_user(user, limit=5):
    """Get suggested requests based on user's activity"""
    suggestions = []
    
    try:
        # Get user's product categories
        user_product_categories = user.profile.seller_listings.values_list('category', flat=True)
        
        # Get user's service categories  
        user_service_categories = user.profile.service_listings.values_list('category', flat=True)
        
        # Find requests in those categories
        product_requests = BuyerRequest.objects.filter(
            product_category__in=user_product_categories,
            status='active',
            is_suspended=False
        )[:limit//2]
        
        service_requests = BuyerRequest.objects.filter(
            service_category__in=user_service_categories,
            status='active', 
            is_suspended=False
        )[:limit//2]
        
        suggestions.extend(product_requests)
        suggestions.extend(service_requests)
        
    except AttributeError:
        pass
    
    return suggestions[:limit]

def get_smart_category_suggestions(request_description):
    """AI-powered category suggestions based on request description"""
    # This could be enhanced with actual AI/ML later
    # For now, simple keyword matching
    
    description_lower = request_description.lower()
    
    # Product category suggestions
    product_keywords = {
        'phone': 'Smartphones and Tablets',
        'laptop': 'Electronics', 
        'furniture': 'Home Appliances & Furnitures',
        'car': 'Vehicles',
        'makeup': 'Health & Beauty',
        'solar': 'Solar & Renewable Energy',
    }
    
    # Service category suggestions
    service_keywords = {
        'website': 'technology',
        'design': 'creative',
        'logo': 'creative',
        'accounting': 'business',
        'cleaning': 'home',
        'repair': 'home',
        'fitness': 'health',
        'legal': 'professional',
    }
    
    suggestions = {'product': None, 'service': None}
    
    for keyword, category in product_keywords.items():
        if keyword in description_lower:
            suggestions['product'] = category
            break
    
    for keyword, category in service_keywords.items():
        if keyword in description_lower:
            suggestions['service'] = category
            break
    
    return suggestions