# Services/models.py - Updated with consistent simplified approach

import uuid
import os
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.urls import reverse
from django.db.models import Avg, Count, F, Q
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from User.models import Profile, Location, SavedItem, State, LGA


def service_image_path(instance, filename):
    """Generate upload path for service images"""
    service = instance.service
    return f'service_images/{service.provider.user.username}/{service.id}/{filename}'

def service_document_path(instance, filename):
    """Generate upload path for service documents"""
    return f'service_documents/{instance.service.provider.user.username}/{instance.service.id}/{filename}'

class ServiceListing(models.Model):
    """
    Simplified service listings with just 6 broad categories
    Clean, easy to understand, focused on what users actually need
    """
    
    # SIMPLIFIED: Just 6 service categories (not separate models)
    SERVICE_CATEGORIES = [
        ('technology', 'Technology & Digital'),
        ('creative', 'Creative & Design'),
        ('business', 'Business Services'),
        ('home', 'Home & Lifestyle'),
        ('health', 'Health & Beauty'),
        ('professional', 'Professional Services'),
    ]
    
    SERVICE_TYPES = [
        ('skill', 'Professional Skill'),
        ('service', 'Service Offering'),
        ('consultation', 'Consultation'),
        ('maintenance', 'Maintenance & Support'),
        ('training', 'Training/Teaching'),
    ]
    
    PRICING_TYPES = [
        ('fixed', 'Fixed Price'),
        ('hourly', 'Hourly Rate'),
        ('project', 'Per Project'),
        ('package', 'Package Deal'),
        ('negotiable', 'Negotiable'),
    ]
    
    EXPERIENCE_LEVELS = [
        ('beginner', 'Beginner (0-2 years)'),
        ('intermediate', 'Intermediate (3-5 years)'),
        ('experienced', 'Experienced (6-10 years)'),
        ('expert', 'Expert (10+ years)'),
    ]
    
    AVAILABILITY_TYPES = [
        ('full_time', 'Full Time Available'),
        ('part_time', 'Part Time Available'),
        ('weekends', 'Weekends Only'),
        ('flexible', 'Flexible Schedule'),
        ('by_appointment', 'By Appointment'),
    ]
    
    DELIVERY_METHODS = [
        ('remote', 'Remote/Online'),
        ('onsite', 'On-site'),
        ('both', 'Both Remote & On-site'),
        ('client_location', 'At Client Location'),
        ('my_location', 'At My Location'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, editable=False)
    provider = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='service_listings')
    title = models.CharField(max_length=255, help_text="Service/Skill title")
    description = models.TextField(help_text="Detailed description of your service/skill")
    
    # SIMPLIFIED CATEGORIZATION - Just 6 choices, no complex models
    category = models.CharField(max_length=20, choices=SERVICE_CATEGORIES, help_text="Main service category")
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES, default='skill')
    
    # Skills and Tools (simple text fields)
    skills_offered = models.TextField(blank=True, help_text="Main skills/services you offer (comma-separated)")
    tools_used = models.TextField(blank=True, help_text="Tools, software, or equipment you use")
    
    # Pricing Information
    pricing_type = models.CharField(max_length=20, choices=PRICING_TYPES, default='negotiable')
    base_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Base price (per hour/project/fixed)"
    )
    min_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Minimum price for negotiable services"
    )
    max_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Maximum price for negotiable services"
    )
    revision_limit = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Number of revisions included (0-10)"
    )
    delivery_days = models.PositiveIntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Expected delivery time in days"
    )
    
    # Professional Details
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVELS, default='intermediate')
    years_of_experience = models.PositiveIntegerField(null=True, blank=True, help_text="Years of experience")
    availability = models.CharField(max_length=20, choices=AVAILABILITY_TYPES, default='flexible')
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHODS, default='both')
    delivery_time = models.CharField(max_length=100, blank=True, help_text="e.g., '24 hours', '3-5 days'")
    languages = models.CharField(max_length=255, default='English', help_text="Languages you work in")
    
    # Service Details
    requirements = models.TextField(blank=True, help_text="What you need from clients")
    what_you_get = models.TextField(blank=True, help_text="What clients will receive")
    extra_services = models.TextField(blank=True, help_text="Additional services you can provide")
    
    # Professional Portfolio
    portfolio_url = models.URLField(blank=True, help_text="Link to your portfolio/website")
    certifications = models.TextField(blank=True, help_text="Relevant certifications or qualifications")
    
    # Communication
    contact_instructions = models.TextField(blank=True, help_text="How clients should contact you")
    
    # Location (same as products)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    serves_nationwide = models.BooleanField(default=True, help_text="Do you serve clients nationwide?")
    
    # Status and Management
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True, null=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='suspended_services'
    )
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    inquiry_count = models.PositiveIntegerField(default=0)
    hire_count = models.PositiveIntegerField(default=0)
    
    # Boost system (reuse existing from Account app)
    boost_score = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Combined score for sorting"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expiration_date = models.DateTimeField(null=True, blank=True)
    deletion_warning_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-is_featured', '-boost_score', '-created_at']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['provider', '-created_at']),
            models.Index(fields=['-boost_score', '-created_at']),
            models.Index(fields=['expiration_date', 'is_active']),
        ]
        verbose_name = 'Service Listing'
        verbose_name_plural = 'Service Listings'
    
    def __str__(self):
        return f"{self.title} - {self.provider.user.username}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Set expiration for new services
        if is_new and not self.expiration_date:
            try:
                # Pro users get 90 days, free users get 60 days
                if self.provider.user.account.effective_status.tier_type == 'pro':
                    self.expiration_date = timezone.now() + timedelta(days=90)
                    self.is_featured = True  # Auto-feature pro users
                else:
                    self.expiration_date = timezone.now() + timedelta(days=60)
            except:
                self.expiration_date = timezone.now() + timedelta(days=60)
        
        super().save(*args, **kwargs)
        
        # Update boost score
        calculated_score = self.calculate_boost_score()
        if self.boost_score != calculated_score:
            ServiceListing.objects.filter(pk=self.pk).update(boost_score=calculated_score)
            self.boost_score = calculated_score

        # Update provider stats on creation
        if is_new:
            Profile.objects.filter(id=self.provider.id).update(
                total_services_listed=F('total_services_listed') + 1
            )
            self.provider.refresh_from_db(fields=['total_services_listed'])
    
    def delete(self, *args, **kwargs):
        # Clean up files
        for image in self.images.all():
            image.delete()
        for document in self.documents.all():
            document.delete()
        
        service_path = f'service_images/{self.provider.user.username}/{self.id}/'
        if default_storage.exists(service_path):
            default_storage.delete(service_path)
        
        super().delete(*args, **kwargs)
    
    def get_skills_list(self):
        """Get skills as a list"""
        if self.skills_offered:
            return [skill.strip() for skill in self.skills_offered.split(',') if skill.strip()]
        return []
    
    def get_tools_list(self):
        """Get tools as a list"""
        if self.tools_used:
            return [tool.strip() for tool in self.tools_used.split(',') if tool.strip()]
        return []
    
    def increase_view_count(self):
        """Increase view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    @property
    def primary_image(self):
        """Get primary image"""
        return self.images.filter(is_primary=True).first() or self.images.first()
    
    @property
    def provider_is_verified_business(self):
        """Check if provider is verified business"""
        try:
            return self.provider.business_verification_status == 'verified'
        except AttributeError:
            return False
    
    @property
    def is_pro_provider(self):
        """Check if provider is pro user"""
        try:
            return self.provider.user.account.is_subscription_active
        except AttributeError:

            return False
    
    @property
    def average_rating(self):
        """Calculate average rating"""
        return self.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    
    @property
    def total_reviews(self):
        """Get total review count"""
        return self.reviews.count()
    
    @property
    def price_display(self):
        """Display price in user-friendly format"""
        if self.pricing_type == 'fixed' and self.base_price:
            return f"₦{self.base_price:,.0f}"
        elif self.pricing_type == 'hourly' and self.base_price:
            return f"₦{self.base_price:,.0f}/hour"
        elif self.pricing_type == 'project' and self.base_price:
            return f"Starting at ₦{self.base_price:,.0f}"
        elif self.pricing_type == 'package' and self.base_price:
            return f"From ₦{self.base_price:,.0f}"
        elif self.pricing_type == 'negotiable':
            if self.min_price and self.max_price:
                return f"₦{self.min_price:,.0f} - ₦{self.max_price:,.0f}"
            return "Negotiable"
        return "Contact for pricing"
    
    @property
    def category_display(self):
        """Get human-readable category name"""
        return dict(self.SERVICE_CATEGORIES).get(self.category, self.category)
    
    @property
    def is_expired(self):
        """Check if service has expired"""
        if not self.expiration_date:
            return False
        return timezone.now() > self.expiration_date
    
    @property
    def days_until_expiration(self):
        """Days until service expires"""
        if not self.expiration_date:
            return None
        delta = (self.expiration_date - timezone.now()).days
        return max(0, delta)
    
    def calculate_boost_score(self):
        """Calculate boost score for ranking"""
        score = 0
        
        # Pro user bonus
        try:
            if self.provider.user.account.effective_status.tier_type == 'pro':
                score += 50
        except AttributeError:
            # No Account app or user has no account
            pass
        
        # Verification bonus
        if self.provider_is_verified_business:
            score += 30
        
        # Experience bonus
        experience_scores = {
            'expert': 25,
            'experienced': 20,
            'intermediate': 15,
            'beginner': 10
        }
        score += experience_scores.get(self.experience_level, 0)
        
        # Portfolio bonus
        if self.portfolio_url:
            score += 15
        
        # Certification bonus
        if self.certifications:
            score += 10
        
        # Rating bonus
        avg_rating = self.average_rating
        if avg_rating > 0:
            score += (avg_rating * 8)  # Up to 40 points for 5-star rating
        
        # Activity bonus
        if self.created_at:
            days_old = (timezone.now() - self.created_at).days
            time_score = max(0, 15 - (days_old * 0.1))
            score += time_score
        
        # Popularity bonus
        if self.view_count > 0:
            score += min(20, self.view_count * 0.05)
        
        return score
    
    def get_absolute_url(self):
        return reverse('services:detail', kwargs={'pk': self.pk})
    
    def is_saved_by_user(self, user):
        """Check if service is saved by user"""
        if not user.is_authenticated:
            return False
        return SavedItem.objects.filter(user=user, service=self).exists()
    
    def send_deletion_warning(self):
        """Send deletion warning for expiring services"""
        if not self.deletion_warning_sent and self.days_until_expiration in [1, 3, 7]:
            try:
                from Notifications.models import create_notification, NotificationCategory, NotificationPriority
                create_notification(
                    user=self.provider.user,
                    title="Service Expiring Soon",
                    message=f'Your service "{self.title}" will expire in {self.days_until_expiration} day(s).',
                    category=NotificationCategory.ALERTS,
                    priority=NotificationPriority.HIGH,
                    content_object=self,
                    action_url=self.get_absolute_url(),
                    action_text="Renew Service"
                )
                self.deletion_warning_sent = True
                self.save(update_fields=['deletion_warning_sent'])
            except ImportError:
                pass
    
    def suspend(self, admin_user, reason=None):
        """Suspend the service"""
        self.is_suspended = True
        self.suspended_at = timezone.now()
        self.suspended_by = admin_user
        if reason:
            self.suspension_reason = reason
        self.save()
        
        # Notify the provider
        context = {
            'service': self,
            'reason': reason or 'Policy violation',
            'provider': self.provider
        }
        
        email_body = render_to_string('emails/service_suspended_email.html', context)
        
        try:
            send_mail(
                subject=f'Your service "{self.title}" has been suspended',
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.provider.user.email],
                html_message=email_body,
                fail_silently=True,
            )
        except Exception as e:
            import logging
            logging.error(f"Error sending suspension email: {e}")
    
    def unsuspend(self):
        """Unsuspend the service"""
        self.is_suspended = False
        self.save()
        
        # Notify the provider
        context = {
            'service': self,
            'provider': self.provider
        }
        
        email_body = render_to_string('emails/service_unsuspended_email.html', context)
        
        try:
            send_mail(
                subject=f'Your service "{self.title}" has been reinstated',
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.provider.user.email],
                html_message=email_body,
                fail_silently=True,
            )
        except Exception as e:
            import logging
            logging.error(f"Error sending unsuspension email: {e}")
    
    @classmethod
    def delete_expired_services(cls):
        """Delete expired services"""
        try:
            expired = cls.objects.filter(
                expiration_date__lte=timezone.now(),
                is_active=True
            )
            
            count = expired.count()
            
            for service in expired:
                try:
                    service.delete()
                except Exception:
                    pass
            
            return count
        except Exception as e:
            import logging
            logging.warning(f"Could not delete expired services: {e}")
            return 0

class ServiceImage(models.Model):
    """Service images (same pattern as Product_Image)"""
    service = models.ForeignKey(ServiceListing, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to=service_image_path)
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_primary', 'created_at']
    
    def __str__(self):
        return f"Image for {self.service.title}"
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            ServiceImage.objects.filter(
                service=self.service, 
                is_primary=True
            ).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        self.image.delete(save=False)
        super().delete(*args, **kwargs)

class ServiceDocument(models.Model):
    """Service documents like certificates, portfolios"""
    service = models.ForeignKey(ServiceListing, related_name='documents', on_delete=models.CASCADE)
    document = models.FileField(
        upload_to=service_document_path,
        validators=[FileExtensionValidator(['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'])]
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    document_type = models.CharField(max_length=50, choices=[
        ('certificate', 'Certificate'),
        ('portfolio', 'Portfolio Sample'),
        ('testimonial', 'Client Testimonial'),
        ('license', 'Professional License'),
        ('other', 'Other'),
    ], default='other')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['document_type', 'created_at']
    
    def __str__(self):
        return f"{self.title} - {self.service.title}"
    
    def delete(self, *args, **kwargs):
        self.document.delete(save=False)
        super().delete(*args, **kwargs)

class ServiceInquiry(models.Model):
    """Service inquiries (when someone wants to hire)"""
    
    INQUIRY_STATUS = [
        ('pending', 'Pending'),
        ('responded', 'Provider Responded'),
        ('negotiating', 'Negotiating'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, editable=False)
    service = models.ForeignKey(ServiceListing, on_delete=models.CASCADE, related_name='inquiries')
    client = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='service_inquiries')
    
    # Inquiry Details
    message = models.TextField(help_text="Describe your project/requirement")
    conversation = models.OneToOneField(
    'Messages.Conversation',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='service_inquiry')
    
    budget = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Your budget for this project"
    )
    timeline = models.CharField(max_length=255, blank=True, help_text="When do you need this completed?")
    requirements = models.TextField(blank=True, help_text="Specific requirements")
    
    # Contact Information
    contact_phone = models.CharField(max_length=15, blank=True)
    contact_email = models.EmailField(blank=True)
    preferred_contact = models.CharField(max_length=20, choices=[
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('whatsapp', 'WhatsApp'),
        ('platform', 'Through Platform'),
    ], default='platform')
    
    # Status and Response
    status = models.CharField(max_length=20, choices=INQUIRY_STATUS, default='pending')
    provider_response = models.TextField(blank=True)
    provider_quote = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True,
        blank=True,
        help_text="Provider's quoted price"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service', '-created_at']),
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"Inquiry for '{self.service.title}' by {self.client.user.username}"
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        
        if is_new:
            ServiceListing.objects.filter(id=self.service.id).update(
                inquiry_count=F('inquiry_count') + 1
            )
            
    
    @property
    def formatted_budget(self):
        """Format budget display"""
        if self.budget:
            return f"₦{self.budget:,.0f}"
        return "Budget not specified"
    
    @property
    def formatted_quote(self):
        """Format provider quote display"""
        if self.provider_quote:
            return f"₦{self.provider_quote:,.0f}"
        return "No quote provided"

class ServiceReview(models.Model):
    """Service reviews (same pattern as product reviews)"""
    service = models.ForeignKey(ServiceListing, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_reviews_given')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review_text = models.TextField()
    
    # Service-specific ratings
    communication_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        help_text="Rate communication"
    )
    quality_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        help_text="Rate work quality"
    )
    timeliness_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        help_text="Rate timeliness"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('service', 'reviewer')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.reviewer.username}'s review of {self.service.title} - {self.rating} stars"
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        
        # Send notification to service provider
        if is_new:
            try:
                from Notifications.models import create_notification, NotificationCategory
                create_notification(
                    user=self.service.provider.user,
                    title="New Service Review",
                    message=f'{self.reviewer.username} left a {self.rating}-star review for "{self.service.title}"',
                    category=NotificationCategory.REVIEW,
                    content_object=self,
                    action_url=self.service.get_absolute_url(),
                    action_text="View Review"
                )
            except ImportError:
                pass

class ServiceReviewReply(models.Model):
    """Replies to service reviews"""
    review = models.ForeignKey(ServiceReview, on_delete=models.CASCADE, related_name='replies')
    replier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_review_replies_given')
    reply_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reply to {self.review}'s review by {self.replier.username}"

    class Meta:
        verbose_name_plural = 'Service Review Replies'

# Utility functions for category management
def get_service_category_choices():
    """Get service categories for forms"""
    return ServiceListing.SERVICE_CATEGORIES

def get_services_by_category(category_slug):
    """Get active services by category"""
    return ServiceListing.objects.filter(
        category=category_slug,
        is_active=True,
        is_suspended=False
    ).order_by('-boost_score', '-created_at')

def get_category_stats():
    """Get statistics for all service categories"""
    stats = {}
    for category_key, category_name in ServiceListing.SERVICE_CATEGORIES:
        stats[category_key] = {
            'name': category_name,
            'total_services': ServiceListing.objects.filter(
                category=category_key, 
                is_active=True,
                is_suspended=False
            ).count(),
            'total_providers': ServiceListing.objects.filter(
                category=category_key,
                is_active=True,
                is_suspended=False
            ).values('provider').distinct().count()
        }
    return stats