from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .utils import user_directory_path
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill
from django.db import models
from django.utils.crypto import get_random_string
from django.urls import reverse
from django.db.models import Avg
import random


# Create your models here.
class State(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']

class LGA(models.Model):
    name = models.CharField(max_length=100)
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='lgas')  # Removed trailing comma
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name}, {self.state.name}"
    
    class Meta:
        ordering = ['name']
        unique_together = ['name', 'state']

class Location(models.Model):
    address = models.CharField(max_length=120, blank=True, null=True)
    address_2 = models.CharField(max_length=120, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)  # New field
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    lga = models.ForeignKey(LGA, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        location_parts = []
        if self.address:
            location_parts.append(self.address)
        if self.city:
            location_parts.append(self.city)
        if self.lga:
            location_parts.append(self.lga.name)
        if self.state:
            location_parts.append(self.state.name)
        
        if location_parts:
            return ', '.join(filter(None, location_parts))
        return "No location details provided" # Fallback for empty locations

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    photo = ProcessedImageField(
        upload_to=user_directory_path,
        processors=[ResizeToFill(200, 200)], 
        format='JPEG',
        options={'quality': 85},
        null=True
    )
    bio = models.CharField(max_length=225, blank=True)
    phone_number = models.CharField(max_length=11, blank=True)
    location = models.OneToOneField(
        Location, on_delete=models.SET_NULL, null=True
    )
    email_verified = models.BooleanField(default=False)
    email_otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    total_products_listed = models.PositiveIntegerField(default=0)
    
    # Business Verification Fields
    business_name = models.CharField(max_length=255, blank=True, null=True)
    business_registration_number = models.CharField(max_length=100, blank=True, null=True)
    business_type = models.CharField(
        max_length=50, 
        choices=[
            ('sole_proprietorship', 'Sole Proprietorship'),
            ('partnership', 'Partnership'),
            ('limited_liability', 'Limited Liability Company'),
            ('corporation', 'Corporation'),
            ('cooperative', 'Cooperative Society'),
            ('ngo', 'Non-Governmental Organization'),
            ('other', 'Other'),
        ],
        blank=True, null=True
    )
    business_verification_status = models.CharField(
        max_length=20,
        choices=[
            ('unverified', 'Unverified'),
            ('pending', 'Pending Review'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
            ('suspended', 'Suspended'),
        ],
        default='unverified'
    )
    business_verified_at = models.DateTimeField(null=True, blank=True)
    business_verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_businesses'
    )
    business_description = models.TextField(blank=True, null=True, max_length=1000)
    business_website = models.URLField(blank=True, null=True)
    business_email = models.EmailField(blank=True, null=True)
    business_phone = models.CharField(max_length=15, blank=True, null=True)
    business_address_visible = models.BooleanField(default=True)
    
    # Additional verification fields
    business_rejection_reason = models.TextField(blank=True, null=True)
    business_verification_notes = models.TextField(blank=True, null=True)
    business_last_verification_attempt = models.DateTimeField(null=True, blank=True)
    
    # Business privileges and features
    permanent_listing_enabled = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    featured_store = models.BooleanField(default=False)
    
    # TODO: Uncomment when Services app is ready
    # total_services_listed = models.PositiveIntegerField(default=0, help_text="Total services ever listed")
    # total_service_inquiries = models.PositiveIntegerField(default=0, help_text="Total service inquiries received")
    # service_provider_rating = models.DecimalField(
    #     max_digits=3, 
    #     decimal_places=2, 
    #     default=0.0,
    #     help_text="Average rating as service provider"
    # )
    # total_service_reviews = models.PositiveIntegerField(default=0, help_text="Total reviews as service provider")
    
    # TODO: Uncomment when BuyerRequest app is ready
    # # Buyer request statistics  
    # total_requests_posted = models.PositiveIntegerField(default=0, help_text="Total buyer requests posted")
    # buyer_rating = models.DecimalField(
    #     max_digits=3, 
    #     decimal_places=2, 
    #     default=0.0,
    #     help_text="Average rating as buyer"
    # )
    # total_buyer_reviews = models.PositiveIntegerField(default=0, help_text="Total reviews as buyer")
    
    # TODO: Uncomment when Services app is ready
    # # Professional information for service providers
    # professional_title = models.CharField(
    #     max_length=100, 
    #     blank=True,
    #     help_text="Professional title (e.g., 'Graphic Designer', 'Web Developer')"
    # )
    # skills = models.TextField(
    #     blank=True,
    #     help_text="List of skills separated by commas"
    # )
    # years_of_experience = models.PositiveIntegerField(
    #     null=True, 
    #     blank=True,
    #     help_text="Years of professional experience"
    # )
    
    # # Service availability
    # available_for_services = models.BooleanField(
    #     default=False,
    #     help_text="Available to provide services"
    # )
    # service_availability_note = models.CharField(
    #     max_length=255,
    #     blank=True,
    #     help_text="Brief note about your availability"
    # )
    
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    @property
    def is_verified_business(self):
        """Check if the user is a verified business"""
        return self.business_verification_status == 'verified'
    
    @property
    def has_pending_verification(self):
        """Check if the user has a pending verification request"""
        return self.business_verification_status == 'pending'
    
    @property
    def is_business_profile(self):
        """Check if this is a business profile (has business info)"""
        return bool(self.business_name and self.business_type)
    
    @property
    def can_create_permanent_listing(self):
        """Check if user can create permanent listings"""
        return self.is_verified_business and self.permanent_listing_enabled
    
    @property
    def business_display_name(self):
        """Get the business display name or username"""
        if self.is_verified_business and self.business_name:
            return self.business_name
        return self.user.username
    
    @property
    def verification_status_display(self):
        """Get human-readable verification status"""
        status_map = {
            'unverified': 'Not Verified',
            'pending': 'Verification Pending',
            'verified': 'Verified Business',
            'rejected': 'Verification Rejected',
            'suspended': 'Verification Suspended'
        }
        return status_map.get(self.business_verification_status, 'Unknown')
    
    # TODO: Uncomment when Services app is ready
    # @property
    # def service_provider_average_rating(self):
    #     """Get average rating as service provider"""
    #     try:
    #         from Services.models import ServiceReview
    #         reviews = ServiceReview.objects.filter(service__provider=self)
    #         if reviews.exists():
    #             avg_rating = reviews.aggregate(avg_rating=models.Avg('rating'))['avg_rating']
    #             return round(avg_rating, 1) if avg_rating else 0
    #         return 0
    #     except ImportError:
    #         return 0
    
    # @property
    # def combined_rating(self):
    #     """Get combined rating from products and services"""
    #     product_rating = self.seller_average_rating
    #     service_rating = self.service_provider_average_rating
    #     product_count = self.total_seller_reviews
    #     service_count = self.total_service_reviews
        
    #     if product_count + service_count == 0:
    #         return 0
        
    #     total_rating = (product_rating * product_count) + (service_rating * service_count)
    #     return round(total_rating / (product_count + service_count), 1)
    
    # @property
    # def is_verified_provider(self):
    #     """Check if user is a verified provider (business or high-rated)"""
    #     return (
    #         self.business_verification_status == 'verified' or
    #         (self.combined_rating >= 4.5 and (self.total_seller_reviews + self.total_service_reviews) >= 10)
    #     )
    
    # @property
    # def provider_badge(self):
    #     """Get provider badge based on performance"""
    #     total_reviews = self.total_seller_reviews + self.total_service_reviews
    #     avg_rating = self.combined_rating
        
    #     if self.business_verification_status == 'verified':
    #         return 'verified_business'
    #     elif avg_rating >= 4.8 and total_reviews >= 50:
    #         return 'top_rated'
    #     elif avg_rating >= 4.5 and total_reviews >= 20:
    #         return 'highly_rated'
    #     elif avg_rating >= 4.0 and total_reviews >= 10:
    #         return 'rated'
    #     else:
    #         return 'new'
    
    # def get_provider_badge_display(self):
    #     """Get human-readable provider badge"""
    #     badge_map = {
    #         'verified_business': 'Verified Business',
    #         'top_rated': 'Top Rated',
    #         'highly_rated': 'Highly Rated', 
    #         'rated': 'Rated',
    #         'new': 'New Provider'
    #     }
    #     return badge_map.get(self.provider_badge, 'Provider')
    
    # @property
    # def total_marketplace_activity(self):
    #     """Get total marketplace activity count"""
    #     return (
    #         self.total_products_listed + 
    #         self.total_services_listed + 
    #         self.total_requests_posted
    #     )
    
    # @property
    # def is_active_provider(self):
    #     """Check if user is actively providing products or services"""
    #     try:
    #         from Services.models import ServiceListing
    #         active_services = ServiceListing.objects.filter(
    #             provider=self, 
    #             is_active=True, 
    #             is_suspended=False
    #         ).count()
            
    #         from Home.models import Product_Listing
    #         active_products = Product_Listing.objects.filter(
    #             seller=self,
    #             is_suspended=False
    #         ).exclude(
    #             expiration_date__lte=timezone.now()
    #         ).count()
            
    #         return (active_services + active_products) > 0
    #     except ImportError:
    #         return self.total_products_listed > 0
    
    # def get_skills_list(self):
    #     """Get skills as a list"""
    #     if self.skills:
    #         return [skill.strip() for skill in self.skills.split(',') if skill.strip()]
    #     return []
    
    # def set_skills_list(self, skills_list):
    #     """Set skills from a list"""
    #     if skills_list:
    #         self.skills = ', '.join(skills_list)
    #     else:
    #         self.skills = ''
    
    # def update_service_stats(self):
    #     """Update service-related statistics"""
    #     try:
    #         from Services.models import ServiceListing, ServiceReview
            
    #         # Update service counts
    #         self.total_services_listed = ServiceListing.objects.filter(provider=self).count()
            
    #         # Update service ratings
    #         service_reviews = ServiceReview.objects.filter(service__provider=self)
    #         self.total_service_reviews = service_reviews.count()
    #         if service_reviews.exists():
    #             self.service_provider_rating = service_reviews.aggregate(
    #                 avg_rating=models.Avg('rating')
    #             )['avg_rating'] or 0
            
    #         self.save(update_fields=[
    #             'total_services_listed', 'total_service_reviews', 'service_provider_rating'
    #         ])
    #     except ImportError:
    #         pass
    
    # def update_request_stats(self):
    #     """Update buyer request statistics"""
    #     try:
    #         from BuyerRequest.models import BuyerRequest
            
    #         # Update request counts
    #         self.total_requests_posted = BuyerRequest.objects.filter(buyer=self).count()
            
    #         self.save(update_fields=['total_requests_posted'])
    #     except ImportError:
    #         pass
    
    def verify_business(self, verified_by_user, notes=None):
        """Verify the business profile"""
        self.business_verification_status = 'verified'
        self.business_verified_at = timezone.now()
        self.business_verified_by = verified_by_user
        self.permanent_listing_enabled = True  # Enable permanent listings
        self.priority_support = True
        if notes:
            self.business_verification_notes = notes
        self.save()
    
    def reject_business_verification(self, reason=None, notes=None):
        """Reject the business verification"""
        self.business_verification_status = 'rejected'
        if reason:
            self.business_rejection_reason = reason
        if notes:
            self.business_verification_notes = notes
        self.save()
    
    def suspend_business_verification(self, reason=None):
        """Suspend the business verification"""
        self.business_verification_status = 'suspended'
        self.permanent_listing_enabled = False
        if reason:
            self.business_rejection_reason = reason
        self.save()
    
    def get_business_contact_info(self):
        """Get business contact information"""
        if not self.is_verified_business:
            return None
        
        contact_info = {}
        if self.business_email:
            contact_info['email'] = self.business_email
        if self.business_phone:
            contact_info['phone'] = self.business_phone
        if self.business_website:
            contact_info['website'] = self.business_website
        
        return contact_info if contact_info else None

    def __str__(self):
        return f'{self.user.username}'
    
    def get_or_create_email_preferences(self):
        """
        Get or create the email preferences for this profile
        
        Returns:
            EmailPreferences: The email preferences object for this profile
        """
        if hasattr(self, 'email_preferences'):
            return self.email_preferences
        
        # Create new preferences with default settings
        from .models import EmailPreferences  # Import here to avoid circular imports
        preferences = EmailPreferences.objects.create(profile=self)
        return preferences
    
    def save(self, *args, **kwargs):
        
        try:
            old = Profile.objects.get(pk=self.pk)
            if old.photo and old.photo != self.photo:
                old.photo.delete(save=False)
        except Profile.DoesNotExist:
            pass
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # NEW: Auto-create email preferences for new profiles
        if is_new:
            from User.models import EmailPreferences
            EmailPreferences.objects.get_or_create(
                profile=self,
                defaults={
                    'receive_marketing': True,
                    'receive_announcements': True,
                    'receive_notifications': True,
                }
            )
    
    def delete(self, *args, **kwargs):
        if self.photo:
            self.photo.delete(save=False)
        super().delete(*args, **kwargs)
    
    @property
    def average_rating(self):
        return self.seller_reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    
    def generate_otp(self):
        """Generate a 6-digit OTP for email verification"""
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.email_otp = otp
        self.otp_created_at = timezone.now()
        self.save()
        return otp
    
    def is_otp_valid(self):
        """Check if the OTP is still valid (within 10 minutes)"""
        if not self.otp_created_at:
            return False
        
        time_diff = timezone.now() - self.otp_created_at
        return time_diff.total_seconds() < 600  # 10 minutes
    
    @property
    def seller_average_rating(self):
        """Calculate average rating across all seller's products"""
        from Home.models import Review, Product_Listing
        
        # Get all products by this seller
        seller_products = Product_Listing.objects.filter(seller=self)
        
        # Get all reviews for these products
        reviews = Review.objects.filter(product__in=seller_products)
        
        if reviews.exists():
            avg_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
            return round(avg_rating, 1) if avg_rating else 0
        return 0
    
    @property
    def total_seller_reviews(self):
        """Get total count of reviews across all seller's products"""
        from Home.models import Review, Product_Listing
        
        seller_products = Product_Listing.objects.filter(seller=self)
        return Review.objects.filter(product__in=seller_products).count()

class BusinessVerificationDocument(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='verification_documents')
    document_type = models.CharField(
        max_length=50,
        choices=[
            ('business_registration', 'Business Registration Certificate'),
            ('tax_certificate', 'Tax Identification Certificate'),
            ('business_license', 'Business License'),
            ('bank_statement', 'Bank Statement'),
            ('utility_bill', 'Utility Bill'),
            ('other', 'Other Document'),
        ]
    )
    document = models.FileField(upload_to='business_verification_docs/')
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.profile.user.username} - {self.get_document_type_display()}"
    
class EmailPreferences(models.Model):

    profile = models.OneToOneField('Profile', on_delete=models.CASCADE, related_name='email_preferences')
    
    receive_marketing = models.BooleanField(default=True, help_text="Marketing emails and newsletters")
    receive_announcements = models.BooleanField(default=True, help_text="Important announcements about OpenSell")
    receive_notifications = models.BooleanField(default=True, help_text="Activity notifications")
    
    unsubscribe_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    token_created_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Email preferences for {self.profile.user.username}"
    
    def save(self, *args, **kwargs):
        # Generate unsubscribe token if not present
        if not self.unsubscribe_token:
            self.unsubscribe_token = get_random_string(64)
            self.token_created_at = timezone.now()
        super().save(*args, **kwargs)
    
    def generate_new_token(self):
        self.unsubscribe_token = get_random_string(64)
        self.token_created_at = timezone.now()
        self.save()
        return self.unsubscribe_token
    
    @property
    def is_completely_unsubscribed(self):
        return not (self.receive_marketing or self.receive_announcements or self.receive_notifications)
    
    def get_absolute_preferences_url(self):
        return reverse('email_preferences') + f"?user={self.profile.user.id}&token={self.unsubscribe_token}"        return reverse('email_preferences') + f"?user={self.profile.user.id}&token={self.unsubscribe_token}"

class BulkEmail(models.Model):
    """Simplified email campaign model"""
    CAMPAIGN_TYPE_CHOICES = [
        ('marketing', 'Marketing'),
        ('announcement', 'Announcement'),
        ('notification', 'Notification'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
    ]
    
    # Basic info
    title = models.CharField(max_length=255)
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPE_CHOICES)
    subject = models.CharField(max_length=255)
    message = models.TextField(help_text="Plain HTML content")
    
    # Simple targeting
    target_all = models.BooleanField(default=True)
    verified_only = models.BooleanField(default=False)
    business_only = models.BooleanField(default=False)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_sent = models.IntegerField(default=0)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.status})"
    
    def get_recipients_query(self):
        """Get queryset of users who should receive this email - NO execution"""
        from User.models import EmailPreferences
        
        users = User.objects.filter(is_active=True).select_related('profile')
        
        # CRITICAL: Filter by preferences (using your existing EmailPreferences model)
        # Only users who opted IN for this type will receive emails
        if self.campaign_type == 'marketing':
            # Get profiles that have email_preferences with receive_marketing=True
            opted_in_profiles = EmailPreferences.objects.filter(
                receive_marketing=True
            ).values_list('profile_id', flat=True)
            
            users = users.filter(profile__id__in=opted_in_profiles)
            
        elif self.campaign_type == 'announcement':
            opted_in_profiles = EmailPreferences.objects.filter(
                receive_announcements=True
            ).values_list('profile_id', flat=True)
            
            users = users.filter(profile__id__in=opted_in_profiles)
            
        elif self.campaign_type == 'notification':
            opted_in_profiles = EmailPreferences.objects.filter(
                receive_notifications=True
            ).values_list('profile_id', flat=True)
            
            users = users.filter(profile__id__in=opted_in_profiles)
        
        # Additional filters
        if self.verified_only:
            users = users.filter(profile__email_verified=True)
        
        if self.business_only:
            users = users.filter(profile__business_verification_status='verified')
        
        return users.only('id', 'email', 'first_name', 'username')  # Only load needed fields
    
    def get_recipient_count(self):
        """Efficient count without loading all users"""
        return self.get_recipients_query().count()