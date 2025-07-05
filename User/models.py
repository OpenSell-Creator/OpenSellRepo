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
    
    @property
    def seller_average_rating(self):
        """Calculate average rating across all seller's products"""
        from .models import Review, Product_Listing
        
        seller_products = Product_Listing.objects.filter(seller=self)
        reviews = Review.objects.filter(product__in=seller_products)
        
        if reviews.exists():
            avg_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
            return round(avg_rating, 1) if avg_rating else 0
        return 0
    
    @property
    def total_seller_reviews(self):
        """Get total count of reviews across all seller's products"""
        from .models import Review, Product_Listing
        
        seller_products = Product_Listing.objects.filter(seller=self)
        return Review.objects.filter(product__in=seller_products).count()
    
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
        from .models import Review, Product_Listing
        
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
        from .models import Review, Product_Listing
        
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
        return reverse('email_preferences') + f"?user={self.profile.user.id}&token={self.unsubscribe_token}"