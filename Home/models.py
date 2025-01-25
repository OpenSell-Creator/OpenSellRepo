import uuid
from django.contrib.auth.models import User
from User.models import Profile, location
from User import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from .utils import user_listing_path
from django.db.models import Avg
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to=user_listing_path, null=True, blank=True)
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
    title = models.CharField(max_length=255)
    seller = models.ForeignKey(Profile, on_delete=models.CASCADE)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, default=1)
    subcategory = models.ForeignKey(Subcategory, related_name='products', on_delete=models.SET_NULL, null=True)
    brand = models.ForeignKey(Brand, related_name='products', null=True, blank=True, on_delete=models.SET_NULL)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    location = models.OneToOneField(
        location, on_delete=models.SET_NULL, null=True)
    condition = models.CharField(max_length=4, choices=CONDITION_CHOICES)
    view_count = models.PositiveIntegerField(default=0)

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
    
class Product_Image(models.Model):
    product = models.ForeignKey(Product_Listing, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to=user_listing_path)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.product.title}"

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
    image = models.ImageField(upload_to='banners/')
    url = models.URLField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Banner {self.id}"

    class Meta:
        ordering = ['-updated_at']

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