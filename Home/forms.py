from django import forms
from .models import Product_Listing,Product_Image, Review
from django.forms.widgets import NumberInput
from django.core.validators import MinLengthValidator
from decimal import Decimal, InvalidOperation
from .models import Category,Brand, Subcategory,Profile, Review,ReviewReply
from User.models import State, LGA

class ListingFilterForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, label='Category')
    
    def __init__(self, *args, **kwargs):
        
        super(ListingFilterForm, self).__init__(*args, **kwargs)
        self.fields['category'].widget.attrs.update({'class': 'form-select'})

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True
    
class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class FormattedPriceInput(forms.NumberInput):
    def format_value(self, value):
        if value is None:
            return ''
        return '₦ {:,.0f}'.format(Decimal(value))
    
class ListingForm(forms.ModelForm):
    images = MultipleFileField(required=False)
    formatted_price = forms.CharField(label='Price', required=True)

    ALL_LISTING_TYPE_CHOICES = [
        ('standard', 'Standard Listing (45 days) - Free'),
        ('urgent', 'Urgent Sale (30 days) - Free'),
        ('permanent', 'Permanent Retail Listing - Free'),
    ]

    REGULAR_LISTING_TYPE_CHOICES = [
        ('standard', 'Standard Listing (45 days) - Free'),
        ('urgent', 'Urgent Sale (30 days) - Free'),
    ]
    
    listing_type = forms.ChoiceField(
        choices=REGULAR_LISTING_TYPE_CHOICES, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    quantity = forms.IntegerField(
        min_value=1, 
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    is_always_available = forms.BooleanField(
        required=False, 
        label='Always Available',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'data-toggle': 'tooltip',
            'title': 'Products marked as always available will not be removed from listings',
        })
    )
    
    receipt_images = MultipleFileField(required=False)
    receipt_type = forms.ChoiceField(
        choices=[
            ('store_receipt', 'Store Receipt'),
            ('bank_transfer', 'Bank Transfer / Payment Proof'),
            ('warranty_card', 'Warranty Card'),
            ('invoice', 'Invoice'),
            ('packaging', 'Original Box / Packaging Photo'),
            ('other', 'Other Proof'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    receipt_notes = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional note about this receipt'})
    )

    class Meta:
        model = Product_Listing
        fields = ['title', 'description', 'formatted_price', 'condition',
            'category', 'subcategory', 'brand', 'images', 'listing_type',
            'quantity', 'is_always_available',
            'has_receipt', 'receipt_visibility',
            'negotiable', 'reason_for_selling',
            'inspection_allowed', 'inspection_location',
            'swap_accepted', 'swap_preference',
            'delivery_available', 'original_accessories_included',
            'bundle_description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'subcategory': forms.Select(attrs={'class': 'form-select'}),
            'brand': forms.Select(attrs={'class': 'form-select'}),
            'has_receipt': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_has_receipt'}),
            'receipt_visibility': forms.Select(attrs={'class': 'form-select'}),
            'negotiable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reason_for_selling': forms.Select(attrs={'class': 'form-select'}),
            'inspection_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'inspection_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Ikeja, Lagos'}),
            'swap_accepted': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'swap_preference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. iPhone 13, cash top-up welcome'}),
            'delivery_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'original_accessories_included': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'bundle_description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Describe what is included in the bundle'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set listing type choices based on user verification status
        if self.user and hasattr(self.user, 'profile'):
            if self.user.profile.is_verified_business:
                self.fields['listing_type'].choices = self.ALL_LISTING_TYPE_CHOICES
                self.fields['listing_type'].initial = 'permanent'
            else:
                self.fields['listing_type'].choices = self.REGULAR_LISTING_TYPE_CHOICES
        else:
            self.fields['listing_type'].choices = self.REGULAR_LISTING_TYPE_CHOICES

        self.fields['subcategory'].queryset = Subcategory.objects.none()
        self.fields['brand'].queryset = Brand.objects.none()

        self.fields['category'].empty_label = "Select Category"
        self.fields['subcategory'].empty_label = "Select Subcategory"
        self.fields['brand'].empty_label = "Select Brand"
        self.fields['condition'].empty_label = "Select Condition"

        # Prepend a blank placeholder so the dropdown reads "Select your reason"
        # instead of defaulting to the first choice
        self.fields['reason_for_selling'].choices = [
            ('', 'Select your reason'),
        ] + list(self._meta.model.REASON_FOR_SELLING_CHOICES)
        
        self.fields['category'].queryset = Category.objects.all()
        
        if 'category' in self.data:
            try:
                category_id = int(self.data.get('category'))
                self.fields['subcategory'].queryset = Subcategory.objects.filter(
                    category_id=category_id
                )
            except (ValueError, TypeError):
                pass
                
        if 'subcategory' in self.data:
            try:
                subcategory_id = int(self.data.get('subcategory'))
                self.fields['brand'].queryset = Brand.objects.filter(
                    subcategories=subcategory_id
                )
            except (ValueError, TypeError):
                pass

        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'category') and self.instance.category:
                self.fields['subcategory'].queryset = Subcategory.objects.filter(
                    category=self.instance.category
                )
            if hasattr(self.instance, 'subcategory') and self.instance.subcategory:
                self.fields['brand'].queryset = Brand.objects.filter(
                    subcategories=self.instance.subcategory
                )
            if hasattr(self.instance, 'price') and self.instance.price:
                self.fields['formatted_price'].initial = f'₦ {self.instance.price:,.0f}'
            
            self.fields['quantity'].required = self.instance.listing_type != 'permanent'
            self.fields['images'].required = False
            self.fields['images'].help_text = "Leave empty to keep existing images"
            self.fields['receipt_images'].required = False
            self.fields['receipt_images'].help_text = "Leave empty to keep existing receipts"

            # Pre-populate new boolean fields from instance
            self.fields['has_receipt'].initial = self.instance.has_receipt
            self.fields['receipt_visibility'].initial = self.instance.receipt_visibility
            self.fields['negotiable'].initial = self.instance.negotiable
            self.fields['reason_for_selling'].initial = self.instance.reason_for_selling
            self.fields['inspection_allowed'].initial = self.instance.inspection_allowed
            self.fields['inspection_location'].initial = self.instance.inspection_location
            self.fields['swap_accepted'].initial = self.instance.swap_accepted
            self.fields['swap_preference'].initial = self.instance.swap_preference
            self.fields['delivery_available'].initial = self.instance.delivery_available
            self.fields['original_accessories_included'].initial = self.instance.original_accessories_included
            self.fields['bundle_description'].initial = self.instance.bundle_description

    def clean_listing_type(self):
        """Validate that the selected listing type is allowed for this user"""
        listing_type = self.cleaned_data.get('listing_type')
        
        if self.user and hasattr(self.user, 'profile'):
            # Check if user is trying to select permanent listing without verification
            if listing_type == 'permanent' and not self.user.profile.is_verified_business:
                raise forms.ValidationError(
                    "Permanent listings are only available for verified businesses. "
                    "Please apply for business verification first."
                )
        
        return listing_type

    def clean_formatted_price(self):
        formatted_price = self.cleaned_data.get('formatted_price')
        if formatted_price:
            try:
                return Decimal(formatted_price.replace('₦', '').replace(',', '').strip())
            except InvalidOperation:
                raise forms.ValidationError("Invalid price format")
        raise forms.ValidationError("Price is required")

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        subcategory = cleaned_data.get('subcategory')

        if category and subcategory and subcategory.category != category:
            self.add_error('subcategory', 'The selected subcategory does not belong to the selected category.')

        cleaned_data['price'] = cleaned_data.get('formatted_price')

        # Condition-dependent field validation
        # Condition-dependent field validation
        condition = cleaned_data.get('condition')
        if condition == 'new':
            # These fields only make sense for used items; clear them silently
            cleaned_data['reason_for_selling'] = None
            cleaned_data['original_accessories_included'] = False
            # Receipt fields are only valid for used items
            cleaned_data['has_receipt'] = False
            cleaned_data['receipt_visibility'] = 'public'

        # Inspection location required if inspection is allowed
        if cleaned_data.get('inspection_allowed') and not cleaned_data.get('inspection_location'):
            self.add_error('inspection_location', 'Please provide an inspection location.')

        # Swap preference required if swap is accepted
        # Swap preference required if swap is accepted
        if cleaned_data.get('swap_accepted') and not cleaned_data.get('swap_preference'):
            self.add_error('swap_preference', 'Please describe what you would accept as a swap.')

        # Clear dependent fields server-side when their toggle/condition is off
        if not cleaned_data.get('inspection_allowed'):
            cleaned_data['inspection_location'] = None
        if not cleaned_data.get('swap_accepted'):
            cleaned_data['swap_preference'] = None
        if int(cleaned_data.get('quantity') or 1) <= 1:
            cleaned_data['bundle_description'] = None

        return cleaned_data
    
    def clean_receipt_images(self):
        files = self.files.getlist('receipt_images')
        for f in files:
            if f.size > 5 * 1024 * 1024:
                raise forms.ValidationError(
                    f'Receipt image "{f.name}" exceeds the 5MB limit. Please compress it before uploading.'
                )
            ext = f.name.rsplit('.', 1)[-1].lower()
            if ext not in ('jpg', 'jpeg', 'png', 'webp'):
                raise forms.ValidationError(
                    f'"{f.name}" is not a supported image format. Use JPG, PNG, or WebP.'
                )
        return files
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.price = self.cleaned_data.get('price')

        # Write all new fields explicitly so they are never left at stale values
        instance.has_receipt = self.cleaned_data.get('has_receipt', False)
        instance.receipt_visibility = self.cleaned_data.get('receipt_visibility', 'public')
        instance.negotiable = self.cleaned_data.get('negotiable', False)
        instance.reason_for_selling = self.cleaned_data.get('reason_for_selling') or None
        instance.inspection_allowed = self.cleaned_data.get('inspection_allowed', False)
        instance.inspection_location = self.cleaned_data.get('inspection_location') or None
        instance.swap_accepted = self.cleaned_data.get('swap_accepted', False)
        instance.swap_preference = self.cleaned_data.get('swap_preference') or None
        instance.delivery_available = self.cleaned_data.get('delivery_available', False)
        instance.original_accessories_included = self.cleaned_data.get('original_accessories_included', False)
        instance.bundle_description = self.cleaned_data.get('bundle_description') or None

        if commit:
            instance.save()
        return instance
        
class ProductSearchForm(forms.Form):
    query = forms.CharField(label='Search', max_length=100, required=False)
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, empty_label="All Categories")
    subcategory = forms.ModelChoiceField(queryset=Subcategory.objects.none(), required=False, empty_label="All Subcategories")
    brand = forms.ModelChoiceField(queryset=Brand.objects.none(), required=False, empty_label="All Brands")  # Add brand field
    min_price = forms.DecimalField(min_value=0, required=False)
    max_price = forms.DecimalField(min_value=0, required=False)
    condition = forms.ChoiceField(choices=[('', 'Any')] + Product_Listing.CONDITION_CHOICES, required=False)
    state = forms.ModelChoiceField(queryset=State.objects.all(), required=False, empty_label="States")
    lga = forms.ModelChoiceField(queryset=LGA.objects.none(), required=False, empty_label="LGAs")
    verified_business = forms.BooleanField(required=False, label="Verified Businesses Only",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['subcategory'].queryset = Subcategory.objects.none()
        self.fields['brand'].queryset = Brand.objects.none()
        self.fields['lga'].queryset = LGA.objects.none()

        category_id = self.data.get('category', None)
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                self.fields['subcategory'].queryset = Subcategory.objects.filter(category_id=category_id)
                self.fields['brand'].queryset = Brand.objects.filter(categories=category)
            except Category.DoesNotExist:
                pass
        else:
            self.fields['brand'].queryset = Brand.objects.all()

        state_id = self.data.get('state', None)
        if state_id:
            self.fields['lga'].queryset = LGA.objects.filter(state_id=state_id)
        
        if 'verified_business' in self.data and self.data['verified_business'] == '1':
            self.fields['verified_business'].initial = True
    
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(choices=[(i, str(i)) for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class ReviewReplyForm(forms.ModelForm):
    class Meta:
        model = ReviewReply
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        
class ProductReportForm(forms.Form):
    REPORT_REASONS = [
        ('spam', 'Spam or Misleading Content'),
        ('fraud', 'Fraudulent Listing'),
        ('inappropriate', 'Inappropriate Content'),
        ('expired', 'Expired or Sold Item'),
        ('other', 'Other Reason')
    ]

    reason = forms.ChoiceField(
        choices=REPORT_REASONS, 
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )
    details = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 4, 
            'placeholder': 'Please provide additional details about your report'
        }),
        validators=[MinLengthValidator(10, 'Please provide more details')],
        required=True
    )
    reporter_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Your email (optional)'
        }),
        required=False
    )